"""Stage 2 regression: the on-demand recon routes must honour the global kill
switch (no new network-touching activity while the range is halted) and fail
closed on an unauthorized (public) target. These routes do not run attack
adapters, but they DO generate outbound traffic, so the kill switch must gate
them exactly like the gateway-backed execution routes."""
from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app
from app.safety.killswitch import kill_switch

client = TestClient(app)


def test_probe_rejected_when_kill_switch_engaged():
    kill_switch.engage("test")
    r = client.post("/api/telemetry/probe", json={"target": "10.9.9.9"})
    assert r.status_code == 423
    assert "kill switch" in r.json()["detail"].lower()


def test_soc_activity_rejected_when_kill_switch_engaged():
    kill_switch.engage("test")
    r = client.post("/api/attacks/soc-activity", json={"kind": "ddos", "target": "10.9.9.9"})
    assert r.status_code == 423
    assert "kill switch" in r.json()["detail"].lower()


def test_soc_activity_refuses_public_ip():
    # Not halted: authorization must still fail closed for a public IP.
    r = client.post("/api/attacks/soc-activity", json={"kind": "ddos", "target": "8.8.8.8"})
    assert r.status_code == 423
    assert "public" in r.json()["detail"].lower() or "not authorized" in r.json()["detail"].lower()


def test_probe_refuses_public_ip():
    r = client.post("/api/telemetry/probe", json={"target": "8.8.8.8"})
    # Probe returns 200 with available=False + a refusal note (honest, non-throwing).
    assert r.status_code == 200
    body = r.json()
    assert body.get("available") is False
    assert "refused" in (body.get("soc_note") or "").lower()
