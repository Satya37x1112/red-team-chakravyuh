"""Blackbox (agentless, IP-only) telemetry — authorization, IP validation, and
probe-budget tests. Socket operations are MOCKED: no real port discovery, no
external network, no target contact."""
from __future__ import annotations

import time

import pytest

from app.config import settings
from app.telemetry import collector as C
from app.telemetry.collector import BlackboxSource, authorize_blackbox_target, build_source


def _arm(monkeypatch, *, target="192.168.176.50", ports="80,443",
         allowlist="192.168.176.50", allow_loopback=False, http=False,
         budget=20.0, timeout=1.0):
    monkeypatch.setattr(settings, "blackbox_target", target)
    monkeypatch.setattr(settings, "blackbox_ports", ports)
    monkeypatch.setattr(settings, "blackbox_allowlist", allowlist)
    monkeypatch.setattr(settings, "blackbox_allow_loopback", allow_loopback)
    monkeypatch.setattr(settings, "blackbox_timeout_seconds", timeout)
    monkeypatch.setattr(settings, "blackbox_total_budget_seconds", budget)
    monkeypatch.setattr(settings, "blackbox_http", http)


def _mock_probe(monkeypatch, fn):
    """Replace the real TCP probe — guarantees NO socket is ever opened."""
    monkeypatch.setattr(C, "_probe_port", fn)


# ---------- authorization / IP validation ----------

def test_missing_config_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "blackbox_target", "")
    t = BlackboxSource().collect()
    assert t.available is False and "BLACKBOX_TARGET" in (t.error or "")


def test_authorized_private_ip_accepted(monkeypatch):
    _arm(monkeypatch)
    _mock_probe(monkeypatch, lambda h, p, to: (p == 80, 1.2, "open" if p == 80 else "refused"))
    t = BlackboxSource().collect()
    assert t.available is True and t.source == "blackbox"
    assert t.network.target == "192.168.176.50"
    assert 80 in t.network.open_ports


def test_unauthorized_private_ip_rejected(monkeypatch):
    # Target is a valid RFC1918 IP but NOT in the allowlist.
    _arm(monkeypatch, target="192.168.176.99", allowlist="192.168.176.50")
    called = {"n": 0}
    _mock_probe(monkeypatch, lambda h, p, to: called.__setitem__("n", called["n"] + 1))
    t = BlackboxSource().collect()
    assert t.available is False and "BLACKBOX_ALLOWLIST" in (t.error or "")
    assert called["n"] == 0  # no probe attempted


def test_public_ip_rejected(monkeypatch):
    # In the allowlist, but public -> still rejected (public check precedes allowlist).
    _arm(monkeypatch, target="8.8.8.8", allowlist="8.8.8.8")
    t = BlackboxSource().collect()
    assert t.available is False and "public" in (t.error or "").lower()


def test_hostname_rejected(monkeypatch):
    _arm(monkeypatch, target="example.com", allowlist="example.com")
    t = BlackboxSource().collect()
    assert t.available is False and "not a valid IPv4 literal" in (t.error or "")


@pytest.mark.parametrize("bad", ["999.1.1.1", "1.2.3", "192.168.1", "", "10.0.0.0/8", "::1"])
def test_malformed_ip_rejected(monkeypatch, bad):
    monkeypatch.setattr(settings, "blackbox_target", bad)
    monkeypatch.setattr(settings, "blackbox_allowlist", bad)
    t = BlackboxSource().collect()
    assert t.available is False  # either empty-config or invalid-IPv4


def test_loopback_rejected_in_production(monkeypatch):
    _arm(monkeypatch, target="127.0.0.1", allowlist="127.0.0.1", allow_loopback=False)
    t = BlackboxSource().collect()
    assert t.available is False and "loopback" in (t.error or "").lower()


def test_loopback_allowed_only_with_test_flag(monkeypatch):
    _arm(monkeypatch, target="127.0.0.1", allowlist="127.0.0.1", allow_loopback=True)
    _mock_probe(monkeypatch, lambda h, p, to: (False, 0.3, "refused"))
    t = BlackboxSource().collect()
    assert t.available is True


def test_no_socket_opened_before_authorization(monkeypatch):
    _arm(monkeypatch, target="8.8.8.8", allowlist="8.8.8.8")  # unauthorized (public)
    def tripwire(h, p, to):
        raise AssertionError("socket opened before authorization!")
    _mock_probe(monkeypatch, tripwire)
    t = BlackboxSource().collect()
    assert t.available is False  # tripwire never fired


