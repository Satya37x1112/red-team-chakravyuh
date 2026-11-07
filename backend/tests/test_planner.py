"""Centralized AI planner: structured plan generation + honest fallback."""
from __future__ import annotations

import json

from app.agent.context import build_context
from app.agent.planner import generate_plan
from app.safety.plan_schema import ModuleId, PlanSource


def _llm(text, model="mock-model"):
    return lambda s, u: (text, model, [])


def _ctx(objective="crack the lab login", hint=None):
    return build_context(objective, scenario_id="t", module_hint=hint)


def test_valid_structured_plan(armed_bruteforce):
    payload = json.dumps({"module": "bruteforce", "params": {"tasks": 2, "run_seconds": 10},
                          "reasoning": "weak creds likely", "expected_observations": "a hit",
                          "confidence": "medium"})
    res = generate_plan(_ctx(hint="bruteforce"), llm=_llm(payload))
    assert res.status == "ai"
    assert res.plan.module is ModuleId.bruteforce
    assert res.plan.source is PlanSource.ai
    # Target is bound to the authorized scope, NOT taken from the model.
    assert res.plan.requested_target == armed_bruteforce
    assert res.plan.params.tasks == 2


def test_ai_never_sets_target(armed_bruteforce):
    payload = json.dumps({"module": "bruteforce", "target": "6.6.6.6", "params": {},
                          "reasoning": "x"})
    res = generate_plan(_ctx(), llm=_llm(payload))
    assert res.plan.requested_target == armed_bruteforce  # not 6.6.6.6


def test_malformed_response_falls_back(armed_bruteforce):
    res = generate_plan(_ctx(), llm=_llm("this is not json at all"))
    assert res.status == "fallback"
    assert res.plan is not None
    assert res.plan.source is PlanSource.system  # NOT ai
    assert "fallback" in res.reasoning.lower()


def test_missing_module_falls_back(armed_bruteforce):
    res = generate_plan(_ctx(), llm=_llm(json.dumps({"params": {}, "reasoning": "x"})))
    assert res.status == "fallback"
    assert res.plan.source is PlanSource.system


def test_invalid_module_falls_back(armed_bruteforce):
    res = generate_plan(_ctx(), llm=_llm(json.dumps({"module": "sql_injection", "params": {}})))
    assert res.status == "fallback"


def test_out_of_range_params_clamped_to_schema(armed_bruteforce):
    res = generate_plan(_ctx(hint="bruteforce"),
                        llm=_llm(json.dumps({"module": "bruteforce", "params": {"tasks": 9999},
                                             "reasoning": "x"})))
    assert res.status == "ai"
    assert res.plan.params.tasks == 64  # clamped to schema max; gateway clamps to caps later


def test_llm_unavailable_labeled_fallback(armed_bruteforce):
    res = generate_plan(_ctx(), llm=lambda s, u: (None, None, ["no OpenRouter key"]))
    assert res.status == "fallback"
    assert res.plan.source is PlanSource.system
    assert res.status != "ai"  # never mislabel a heuristic as AI


def test_llm_timeout_falls_back(armed_bruteforce):
    def boom(s, u):
        raise TimeoutError("model timed out")
    res = generate_plan(_ctx(), llm=boom)
    assert res.status == "fallback"
    assert res.plan is not None


def test_no_runnable_module_is_unavailable():
    # Nothing armed -> no runnable module -> honest unavailable, no plan.
    res = generate_plan(_ctx(), llm=_llm(json.dumps({"module": "bruteforce", "params": {}})))
    assert res.status == "unavailable"
    assert res.plan is None


def test_records_model_and_prompt_version(armed_bruteforce):
    res = generate_plan(_ctx(hint="bruteforce"),
                        llm=_llm(json.dumps({"module": "bruteforce", "params": {}, "reasoning": "x"}),
                                 model="mymodel/v1"))
    assert res.model == "mymodel/v1"
    assert res.prompt_version  # recorded for audit
    assert res.plan.metadata.get("prompt_version") == res.prompt_version
