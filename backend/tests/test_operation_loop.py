"""Full centralized AI loop with MOCK LLM + MOCK adapters (no real tools/target)."""
from __future__ import annotations

import json

from app.agent.operation import run_operation
from app.config import settings
from app.safety.killswitch import kill_switch


def smart_llm(plan_module="bruteforce", feedback="CONTINUE", params=None):
    """One mock that answers planner, feedback, and analysis prompts correctly."""
    def f(system, user):
        if "planning brain" in system:
            return (json.dumps({"module": plan_module, "params": params or {}, "reasoning": "r"}), "mock", [])
        if "ONE word only" in system:  # feedback
            return (feedback, "mock", [])
        return ("Interpretation: evidence is partial.", "mock", [])  # analysis
    return f


def hydra_hit(p):
    return {"exit_code": 0, "found_count": 1, "attempts_made": 5, "message": "1 valid pair"}


def hydra_miss(p):
    return {"exit_code": 0, "found_count": 0, "attempts_made": 10, "message": "no valid pairs"}


def test_loop_completes_when_objective_met(armed_bruteforce):
    op = run_operation("crack lab login", module_hint="bruteforce", max_iterations=3,
                       llm=smart_llm("bruteforce", "CONTINUE"), adapters={"hydra": hydra_hit})
    assert op["status"] == "COMPLETED"
    assert op["iterations"] == 1
    assert op["final_recommendation"] == "STOP"  # objective met -> deterministic stop
    assert op["steps"][0]["execution_state"] == "COMPLETED"
    assert op["steps"][0]["analysis"]["objective_met"] is True


def test_approved_hydra_reaches_mock_adapter_with_clamped_params(armed_bruteforce):
    calls = []
    op = run_operation("x", module_hint="bruteforce", llm=smart_llm("bruteforce", "STOP"),
                       adapters={"hydra": lambda p: calls.append(p) or hydra_hit(p)})
    assert len(calls) == 1
    assert calls[0]["tasks"] == 4           # empty AI params -> gateway used the cap
    assert calls[0]["run_seconds"] == 30


def test_approved_locust_reaches_mock_adapter(armed_ddos):
    calls = []
    adapter = lambda p: calls.append(p) or {"exit_code": 0, "totals": {"requests": 100, "failures": 7, "rps": 10}}
    op = run_operation("load test", module_hint="ddos", llm=smart_llm("ddos", "CONTINUE"),
                       adapters={"locust": adapter})
    assert len(calls) == 1
    assert op["status"] == "COMPLETED"       # observed failures -> objective met


def test_execution_error_recorded_and_stops(armed_bruteforce):
    settings.ai_consecutive_failure_stop = 2
    def boom(p):
        raise ValueError("adapter boom")
    op = run_operation("x", module_hint="bruteforce", max_iterations=5,
                       llm=smart_llm("bruteforce", "CONTINUE"), adapters={"hydra": boom})
    assert op["status"] == "STOPPED"
    assert op["iterations"] == 2             # stopped after 2 consecutive failures
    assert op["steps"][0]["execution_state"] == "FAILED"


def test_killswitch_prevents_execution(armed_bruteforce):
    kill_switch.engage("test")
    calls = []
    op = run_operation("x", module_hint="bruteforce", llm=smart_llm("bruteforce"),
                       adapters={"hydra": lambda p: calls.append(p) or hydra_hit(p)})
    assert calls == []                        # nothing ran
    assert op["steps"][0]["execution_state"] == "REJECTED"
    assert op["status"] == "STOPPED"


def test_rat_related_never_runs(armed_bruteforce):
    # LLM proposes rat_related; planner must fall back to a runnable module.
    op = run_operation("remote control", module_hint="bruteforce",
                       llm=smart_llm("rat_related", "STOP"), adapters={"hydra": hydra_miss})
    assert op["steps"][0]["gateway_decision"]["module"] == "bruteforce"
    assert op["steps"][0]["plan_source"] == "system"  # fallback, not AI


def test_missing_telemetry_is_honest(armed_bruteforce):
    op = run_operation("x", module_hint="bruteforce", llm=smart_llm("bruteforce", "STOP"),
                       adapters={"hydra": hydra_miss})
    facts = op["steps"][0]["analysis"]["measured_facts"]
    assert any("unavailable" in f.lower() or "not substituting" in f.lower() for f in facts)


def test_no_fabricated_metrics(armed_bruteforce):
    op = run_operation("x", module_hint="bruteforce", llm=smart_llm("bruteforce", "STOP"),
                       adapters={"hydra": lambda p: {"exit_code": 0}})  # no found_count
    analysis = op["steps"][0]["analysis"]
    assert analysis["objective_met"] is False
    assert not any("valid credential" in f.lower() for f in analysis["measured_facts"])


def test_continue_then_capped_stop(armed_bruteforce):
    settings.ai_max_feedback_iterations = 2
    op = run_operation("x", module_hint="bruteforce", max_iterations=5,
                       llm=smart_llm("bruteforce", "CONTINUE"), adapters={"hydra": hydra_miss})
    assert op["iterations"] == 2              # capped
    assert op["final_recommendation"] == "STOP"
    assert op["status"] == "STOPPED"


def test_max_iterations_request_is_clamped(armed_bruteforce):
    settings.ai_max_feedback_iterations = 2
    op = run_operation("x", module_hint="bruteforce", max_iterations=50,
                       llm=smart_llm("bruteforce", "CONTINUE"), adapters={"hydra": hydra_miss})
    assert op["iterations"] <= 2              # request 50 clamped to the deterministic cap


def test_feedback_cannot_bypass_gateway(armed_bruteforce, monkeypatch):
    import app.agent.operation as opmod
    settings.ai_max_feedback_iterations = 2
    calls = {"n": 0}
    real = opmod.gateway.evaluate

    def counting(plan, **k):
        calls["n"] += 1
        return real(plan, **k)

    monkeypatch.setattr(opmod.gateway, "evaluate", counting)
    op = run_operation("x", module_hint="bruteforce", llm=smart_llm("bruteforce", "CONTINUE"),
                       adapters={"hydra": hydra_miss})
    assert calls["n"] == op["iterations"]     # the Gateway re-authorizes EVERY iteration
