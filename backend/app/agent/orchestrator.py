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



def _build_assessment(kind: str, plan, execution, observation, risk, anomalies: list[dict]) -> dict:
    """A grounded, smart post-run assessment: what ran, what it found, where the
    weak points are, and how to harden. Built from the real snapshot + the
    simulation's own synthetic metrics — no fabricated telemetry."""
    m = execution.metrics
    deltas = observation.deltas if observation else {}
    results: list[str] = []
    weak: list[str] = []
    recs: list[str] = []

    if kind == "ddos":
        sources = m.get("simulated_sources")
        dropped = m.get("simulated_dropped")
        serviced = m.get("serviced_pct")
        peak = m.get("simulated_peak_load_pct")
        loss = round(100 - (serviced or 0), 1)
        results.append(f"Modelled {sources} load sources; simulated target load peaked at {peak}%.")
        results.append(f"{serviced}% of simulated requests serviced, {dropped} dropped ({loss}% loss).")
        if (serviced or 100) < 85:
            weak.append(f"Only {serviced}% of load absorbed — limited headroom, service degrades under a modest source count.")
        if (peak or 0) >= 85:
            weak.append(f"Simulated load drives the host to ~{peak}% — no rate limiting or shedding is modelled in front of it.")
        cpu_d = deltas.get("cpu_percent")
        if cpu_d is not None and cpu_d > 10:
            weak.append(f"Real CPU moved {cpu_d:+.0f} pts across the run — the host is sensitive to added load.")
        recs += [
            "Put a rate limiter / reverse proxy (nginx, HAProxy) in front and cap per-source connections.",
            "Add autoscaling or a CDN/WAF so a small source count can't saturate the origin.",
            "Alert when request-drop rate crosses a threshold.",
        ]

    elif kind == "bruteforce":
        rate = m.get("simulated_attempt_rate")
        attempts = m.get("simulated_attempts")
        lockouts = m.get("simulated_lockouts")
        size = m.get("mock_wordlist_size")
        pws = m.get("mock_passwords") or []
        logons = m.get("grounded_on_observed_logon_events")
        results.append(f"Modelled {attempts} attempts at {rate}/min against a {size}-entry mock wordlist.")
        results.append(f"{lockouts} account lockouts would trigger; {logons} real logon events observed for context.")
        weak.append(f"Weak, common passwords are in scope (e.g. {', '.join(pws[:3])}) — these fall to any dictionary run.")
        if (lockouts or 0) == 0:
            weak.append("No lockout would trigger at this rate — a slow brute force could run unnoticed.")
        else:
            weak.append(f"Lockouts fire quickly ({lockouts}) — an attacker can also weaponise this for account-lockout DoS.")
        recs += [
            "Enforce MFA so a recovered password alone is not enough.",
            "Require a strong password policy and screen against common-password lists.",
            "Tune lockout thresholds and alert on bursts of 4625 (failed logon) events.",
        ]

    else:  # ratuba
        techniques = m.get("simulated_techniques")
        window = m.get("simulated_baseline_window_minutes")
        procs = m.get("grounded_on_distinct_processes")
        rscore = int((risk or 0) * 100)
        results.append(f"Emulated {techniques} technique(s) over a {window}-min baseline across {procs} distinct processes.")
        results.append(f"UBA risk score {rscore}/100 from {len(anomalies)} behavioural anomaly(ies).")
        if rscore >= 70:
            weak.append(f"High behavioural risk ({rscore}/100) — current baseline would not suppress this as noise.")
        cats = sorted({a.get("category") for a in anomalies if a.get("category")})
        if cats:
            weak.append(f"Deviations span {', '.join(cats)} activity — these channels lack tight monitoring.")
        if not anomalies:
            weak.append("No anomalies crossed the baseline — detection depends on a well-populated baseline window.")
        recs += [
            "Deploy EDR / Sysmon and forward process, logon and network telemetry to a SIEM.",
            "Alert on deviations from the user-behaviour baseline rather than fixed signatures.",
            f"Keep at least a {window}-min baseline so normal variance doesn't mask real activity.",
        ]

    headline = f"After the simulation: {execution.summary}"
    return {"headline": headline, "results": results, "weak_points": weak, "recommendations": recs}


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
        anomaly_list: list[dict] = []
        if isinstance(module, RATUBAModule):
            scored = module.score_latest(after)
            risk = scored["risk_score"]
            anomaly_list = scored["anomalies"]
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
        assessment = _build_assessment(kind, plan, execution, observation, risk, anomaly_list)
        await self._emit(session_id, "SIMULATION_COMPLETE", "ANALYZE", report.summary, {"findings": report.findings})
        self._persist_result(session_id, plan, report, execution.metrics, assessment)
        await self._emit(
            session_id, "SIMULATION_COMPLETE", "RESULT", assessment["headline"],
            {"risk_score": report.risk_score, "simulation_metrics": execution.metrics, "assessment": assessment},
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

    def _persist_result(self, session_id: str, plan, report, metrics: dict | None = None, assessment: dict | None = None) -> None:
        db = SessionLocal()
        try:
            db.add(
                AttackResult(
                    session_id=session_id,
                    summary=report.summary,
                    risk_score=report.risk_score,
                    decision=plan.raw,
                    analysis={"findings": report.findings, "simulation_metrics": metrics or {}, "assessment": assessment or {}},
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
