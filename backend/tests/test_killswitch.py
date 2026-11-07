"""Unified kill switch: real managed-process termination and safety."""
from __future__ import annotations

import os
import subprocess
import threading
import time

import pytest

from app.safety import dispatcher, gateway, process
from app.safety.killswitch import kill_switch
from app.safety.plan_schema import ExecutionParams, ExecutionPlan, ModuleId
from app.safety.registry import ExecState, registry


def _plan(target):
    return ExecutionPlan(
        scenario_id="k", module=ModuleId.bruteforce, requested_target=target,
        params=ExecutionParams(tasks=1, run_seconds=30),
    )


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, OSError):
        return False


def _sleep_adapter(params: dict) -> dict:
    # A harmless stand-in for a real tool: a long-lived managed subprocess, so
    # the kill switch has something real to terminate. NOT an attack tool.
    proc = process.run_managed(["python3", "-c", "import time; time.sleep(30)"], timeout=60)
    return {"exit_code": proc.returncode}


def test_new_executions_rejected_after_activation(armed_bruteforce):
    kill_switch.engage("test")
    d = gateway.evaluate(_plan(armed_bruteforce))
    assert d.rejected and "kill switch" in d.reason.lower()


def test_active_execution_cancelled_and_process_terminated(armed_bruteforce):
    d = gateway.evaluate(_plan(armed_bruteforce))
    assert d.approved
    eid = d.execution_id

    t = threading.Thread(target=dispatcher.run_execution, args=(eid,),
                         kwargs={"adapters": {"hydra": _sleep_adapter}})
    t.start()

    # Wait until the managed subprocess is tracked for this execution.
    pid = None
    for _ in range(100):
        procs = [p for p in process.active_processes() if p["execution_id"] == eid]
        if procs:
            pid = procs[0]["pid"]
            break
        time.sleep(0.05)
    assert pid is not None, "managed subprocess was never tracked"
    assert _pid_alive(pid)

    report = kill_switch.engage("test cancel")
    t.join(timeout=10)
    assert not t.is_alive()

    assert not _pid_alive(pid), "subprocess should be dead after kill switch"
    assert registry.get(eid).state is ExecState.CANCELLED
    assert any(o["pid"] == pid for o in report.processes_terminated)
    assert process.active_processes() == [] or all(
        p["execution_id"] != eid for p in process.active_processes()
    )


def test_repeated_activation_is_safe(armed_bruteforce):
    r1 = kill_switch.engage("one")
    r2 = kill_switch.engage("two")
    assert r1.engaged and r2.engaged
    assert kill_switch.is_engaged()


def test_reset_requires_authorization(armed_bruteforce):
    from app.config import settings

    kill_switch.engage("test")
    # No token configured -> refused.
    settings.safety_admin_token = ""
    ok, msg = kill_switch.reset(None)
    assert not ok and "not configured" in msg.lower()

    settings.safety_admin_token = "s3cr3t-admin"
    ok, msg = kill_switch.reset("wrong")
    assert not ok and "invalid" in msg.lower()

    ok, msg = kill_switch.reset("s3cr3t-admin")
    assert ok
    assert not kill_switch.is_engaged()


def test_cancellation_failure_is_recorded(armed_bruteforce, monkeypatch):
    d = gateway.evaluate(_plan(armed_bruteforce))
    registry.transition(d.execution_id, ExecState.RUNNING)

    fake = process.TerminationOutcome(pid=1234, execution_id=d.execution_id, cmd="x",
                                     stopped=False, method="error", detail="stuck")
    monkeypatch.setattr(dispatcher.process, "terminate_execution", lambda eid, **k: [fake])
    out = dispatcher.cancel_execution(d.execution_id)
    assert out["all_stopped"] is False
    assert registry.get(d.execution_id).state is ExecState.FAILED


def test_unrelated_process_not_terminated(armed_bruteforce):
    # A process the app did NOT launch through run_managed must survive.
    unrelated = subprocess.Popen(["sleep", "10"])
    try:
        time.sleep(0.2)
        kill_switch.engage("test")
        time.sleep(0.2)
        assert unrelated.poll() is None, "kill switch must not touch unrelated processes"
    finally:
        unrelated.terminate()
        try:
            unrelated.wait(timeout=5)
        except Exception:
            unrelated.kill()
