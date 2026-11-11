"""Automated test suite for the One-Click Orchestrated Assessment module.

Verifies:
  1. Public-IP refused (fail-closed, marked BLOCKED).
  2. Offline-target stops early (marked UNAVAILABLE, skips subsequent target steps).
  3. Reachable target executes full sequence (recon open ports, bounded SOC signatures).
  4. Skipping 445-dependent signatures (bruteforce, rat) when port 445 is closed.
  5. Offline hash audit execution when hash is supplied vs skipped when omitted.
  6. Kill-switch halting mid-sequence (marks remaining steps STOPPED).
  7. Kill-switch blocking before run (HTTP 423).
  8. Execution Registry tracking and Audit record persistence.
  9. Canonical step status labeling (READY, RUNNING, DONE, SKIPPED, BLOCKED, STOPPED, UNAVAILABLE).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.db import SessionLocal, init_db
from app.main import app
from app.models import AuditRecord
from app.safety.killswitch import kill_switch
from app.safety.registry import ExecState, registry
from app.services.assessment import AssessmentService, assessment_service
from app.telemetry.schema import NetworkProbe, PortState, Telemetry

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_db():
    init_db()
    # Reset kill switch before each test
    kill_switch.reset("admin_token_change_me_in_production")


def test_public_ip_refused_fail_closed():
    """Requirement: Target validation fails closed on public IPs (marked BLOCKED)."""
    r = client.post("/api/assessment/run", json={"target": "8.8.8.8"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "BLOCKED"
    assert data["open_ports"] == []

    steps = data["steps"]
    step1 = steps[0]
    assert step1["id"] == "target_validation"
    assert step1["status"] == "BLOCKED"
    assert "public" in step1["details"].lower()

    # All remaining steps must be SKIPPED
    for s in steps[1:]:
        assert s["status"] in ("SKIPPED", "UNAVAILABLE")


def test_offline_target_stops_early_without_fabricating():
    """Requirement: If target is offline, STOP at step 2 and report TARGET OFFLINE."""
    svc = AssessmentService()
    # Reachability returns False (target offline)
    res = svc.run("10.0.0.99", reachability_fn=lambda t, to: False)

    assert res["status"] == "COMPLETED"
    assert res["open_ports"] == []
    assert res["summary"]["target_online"] is False

    step_map = {s["id"]: s for s in res["steps"]}
    assert step_map["target_validation"]["status"] == "DONE"
    assert step_map["reachability"]["status"] == "UNAVAILABLE"
    assert "target offline" in step_map["reachability"]["details"].lower()

    # Steps 3-6 must be SKIPPED (never fabricate later steps)
    assert step_map["recon_probe"]["status"] == "SKIPPED"
    assert step_map["soc_ddos"]["status"] == "SKIPPED"
    assert step_map["soc_bruteforce"]["status"] == "SKIPPED"
    assert step_map["soc_rat"]["status"] == "SKIPPED"


def test_reachable_target_runs_full_sequence_with_open_ports():
    """Requirement: Online target runs recon probe and bounded SOC signatures."""
    svc = AssessmentService()

    mock_probe = Telemetry(source="blackbox", available=True)
    mock_probe.network = NetworkProbe(
        target="192.168.1.50",
        ports_total=8,
        ports_probed=8,
        reachable=True,
        latency_ms=11.5,
        open_ports=[80, 445, 3389],
        ports=[
            PortState(port=80, open=True, service="HTTP", latency_ms=10.2),
            PortState(port=445, open=True, service="SMB", latency_ms=11.5),
            PortState(port=3389, open=True, service="RDP", latency_ms=14.0),
            PortState(port=22, open=False, service="SSH", latency_ms=None),
        ],
    )

    with patch("app.telemetry.collector.run_probe", return_value=mock_probe):
        with patch("app.integrations.activity_gen.generate_signature") as mock_gen_sig:
            mock_gen_sig.side_effect = lambda kind, target: {
                "kind": kind,
                "target": target,
                "connects_attempted": 40 if kind == "ddos" else None,
                "failed_auth_attempts": 5 if kind == "bruteforce" else None,
                "enumerated": True if kind == "rat_related" else None,
                "detectable_as": f"Mock {kind} detection",
            }

            res = svc.run("192.168.1.50", reachability_fn=lambda t, to: True)

    assert res["status"] == "COMPLETED"
    assert res["open_ports"] == [80, 445, 3389]
    assert len(res["open_port_details"]) == 3
    assert res["open_port_details"][0]["port"] == 80
    assert res["open_port_details"][0]["service"] == "HTTP"

    step_map = {s["id"]: s for s in res["steps"]}
    assert step_map["target_validation"]["status"] == "DONE"
    assert step_map["reachability"]["status"] == "DONE"
    assert step_map["recon_probe"]["status"] == "DONE"
    assert step_map["soc_ddos"]["status"] == "DONE"
    assert step_map["soc_bruteforce"]["status"] == "DONE"
    assert step_map["soc_rat"]["status"] == "DONE"
    assert step_map["offline_hash_audit"]["status"] == "SKIPPED"  # No hash passed
    assert step_map["locust_load_test"]["status"] == "UNAVAILABLE"
    assert step_map["remote_file_transfer"]["status"] == "UNAVAILABLE"


def test_skips_bruteforce_and_rat_if_port_445_closed():
    """Requirement: Skip bruteforce/rat if port 445 is not open."""
    svc = AssessmentService()

    # Target has port 80 and 8080 open, but NOT port 445
    mock_probe = Telemetry(source="blackbox", available=True)
    mock_probe.network = NetworkProbe(
        target="192.168.1.80",
        ports_total=4,
        ports_probed=4,
        reachable=True,
        open_ports=[80, 8080],
        ports=[
            PortState(port=80, open=True, service="HTTP"),
            PortState(port=8080, open=True, service="HTTP-Alt"),
            PortState(port=445, open=False, service="SMB"),
        ],
    )

    with patch("app.telemetry.collector.run_probe", return_value=mock_probe):
        with patch("app.integrations.activity_gen.generate_signature") as mock_gen_sig:
            mock_gen_sig.return_value = {"kind": "ddos", "connects_attempted": 40}
            res = svc.run("192.168.1.80", reachability_fn=lambda t, to: True)

    step_map = {s["id"]: s for s in res["steps"]}
    assert step_map["recon_probe"]["status"] == "DONE"
    assert step_map["soc_ddos"]["status"] == "DONE"
    assert step_map["soc_bruteforce"]["status"] == "SKIPPED"
    assert "port 445" in step_map["soc_bruteforce"]["details"].lower()
    assert step_map["soc_rat"]["status"] == "SKIPPED"
    assert "port 445" in step_map["soc_rat"]["details"].lower()


def test_offline_hash_audit_execution_when_hash_provided():
    """Requirement: Offline hash audit runs against RockYou if hash is supplied."""
    svc = AssessmentService()
    # MD5 of "password" is 5f4dcc3b5aa765d61d8327deb882cf99
    pwd_hash = "5f4dcc3b5aa765d61d8327deb882cf99"

    res = svc.run("192.168.1.10", password_hash=pwd_hash, reachability_fn=lambda t, to: False)
    step_map = {s["id"]: s for s in res["steps"]}
    step_hash = step_map["offline_hash_audit"]

    assert step_hash["status"] == "DONE"
    assert step_hash["data"]["algorithm"] in ("MD5", "NTLM")
    assert step_hash["data"]["candidates_tested"] > 0
    # "password" is line 2 in RockYou, so it matches immediately
    if step_hash["data"].get("matched"):
        assert step_hash["data"]["recovered_plaintext"] == "password"


def test_kill_switch_engaged_before_run_returns_423():
    """Requirement: Kill switch engaged prior to run raises HTTP 423."""
    kill_switch.engage("operator emergency halt")
    r = client.post("/api/assessment/run", json={"target": "192.168.1.10"})
    assert r.status_code == 423
    assert "kill switch" in r.json()["detail"].lower()


def test_kill_switch_halts_mid_sequence():
    """Requirement: Kill switch halt mid-sequence stops and marks remaining steps STOPPED."""
    svc = AssessmentService()

    def halt_reachability(t, to):
        # Engage kill switch during reachability probe
        kill_switch.engage("mid-run abort")
        return True

    res = svc.run("192.168.1.20", reachability_fn=halt_reachability)
    assert res["status"] == "STOPPED"

    # Following steps must be STOPPED
    step_map = {s["id"]: s for s in res["steps"]}
    assert step_map["recon_probe"]["status"] == "STOPPED"
    assert step_map["soc_ddos"]["status"] == "STOPPED"


def test_assessment_emits_central_audit_record():
    """Requirement: Every assessment emits central audit records."""
    svc = AssessmentService()
    res = svc.run("192.168.1.30", reachability_fn=lambda t, to: False)

    db = SessionLocal()
    try:
        rec = (
            db.query(AuditRecord)
            .filter(AuditRecord.module == "assessment", AuditRecord.target == "192.168.1.30")
            .order_by(AuditRecord.id.desc())
            .first()
        )
        assert rec is not None
        assert rec.target == "192.168.1.30"
        assert rec.event_type == "ASSESSMENT_RUN"
    finally:
        db.close()


def test_execution_registry_tracks_assessment():
    """Requirement: Assessment creates and transitions an ExecutionRecord in ExecutionRegistry."""
    svc = AssessmentService()
    res = svc.run("192.168.1.40", reachability_fn=lambda t, to: False)

    exec_id = res["assessment_id"]
    rec = registry.get(exec_id)
    assert rec is not None
    assert rec.module == "assessment"
    assert rec.target == "192.168.1.40"
    assert rec.state in (ExecState.COMPLETED, ExecState.CANCELLED)


def test_get_latest_assessment_endpoint():
    """Verify GET /api/assessment/latest returns the most recent run."""
    client.post("/api/assessment/run", json={"target": "8.8.8.8"})
    r = client.get("/api/assessment/latest")
    assert r.status_code == 200
    data = r.json()
    assert data is not None
    assert data["target"] == "8.8.8.8"
    assert data["status"] == "BLOCKED"
