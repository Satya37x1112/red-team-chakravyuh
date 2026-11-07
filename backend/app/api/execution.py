"""Controlled execution API (Section 2).

The single front door for structured execution requests. Everything here goes
through the deterministic pipeline:

    ExecutionPlan -> SafetyGateway -> Registry -> dispatcher -> adapter

There is no endpoint that invokes an adapter directly. Rejected plans return
423 and never touch an adapter. Secrets are masked before any value leaves here.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..safety import dispatcher, evaluate
from ..safety.killswitch import kill_switch
from ..safety.plan_schema import ExecutionPlan
from ..safety.registry import ExecState, registry

router = APIRouter(prefix="/api/execution")


@router.post("/submit")
def submit_execution(plan: ExecutionPlan) -> dict:
    """Submit a structured plan. Validates (schema) -> authorizes (Gateway) ->
    runs the approved execution through the controlled dispatcher."""
    decision = evaluate(plan)
    if decision.rejected:
        # 423 Locked: policy/kill-switch/scope/limit rejection (fail-closed).
        raise HTTPException(423, decision.reason)
    outcome = dispatcher.run_execution(decision.execution_id)  # type: ignore[arg-type]
    rec = registry.get(decision.execution_id)  # type: ignore[arg-type]
    if rec and rec.state == ExecState.FAILED:
        raise HTTPException(502, f"execution failed: {rec.error}")
    return {"decision": decision.as_dict(), **outcome}


@router.get("")
def list_executions(active_only: bool = False) -> list[dict]:
    return [r.as_dict() for r in registry.list(active_only=active_only)]


@router.get("/killswitch")
def killswitch_state() -> dict:
    return kill_switch.state()


@router.get("/{execution_id}")
def get_execution(execution_id: str) -> dict:
    rec = registry.get(execution_id)
    if rec is None:
        raise HTTPException(404, "execution not found")
    return rec.as_dict()


@router.post("/{execution_id}/cancel")
def cancel_execution(execution_id: str) -> dict:
    rec = registry.get(execution_id)
    if rec is None:
        raise HTTPException(404, "execution not found")
    return dispatcher.cancel_execution(execution_id)
