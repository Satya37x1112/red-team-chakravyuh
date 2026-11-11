"""Security remediation regression tests (Network Discovery audit findings)."""
from __future__ import annotations

import pytest

from app.config import settings
from app.telemetry import collector
from app.services import discovery as disc
from app.services.discovery import (
    DiscoveryScan, ScanState, discovery_service, target_inventory, validate_discovery_scope,
)


@pytest.fixture(autouse=True)
def _det(monkeypatch):
    # Deterministic: don't depend on the live default route; use the configured subnet.
    monkeypatch.setattr(collector, "_default_route_subnet", lambda: None)
    monkeypatch.setattr(settings, "discovery_prohibited_subnets", "10.81.189.0/24")
    target_inventory._targets.clear()
    discovery_service._scans.clear()
    yield
    target_inventory._targets.clear()
    discovery_service._scans.clear()


# ---- CRIT-01: hotspot authorization bypass ----
@pytest.mark.parametrize("ip", ["10.81.189.204", "10.81.189.1", "10.81.189.254"])
def test_crit01_hotspot_rejected(ip):
    ok, reason = collector.authorize_recon_target(ip)
    assert ok is False and "prohibited" in reason.lower()

def test_crit01_other_rfc1918_still_allowed():
    ok, _ = collector.authorize_recon_target("192.168.56.10")
    assert ok is True