def test_authorize_helper_direct(monkeypatch):
    monkeypatch.setattr(settings, "blackbox_allowlist", "192.168.56.20")
    monkeypatch.setattr(settings, "blackbox_allow_loopback", False)
    assert authorize_blackbox_target("192.168.56.20")[0] is True
    assert authorize_blackbox_target("192.168.56.21")[0] is False  # not allowlisted
    assert authorize_blackbox_target("1.1.1.1")[0] is False        # public
    assert authorize_blackbox_target("nope")[0] is False           # not IPv4


# ---------- probe budget / slow-port handling ----------

def test_probe_budget_enforced(monkeypatch):
    _arm(monkeypatch, ports="80,443,445,3389,5985,22", budget=0.05, timeout=1.0)

    def slow(h, p, to):
        time.sleep(0.03)  # each probe is slow; budget cuts the sweep short
        return (False, 20.0, "no-response")
    _mock_probe(monkeypatch, slow)
    t = BlackboxSource().collect()
    assert t.network.complete is False                       # budget cut the sweep short
    assert t.network.ports_probed < t.network.ports_total    # not all ports probed
    assert len(t.network.ports) == t.network.ports_probed     # only probed ports recorded


def test_incomplete_probe_not_reported_as_closed(monkeypatch):
    _arm(monkeypatch, ports="80,443,445,3389", budget=0.05)

    def slow(h, p, to):
        time.sleep(0.03)
        return (False, None, "no-response")
    _mock_probe(monkeypatch, slow)
    t = BlackboxSource().collect()
    probed_ports = {p.port for p in t.network.ports}
    unprobed = set(settings.blackbox_port_list) - probed_ports
    assert unprobed  # some ports were NOT probed...
    # ...and they are simply absent — never invented as "closed".
    assert all(p.port in probed_ports for p in t.network.ports)


def test_slow_port_does_not_block_indefinitely(monkeypatch):
    _arm(monkeypatch, ports="80,443", budget=0.05)
    _mock_probe(monkeypatch, lambda h, p, to: (time.sleep(0.03), (False, None, "no-response"))[1])
    start = time.monotonic()
    t = BlackboxSource().collect()
    assert (time.monotonic() - start) < 2.0  # returns promptly, bounded by budget
    assert t.available is True


# ---------- parsing / compatibility ----------

def test_port_list_parsing_and_cap(monkeypatch):
    monkeypatch.setattr(settings, "blackbox_ports", "80, 443 , 445, bad, 99999, 22")
    assert settings.blackbox_port_list == [80, 443, 445, 22]
    monkeypatch.setattr(settings, "blackbox_ports", ",".join(str(p) for p in range(1, 200)))
    assert len(settings.blackbox_port_list) == 64


def test_build_source_selects_blackbox(monkeypatch):
    monkeypatch.setattr(settings, "telemetry_source", "blackbox")
    assert isinstance(build_source(), BlackboxSource)


def test_blackbox_never_fakes_inside_metrics(monkeypatch):
    _arm(monkeypatch)
    _mock_probe(monkeypatch, lambda h, p, to: (p == 80, 1.0, "open" if p == 80 else "refused"))
    t = BlackboxSource().collect()
    assert t.cpu_percent is None and t.memory_percent is None and t.process_count is None


def test_existing_telemetry_compatibility(monkeypatch):
    # Non-blackbox sources are unaffected; network stays None by default.
    from app.telemetry.collector import NullSource
    from app.telemetry.schema import Telemetry

    monkeypatch.setattr(settings, "telemetry_source", "none")
    assert NullSource().collect().available is False
    assert Telemetry().network is None


def test_context_view_labels_blackbox_external(monkeypatch):
    from app.agent import context
    from app.telemetry.service import service as svc

    _arm(monkeypatch)
    _mock_probe(monkeypatch, lambda h, p, to: (p == 80, 1.0, "open" if p == 80 else "refused"))
    snap = BlackboxSource().collect()
    monkeypatch.setattr(svc, "latest", snap)
    ctx = context.build_context("recon the lab host", scenario_id="t")
    assert ctx.telemetry["scope"] == "windows_target_external"
    assert ctx.telemetry["network"]["reachable"] is True
