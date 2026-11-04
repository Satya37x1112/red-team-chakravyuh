"""REST API for the external-tool integrations.

All endpoints are read/analysis-oriented except POST /locust/run, which is the
one gated real-action path and fail-closed (see integrations/locust.py).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..integrations import all_status, get_integration
from ..integrations.caldera import analyze, list_samples, load_sample
from ..integrations.locust import LocustIntegration
from ..integrations.vervet import VervetIntegration
from ..models import IntegrationArtifact

router = APIRouter(prefix="/api/integrations")


def _save_artifact(db: Session, integration: str, kind: str, title: str, summary: str, payload: dict) -> str:
    """Persist one integration output to the central store; return its id."""
    art = IntegrationArtifact(
        integration=integration, kind=kind, title=title[:200], summary=summary[:2000], payload=payload
    )
    db.add(art)
    db.commit()
    return art.id


@router.get("/artifacts")
def list_artifacts(integration: str | None = None, limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    """Recent persisted integration outputs, newest first (central store)."""
    stmt = select(IntegrationArtifact).order_by(IntegrationArtifact.created_at.desc()).limit(max(1, min(limit, 500)))
    if integration:
        stmt = stmt.where(IntegrationArtifact.integration == integration)
    rows = db.scalars(stmt).all()
    return [
        {
            "id": a.id,
            "created_at": a.created_at.isoformat(),
            "integration": a.integration,
            "kind": a.kind,
            "title": a.title,
            "summary": a.summary,
        }
        for a in rows
    ]


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str, db: Session = Depends(get_db)) -> dict:
    a = db.get(IntegrationArtifact, artifact_id)
    if not a:
        raise HTTPException(404, "artifact not found")
    return {
        "id": a.id,
        "created_at": a.created_at.isoformat(),
        "integration": a.integration,
        "kind": a.kind,
        "title": a.title,
        "summary": a.summary,
        "payload": a.payload,
    }


# ---- generic ---------------------------------------------------------------

@router.get("")
def list_integrations() -> list[dict]:
    return all_status()


@router.get("/{name}")
def integration_status(name: str) -> dict:
    integ = get_integration(name)
    if integ is None:
        raise HTTPException(404, f"unknown integration '{name}'")
    return integ.status().as_dict()


# ---- caldera ---------------------------------------------------------------

class CalderaAnalyzeRequest(BaseModel):
    reports: list[dict[str, Any]] | None = None   # raw Caldera operation JSON
    sample: str | None = None                     # or a vendored sample filename
    # Red-team posture: the blue-team "SOC narrative" is off by default. The
    # structured ATT&CK coverage is what matters for emulation review.
    ai: bool = False


@router.get("/caldera/samples")
def caldera_samples() -> list[dict]:
    return list_samples()


@router.post("/caldera/analyze")
def caldera_analyze(req: CalderaAnalyzeRequest, db: Session = Depends(get_db)) -> dict:
    reports = req.reports or []
    if req.sample:
        try:
            reports = [load_sample(req.sample)]
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
    if not reports:
        raise HTTPException(400, "provide `reports` (raw Caldera JSON) or a `sample` filename")
    try:
        result = analyze(reports, ai=req.ai)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, f"could not analyze report(s): {exc}") from exc
    stats = result.get("stats", {})
    ops = ", ".join(sorted({(r.get("operation") or "?") for r in result.get("reports", [])})) or "Caldera report"
    summary = (
        f"{stats.get('total_steps', 0)} steps · {stats.get('distinct_techniques', 0)} techniques · "
        f"{stats.get('distinct_tactics', 0)} tactics · {stats.get('success', 0)} ok / {stats.get('failed', 0)} failed"
    )
    result["artifact_id"] = _save_artifact(db, "caldera", "analysis", ops, summary, result)
    return result


# ---- vervet ----------------------------------------------------------------

@router.get("/vervet/describe")
def vervet_describe(db: Session = Depends(get_db)) -> dict:
    integ = VervetIntegration()
    st = integ.status()
    if not st.available:
        raise HTTPException(503, st.reason)
    try:
        doc = integ.describe()
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
    techniques = doc.get("techniques", []) if isinstance(doc, dict) else []
    verbs = doc.get("verbs", []) if isinstance(doc, dict) else []
    summary = f"{len(techniques)} techniques · verbs: {', '.join(verbs)}"
    doc["artifact_id"] = _save_artifact(db, "vervet", "describe", "vervet describe (vq1)", summary, doc)
    return doc


class VervetEmulateRequest(BaseModel):
    target: str
    technique: str = "T1046"


@router.post("/vervet/emulate")
def vervet_emulate(req: VervetEmulateRequest, db: Session = Depends(get_db)) -> dict:
    """Auto-sign a scope for the target and fire a vervet service-discovery scan."""
    integ = VervetIntegration()
    st = integ.status()
    if not st.available:
        raise HTTPException(503, st.reason)
    try:
        result = integ.emulate(req.target, req.technique)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(422, str(exc)) from exc
    ports = [f.get("detail") for f in result.get("findings", []) if f.get("detail")]
    summary = f"{req.technique} vs {req.target}: {len(ports)} observation(s)" + (
        f" — {', '.join(ports)}" if ports else ""
    )
    result["artifact_id"] = _save_artifact(
        db, "vervet", "emulate", f"{req.technique} → {req.target}", summary, result
    )
    return result


# ---- locust ----------------------------------------------------------------

class LocustRunRequest(BaseModel):
    users: int | None = Field(default=None, ge=1)
    spawn_rate: int | None = Field(default=None, ge=1)
    run_seconds: int | None = Field(default=None, ge=1)


@router.post("/locust/run")
def locust_run(req: LocustRunRequest, db: Session = Depends(get_db)) -> dict:
    integ = LocustIntegration()
    blocked = integ.preconditions()
    if blocked:
        # 423 Locked: armed-but-not-configured or disabled; mirrors the kill switch.
        raise HTTPException(423, blocked)
    try:
        result = integ.run(users=req.users, spawn_rate=req.spawn_rate, run_seconds=req.run_seconds)
    except RuntimeError as exc:
        raise HTTPException(423, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"locust run failed: {exc}") from exc
    p = result.get("params", {})
    agg = None
    for row in result.get("stats") or []:
        if isinstance(row, dict) and row.get("name") in ("Aggregated", "Total", "/"):
            agg = row
            break
    reqs = agg.get("num_requests") if agg else "?"
    fails = agg.get("num_failures") if agg else "?"
    summary = f"{p.get('users')} users · {p.get('run_seconds')}s · {reqs} requests, {fails} failures → {p.get('target')}"
    result["artifact_id"] = _save_artifact(db, "locust", "load_test", f"Load test → {p.get('target')}", summary, result)
    return result
