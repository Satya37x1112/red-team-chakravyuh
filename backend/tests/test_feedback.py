"""Feedback engine: deterministic guardrails always win over the AI."""
from __future__ import annotations

from app.agent.analysis import AnalysisResult
from app.agent.context import build_context
from app.agent.feedback import CONTINUE, MODIFY, STOP, decide
from app.config import settings


def _ctx(killswitch=False):
    ctx = build_context("obj", scenario_id="t")
    ctx.safety["kill_switch_engaged"] = killswitch
    return ctx


def _analysis(met=False):
    return AnalysisResult(measured_facts=[], interpretation="", source="deterministic", objective_met=met)


def _unavailable_llm():
    return lambda s, u: (None, None, ["no key"])


def test_objective_met_forces_stop():
    rec = decide(_analysis(met=True), _ctx(), iteration=0, max_iterations=5,
                 consecutive_failures=0, last_state="COMPLETED", llm=_unavailable_llm())
    assert rec.action == STOP and rec.source == "deterministic"


def test_kill_switch_forces_stop():
    rec = decide(_analysis(), _ctx(killswitch=True), iteration=0, max_iterations=5,
                 consecutive_failures=0, last_state="COMPLETED", llm=_unavailable_llm())
    assert rec.action == STOP


def test_max_iterations_forces_stop():
    rec = decide(_analysis(), _ctx(), iteration=4, max_iterations=5,
                 consecutive_failures=0, last_state="COMPLETED", llm=_unavailable_llm())
    assert rec.action == STOP


def test_consecutive_failures_force_stop():
    settings.ai_consecutive_failure_stop = 2
    rec = decide(_analysis(), _ctx(), iteration=0, max_iterations=5,
                 consecutive_failures=2, last_state="FAILED", llm=_unavailable_llm())
    assert rec.action == STOP


def test_failed_state_defaults_to_modify():
    rec = decide(_analysis(), _ctx(), iteration=0, max_iterations=5,
                 consecutive_failures=1, last_state="FAILED", llm=_unavailable_llm())
    assert rec.action == MODIFY and rec.source == "deterministic"


def test_completed_not_met_defaults_to_continue():
    rec = decide(_analysis(met=False), _ctx(), iteration=0, max_iterations=5,
                 consecutive_failures=0, last_state="COMPLETED", llm=_unavailable_llm())
    assert rec.action == CONTINUE


def test_ai_recommendation_used_when_safe():
    rec = decide(_analysis(), _ctx(), iteration=0, max_iterations=5, consecutive_failures=0,
                 last_state="COMPLETED", llm=lambda s, u: ("MODIFY", "mock", []))
    assert rec.action == MODIFY and rec.source == "ai"


def test_ai_cannot_override_deterministic_stop():
    # Even if the AI says CONTINUE, max-iterations STOP wins.
    rec = decide(_analysis(), _ctx(), iteration=4, max_iterations=5, consecutive_failures=0,
                 last_state="COMPLETED", llm=lambda s, u: ("CONTINUE", "mock", []))
    assert rec.action == STOP and rec.source == "deterministic"
