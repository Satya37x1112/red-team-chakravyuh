"""SAFETY_TARGET_ALLOWLIST authorizes a target for every gated module."""
from app.config import settings
from app.safety import policy
from app.safety.plan_schema import ModuleId


def test_safety_allowlist_authorizes_all_gated_modules(monkeypatch):
    monkeypatch.setattr(settings, "safety_target_allowlist", "100.80.167.51")
    for m in (ModuleId.bruteforce, ModuleId.ddos, ModuleId.rat_related):
        assert "100.80.167.51" in policy.authorized_targets(m)
        assert policy.is_target_authorized(m, "100.80.167.51") is True


def test_safety_allowlist_empty_authorizes_nothing_extra(monkeypatch):
    monkeypatch.setattr(settings, "safety_target_allowlist", "")
    monkeypatch.setattr(settings, "hydra_target", "")
    assert policy.is_target_authorized(ModuleId.bruteforce, "100.80.167.51") is False
