"""Shared fixtures for the Section-2 safety test suite.

These tests NEVER contact a real target and NEVER run a real attack tool. Where
an execution path is exercised, a mock adapter (or a harmless `sleep` subprocess)
stands in for Hydra/Locust. Config is mutated in-memory and restored per test.
"""
from __future__ import annotations

import pytest

from app.config import settings
from app.safety.killswitch import kill_switch
from app.safety.registry import registry

# Attributes these tests mutate; snapshot + restore so tests don't leak state.
_WATCHED = [
    "hydra_enabled", "hydra_target", "hydra_max_tasks", "hydra_max_run_seconds",
    "locust_enabled", "locust_target_url", "locust_max_users", "locust_max_spawn_rate",
    "locust_max_run_seconds", "safety_target_allowlist", "safety_max_concurrent_executions",
    "safety_admin_token", "killswitch_grace_seconds",
    "ai_max_feedback_iterations", "ai_consecutive_failure_stop", "ai_prompt_version",
    "remote_access_enabled", "remote_access_target", "remote_access_user",
    "remote_access_password", "remote_access_domain", "remote_access_protocol",
    "remote_access_max_run_seconds", "remote_access_bin",
]


@pytest.fixture(autouse=True)
def _isolate_state():
    snapshot = {k: getattr(settings, k) for k in _WATCHED}
    # Clean registry + disengaged kill switch before each test.
    registry._records.clear()
    kill_switch._engaged = False
    kill_switch._engaged_at = None
    kill_switch._reason = ""
    try:
        yield
    finally:
        for k, v in snapshot.items():
            setattr(settings, k, v)
        registry._records.clear()
        kill_switch._engaged = False
        kill_switch._engaged_at = None
        kill_switch._reason = ""


@pytest.fixture
def armed_bruteforce():
    """Enable the bruteforce module against an authorized lab target (no run)."""
    settings.hydra_enabled = True
    settings.hydra_target = "10.9.9.9"
    settings.safety_target_allowlist = "10.9.9.9"
    settings.hydra_max_tasks = 4
    settings.hydra_max_run_seconds = 30
    return "10.9.9.9"


@pytest.fixture
def armed_remote_access():
    """Enable credentialed remote access against an authorized target (no real call)."""
    settings.remote_access_enabled = True
    settings.remote_access_target = "192.168.176.50"
    settings.safety_target_allowlist = "192.168.176.50"
    settings.remote_access_user = "labadmin"
    settings.remote_access_password = "Welcome1"   # synthetic lab cred for tests
    settings.remote_access_domain = "LAB"
    settings.remote_access_protocol = "smb"
    settings.remote_access_max_run_seconds = 30
    return "192.168.176.50"


@pytest.fixture
def armed_ddos():
    settings.locust_enabled = True
    settings.locust_target_url = "http://10.9.9.9:8080"
    settings.safety_target_allowlist = "http://10.9.9.9:8080"
    settings.locust_max_users = 50
    settings.locust_max_spawn_rate = 10
    settings.locust_max_run_seconds = 30
    return "http://10.9.9.9:8080"
