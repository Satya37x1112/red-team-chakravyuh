"""Blackbox (agentless, IP-only) telemetry. All local — probes only a loopback
socket opened by the test. No external target is ever contacted."""
from __future__ import annotations

import socket

import pytest

from app.config import settings
from app.telemetry.collector import BlackboxSource, build_source


@pytest.fixture
def open_local_port():
    """A real listening socket on 127.0.0.1 — gives a genuinely-open port to probe."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    port = srv.getsockname()[1]
    yield port
    srv.close()


def _arm(monkeypatch, ports: str, http=False):
    monkeypatch.setattr(settings, "blackbox_target", "127.0.0.1")
    monkeypatch.setattr(settings, "blackbox_ports", ports)
    monkeypatch.setattr(settings, "blackbox_timeout_seconds", 1.0)
    monkeypatch.setattr(settings, "blackbox_http", http)


def test_unavailable_without_target(monkeypatch):
    monkeypatch.setattr(settings, "blackbox_target", "")
    t = BlackboxSource().collect()
    assert t.available is False
    assert "BLACKBOX_TARGET" in (t.error or "")


def test_detects_open_port(monkeypatch, open_local_port):
    _arm(monkeypatch, str(open_local_port))
    t = BlackboxSource().collect()
    assert t.available is True
    assert t.source == "blackbox"
    assert t.network is not None
    assert open_local_port in t.network.open_ports
    assert t.network.reachable is True
    assert t.network.latency_ms is not None


def test_closed_port_is_not_open_but_host_reachable(monkeypatch):
    # Port 1 on localhost is almost certainly closed -> connection refused -> host up.
    _arm(monkeypatch, "1")
    t = BlackboxSource().collect()
    assert t.network.open_ports == []
    assert t.network.reachable is True  # refused == host responded


def test_blackbox_never_fakes_inside_metrics(monkeypatch, open_local_port):
    _arm(monkeypatch, str(open_local_port))
    t = BlackboxSource().collect()
    # External probe cannot see inside — these MUST stay None, never fabricated.
    assert t.cpu_percent is None
    assert t.memory_percent is None
    assert t.process_count is None


def test_port_list_parsing_and_cap(monkeypatch):
    monkeypatch.setattr(settings, "blackbox_ports", "80, 443 , 445, bad, 99999, 22")
    assert settings.blackbox_port_list == [80, 443, 445, 22]
    monkeypatch.setattr(settings, "blackbox_ports", ",".join(str(p) for p in range(1, 200)))
    assert len(settings.blackbox_port_list) == 64  # hard cap


def test_build_source_selects_blackbox(monkeypatch):
    monkeypatch.setattr(settings, "telemetry_source", "blackbox")
    assert isinstance(build_source(), BlackboxSource)


def test_context_view_labels_blackbox_as_external(monkeypatch, open_local_port):
    from app.agent import context
    from app.telemetry.service import service as svc

    _arm(monkeypatch, str(open_local_port))
    snap = BlackboxSource().collect()
    monkeypatch.setattr(svc, "latest", snap)
    ctx = context.build_context("recon the lab host", scenario_id="t")
    assert ctx.telemetry["scope"] == "windows_target_external"
    assert ctx.telemetry["available"] is True
    assert ctx.telemetry["network"]["reachable"] is True
    assert open_local_port in ctx.telemetry["network"]["open_ports"]
