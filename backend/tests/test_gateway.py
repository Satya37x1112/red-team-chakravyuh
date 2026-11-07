"""Deterministic Safety Gateway behaviour."""
from __future__ import annotations

from app.safety import gateway
from app.safety.plan_schema import ExecutionParams, ExecutionPlan, ModuleId, PlanSource
from app.safety.registry import ExecState, registry


def _plan(module=ModuleId.bruteforce, target="10.9.9.9", **params):
    return ExecutionPlan(
        scenario_id="t", module=module, requested_target=target,
        params=ExecutionParams(**params),
    )


def test_authorized_target_accepted(armed_bruteforce):
    d = gateway.evaluate(_plan(target=armed_bruteforce))
    assert d.approved, d.reason
    assert d.execution_id
    rec = registry.get(d.execution_id)
    assert rec.state is ExecState.APPROVED


def test_unauthorized_target_rejected(armed_bruteforce):
    d = gateway.evaluate(_plan(target="10.0.0.254"))
    assert d.rejected
    assert "allowlist" in d.reason.lower()
    # A rejected plan creates NO runnable record.
    assert registry.active_count() == 0


def test_disabled_module_rejected():
    # default config: hydra disabled
    d = gateway.evaluate(_plan())
    assert d.rejected
    assert "disabled" in d.reason.lower()


def test_rat_related_rejected_when_disabled():
    # rat_related is a real module since Section 4, but disabled by default, so a
    # plan for it is still rejected (fail-closed) until explicitly armed.
    d = gateway.evaluate(_plan(module=ModuleId.rat_related))
    assert d.rejected
    assert "disabled" in d.reason.lower()


def test_unavailable_integration_rejected(armed_bruteforce, monkeypatch):
    monkeypatch.setattr(gateway.policy, "integration_available", lambda m: (False, "binary not found"))
    d = gateway.evaluate(_plan(target=armed_bruteforce))
    assert d.rejected
    assert "unavailable" in d.reason.lower()


def test_ai_cannot_exceed_fixed_limits(armed_ddos):
    # AI asks for 5000 users; cap is 50 -> clamped DOWN, never raised.
    plan = ExecutionPlan(
        scenario_id="t", module=ModuleId.ddos, source=PlanSource.ai,
        requested_target=armed_ddos, params=ExecutionParams(users=5000, spawn_rate=9999, run_seconds=80000),
    )
    d = gateway.evaluate(plan)
    assert d.approved, d.reason
    assert d.validated_parameters["users"] == 50
    assert d.validated_parameters["spawn_rate"] == 10
    assert d.validated_parameters["run_seconds"] == 30


def test_excessive_param_beyond_sanity_rejected_at_schema(armed_ddos):
    # Absurd values are rejected by the schema before the Gateway is reached.
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ExecutionPlan(
            scenario_id="t", module=ModuleId.ddos, requested_target=armed_ddos,
            params=ExecutionParams(users=999_999),
        )


def test_gateway_fails_closed_on_internal_error(armed_bruteforce, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("policy backend down")

    monkeypatch.setattr(gateway.policy, "clamp_params", boom)
    d = gateway.evaluate(_plan(target=armed_bruteforce))
    assert d.rejected
    assert "fail-closed" in d.reason.lower()


def test_kill_switch_blocks_new_plans(armed_bruteforce):
    gateway.kill_switch.engage("test")
    d = gateway.evaluate(_plan(target=armed_bruteforce))
    assert d.rejected
    assert "kill switch" in d.reason.lower()


def test_concurrency_limit_enforced(armed_bruteforce):
    from app.config import settings
    settings.safety_max_concurrent_executions = 1
    d1 = gateway.evaluate(_plan(target=armed_bruteforce))
    assert d1.approved
    d2 = gateway.evaluate(_plan(target=armed_bruteforce))
    assert d2.rejected
    assert "concurrency" in d2.reason.lower()
