"""REST API."""
from __future__ import annotations

import asyncio

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..agent.decision import decide
from ..agent.orchestrator import orchestrator
from ..db import get_db
from ..models import AgentEvent, AttackKind, AttackResult, AttackSession, Target, TelemetrySnapshot
from ..telemetry.service import service
from ..ws import hub

router = APIRouter(prefix="/api")

class StartRequest(BaseModel):
    kind: AttackKind
    target_id: str | None = None


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "telemetry_source": service.source.name, "halted": orchestrator.halted}


@router.get("/telemetry/history")
def telemetry_history(minutes: int = 60, db: Session = Depends(get_db)) -> list[dict]:
    """Persisted real snapshots for the last `minutes`, oldest first."""
    since = datetime.now(timezone.utc) - timedelta(minutes=max(1, min(minutes, 24 * 60)))
    rows = db.scalars(
        select(TelemetrySnapshot)
        .where(TelemetrySnapshot.collected_at >= since, TelemetrySnapshot.available.is_(True))
        .order_by(TelemetrySnapshot.collected_at)
    ).all()
    step = max(1, len(rows) // 240)
    return [
        {
            "t": r.collected_at.isoformat(),
            "cpu": r.cpu_percent,
            "mem": r.memory_percent,
            "disk": r.disk_percent,
            "procs": r.process_count,
        }
        for r in rows[::step]
    ]


@router.get("/telemetry/latest")
def telemetry_latest() -> dict:
    if service.latest is None:
        service.collect_once()
    return service.latest.model_dump(mode="json")


@router.get("/decision/{kind}")
def decision(kind: AttackKind) -> dict:
    """AGENT DECISION for the current real snapshot. Read-and-reason only."""
    snap = service.latest or service.collect_once()
    return decide(kind.value, snap)


@router.get("/targets")
def list_targets(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Target)).all()
    return [
        {"id": t.id, "name": t.name, "address": t.address, "os_name": t.os_name, "role": t.role_label}
        for t in rows
    ]


@router.get("/targets/{target_id}")
def get_target(target_id: str, db: Session = Depends(get_db)) -> dict:
    t = db.get(Target, target_id)
    if not t:
        raise HTTPException(404, "target not found")
    return {"id": t.id, "name": t.name, "address": t.address, "os_name": t.os_name, "role": t.role_label}


@router.post("/attacks/start")
async def start_attack(req: StartRequest, db: Session = Depends(get_db)) -> dict:
    if orchestrator.halted:
        raise HTTPException(423, "Kill switch is engaged. Re-arm the range before starting a session.")
    target = db.get(Target, req.target_id) if req.target_id else db.query(Target).first()
    if target is None:
        service.collect_once()  # creates a target row from the first snapshot
        target = db.query(Target).first()
    if target is None:
        raise HTTPException(400, "no target available")

    seq = (db.scalar(select(func.count()).select_from(AttackSession)) or 0) + 1
    sess = AttackSession(label=f"RT-{datetime.now().year}-{seq:04d}", kind=req.kind, target_id=target.id)
    db.add(sess)
    db.commit()

    asyncio.create_task(orchestrator.run(sess.id, req.kind.value))
    return {"session_id": sess.id, "label": sess.label, "kind": req.kind.value, "state": sess.state.value}


@router.post("/attacks/{session_id}/stop")
def stop_attack(session_id: str) -> dict:
    orchestrator.kill(session_id)
    return {"session_id": session_id, "stopping": True}


@router.post("/attacks/{session_id}/kill")
def kill_attack(session_id: str, db: Session = Depends(get_db)) -> dict:
    if not db.get(AttackSession, session_id):
        raise HTTPException(404, "session not found")
    orchestrator.kill(session_id)
    return {"session_id": session_id, "reason": "Manual Kill Switch", "killed": True}


@router.post("/killswitch")
async def engage_kill_switch() -> dict:
    killed = orchestrator.engage_kill_switch()
    await hub.broadcast(
        "KILL_SWITCH_ENGAGED",
        {"killed": killed, "message": f"Kill switch engaged. {len(killed)} session(s) terminated; range halted."},
    )
    return {"halted": True, "killed": killed}


