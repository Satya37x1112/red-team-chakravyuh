"""Operation Runner — the centralized AI loop.

Drives one user objective through bounded iterations of:

  context -> AI plan -> schema validation -> Safety Gateway -> dispatcher ->
  execution -> observation -> AI analysis -> feedback (CONTINUE/MODIFY/STOP)

Deterministic throughout: the Gateway authorizes (never the AI); the iteration
cap and stop conditions are config-driven; every secret is masked before it is
persisted. LLM and execution adapters are injectable so tests use mocks and no
real tool runs and no target is contacted.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..config import settings
from ..db import SessionLocal
from ..models import Operation, OperationIteration
from ..safety import gateway
from ..safety.audit import mask_secrets
from ..safety.dispatcher import Adapter, run_execution
from ..safety.registry import ExecState, registry
from .analysis import analyze
from .context import build_context
from .feedback import STOP, decide as feedback_decide
from .llm import LLMComplete
from .planner import generate_plan

_PLAN_SOURCE_DB = {"ai": "ai", "fallback": "system", "unavailable": "none"}
_PERMANENT_REJECT_HINTS = ("disabled", "unavailable", "kill switch", "not executable")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _summarize_result(module: str, result: dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return ""
    if module == "bruteforce":
        return f"found={result.get('found_count')} attempts={result.get('attempts_made')} msg={result.get('message')}"[:2000]
    if module == "ddos":
        t = result.get("totals") or {}
        return f"requests={t.get('requests')} failures={t.get('failures')} rps={t.get('rps')}"[:2000]
    return str(result)[:2000]


def run_operation(
    objective: str,
    *,
    scenario_id: str | None = None,
    module_hint: str | None = None,
    max_iterations: int | None = None,
    llm: LLMComplete | None = None,
    adapters: dict[str, Adapter] | None = None,
) -> dict[str, Any]:
    scenario_id = scenario_id or f"op-{uuid.uuid4().hex[:8]}"
    # Deterministic cap — the AI cannot raise it.
    cap = settings.ai_max_feedback_iterations
    max_iter = max(1, min(max_iterations or cap, cap))

    db = SessionLocal()
    op = Operation(objective=objective[:4000], scenario_id=scenario_id,
                   module_hint=module_hint, status="RUNNING")
    db.add(op)
    db.commit()
    op_id = op.id
    db.close()

    history: list[dict[str, Any]] = []
    consecutive_failures = 0
    objective_met = False
    final_action: str | None = None
    iterations_run = 0

    for i in range(max_iter):
        ctx = build_context(objective, scenario_id=scenario_id, module_hint=module_hint, history=history)
        planning = generate_plan(ctx, llm=llm)

        it = {
            "index": i,
            "plan_source": _PLAN_SOURCE_DB.get(planning.status, "none"),
            "model": planning.model,
            "prompt_version": planning.prompt_version,
            "ai_output": mask_secrets(planning.ai_raw),
        }

        # No plan available -> honest stop.
        if planning.plan is None:
            it.update(validation_ok=False, validation_error=planning.reasoning,
                      feedback_action=STOP, feedback_reasoning="No runnable/valid plan available.")
            _persist_iteration(op_id, it)
            iterations_run += 1
            final_action = STOP
            break

        it["validation_ok"] = True  # pydantic validated at construction
        decision = gateway.evaluate(planning.plan)
        it["gateway_decision"] = mask_secrets(decision.as_dict())

        if decision.rejected:
            # Gateway rejected — a deterministic fact. Permanent reasons stop now.
            permanent = any(h in decision.reason.lower() for h in _PERMANENT_REJECT_HINTS)
            consecutive_failures += 1
            action = STOP if (permanent or consecutive_failures >= settings.ai_consecutive_failure_stop) else "MODIFY"
            it.update(
                execution_state="REJECTED",
                analysis={"measured_facts": [f"Safety Gateway rejected the plan: {decision.reason}"],
                          "interpretation": "No execution occurred; the deterministic gateway denied authorization.",
                          "interpretation_source": "deterministic", "objective_met": False},
                feedback_action=action,
                feedback_reasoning=("Permanent policy rejection; stopping." if permanent
                                    else "Gateway rejected; stopping after repeated rejections."
                                    if action == STOP else "Gateway rejected; the planner may try a revised approach."),
            )
            _persist_iteration(op_id, it)
            iterations_run += 1
            history.append({"module": planning.plan.module.value, "state": "REJECTED",
                            "reason": decision.reason, "feedback": action})
            final_action = action
            if action == STOP:
                break
            continue

        # Approved -> run through the controlled dispatcher (mock adapters in tests).
        outcome = run_execution(decision.execution_id, adapters=adapters)  # type: ignore[arg-type]
        rec = registry.get(decision.execution_id)  # type: ignore[arg-type]
        result = outcome.get("result") or {}
        state = rec.state.value if rec else outcome.get("state", "UNKNOWN")

        analysis = analyze(rec, result, ctx, llm=llm) if rec else None
        if state in ("FAILED", "TIMED_OUT", "CANCELLED"):
            consecutive_failures += 1
        else:
            consecutive_failures = 0

        fb = feedback_decide(
            analysis, ctx, iteration=i, max_iterations=max_iter,
            consecutive_failures=consecutive_failures, last_state=state, llm=llm,
        ) if analysis else None

        it.update(
            execution_id=decision.execution_id,
            execution_state=state,
            result_summary=mask_secrets({"s": _summarize_result(planning.plan.module.value, result)})["s"],
            analysis=mask_secrets(analysis.as_dict()) if analysis else {},
            feedback_action=fb.action if fb else STOP,
            feedback_reasoning=fb.reasoning if fb else "No analysis available.",
        )
        _persist_iteration(op_id, it)
        iterations_run += 1

        objective_met = objective_met or (analysis.objective_met if analysis else False)
        final_action = fb.action if fb else STOP
        history.append({
            "module": planning.plan.module.value,
            "params": planning.plan.params.model_dump(exclude_none=True),
            "state": state,
            "measured_facts": analysis.measured_facts if analysis else [],
            "feedback": final_action,
        })
        if final_action == STOP:
            break

    status = "COMPLETED" if objective_met else ("FAILED" if iterations_run == 0 else "STOPPED")
    _finalize(op_id, status, final_action, iterations_run)
    return get_operation(op_id)


def _persist_iteration(op_id: str, fields: dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        db.add(OperationIteration(operation_id=op_id, **fields))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _finalize(op_id: str, status: str, final_action: str | None, iterations: int) -> None:
    db = SessionLocal()
    try:
        op = db.get(Operation, op_id)
        if op:
            op.status = status
            op.final_recommendation = final_action
            op.iterations = iterations
            op.ended_at = _now()
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def get_operation(op_id: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        op = db.get(Operation, op_id)
        if op is None:
            return {}
        its = (db.query(OperationIteration)
               .filter(OperationIteration.operation_id == op_id)
               .order_by(OperationIteration.index).all())
        return {
            "id": op.id,
            "objective": op.objective,
            "scenario_id": op.scenario_id,
            "module_hint": op.module_hint,
            "status": op.status,
            "final_recommendation": op.final_recommendation,
            "iterations": op.iterations,
            "created_at": op.created_at.isoformat(),
            "ended_at": op.ended_at.isoformat() if op.ended_at else None,
            "steps": [{
                "index": it.index,
                "plan_source": it.plan_source,
                "model": it.model,
                "prompt_version": it.prompt_version,
                "ai_output": it.ai_output,
                "validation_ok": it.validation_ok,
                "validation_error": it.validation_error,
                "gateway_decision": it.gateway_decision,
                "execution_id": it.execution_id,
                "execution_state": it.execution_state,
                "result_summary": it.result_summary,
                "analysis": it.analysis,
                "feedback_action": it.feedback_action,
                "feedback_reasoning": it.feedback_reasoning,
            } for it in its],
        }
    finally:
        db.close()


def list_operations(limit: int = 50) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        ops = (db.query(Operation).order_by(Operation.created_at.desc())
               .limit(max(1, min(limit, 200))).all())
        return [{
            "id": o.id, "objective": o.objective, "scenario_id": o.scenario_id,
            "status": o.status, "final_recommendation": o.final_recommendation,
            "iterations": o.iterations, "created_at": o.created_at.isoformat(),
        } for o in ops]
    finally:
        db.close()
