"""Comprehensive tests for Network Discovery & Target Selection service and APIs."""
import ipaddress
import socket
import unittest.mock as mock
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.safety.killswitch import kill_switch
from app.safety.registry import ExecState, registry
from app.services.discovery import (
    DISALLOWED_SUBNETS,
    DiscoveryScan,
    DiscoveryService,
    ScanState,
    discovery_service,
    enumerate_interfaces,
    enumerate_subnets,
    enumerate_tailnet_peers,
    target_inventory,
    validate_discovery_scope,
)


@pytest.fixture(autouse=True)
def reset_killswitch_state():
    """Ensure the kill switch is disarmed and reset before and after each test."""
    kill_switch.reset("admin_token_change_me_in_production")
    yield
    kill_switch.reset("admin_token_change_me_in_production")


# -----------------------------------------------------------------------------
# 1. Interface & Subnet Enumeration Tests
# -----------------------------------------------------------------------------

def test_enumerate_interfaces_and_subnets():
    interfaces = enumerate_interfaces()
    assert isinstance(interfaces, list)
    assert len(interfaces) > 0

    # Ensure key fields exist on each interface
    for iface in interfaces:
        assert "interface" in iface
        assert "ip" in iface
        assert "cidr" in iface
        assert "category" in iface
        assert "authorized_for_discovery" in iface
        assert "rejection_reason" in iface

    subnets = enumerate_subnets()
    assert isinstance(subnets, list)
    assert len(subnets) > 0
    for sub in subnets:
        assert "subnet" in sub
        assert "category" in sub
        assert "authorized_for_discovery" in sub


def test_hotspot_interface_is_disallowed():
    """Verify that any interface on 10.81.189.0/24 is categorized as hotspot_disallowed and unauthorized."""
    interfaces = enumerate_interfaces()
    for iface in interfaces:
        if "10.81.189." in iface["ip"]:
            assert iface["category"] == "hotspot_disallowed"
            assert iface["authorized_for_discovery"] is False
            assert "strictly disallowed" in iface["rejection_reason"]


# -----------------------------------------------------------------------------
# 2. Tailnet Peer Enumeration Tests
# -----------------------------------------------------------------------------

def test_enumerate_tailnet_peers_mocked():
    mock_json = """{
        "Self": {
            "HostName": "kali",
            "DNSName": "kali.tailnet.ts.net.",
            "TailscaleIPs": ["100.80.154.42"],
            "OS": "linux",
            "Online": true
        },
        "Peer": {
            "node1": {
                "HostName": "CyberKabbali",
                "DNSName": "cyberkabbali.tailnet.ts.net.",
                "TailscaleIPs": ["100.84.184.33"],
                "OS": "windows",
                "Online": true,
                "LastSeen": "2026-11-11T09:00:00Z"
            },
            "node2": {
                "HostName": "OpenSOC-Windows",
                "DNSName": "opensoc.tailnet.ts.net.",
                "TailscaleIPs": ["100.80.167.51"],
                "OS": "windows",
                "Online": false,
                "LastSeen": "2026-11-10T22:00:00Z"
            }
        }
    }"""

    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0, stdout=mock_json)
        res = enumerate_tailnet_peers()
        assert res["available"] is True
        assert res["self"]["hostname"] == "kali"
        assert res["self"]["tailscale_ip"] == "100.80.154.42"
        assert res["total_peers"] == 2
        
        peer_ips = [p["ip"] for p in res["peers"]]
        assert "100.84.184.33" in peer_ips
        assert "100.80.167.51" in peer_ips

        kabbali = next(p for p in res["peers"] if p["ip"] == "100.84.184.33")
        assert kabbali["reachability_status"] == "reachable"
        assert kabbali["os"] == "windows"

        opensoc = next(p for p in res["peers"] if p["ip"] == "100.80.167.51")
        assert opensoc["reachability_status"] == "unreachable"