@router.post("/killswitch/reset")
async def reset_kill_switch() -> dict:
    orchestrator.halted = False
    await hub.broadcast("KILL_SWITCH_RESET", {"message": "Range re-armed by operator."})
    return {"halted": False}


@router.get("/events/recent")
def recent_events(limit: int = 60, db: Session = Depends(get_db)) -> list[dict]:
    """Persisted agent events, newest first, shaped like WebSocket messages."""
    rows = db.scalars(select(AgentEvent).order_by(AgentEvent.created_at.desc()).limit(max(1, min(limit, 500)))).all()
    return [
        {
            "type": e.event_type,
            "ts": e.created_at.isoformat(),
            "payload": {"session_id": e.session_id, "phase": e.phase, "message": e.message, **(e.payload or {})},
        }
        for e in rows
    ]


@router.get("/analytics/sessions")
def session_analytics(db: Session = Depends(get_db)) -> list[dict]:
    """One row per session, built only from persisted results and agent events."""
    sessions = db.scalars(select(AttackSession).order_by(AttackSession.started_at)).all()
    results = {r.session_id: r for r in db.scalars(select(AttackResult)).all()}
    wanted = ("PLAN_CREATED", "UBA_EVENT_DETECTED")
    events: dict[str, list[AgentEvent]] = {}
    for e in db.scalars(
        select(AgentEvent).where(
            (AgentEvent.event_type.in_(wanted)) | ((AgentEvent.event_type == "ADAPTATION") & (AgentEvent.phase.in_(("OBSERVE", "ADAPT"))))
        )
    ).all():
        events.setdefault(e.session_id, []).append(e)

    rows = []
    for s in sessions:
        evs = events.get(s.id, [])
        plan = next((e.payload for e in evs if e.event_type == "PLAN_CREATED"), {})
        observe = next((e.payload for e in evs if e.event_type == "ADAPTATION" and e.phase == "OBSERVE"), {})
        adapt = next((e.payload for e in evs if e.event_type == "ADAPTATION" and e.phase == "ADAPT"), {})
        result = results.get(s.id)
        rows.append(
            {
                "id": s.id,
                "label": s.label,
                "kind": s.kind.value,
                "state": s.state.value,
                "started_at": s.started_at.isoformat(),
                "duration_s": (s.ended_at - s.started_at).total_seconds() if s.ended_at else None,
                "parameter": plan.get("parameter"),
                "decision": plan.get("value"),
                "decision_source": plan.get("source"),
                "adapted": adapt.get("value"),
                "risk_score": result.risk_score if result else None,
                "before": observe.get("before"),
                "after": observe.get("after"),
                "deltas": observe.get("deltas"),
                "anomalies": [
                    {"category": e.payload.get("category"), "score": e.payload.get("score"), "message": e.message}
                    for e in evs
                    if e.event_type == "UBA_EVENT_DETECTED"
                ],
            }
        )
    return rows


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(AttackSession).order_by(AttackSession.started_at.desc())).all()
    return [_session_brief(s) for s in rows]


@router.get("/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)) -> dict:
    s = db.get(AttackSession, session_id)
    if not s:
        raise HTTPException(404, "session not found")
    events = db.scalars(
        select(AgentEvent).where(AgentEvent.session_id == session_id).order_by(AgentEvent.created_at)
    ).all()
    return {
        **_session_brief(s),
        "events": [
            {
                "id": e.id,
                "created_at": e.created_at.isoformat(),
                "event_type": e.event_type,
                "phase": e.phase,
                "message": e.message,
                "payload": e.payload,
            }
            for e in events
        ],
    }


@router.get("/results/{session_id}")
def get_result(session_id: str, db: Session = Depends(get_db)) -> dict:
    r = db.scalar(select(AttackResult).where(AttackResult.session_id == session_id))
    if not r:
        raise HTTPException(404, "result not available yet")
    return {
        "session_id": r.session_id,
        "created_at": r.created_at.isoformat(),
        "summary": r.summary,
        "risk_score": r.risk_score,
        "decision": r.decision,
        "analysis": r.analysis,
    }


def _session_brief(s: AttackSession) -> dict:
    return {
        "id": s.id,
        "label": s.label,
        "kind": s.kind.value,
        "state": s.state.value,
        "target_id": s.target_id,
        "started_at": s.started_at.isoformat(),
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
    }
