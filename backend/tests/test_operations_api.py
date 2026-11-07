"""Operations API endpoints (fail-closed; no real execution)."""
from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)  # no lifespan: routers are mounted at construction


def test_plan_preview_unavailable_when_nothing_armed():
    r = client.post("/api/operations/plan", json={"objective": "crack the login"})
    assert r.status_code == 200
    body = r.json()
    assert body["planning_status"] == "unavailable"
    assert body["plan"] is None
    assert body["gateway_decision"] is None
    assert body["telemetry_scope"] in ("unavailable", "kali_host", "windows_target")


def test_plan_preview_armed_is_fallback_and_would_be_approved(armed_bruteforce):
    # No OpenRouter key in tests -> the default LLM is unavailable -> honest fallback.
    r = client.post("/api/operations/plan", json={"objective": "test", "module_hint": "bruteforce"})
    assert r.status_code == 200
    body = r.json()
    assert body["planning_status"] == "fallback"       # NOT labelled 'ai'
    assert body["plan"] is not None
    assert body["gateway_decision"]["approved"] is True
    assert body["plan"]["requested_target"] == armed_bruteforce


def test_operation_run_disabled_produces_no_execution():
    # Nothing armed -> no runnable module -> the planner honestly has no plan, so
    # nothing reaches the gateway or an adapter. This is the fail-closed outcome.
    r = client.post("/api/operations", json={"objective": "x"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("STOPPED", "FAILED")
    step = body["steps"][0]
    assert step["plan_source"] == "none"        # no runnable plan
    assert step["validation_ok"] is False
    assert step["execution_state"] is None       # never executed
    assert step["execution_id"] is None          # no execution id issued
    assert step["feedback_action"] == "STOP"


def test_list_and_get_operation():
    created = client.post("/api/operations", json={"objective": "listing test"}).json()
    op_id = created["id"]
    lst = client.get("/api/operations").json()
    assert any(o["id"] == op_id for o in lst)
    detail = client.get(f"/api/operations/{op_id}").json()
    assert detail["id"] == op_id
    assert isinstance(detail["steps"], list)


def test_get_unknown_operation_404():
    r = client.get("/api/operations/does-not-exist")
    assert r.status_code == 404