def test_enumerate_tailnet_peers_fallback():
    mock_table = """
100.84.184.33   CyberKabbali    windows -
100.80.167.51   OpenSOC-Windows windows offline
"""
    with mock.patch("subprocess.run") as mock_run:
        # First call (json) fails, second call (text) succeeds
        mock_run.side_effect = [
            mock.Mock(returncode=1, stdout=""),
            mock.Mock(returncode=0, stdout=mock_table),
        ]
        res = enumerate_tailnet_peers()
        assert res["available"] is True
        assert res["total_peers"] == 2
        peer_ips = [p["ip"] for p in res["peers"]]
        assert "100.84.184.33" in peer_ips
        assert "100.80.167.51" in peer_ips


# -----------------------------------------------------------------------------
# 3. Scope Policy Validation Tests
# -----------------------------------------------------------------------------

def test_validate_scope_tailnet():
    ok, err = validate_discovery_scope("tailnet")
    assert ok is True
    assert err == ""


def test_validate_scope_hotspot_rejected():
    """Hotspot 10.81.189.0/24 and overlapping subnets must fail closed."""
    ok, err = validate_discovery_scope("lab_subnet", "10.81.189.0/24", enable_lab_subnet=True)
    assert ok is False
    assert "shared hotspot" in err.lower()

    ok, err = validate_discovery_scope("lab_subnet", "10.81.189.128/25", enable_lab_subnet=True)
    assert ok is False
    assert "shared hotspot" in err.lower()


def test_validate_scope_public_ip_rejected():
    """Public subnets (e.g. 8.8.8.0/24) must be rejected."""
    ok, err = validate_discovery_scope("lab_subnet", "8.8.8.0/24", enable_lab_subnet=True)
    assert ok is False
    assert "public" in err.lower()


def test_validate_scope_loopback_rejected():
    """Loopback (127.0.0.0/8) must be rejected."""
    ok, err = validate_discovery_scope("lab_subnet", "127.0.0.0/8", enable_lab_subnet=True)
    assert ok is False
    assert "loopback" in err.lower()


def test_validate_scope_oversized_subnet_rejected():
    """Subnets broader than /24 (e.g. /16) must be rejected to prevent excessive network sweeps."""
    ok, err = validate_discovery_scope("lab_subnet", "192.168.0.0/16", enable_lab_subnet=True)
    assert ok is False
    assert "too large" in err.lower()


def test_validate_scope_lab_subnet_disabled_by_default():
    """Without explicit checkbox (enable_lab_subnet=True), lab subnet discovery is refused."""
    ok, err = validate_discovery_scope("lab_subnet", "192.168.100.0/24", enable_lab_subnet=False)
    assert ok is False
    assert "disabled by default" in err.lower()


def test_validate_scope_authorized_lab_subnet_allowed():
    """Authorized lab subnet with explicit enablement must pass."""
    ok, err = validate_discovery_scope("lab_subnet", "192.168.100.0/24", enable_lab_subnet=True)
    assert ok is True
    assert err == ""


# -----------------------------------------------------------------------------
# 4. Target Inventory & Authorization (Discovered != Authorized)
# -----------------------------------------------------------------------------

def test_target_selection_unauthorized_target():
    """Selecting an invalid target (e.g. public IP or non-peer) must be rejected."""
    # Reset target
    ok, reason, target = target_inventory.select("8.8.8.8")
    assert ok is False
    assert "public" in reason.lower()
    assert target["authorization_status"] == "unauthorized"
    assert target["selected"] is False


def test_target_selection_authorized_target():
    """Selecting an RFC1918 lab target must succeed and authorize."""
    ok, reason, target = target_inventory.select("192.168.100.50", hostname="lab-workstation")
    assert ok is True
    assert target["authorization_status"] == "authorized"
    assert target["selected"] is True
    assert target["hostname"] == "lab-workstation"


# -----------------------------------------------------------------------------
# 5. Discovery Service Lifecycle & Kill Switch Tests
# -----------------------------------------------------------------------------

