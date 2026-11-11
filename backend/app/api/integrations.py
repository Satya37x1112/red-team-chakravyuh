"""REST API for the external-tool integrations.

All endpoints are read/analysis-oriented except POST /locust/run, which is the
one gated real-action path and fail-closed (see integrations/locust.py).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..integrations import all_status, get_integration
from ..integrations.caldera import analyze, list_samples, load_sample
from ..integrations.pentestgpt import list_runs as pentestgpt_list_runs
from ..integrations.vervet import VervetIntegration
from ..models import IntegrationArtifact
from ..safety import dispatcher, evaluate
from ..safety.plan_schema import ExecutionParams, ExecutionPlan, ModuleId, PlanSource
from ..safety.registry import ExecState, registry

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
    """Recent persisted integration outputs, newest first (central store).

    `integration` may be a single name or a comma-separated list (e.g.
    "vervet,caldera,pentestgpt").
    """
    stmt = select(IntegrationArtifact).order_by(IntegrationArtifact.created_at.desc()).limit(max(1, min(limit, 500)))
    if integration:
        names = [n.strip() for n in integration.split(",") if n.strip()]
        if names:
            stmt = stmt.where(IntegrationArtifact.integration.in_(names))
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


# ---- pentestgpt ------------------------------------------------------------

@router.post("/pentestgpt/ingest")
def pentestgpt_ingest(db: Session = Depends(get_db)) -> dict:
    """Pull PentestGPT CLI run outputs into the central store (so they reach RAT/report)."""
    runs = pentestgpt_list_runs()
    existing = db.scalars(
        select(IntegrationArtifact).where(IntegrationArtifact.integration == "pentestgpt")
    ).all()
    seen = {(a.payload or {}).get("run_id") for a in existing}
    added = 0
    for r in runs:
        rid = r.get("run_id")
        if rid in seen:
            continue
        summary = (
            f"goal: {r.get('goal') or '—'} · target: {r.get('target') or '—'} · "
            f"{r.get('episodes', 0)} episode(s)"
        )
        _save_artifact(db, "pentestgpt", "run", f"PentestGPT run {rid}", summary, r)
        added += 1
    return {"runs_found": len(runs), "added": added}


# ---- locust ----------------------------------------------------------------

class LocustRunRequest(BaseModel):
    target_url: str | None = None
    users: int | None = Field(default=None, ge=1)
    spawn_rate: int | None = Field(default=None, ge=1)
    run_seconds: int | None = Field(default=None, ge=1)


@router.post("/locust/run")
def locust_run(req: LocustRunRequest, db: Session = Depends(get_db)) -> dict:
    # Section 2: this real-action path now runs THROUGH the Safety Gateway and the
    # execution registry/dispatcher — it can no longer bypass centralized control.
    effective_target = (req.target_url or settings.locust_target_url or "unconfigured").strip()
    plan = ExecutionPlan(
        scenario_id="integration:locust",
        module=ModuleId.ddos,
        source=PlanSource.manual,
        requested_target=effective_target,
        params=ExecutionParams(users=req.users, spawn_rate=req.spawn_rate, run_seconds=req.run_seconds),
    )
    decision = evaluate(plan)
    if decision.rejected:
        raise HTTPException(423, decision.reason)
    outcome = dispatcher.run_execution(decision.execution_id)  # type: ignore[arg-type]
    rec = registry.get(decision.execution_id)  # type: ignore[arg-type]
    if rec and rec.state == ExecState.FAILED:
        raise HTTPException(502, f"locust run failed: {rec.error}")
    result = outcome.get("result") or {}
    p = result.get("params", {})
    rows = [r for r in (result.get("stats") or []) if isinstance(r, dict)]
    agg = next((r for r in rows if r.get("name") in ("Aggregated", "Total")), None)
    if agg:
        reqs = agg.get("num_requests", 0)
        fails = agg.get("num_failures", 0)
    else:
        # Locust's --only-summary JSON has no aggregate row — sum the per-endpoint rows.
        reqs = sum(int(r.get("num_requests") or 0) for r in rows)
        fails = sum(int(r.get("num_failures") or 0) for r in rows)
    secs = p.get("run_seconds") or 0
    rps = round(reqs / secs, 1) if secs else reqs
    # Expose the totals so the dashboard can show them without re-deriving.
    result["totals"] = {"requests": reqs, "failures": fails, "rps": rps}
    summary = f"{p.get('users')} users · {secs}s · {reqs} requests (~{rps}/s), {fails} failures → {p.get('target')}"
    result["artifact_id"] = _save_artifact(db, "locust", "load_test", f"Load test → {p.get('target')}", summary, result)
    result["execution_id"] = decision.execution_id
    result["execution_state"] = outcome.get("state")
    return result


class LocustSimRequest(BaseModel):
    users: int | None = Field(default=None, ge=1)
    spawn_rate: int | None = Field(default=None, ge=1)
    run_seconds: int | None = Field(default=None, ge=1)


@router.post("/locust/simulate")
def locust_simulate(req: LocustSimRequest, db: Session = Depends(get_db)) -> dict:
    """DDoS **SIMULATION** — runs through the SAME lifecycle (Gateway → Registry →
    Dispatcher → audit) but generates synthetic telemetry and NO network traffic.
    Routed to the dedicated 'locust_sim' adapter; it can never invoke real Locust."""
    plan = ExecutionPlan(
        scenario_id="integration:locust-sim",
        module=ModuleId.ddos,
        source=PlanSource.manual,
        simulate=True,
        requested_target="simulation",
        params=ExecutionParams(users=req.users, spawn_rate=req.spawn_rate, run_seconds=req.run_seconds),
    )
    decision = evaluate(plan)
    if decision.rejected:
        raise HTTPException(423, decision.reason)
    outcome = dispatcher.run_execution(decision.execution_id)  # type: ignore[arg-type]
    rec = registry.get(decision.execution_id)  # type: ignore[arg-type]
    if rec and rec.state == ExecState.FAILED:
        raise HTTPException(502, f"simulation failed: {rec.error}")
    result = outcome.get("result") or {}
    t = result.get("totals", {})
    p = result.get("params", {})
    summary = (
        f"SIMULATION · {p.get('users')} users · {p.get('actual_seconds')}s · "
        f"{t.get('requests')} sim requests (~{t.get('rps')}/s), {t.get('error_pct')}% sim errors "
        f"— NO NETWORK TRAFFIC"
    )
    result["artifact_id"] = _save_artifact(
        db, "locust", "load_test_simulation", "DDoS simulation (no traffic)", summary, result
    )
    result["execution_id"] = decision.execution_id
    result["execution_state"] = outcome.get("state")
    return result


# ---- hydra -----------------------------------------------------------------

class HydraRunRequest(BaseModel):
    tasks: int | None = Field(default=None, ge=1)
    run_seconds: int | None = Field(default=None, ge=1)


@router.post("/hydra/run")
def hydra_run(req: HydraRunRequest, db: Session = Depends(get_db)) -> dict:
    # Section 2: routed through the Safety Gateway + execution registry/dispatcher.
    plan = ExecutionPlan(
        scenario_id="integration:hydra",
        module=ModuleId.bruteforce,
        source=PlanSource.manual,
        requested_target=settings.hydra_target or "unconfigured",
        params=ExecutionParams(tasks=req.tasks, run_seconds=req.run_seconds),
    )
    decision = evaluate(plan)
    if decision.rejected:
        raise HTTPException(423, decision.reason)
    exec_outcome = dispatcher.run_execution(decision.execution_id)  # type: ignore[arg-type]
    rec = registry.get(decision.execution_id)  # type: ignore[arg-type]
    if rec and rec.state == ExecState.FAILED:
        raise HTTPException(502, f"hydra run failed: {rec.error}")
    result = exec_outcome.get("result") or {}
    p = result.get("params", {})
    n = result.get("found_count", 0)
    logins = ", ".join(sorted({f.get("login", "?") for f in result.get("found", [])})) or "none"
    outcome = "timed out" if result.get("timed_out") else f"exit {result.get('exit_code')}"
    summary = (
        f"{p.get('service')}://{p.get('target')} · {p.get('tasks')} tasks · "
        f"{outcome} · {n} valid pair(s) found (logins: {logins})"
    )
    result["artifact_id"] = _save_artifact(
        db, "hydra", "credential_test", f"Hydra → {p.get('service')}://{p.get('target')}", summary, result
    )
    result["execution_id"] = decision.execution_id
    result["execution_state"] = exec_outcome.get("state")
    return result


# ---- remote access (Credentialed Remote Access / Post-Exploitation Demo) -----

class RemoteAccessRunRequest(BaseModel):
    operation: str = Field(min_length=1, max_length=41)   # an APPROVED operation id, not a command
    run_seconds: int | None = Field(default=None, ge=1)


@router.post("/remote_access/run")
def remote_access_run(req: RemoteAccessRunRequest, db: Session = Depends(get_db)) -> dict:
    """Run ONE approved read-only remote operation THROUGH the Safety Gateway.
    The AI/API supplies only an operation identifier — never a command string.
    Credentials come from config and never appear in the response."""
    try:
        plan = ExecutionPlan(
            scenario_id="integration:remote_access",
            module=ModuleId.rat_related,
            source=PlanSource.manual,
            requested_target=settings.remote_access_target or "unconfigured",
            params=ExecutionParams(operation=req.operation, run_seconds=req.run_seconds),
        )
    except PydanticValidationError as exc:
        # Unsafe operation token (metachars/injection) — reject at the boundary.
        raise HTTPException(422, f"invalid operation identifier: {exc.errors()[0]['msg']}") from exc
    decision = evaluate(plan)
    if decision.rejected:
        raise HTTPException(423, decision.reason)
    exec_outcome = dispatcher.run_execution(decision.execution_id)  # type: ignore[arg-type]
    rec = registry.get(decision.execution_id)  # type: ignore[arg-type]
    if rec and rec.state == ExecState.FAILED:
        raise HTTPException(502, f"remote access failed: {rec.error}")
    result = exec_outcome.get("result") or {}
    summary = (f"{result.get('operation')} → {result.get('protocol')}://{result.get('target')} "
               f"· status={result.get('status')}")
    result["artifact_id"] = _save_artifact(
        db, "remote_access", "remote_operation",
        f"Remote access → {result.get('operation')} @ {result.get('target')}", summary, result)
    result["execution_id"] = decision.execution_id
    result["execution_state"] = exec_outcome.get("state")
    return result