def test_crit01_no_socket_probe_after_rejection(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(collector, "run_probe", lambda t: called.__setitem__("n", called["n"] + 1))
    t = collector.probe_on_demand("10.81.189.204")
    assert called["n"] == 0  # no probe after rejection
    assert getattr(t, "available", True) is False

def test_crit01_manual_select_hotspot_rejected():
    ok, reason, rec = target_inventory.select("10.81.189.204")
    assert ok is False
    assert rec["authorization_status"] == "unauthorized" and rec["selected"] is False


# ---- HIGH-01: authorization clobbering ----
def test_high01_rediscovery_preserves_authorized():
    target_inventory.select("192.168.56.20")  # authorizes it
    assert target_inventory.get("192.168.56.20")["authorization_status"] == "authorized"
    # passive rediscovery with default pending status
    target_inventory.upsert("192.168.56.20", reachability_status="reachable")
    rec = target_inventory.get("192.168.56.20")
    assert rec["authorization_status"] == "authorized"  # not downgraded


# ---- MED-02: empty allowlist denies lab sweep ----
def test_med02_empty_allowlist_denies(monkeypatch):
    monkeypatch.setattr(settings, "discovery_authorized_subnets", "")
    ok, reason = validate_discovery_scope("lab_subnet", "192.168.56.0/24", enable_lab_subnet=True)
    assert ok is False and "no authorized lab subnets" in reason.lower()

def test_med02_allowlisted_subnet_permitted(monkeypatch):
    monkeypatch.setattr(settings, "discovery_authorized_subnets", "192.168.56.0/24")
    ok, _ = validate_discovery_scope("lab_subnet", "192.168.56.0/24", enable_lab_subnet=True)
    assert ok is True

def test_med02_non_allowlisted_subnet_denied(monkeypatch):
    monkeypatch.setattr(settings, "discovery_authorized_subnets", "192.168.56.0/24")
    ok, _ = validate_discovery_scope("lab_subnet", "192.168.99.0/24", enable_lab_subnet=True)
    assert ok is False


# ---- MED-01: cancellation-before-RUNNING race ----
def test_med01_cancelled_scan_not_set_running():
    scan = DiscoveryScan(scan_id="x", mode="tailnet", subnet=None, max_hosts=4, timeout=0.1)
    scan.state = ScanState.CANCELLED
    discovery_service._run_scan_thread(scan)  # must NOT flip to RUNNING
    assert scan.state == ScanState.CANCELLED


# ---- HIGH-02: concurrency limit ----
def test_high02_concurrency_limit(monkeypatch):
    monkeypatch.setattr(settings, "discovery_max_concurrent_scans", 1)
    # pre-fill one active scan
    s1 = DiscoveryScan(scan_id="a", mode="tailnet", subnet=None, max_hosts=4, timeout=0.1)
    s1.state = ScanState.RUNNING
    discovery_service._scans["a"] = s1
    ok, reason, _ = discovery_service.start_scan(mode="tailnet")
    assert ok is False and "concurrency" in reason.lower()


# ---- LOW-01: tailnet peer enumeration maps fields and never auto-authorizes ----
def test_low01_tailnet_peer_mapping_no_implicit_auth(monkeypatch):
    import json, subprocess
    fake = {
        "Self": {"HostName": "kali", "TailscaleIPs": ["100.80.154.42"], "OS": "linux", "Online": True},
        "Peer": {
            "k1": {"HostName": "opensoc-windows.", "TailscaleIPs": ["100.80.167.51"],
                   "OS": "windows", "Online": True},
        },
    }
    class R:
        returncode = 0
        stdout = json.dumps(fake)
    monkeypatch.setattr(disc.subprocess, "run", lambda *a, **k: R())
    out = disc.enumerate_tailnet_peers()
    peers = out.get("peers", [])
    assert len(peers) == 1
    p = peers[0]
    assert p["hostname"] == "opensoc-windows" and "100.80.167.51" in str(p.get("ip") or p.get("tailscale_ip") or p)
    assert p["os"] == "windows" and p["online"] is True
    assert p["authorization_status"] == "pending"  # discovered != authorized


# ---- Stage9: stale selection must be cleared when target is not authorized ----
def test_stage9_stale_selection_cleared_when_unauthorized():
    # simulate a target that is selected but only pending (stale)
    target_inventory._targets["100.80.167.51"] = {
        "ip": "100.80.167.51", "authorization_status": "pending", "selected": True,
    }
    target_inventory.upsert("100.80.167.51", reachability_status="reachable")
    rec = target_inventory.get("100.80.167.51")
    assert rec["authorization_status"] == "pending"
    assert rec["selected"] is False  # stale selection cleared

def test_stage9_authorized_selection_preserved_on_rediscovery():
    target_inventory.select("192.168.56.30")  # authorize + select
    before = target_inventory.get("192.168.56.30")
    assert before["authorization_status"] == "authorized" and before["selected"] is True
    target_inventory.upsert("192.168.56.30", reachability_status="reachable")  # passive rediscovery
    after = target_inventory.get("192.168.56.30")
    assert after["authorization_status"] == "authorized" and after["selected"] is True

def test_stage9_online_status_carried_into_inventory():
    target_inventory.upsert("192.168.56.40", online=True, last_seen="2026-11-11T00:00:00Z")
    rec = target_inventory.get("192.168.56.40")
    assert rec["online"] is True and rec["last_seen"] == "2026-11-11T00:00:00Z"


# ---- HIGH-02 TOCTOU: slot reserved atomically (count + insert under one lock) ----
def test_high02_slot_reserved_synchronously(monkeypatch):
    monkeypatch.setattr(settings, "discovery_max_concurrent_scans", 1)
    monkeypatch.setattr(discovery_service, "_run_scan_thread", lambda scan: None)  # no-op worker
    ok1, _, data = discovery_service.start_scan(mode="tailnet")
    assert ok1 is True
    assert data["scan_id"] in discovery_service._scans  # reserved immediately
    ok2, reason2, _ = discovery_service.start_scan(mode="tailnet")  # over limit
    assert ok2 is False and "concurrency" in reason2.lower()

def test_high02_concurrent_requests_do_not_overshoot(monkeypatch):
    import threading
    monkeypatch.setattr(settings, "discovery_max_concurrent_scans", 2)
    hold = threading.Event()
    monkeypatch.setattr(discovery_service, "_run_scan_thread", lambda scan: hold.wait(2))  # hold the slot
    results = []
    barrier = threading.Barrier(8)
    def worker():
        barrier.wait()
        ok, _, _ = discovery_service.start_scan(mode="tailnet")
        results.append(ok)
    ts = [threading.Thread(target=worker) for _ in range(8)]
    for t in ts: t.start()
    for t in ts: t.join()
    hold.set()
    assert sum(1 for r in results if r) == 2  # never more than the limit
