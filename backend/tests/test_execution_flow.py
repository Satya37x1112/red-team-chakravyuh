"""End-to-end controlled-execution flow with MOCK adapters (no real tools)."""
from __future__ import annotations

import json

from starlette.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import AuditRecord
from app.safety import dispatcher, gateway
from app.safety.plan_schema import ExecutionParams, ExecutionPlan, ModuleId
from app.safety.registry import ExecState, registry

# Non-context TestClient: we don't start the background telemetry lifespan (its
# singleton asyncio primitives don't survive repeated per-test event loops). The
# routers are mounted at app construction, so HTTP routing works without it.
client = TestClient(app)


def _bf_plan(target):
    return ExecutionPlan(
        scenario_id="e", module=ModuleId.bruteforce, requested_target=target,
        params=ExecutionParams(tasks=20, run_seconds=99),  # within sanity; clamped to caps
    )


def test_approved_reaches_correct_adapter(armed_bruteforce):
    seen = {}

    def mock(params):
        seen["params"] = params
        return {"exit_code": 0}

    d = gateway.evaluate(_bf_plan(armed_bruteforce))
    assert d.approved
    out = dispatcher.run_execution(d.execution_id, adapters={"hydra": mock, "locust": mock})
    assert out["state"] == ExecState.COMPLETED.value
    # Clamped DOWN to configured caps before reaching the adapter.
    assert seen["params"]["tasks"] == 4
    assert seen["params"]["run_seconds"] == 30


def test_adapter_error_recorded(armed_bruteforce):
    def boom(params):
        raise ValueError("adapter blew up")

    d = gateway.evaluate(_bf_plan(armed_bruteforce))
    out = dispatcher.run_execution(d.execution_id, adapters={"hydra": boom})
    assert out["state"] == ExecState.FAILED.value
    rec = registry.get(d.execution_id)
    assert rec.state is ExecState.FAILED
    assert "adapter blew up" in (rec.error or "")


def test_secrets_never_leak_to_result_or_audit(armed_bruteforce):
    def leaky(params):
        return {
            "exit_code": 0,
            "password": "hunter2",
            "mock_passwords": ["Welcome1", "hunter2"],
            "found": [{"login": "labadmin", "password_found": True}],
        }

    d = gateway.evaluate(_bf_plan(armed_bruteforce))
    out = dispatcher.run_execution(d.execution_id, adapters={"hydra": leaky})
    blob = json.dumps(out)
    assert "hunter2" not in blob, "secret leaked into execution result"

    db = SessionLocal()
    try:
        recs = db.query(AuditRecord).filter(AuditRecord.execution_id == d.execution_id).all()
        audit_blob = json.dumps([r.payload for r in recs])
    finally:
        db.close()
    assert "hunter2" not in audit_blob, "secret leaked into audit log"


# ---- endpoint-level: Hydra/Locust now pass THROUGH the Gateway --------------

def test_hydra_endpoint_rejects_when_disabled():
    r = client.post("/api/integrations/hydra/run", json={})
    assert r.status_code == 423  # gateway rejection (module disabled), no adapter run


def test_hydra_endpoint_uses_gateway(armed_bruteforce, monkeypatch):
    calls = {"n": 0}

    def mock(params):
        calls["n"] += 1
        return {"exit_code": 0, "params": {"target": armed_bruteforce, "service": "ssh"},
                "found": [], "message": "no valid pairs", "attempts_made": 0, "attempt_feed": []}

    monkeypatch.setattr(dispatcher, "default_adapters", lambda: {"hydra": mock, "locust": mock})
    r = client.post("/api/integrations/hydra/run", json={"tasks": 2, "run_seconds": 5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("execution_id")
    assert body.get("execution_state") == ExecState.COMPLETED.value
    assert calls["n"] == 1  # the mock adapter ran via the controlled path


def test_locust_endpoint_uses_gateway(armed_ddos, monkeypatch):
    calls = {"n": 0}

    def mock(params):
        calls["n"] += 1
        return {"exit_code": 0, "params": {"users": params.get("users"), "run_seconds": params.get("run_seconds"),
                "target": armed_ddos}, "stats": []}

    monkeypatch.setattr(dispatcher, "default_adapters", lambda: {"hydra": mock, "locust": mock})
    r = client.post("/api/integrations/locust/run", json={"users": 5, "run_seconds": 5})
    assert r.status_code == 200, r.text
    assert r.json().get("execution_id")
    assert calls["n"] == 1


def test_submit_rejected_never_runs_adapter(monkeypatch):
    ran = {"n": 0}

    def tripwire():
        def adapter(params):
            ran["n"] += 1
            return {}
        return {"hydra": adapter, "locust": adapter}

    monkeypatch.setattr(dispatcher, "default_adapters", tripwire)
    # bruteforce disabled by default -> gateway rejects at submit.
    r = client.post("/api/execution/submit", json={
        "scenario_id": "s", "module": "bruteforce", "requested_target": "10.0.0.1",
    })
    assert r.status_code == 423
    assert ran["n"] == 0  # adapter must never be reached


def test_execution_status_and_listing(armed_bruteforce):
    d = gateway.evaluate(_bf_plan(armed_bruteforce))
    r = client.get(f"/api/execution/{d.execution_id}")
    assert r.status_code == 200
    assert r.json()["execution_id"] == d.execution_id
    r2 = client.get("/api/execution")
    assert any(x["execution_id"] == d.execution_id for x in r2.json())