def test_discovery_scan_tailnet_mocked():
    mock_json = """{
        "Self": {"HostName": "kali", "TailscaleIPs": ["100.80.154.42"]},
        "Peer": {
            "node1": {
                "HostName": "CyberKabbali",
                "TailscaleIPs": ["100.84.184.33"],
                "OS": "windows",
                "Online": true
            }
        }
    }"""
    with mock.patch("subprocess.run") as mock_sub, mock.patch("socket.socket") as mock_sock:
        mock_sub.return_value = mock.Mock(returncode=0, stdout=mock_json)
        # Mock port 445 open, others closed
        instance = mock_sock.return_value
        def fake_connect_ex(addr):
            if addr[1] == 445:
                return 0
            return 111
        instance.connect_ex.side_effect = fake_connect_ex

        ok, msg, scan_data = discovery_service.start_scan(mode="tailnet")
        assert ok is True
        scan_id = scan_data["scan_id"]

        # Wait briefly for thread to finish
        scan = discovery_service.get_scan(scan_id)
        if scan and scan._thread:
            scan._thread.join(timeout=2.0)

        assert scan.state == ScanState.COMPLETED
        assert len(scan.found_hosts) == 1
        h = scan.found_hosts[0]
        assert h["ip"] == "100.84.184.33"
        assert 445 in h["detected_ports"]
        assert h["authorization_status"] == "pending"  # Discovered != Authorized!


def test_discovery_kill_switch_stops_scan():
    """Engaging the kill switch must halt the discovery scan immediately."""
    kill_switch.engage(reason="Test Emergency Halt")

    ok, reason, _ = discovery_service.start_scan(mode="tailnet")
    assert ok is False
    assert "kill switch is engaged" in reason.lower()


def test_discovery_cancel_scan():
    """Cancelling a scan transitions its state to CANCELLED."""
    import time
    with mock.patch.object(DiscoveryService, "_execute_tailnet_discovery", side_effect=lambda scan: time.sleep(0.5)):
        ok, msg, scan_data = discovery_service.start_scan(mode="tailnet")
        assert ok is True
        scan_id = scan_data["scan_id"]

        ok_cancel, cancel_msg = discovery_service.cancel_scan(scan_id)
        assert ok_cancel is True
        assert "cancelled" in cancel_msg.lower()

        scan = discovery_service.get_scan(scan_id)
        assert scan.state == ScanState.CANCELLED


# -----------------------------------------------------------------------------
# 6. REST API Endpoints Tests
# -----------------------------------------------------------------------------

client = TestClient(app)


def test_api_network_interfaces():
    res = client.get("/api/network/interfaces")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_api_network_subnets():
    res = client.get("/api/network/subnets")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)


def test_api_network_tailnet():
    with mock.patch("subprocess.run") as mock_sub:
        mock_sub.return_value = mock.Mock(returncode=0, stdout='{"Self":{"HostName":"test"}, "Peer":{}}')
        res = client.get("/api/network/tailnet")
        assert res.status_code == 200
        data = res.json()
        assert data["available"] is True


def test_api_discovery_start_rejects_hotspot():
    res = client.post("/api/network/discovery/start", json={
        "mode": "lab_subnet",
        "subnet": "10.81.189.0/24",
        "enable_lab_subnet": True,
    })
    assert res.status_code == 400
    assert "shared hotspot" in res.json()["detail"].lower()


def test_api_discovery_start_rejects_public_ip():
    res = client.post("/api/network/discovery/start", json={
        "mode": "lab_subnet",
        "subnet": "1.1.1.0/24",
        "enable_lab_subnet": True,
    })
    assert res.status_code == 400
    assert "public" in res.json()["detail"].lower()


def test_api_target_select_success_and_failure():
    # 1. Failure on public IP
    res_bad = client.post("/api/network/targets/select", json={"ip": "8.8.4.4"})
    assert res_bad.status_code == 400
    assert "rejected" in res_bad.json()["detail"].lower()

    # 2. Success on RFC1918
    res_ok = client.post("/api/network/targets/select", json={"ip": "192.168.1.150", "hostname": "lab-pc"})
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["status"] == "authorized"
    assert data["target"]["selected"] is True
    assert data["target"]["ip"] == "192.168.1.150"


def test_api_get_targets():
    res = client.get("/api/network/targets")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
