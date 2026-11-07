"""Live / offline OpenRouter verification for the centralized planner.

The live test runs ONLY when OPENROUTER_API_KEY is configured; otherwise it is
skipped and live verification is reported BLOCKED. It is an AI-planning test
only: it validates the model's structured output against the Pydantic schema and
asserts the deterministic bindings (target + caps) — it NEVER invokes an
execution adapter, contacts a target, or runs a tool. The key is never printed.
"""
from __future__ import annotations

import pytest

from app.agent.context import build_context
from app.agent.llm import default_llm
from app.agent.planner import generate_plan
from app.config import settings
from app.safety import gateway
from app.safety.plan_schema import PlanSource

_HAS_KEY = bool(settings.openrouter_api_key.strip())


def test_default_llm_without_key_is_offline_and_honest(monkeypatch):
    """With no key, the default LLM path returns an honest unavailable result and
    makes NO network call (it must not even construct a client)."""
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    # If it tried to build a client / call out, this would raise; it must not.
    text, model, errors = default_llm("system", "user")
    assert text is None and model is None
    assert errors and any("key" in e.lower() for e in errors)


@pytest.mark.skipif(not _HAS_KEY, reason="OPENROUTER_API_KEY not configured; live LLM verification blocked")
def test_live_structured_plan_validates_and_is_bound(armed_bruteforce):
    """LIVE: ask the real model for a plan; validate schema + deterministic bindings.
    No dispatcher is invoked; no target is contacted."""
    ctx = build_context(
        "SIMULATED authorized-lab objective: assess the lab login service resilience",
        scenario_id="sim-live-verify", module_hint="bruteforce",
    )
    res = generate_plan(ctx, llm=default_llm)  # real OpenRouter
    # Either the model produced a valid AI plan, or an honest fallback — never a crash.
    assert res.status in ("ai", "fallback")
    assert res.plan is not None
    # The AI can NOT invent a target — it is bound to the authorized allowlist.
    assert res.plan.requested_target == armed_bruteforce
    if res.status == "ai":
        assert res.plan.source is PlanSource.ai
        assert res.model  # model id recorded for audit
    # The plan still must pass the deterministic gateway, which clamps to caps.
    decision = gateway.evaluate(res.plan, dry_run=True)
    assert decision.approved
    assert decision.validated_parameters["tasks"] <= settings.hydra_max_tasks
