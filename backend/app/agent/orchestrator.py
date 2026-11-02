"""Agent lifecycle orchestrator.

Drives a session through the state machine, persisting every transition to
agent_events and broadcasting a WebSocket event per step:

  DISCOVER -> PROFILE -> PLAN -> PREPARE -> (EXECUTE gated) -> OBSERVE
           -> ADAPT -> ANALYZE -> RESULT

EXECUTE is intentionally gated: the module's execute() raises NotImplementedError
(no attack code in this repo), so the orchestrator records that execution is
deferred to an authorized lab adapter and continues with real observation.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from ..db import SessionLocal
from ..models import AgentEvent, AttackKind, AttackResult, AttackSession, SessionState, SimulationMetric
from ..modules.ratuba import RATUBAModule, get_module
from ..telemetry.service import service
from ..ws import hub


TERMINAL = (SessionState.RESULT, SessionState.KILLED, SessionState.FAILED)


class Orchestrator:
    def __init__(self) -> None:
        self._killed: set[str] = set()
        self.halted = False

    def kill(self, session_id: str) -> None:
        self._killed.add(session_id)

    def engage_kill_switch(self) -> list[str]:
        """Halt the range and terminate every session that has not finished."""
        self.halted = True
        db = SessionLocal()
        try:
            live = db.query(AttackSession).filter(AttackSession.state.notin_(TERMINAL)).all()
            ids = [s.id for s in live]
            for s in live:
                s.state = SessionState.KILLED
                s.ended_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()
        self._killed.update(ids)
        return ids

    async def _emit(
        self, session_id: str, event_type: str, phase: str | None, message: str, payload: dict | None = None
    ) -> None:
        payload = payload or {}
        db = SessionLocal()
        try:
            db.add(
                AgentEvent(
                    session_id=session_id,
                    event_type=event_type,
                    phase=phase,
                    message=message,
                    payload=payload,
                )
            )
            if phase:
                sess = db.get(AttackSession, session_id)
                if sess and sess.state not in (SessionState.KILLED, SessionState.FAILED):
                    try:
                        sess.state = SessionState(phase)
                    except ValueError:
                        pass
            db.commit()
        finally:
            db.close()
        await hub.broadcast(
            event_type, {"session_id": session_id, "phase": phase, "message": message, **payload}
        )

    def _check_kill(self, session_id: str) -> bool:
        return session_id in self._killed

    async def run(self, session_id: str, kind: str) -> None:
        module = get_module(kind)
        if module is None:
            await self._emit(session_id, "SIMULATION_COMPLETE", "FAILED", f"Unknown module {kind}")
            return

        # DISCOVER
        await self._emit(session_id, "DISCOVERY_STARTED", "DISCOVER", "Collecting real lab telemetry…")
        before = await asyncio.to_thread(service.collect_once)
        discovery = module.discover(before)
        await self._emit(
            session_id,
            "TARGET_IDENTIFIED",
            "DISCOVER",
            f"Target {discovery.hostname or 'unavailable'} ({discovery.os_name or 'unknown OS'})",
            {"reachable": discovery.reachable, "notes": discovery.notes},
        )
        if self._check_kill(session_id):
            return await self._finish_killed(session_id)

        # PROFILE
        profile = module.profile(before)
        await self._emit(
            session_id, "PROFILE_COMPLETE", "PROFILE", profile.summary, {"facts": profile.facts}
        )

        # For RAT+UBA, baseline from recent real snapshots.
        if isinstance(module, RATUBAModule):
            module.baseline_from(list(service.history))

        # PLAN  (AI decision over the real snapshot)
        plan = await asyncio.to_thread(module.plan, before)
        await self._emit(
            session_id,
            "PLAN_CREATED",
            "PLAN",
            f"Agent decision: {plan.parameter} = {plan.value if plan.value is not None else 'unavailable'}",
            {"parameter": plan.parameter, "value": plan.value, "reasoning": plan.reasoning, "source": plan.source},
        )
        if kind == "ddos":
            await self._emit(
                session_id, "BOT_COUNT_SELECTED", "PLAN",
                f"Required sources: {plan.value if plan.value is not None else 'unavailable'}",
                {"required_sources": plan.value, "reasoning": plan.reasoning},
            )
        if self._check_kill(session_id):
            return await self._finish_killed(session_id)

        # PREPARE / EXECUTE — SIMULATION ONLY. No socket, credential, process, or
        # remote host is ever touched; execute() returns synthetic metrics grounded
        # in the real snapshot, which we persist to simulation_metrics.
        start_event = "RAT_SESSION_STARTED" if kind == "ratuba" else "SIMULATION_STARTED"
        await self._emit(
            session_id, start_event, "PREPARE",
            "Running in-memory simulation grounded in real telemetry (no real action).",
        )
        execution = await asyncio.to_thread(module.execute, plan, before)
        self._persist_metrics(session_id, kind, execution)
        await self._emit(
            session_id, "SIMULATION_STARTED", "PREPARE", execution.summary,
            {"mode": execution.mode, "metrics": execution.metrics, "units": len(execution.series),
             "execution_performed": True},
        )

        # OBSERVE — read real telemetry again and compare.
        after = await asyncio.to_thread(service.collect_once)
        observation = module.observe(before, after)
        await self._emit(
            session_id, "ADAPTATION", "OBSERVE",
            "Observed real telemetry after the controlled step.",
            {"deltas": observation.deltas, "before": observation.before, "after": observation.after},
        )

        # RAT+UBA scoring over the real post-step snapshot.
        risk = None
        if isinstance(module, RATUBAModule):
            scored = module.score_latest(after)
            risk = scored["risk_score"]
            for a in scored["anomalies"]:
                await self._emit(
                    session_id, "UBA_EVENT_DETECTED", "OBSERVE",
                    a["description"], {"category": a["category"], "score": a["score"]},
                )
            await self._emit(
                session_id, "RISK_SCORE_UPDATED", "OBSERVE",
                f"Session risk score: {risk}", {"risk_score": risk, "baseline_ready": scored["ready"]},
            )

        # ADAPT
        adapted = module.adapt(observation, plan)
        await self._emit(
            session_id, "ADAPTATION", "ADAPT", adapted.reasoning,
            {"changed": adapted.changed, "parameter": adapted.parameter, "value": adapted.value},
        )
        if self._check_kill(session_id):
            return await self._finish_killed(session_id)

        # ANALYZE + RESULT
        report = module.analyze(profile, observation)
        if report.risk_score is None:
            report.risk_score = risk
        await self._emit(session_id, "SIMULATION_COMPLETE", "ANALYZE", report.summary, {"findings": report.findings})
        self._persist_result(session_id, plan, report, execution.metrics)
        await self._emit(
            session_id, "SIMULATION_COMPLETE", "RESULT", "Session complete.",
            {"risk_score": report.risk_score, "simulation_metrics": execution.metrics},
        )

    def _persist_metrics(self, session_id: str, kind: str, execution) -> None:
        db = SessionLocal()
        try:
            ak = AttackKind(kind)
            for name, value in execution.metrics.items():
                db.add(SimulationMetric(
                    session_id=session_id, kind=ak, name=name,
                    value=float(value) if isinstance(value, (int, float)) else None,
                    unit="", meta={} if isinstance(value, (int, float)) else {"raw": value},
                ))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _persist_result(self, session_id: str, plan, report, metrics: dict | None = None) -> None:
        db = SessionLocal()
        try:
            db.add(
                AttackResult(
                    session_id=session_id,
                    summary=report.summary,
                    risk_score=report.risk_score,
                    decision=plan.raw,
                    analysis={"findings": report.findings, "simulation_metrics": metrics or {}},
                )
            )
            sess = db.get(AttackSession, session_id)
            if sess:
                sess.ended_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    async def _finish_killed(self, session_id: str) -> None:
        db = SessionLocal()
        try:
            sess = db.get(AttackSession, session_id)
            if sess:
                sess.state = SessionState.KILLED
                sess.ended_at = sess.ended_at or datetime.now(timezone.utc)
            db.add(
                AgentEvent(
                    session_id=session_id,
                    event_type="KILL_SWITCH_ACTIVATED",
                    phase="KILLED",
                    message="Session terminated by operator.",
                    payload={},
                )
            )
            db.commit()
        finally:
            db.close()
        await hub.broadcast(
            "KILL_SWITCH_ACTIVATED",
            {"session_id": session_id, "phase": "KILLED", "message": "Session terminated by operator."},
        )


orchestrator = Orchestrator()
