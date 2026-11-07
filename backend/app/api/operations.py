"""Centralized AI operations API (Section 3).

Exposes the planning brain and the feedback loop without ever bypassing the
Section-2 Safety Gateway:

  POST /api/operations/plan  -> context -> AI plan -> gateway DRY-RUN preview
  POST /api/operations       -> run the bounded plan->gateway->execute->analyze
                                ->feedback loop (fail-closed: disabled modules are
                                rejected by the gateway, so nothing runs for real)
  GET  /api/operations        -> list
  GET  /api/operations/{id}   -> full iteration trail

Secrets are masked in every response.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..agent.context import build_context
from ..agent.operation import get_operation, list_operations, run_operation
from ..agent.planner import generate_plan
from ..safety import gateway
from ..safety.audit import mask_secrets

router = APIRouter(prefix="/api/operations")


class PlanPreviewRequest(BaseModel):
    objective: str = Field(min_length=1, max_length=4000)
    module_hint: str | None = None


class OperationRequest(BaseModel):
    objective: str = Field(min_length=1, max_length=4000)
    module_hint: str | None = None
    max_iterations: int | None = Field(default=None, ge=1, le=20)


@router.post("/plan")
def plan_preview(req: PlanPreviewRequest) -> dict:
    """Generate an AI plan and show the Gateway's dry-run verdict. No execution."""
    ctx = build_context(req.objective, scenario_id="preview", module_hint=req.module_hint)
    planning = generate_plan(ctx)
    out: dict = {
        "planning_status": planning.status,     # ai | fallback | unavailable
        "model": planning.model,
        "prompt_version": planning.prompt_version,
        "reasoning": planning.reasoning,
        "runnable_modules": ctx.runnable_modules(),
        "telemetry_scope": ctx.telemetry.get("scope"),
    }
    if planning.plan is None:
        out["plan"] = None
        out["gateway_decision"] = None
        return out
    decision = gateway.evaluate(planning.plan, dry_run=True)
    out["plan"] = mask_secrets(planning.plan.model_dump(mode="json"))
    out["gateway_decision"] = mask_secrets(decision.as_dict())
    return out


@router.post("")
def start_operation(req: OperationRequest) -> dict:
    """Run the centralized AI loop. Fail-closed: with no module armed, the Gateway
    rejects every plan and nothing executes for real."""
    return run_operation(
        req.objective, module_hint=req.module_hint, max_iterations=req.max_iterations,
    )


@router.get("")
def list_ops(limit: int = 50) -> list[dict]:
    return list_operations(limit=limit)


@router.get("/{operation_id}")
def get_op(operation_id: str) -> dict:
    op = get_operation(operation_id)
    if not op:
        raise HTTPException(404, "operation not found")
    return op
