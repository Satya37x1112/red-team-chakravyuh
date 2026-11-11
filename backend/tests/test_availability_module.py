"""Unit and integration tests for DDoS & Availability Testing Module.

Tests:
  - Target availability pre/post probe reachability
  - Percentiles calculation (p50, p95) from response time distributions
  - Error report parsing from Locust output
  - Locust adapter genuine metrics assembling and parameter clamping
  - Target host telemetry reporting 'Unavailable' (no fabricated metrics)
  - Strict preservation of synthetic simulation separation
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.integrations.locust import LocustIntegration
from app.integrations.locust_sim import BANNER as SIM_BANNER, run_simulation
from app.services.availability import (
    calculate_latency_percentiles,
    parse_locust_errors_from_text,
    probe_target_availability,
)


def test_calculate_latency_percentiles_empty():
    """Verify empty response_times produces safe 0.0 values."""
    res = calculate_latency_percentiles({})
    assert res == {"p50_ms": 0.0, "p95_ms": 0.0}


def test_calculate_latency_percentiles_accurate():
    """Verify accurate p50 and p95 percentile calculation."""
    # 100 requests: 50 at 10ms, 45 at 20ms, 5 at 100ms
    histogram = {"10": 50, "20": 45, "100": 5}
    res = calculate_latency_percentiles(histogram)
    assert res["p50_ms"] == 10.0
    assert res["p95_ms"] == 20.0


def test_parse_locust_errors_from_text():
    """Verify parsing of Locust error report tables."""
    raw_text = """
Type     Name      # reqs
--------|---------|-------
GET      /             10

Error report
# occurrences      Error
------------------|-------------------------------------------------------------
15                 GET /: ConnectionRefusedError(111, 'Connection refused')
3                  GET /: HTTPError('500 Internal Server Error')
------------------|-------------------------------------------------------------
"""
    errors = parse_locust_errors_from_text(raw_text)
    assert len(errors) == 2
    assert errors[0]["occurrences"] == 15
    assert "ConnectionRefusedError" in errors[0]["error"]
    assert errors[1]["occurrences"] == 3
    assert "500 Internal Server Error" in errors[1]["error"]


def test_probe_target_availability_unreachable():
    """Verify availability probe cleanly reports unreachable targets without raising."""
    res = probe_target_availability("http://127.0.0.1:65534", timeout=0.5)
    assert res["available"] is False
    assert res["status_code"] is None
    assert "Connection failed" in res["error"]


def test_locust_adapter_target_unavailable_explicit():
    """Verify target host telemetry explicitly reports 'Unavailable'."""
    locust = LocustIntegration()
    with patch.object(locust, "_run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = """[
            {
                "name": "GET /",
                "num_requests": 50,
                "num_failures": 2,
                "total_response_time": 1000.0,
                "min_response_time": 10.0,
                "max_response_time": 45.0,
                "response_times": {"15": 30, "25": 18, "45": 2}
            }
        ]"""
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        res = locust.run(users=5, spawn_rate=2, run_seconds=2, target_url="http://127.0.0.1:3000")
        assert res["simulated"] is False
        assert res["banner"] == "REAL HTTP LOAD TEST — GENUINE NETWORK TRAFFIC GENERATED"
        # Check target host metrics are explicitly Unavailable
        assert res["target_host_metrics"]["cpu"] == "Unavailable"
        assert res["target_host_metrics"]["ram"] == "Unavailable"
        # Check calculated metrics
        assert res["totals"]["requests"] == 50
        assert res["totals"]["failures"] == 2
        assert res["totals"]["success"] == 48
        assert res["totals"]["median_latency_ms"] == 15.0
        assert res["totals"]["p95_latency_ms"] == 25.0


def test_synthetic_simulation_is_clearly_labelled():
    """Verify synthetic simulation generates no traffic and carries exact simulation banner."""
    assert SIM_BANNER == "SIMULATION — NO NETWORK TRAFFIC GENERATED"
    sim = run_simulation(users=10, spawn_rate=2, run_seconds=1)
    assert sim["simulated"] is True
    assert sim["banner"] == "SIMULATION — NO NETWORK TRAFFIC GENERATED"
    assert "timeline" in sim
    assert "totals" in sim
    assert sim["totals"]["requests"] > 0
