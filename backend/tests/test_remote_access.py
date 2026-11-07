"""Section 4 — Credentialed Remote Access / Post-Exploitation Demo (RAT alt).

All mocked: no NetExec run, no target contact, no live auth. The adapter's
subprocess is replaced by canned NetExec output so parsing/redaction/projection
are tested without executing anything.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from app.agent.context import build_context
from app.agent.operation import run_operation
from app.agent.planner import generate_plan
from app.config import settings
from app.db import SessionLocal
from app.integrations.remote_access import REMOTE_OPS, RemoteAccessIntegration
from app.main import app
from app.models import AuditRecord
from app.safety import dispatcher, gateway
from app.safety.plan_schema import ExecutionParams, ExecutionPlan, ModuleId, PlanSource
from app.safety.registry import ExecState, registry

client = TestClient(app)

# Canned NetExec output (note: the success line echoes the password — the adapter
# must redact it before anything is stored/returned).
_NXC_OK = (
    "SMB  192.168.176.50  445  WIN-LAB  [*] Windows 10 Build 19041 x64 (name:WIN-LAB) (domain:LAB) (signing:False) (SMBv1:False)\n"
    "SMB  192.168.176.50  445  WIN-LAB  [+] LAB\\labadmin:Welcome1 (Pwn3d!)\n"
)
_NXC_FAIL = (
    "SMB  192.168.176.50  445  WIN-LAB  [*] Windows 10 Build 19041 x64 (name:WIN-LAB) (domain:LAB) (signing:False)\n"
    "SMB  192.168.176.50  445  WIN-LAB  [-] LAB\\labadmin:Welcome1 STATUS_LOGON_FAILURE\n"
)


def _fake_run(output, rc=0):
    def _run(self, cmd, timeout=30, cwd=None):
        return subprocess.CompletedProcess(cmd, rc, output, "")
    return _run


def _plan(target="192.168.176.50", operation="connectivity_check"):
    return ExecutionPlan(scenario_id="t", module=ModuleId.rat_related, source=PlanSource.manual,
                         requested_target=target, params=ExecutionParams(operation=operation))


# 1. Adapter initialization
def test_adapter_init_lists_fixed_operations():
    st = RemoteAccessIntegration().status()
    assert set(st.detail["operations"]) == set(REMOTE_OPS.keys())
    assert "connectivity_check" in st.detail["operations"]


# 2. Missing credentials
def test_missing_credentials_not_runnable():
    settings.remote_access_enabled = True
    settings.remote_access_target = "192.168.176.50"
    settings.safety_target_allowlist = "192.168.176.50"
    settings.remote_access_user = ""
    settings.remote_access_password = ""
    integ = RemoteAccessIntegration()
    assert integ.preconditions() is not None  # blocked
    with pytest.raises(RuntimeError):
        integ.run(operation="connectivity_check")


# 3. Missing dependency (nxc binary absent)
def test_missing_dependency_unavailable(monkeypatch):
    monkeypatch.setattr(RemoteAccessIntegration, "_which", staticmethod(lambda b: None))
    st = RemoteAccessIntegration().status()
    assert st.available is False
    assert "not found" in st.reason.lower()


# 4 & 5. Invalid / unauthorized target
def test_unauthorized_target_rejected(armed_remote_access):
    d = gateway.evaluate(_plan(target="10.0.0.9"))
    assert d.rejected and "allowlist" in d.reason.lower()


# 6. Invalid operation identifier (unknown but well-formed)
def test_unknown_operation_rejected_by_gateway(armed_remote_access):
    d = gateway.evaluate(_plan(operation="delete_everything"))
    assert d.rejected and "allowlist" in d.reason.lower()


# 7 & 8. Invalid params / command injection attempts (schema blocks metachars)
@pytest.mark.parametrize("bad", ["whoami; rm -rf /", "a && b", "x|y", "$(id)", "a b", "UPPER", "../x"])
def test_command_injection_operation_rejected_by_schema(bad):
    with pytest.raises(ValidationError):
        ExecutionParams(operation=bad)


# 9. Credential masking — password never in result even though nxc echoed it
def test_password_never_in_result(armed_remote_access, monkeypatch):
    monkeypatch.setattr(RemoteAccessIntegration, "_run", _fake_run(_NXC_OK))
    result = RemoteAccessIntegration().run(operation="whoami")
    assert "Welcome1" not in json.dumps(result)
    assert result["status"] == "success"
    assert result["measured"]["authenticated_as"] == "LAB\\labadmin"


# 10. Schema validation — valid plan builds
def test_valid_remote_access_plan_builds(armed_remote_access):
    p = _plan(operation="system_info")
    assert p.module is ModuleId.rat_related
    assert p.params.operation == "system_info"


# 11. Gateway approval
def test_gateway_approves_armed_valid_operation(armed_remote_access):
    d = gateway.evaluate(_plan(operation="hostname"))
    assert d.approved
    assert d.adapter == "remote_access"
    assert d.validated_parameters["operation"] == "hostname"
    assert d.validated_parameters["run_seconds"] <= settings.remote_access_max_run_seconds


# 12. Gateway rejection when disabled
def test_gateway_rejects_when_disabled():
    d = gateway.evaluate(_plan())
    assert d.rejected and "disabled" in d.reason.lower()


# 13. Kill-switch rejection
def test_killswitch_rejects_remote_access(armed_remote_access):
    gateway.kill_switch.engage("test")
    d = gateway.evaluate(_plan())
    assert d.rejected and "kill switch" in d.reason.lower()


# 14. Execution registry lifecycle (approved → run via mock adapter → COMPLETED)
def test_registry_lifecycle_completed(armed_remote_access):
    d = gateway.evaluate(_plan(operation="connectivity_check"))
    assert d.approved
    out = dispatcher.run_execution(d.execution_id, adapters={
        "remote_access": lambda p: {"operation": p["operation"], "target": "192.168.176.50",
                                    "protocol": "smb", "status": "success", "measured": {}, "exit_code": 0}})
    assert out["state"] == ExecState.COMPLETED.value
    assert registry.get(d.execution_id).state is ExecState.COMPLETED


# 15. Timeout handling
def test_timeout_maps_to_timed_out(armed_remote_access):
    d = gateway.evaluate(_plan())
    def boom(p):
        raise subprocess.TimeoutExpired(["nxc"], 30)
    out = dispatcher.run_execution(d.execution_id, adapters={"remote_access": boom})
    assert out["state"] == ExecState.TIMED_OUT.value


# 16. Adapter failure handling
def test_adapter_failure_recorded(armed_remote_access):
    d = gateway.evaluate(_plan())
    def boom(p):
        raise ValueError("nxc exploded")
    out = dispatcher.run_execution(d.execution_id, adapters={"remote_access": boom})
    assert out["state"] == ExecState.FAILED.value
    assert "nxc exploded" in (registry.get(d.execution_id).error or "")


# 17. Secret-free audit logging
def test_audit_has_no_secret(armed_remote_access):
    d = gateway.evaluate(_plan(operation="whoami"))
    dispatcher.run_execution(d.execution_id, adapters={
        "remote_access": lambda p: {"operation": "whoami", "status": "success",
                                    "measured": {"authenticated_as": "LAB\\labadmin"}, "exit_code": 0}})
    db = SessionLocal()
    try:
        recs = db.query(AuditRecord).filter(AuditRecord.execution_id == d.execution_id).all()
        blob = json.dumps([r.payload for r in recs])
    finally:
        db.close()
    assert "Welcome1" not in blob


# 18. Centralized planner integration
def test_planner_selects_remote_access_operation(armed_remote_access):
    payload = json.dumps({"module": "rat_related", "params": {"operation": "system_info"},
                          "reasoning": "verify remote mgmt"})
    ctx = build_context("confirm remote access", scenario_id="t", module_hint="rat_related")
    res = generate_plan(ctx, llm=lambda s, u: (payload, "mock", []))
    assert res.status == "ai"
    assert res.plan.module is ModuleId.rat_related
    assert res.plan.params.operation == "system_info"
    assert res.plan.requested_target == armed_remote_access  # bound, not AI-chosen


def test_planner_invalid_operation_defaults_to_safe(armed_remote_access):
    payload = json.dumps({"module": "rat_related", "params": {"operation": "rm_rf"}, "reasoning": "x"})
    ctx = build_context("x", scenario_id="t", module_hint="rat_related")
    res = generate_plan(ctx, llm=lambda s, u: (payload, "mock", []))
    # Invalid op is dropped; planner falls back to the first approved op.
    assert res.plan.params.operation in REMOTE_OPS


# 19. Analysis of actual structured results
def test_analysis_separates_facts_and_objective(armed_remote_access):
    from app.agent.analysis import analyze
    from app.safety.registry import ExecutionRecord
    rec = ExecutionRecord(scenario_id="t", module="rat_related", adapter="remote_access",
                          target="192.168.176.50", source="manual")
    rec.state = ExecState.COMPLETED
    result = {"operation": "whoami", "status": "success",
              "measured": {"authenticated_as": "LAB\\labadmin"}}
    ctx = build_context("x", scenario_id="t")
    a = analyze(rec, result, ctx, llm=lambda s, u: (None, None, []))
    assert a.objective_met is True
    assert any("whoami" in f for f in a.measured_facts)


# 20. Feedback-loop integration (full mocked loop)
def test_full_loop_remote_access(armed_remote_access):
    def smart_llm(s, u):
        if "planning brain" in s:
            return (json.dumps({"module": "rat_related", "params": {"operation": "connectivity_check"},
                                "reasoning": "r"}), "mock", [])
        if "ONE word only" in s:
            return ("STOP", "mock", [])
        return ("Interpretation.", "mock", [])
    adapter = lambda p: {"operation": p["operation"], "target": "192.168.176.50", "protocol": "smb",
                         "status": "success", "measured": {"authenticated": True}, "exit_code": 0}
    op = run_operation("confirm remote mgmt", module_hint="rat_related",
                       llm=smart_llm, adapters={"remote_access": adapter})
    assert op["status"] == "COMPLETED"  # auth success = objective met
    assert op["steps"][0]["gateway_decision"]["module"] == "rat_related"


# Rejected plan NEVER reaches the adapter
def test_rejected_plan_never_runs_adapter(armed_remote_access):
    gateway.kill_switch.engage("test")
    ran = {"n": 0}
    op = run_operation("x", module_hint="rat_related",
                       llm=lambda s, u: (json.dumps({"module": "rat_related",
                                                     "params": {"operation": "whoami"}, "reasoning": "r"}), "m", []),
                       adapters={"remote_access": lambda p: ran.__setitem__("n", ran["n"] + 1) or {}})
    assert ran["n"] == 0


# 21. API behavior
def test_api_disabled_returns_423():
    r = client.post("/api/integrations/remote_access/run", json={"operation": "whoami"})
    assert r.status_code == 423  # disabled -> gateway rejects, adapter never runs


def test_api_armed_runs_via_gateway(armed_remote_access, monkeypatch):
    monkeypatch.setattr(RemoteAccessIntegration, "_run", _fake_run(_NXC_OK))
    r = client.post("/api/integrations/remote_access/run", json={"operation": "system_info"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "success"
    assert body["measured"]["hostname"] == "WIN-LAB"
    assert "Welcome1" not in json.dumps(body)   # no secret leak
    assert body["execution_id"]


def test_api_rejects_injection_operation(armed_remote_access):
    r = client.post("/api/integrations/remote_access/run", json={"operation": "whoami; id"})
    assert r.status_code == 422  # schema rejects the unsafe token


# ========== MEDIUM-1 / LOW-1 remediation: secure credential file ==========

def _capturing_run(cap, output=_NXC_OK, rc=0):
    """A fake _run that records the argv + the credential file it was handed."""
    def fake(self, cmd, timeout=30, cwd=None):
        cap["cmd"] = list(cmd)
        i = cmd.index("-p")
        pwf = cmd[i + 1]
        cap["pw_file"] = pwf
        st = os.stat(pwf)
        cap["mode"] = stat.S_IMODE(st.st_mode)
        with open(pwf) as fh:
            cap["content"] = fh.read()
        return subprocess.CompletedProcess(cmd, rc, output, "")
    return fake


def test_password_never_in_argv(armed_remote_access, monkeypatch):
    cap = {}
    monkeypatch.setattr(RemoteAccessIntegration, "_run", _capturing_run(cap))
    result = RemoteAccessIntegration().run(operation="hostname")
    # The password is NOT anywhere on the argv...
    assert "Welcome1" not in " ".join(cap["cmd"])
    # ...instead `-p` points at a file path, which held the secret during the call.
    assert cap["pw_file"] == cap["cmd"][cap["cmd"].index("-p") + 1]
    assert cap["content"].strip() == "Welcome1"
    assert "Welcome1" not in json.dumps(result)


def test_credential_file_prefers_dev_shm(armed_remote_access, monkeypatch):
    cap = {}
    monkeypatch.setattr(RemoteAccessIntegration, "_run", _capturing_run(cap))
    RemoteAccessIntegration().run(operation="connectivity_check")
    # /dev/shm is RAM-backed; prefer it when available.
    if os.path.isdir("/dev/shm") and os.access("/dev/shm", os.W_OK):
        assert cap["pw_file"].startswith("/dev/shm/")


def test_credential_file_is_0600(armed_remote_access, monkeypatch):
    cap = {}
    monkeypatch.setattr(RemoteAccessIntegration, "_run", _capturing_run(cap))
    RemoteAccessIntegration().run(operation="whoami")
    assert cap["mode"] == 0o600


def test_credential_file_cleaned_up_on_success(armed_remote_access, monkeypatch):
    cap = {}
    monkeypatch.setattr(RemoteAccessIntegration, "_run", _capturing_run(cap))
    RemoteAccessIntegration().run(operation="whoami")
    assert not os.path.exists(cap["pw_file"])  # deleted after success


def test_credential_file_cleaned_up_on_timeout(armed_remote_access, monkeypatch):
    seen = {}
    def fake(self, cmd, timeout=30, cwd=None):
        seen["pw_file"] = cmd[cmd.index("-p") + 1]
        raise subprocess.TimeoutExpired(cmd, timeout, output="", stderr="")
    monkeypatch.setattr(RemoteAccessIntegration, "_run", fake)
    result = RemoteAccessIntegration().run(operation="whoami")
    assert result["timed_out"] is True
    assert not os.path.exists(seen["pw_file"])  # cleaned up on timeout


def test_credential_file_cleaned_up_on_failure(armed_remote_access, monkeypatch):
    seen = {}
    def fake(self, cmd, timeout=30, cwd=None):
        seen["pw_file"] = cmd[cmd.index("-p") + 1]
        raise OSError("boom Welcome1 boom")
    monkeypatch.setattr(RemoteAccessIntegration, "_run", fake)
    with pytest.raises(RuntimeError):
        RemoteAccessIntegration().run(operation="whoami")
    assert not os.path.exists(seen["pw_file"])  # cleaned up on failure


def test_exception_message_is_credential_redacted(armed_remote_access, monkeypatch):
    def fake(self, cmd, timeout=30, cwd=None):
        raise ValueError("auth failed for password Welcome1 at host")
    monkeypatch.setattr(RemoteAccessIntegration, "_run", fake)
    with pytest.raises(RuntimeError) as ei:
        RemoteAccessIntegration().run(operation="whoami")
    assert "Welcome1" not in str(ei.value)
    assert "«redacted»" in str(ei.value)


def test_tempfile_creation_failure_fails_closed(armed_remote_access, monkeypatch):
    import app.integrations.remote_access as ra
    monkeypatch.setattr(ra, "_write_secret_file", lambda s: (_ for _ in ()).throw(OSError("no shm Welcome1")))
    ran = {"n": 0}
    monkeypatch.setattr(RemoteAccessIntegration, "_run",
                        lambda self, cmd, timeout=30, cwd=None: ran.__setitem__("n", ran["n"] + 1))
    with pytest.raises(RuntimeError) as ei:
        RemoteAccessIntegration().run(operation="whoami")
    assert ran["n"] == 0  # nxc never invoked -> no argv fallback
    assert "Welcome1" not in str(ei.value)  # creation-error text redacted too
