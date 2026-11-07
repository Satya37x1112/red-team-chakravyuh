"""The AI planner can never bypass the deterministic Safety Gateway."""
from __future__ import annotations

import json

from app.agent.context import build_context
from app.agent.planner import generate_plan
from app.safety import gateway
from app.safety.plan_schema import ExecutionParams, ExecutionPlan, ModuleId, PlanSource
from app.safety.registry import ExecState, registry


def _llm(text, model="mock"):
    return lambda s, u: (text, model, [])


def _ctx(hint=None):
    return build_context("objective", scenario_id="t", module_hint=hint)


def test_valid_ai_plan_reaches_gateway_and_is_approved(armed_bruteforce):
    res = generate_plan(_ctx("bruteforce"),
                        llm=_llm(json.dumps({"module": "bruteforce", "params": {"tasks": 2}, "reasoning": "x"})))
    decision = gateway.evaluate(res.plan)
    assert decision.approved
    assert registry.get(decision.execution_id).state is ExecState.APPROVED


def test_ai_plan_with_unauthorized_target_is_rejected(armed_bruteforce):
    # Even a hand-forged AI-sourced plan with an off-allowlist target is rejected.
    forged = ExecutionPlan(scenario_id="t", module=ModuleId.bruteforce, source=PlanSource.ai,
                           requested_target="192.0.2.99", params=ExecutionParams(tasks=2))
    decision = gateway.evaluate(forged)
    assert decision.rejected
    assert "allowlist" in decision.reason.lower()


def test_ai_cannot_exceed_hard_limits(armed_bruteforce):
    res = generate_plan(_ctx("bruteforce"),
                        llm=_llm(json.dumps({"module": "bruteforce", "params": {"tasks": 9999}, "reasoning": "x"})))
    decision = gateway.evaluate(res.plan)
    assert decision.approved
    # Gateway clamps to the configured cap (4), regardless of the AI's 9999->64.
    assert decision.validated_parameters["tasks"] == 4


def test_ai_cannot_change_allowlist(armed_bruteforce):
    from app.safety import policy
    before = policy.authorized_targets(ModuleId.bruteforce)
    generate_plan(_ctx(), llm=_llm(json.dumps({"module": "bruteforce", "target": "10.0.0.9",
                                               "params": {}, "reasoning": "x"})))
    after = policy.authorized_targets(ModuleId.bruteforce)
    assert before == after  # the AI cannot widen the allowlist


def test_gateway_fail_closed_on_internal_error(armed_bruteforce, monkeypatch):
    res = generate_plan(_ctx("bruteforce"),
                        llm=_llm(json.dumps({"module": "bruteforce", "params": {}, "reasoning": "x"})))
    monkeypatch.setattr(gateway.policy, "clamp_params", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    decision = gateway.evaluate(res.plan)
    assert decision.rejected and "fail-closed" in decision.reason.lower()


def test_rat_related_plan_is_rejected():
    forged = ExecutionPlan(scenario_id="t", module=ModuleId.rat_related, source=PlanSource.ai,
                           requested_target="10.0.0.1")
    decision = gateway.evaluate(forged)
    assert decision.rejected
    assert "not executable" in decision.reason.lower()
