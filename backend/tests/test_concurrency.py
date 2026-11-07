"""Concurrency safety of the Gateway, registry, and kill switch."""
from __future__ import annotations

import threading

from app.config import settings
from app.safety import gateway
from app.safety.killswitch import kill_switch
from app.safety.plan_schema import ExecutionParams, ExecutionPlan, ModuleId
from app.safety.registry import registry


def _plan(target):
    return ExecutionPlan(
        scenario_id="c", module=ModuleId.bruteforce, requested_target=target,
        params=ExecutionParams(tasks=1, run_seconds=5),
    )


def test_concurrency_limit_not_bypassed_under_race(armed_bruteforce):
    settings.safety_max_concurrent_executions = 2
    results = []
    barrier = threading.Barrier(12)

    def worker():
        barrier.wait()  # maximise contention
        results.append(gateway.evaluate(_plan(armed_bruteforce)).approved)

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    approved = sum(1 for a in results if a)
    assert approved == 2, f"expected exactly 2 approvals under the cap, got {approved}"
    assert registry.active_count() == 2


def test_killswitch_and_new_requests_are_safe(armed_bruteforce):
    settings.safety_max_concurrent_executions = 100
    errors = []
    stop = threading.Event()

    def spammer():
        while not stop.is_set():
            try:
                gateway.evaluate(_plan(armed_bruteforce))
            except Exception as exc:  # must never raise
                errors.append(exc)

    t = threading.Thread(target=spammer)
    t.start()
    try:
        kill_switch.engage("race test")
    finally:
        stop.set()
        t.join(timeout=5)

    assert not errors, f"gateway raised under concurrent kill switch: {errors[:3]}"
    # After engage, every new evaluation must be rejected.
    assert gateway.evaluate(_plan(armed_bruteforce)).rejected


def test_registry_state_consistent_under_parallel_transitions(armed_bruteforce):
    settings.safety_max_concurrent_executions = 1000
    ids = []
    for _ in range(50):
        d = gateway.evaluate(_plan(armed_bruteforce))
        if d.approved:
            ids.append(d.execution_id)

    def complete(eid):
        from app.safety.registry import ExecState
        registry.transition(eid, ExecState.RUNNING)
        registry.transition(eid, ExecState.COMPLETED)

    threads = [threading.Thread(target=complete, args=(eid,)) for eid in ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert registry.active_count() == 0
    assert len(registry.list()) == len(ids)
