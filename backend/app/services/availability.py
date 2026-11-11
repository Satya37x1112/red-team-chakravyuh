"""Availability and HTTP load testing metrics collector for CYBER CHAKRAVYUH.

Handles:
- Pre-test and post-test HTTP target reachability/availability measurement
- Accurate parsing of Locust request counts, latency percentiles (p50, p95), and HTTP errors
- Transparent target host metric representation (explicitly reporting 'Unavailable' when host telemetry is absent)
- Clean separation between genuine HTTP metrics and synthetic simulation
"""
from __future__ import annotations

import logging
import re
import time
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger(__name__)


def probe_target_availability(url: str, timeout: float = 2.5) -> dict[str, Any]:
    """Perform a harmless, non-destructive probe to check HTTP target reachability and latency."""
    cleaned = (url or "").strip()
    if not cleaned.startswith(("http://", "https://")):
        return {
            "available": False,
            "status_code": None,
            "latency_ms": None,
            "error": "Invalid URL scheme (must be http:// or https://)",
        }

    start = time.monotonic()
    req = urllib.request.Request(
        cleaned,
        headers={"User-Agent": "CyberChakravyuh-AvailabilityProbe/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            latency = round((time.monotonic() - start) * 1000.0, 2)
            code = response.getcode()
            return {
                "available": True,
                "status_code": code,
                "latency_ms": latency,
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        latency = round((time.monotonic() - start) * 1000.0, 2)
        # HTTP errors (e.g. 404, 500, 503) indicate target service IS running and responding
        return {
            "available": True,
            "status_code": exc.code,
            "latency_ms": latency,
            "error": f"HTTP {exc.code}: {exc.reason}",
        }
    except Exception as exc:
        latency = round((time.monotonic() - start) * 1000.0, 2)
        return {
            "available": False,
            "status_code": None,
            "latency_ms": latency,
            "error": f"Connection failed: {exc}",
        }


def calculate_latency_percentiles(response_times: dict[str, int]) -> dict[str, float]:
    """Calculate p50 (median) and p95 latency in ms from a Locust response-time frequency histogram."""
    if not response_times:
        return {"p50_ms": 0.0, "p95_ms": 0.0}

    # Convert histogram keys to int and sort by latency
    sorted_bins: list[tuple[int, int]] = []
    for k, v in response_times.items():
        try:
            sorted_bins.append((int(k), int(v)))
        except (ValueError, TypeError):
            continue

    sorted_bins.sort(key=lambda item: item[0])
    total_samples = sum(count for _, count in sorted_bins)
    if total_samples <= 0:
        return {"p50_ms": 0.0, "p95_ms": 0.0}

    p50_threshold = total_samples * 0.50
    p95_threshold = total_samples * 0.95

    cum = 0
    p50_val: float | None = None
    p95_val: float | None = None

    for latency_ms, count in sorted_bins:
        cum += count
        if p50_val is None and cum >= p50_threshold:
            p50_val = float(latency_ms)
        if p95_val is None and cum >= p95_threshold:
            p95_val = float(latency_ms)
            break

    return {
        "p50_ms": p50_val if p50_val is not None else 0.0,
        "p95_ms": p95_val if p95_val is not None else (p50_val if p50_val is not None else 0.0),
    }


def parse_locust_errors_from_text(text: str) -> list[dict[str, Any]]:
    """Extract structured error breakdown from Locust stderr/stdout text tables."""
    errors: list[dict[str, Any]] = []
    in_error_table = False

    for line in text.splitlines():
        trimmed = line.strip()
        if "Error report" in trimmed:
            in_error_table = True
            continue
        if in_error_table:
            if trimmed.startswith("---") or trimmed.startswith("# occ"):
                continue
            if not trimmed:
                break
            # Lines look like: "2  GET GET /: ConnectionRefusedError(111, 'Connection refused')"
            m = re.match(r"^(\d+)\s+(.+)$", trimmed)
            if m:
                errors.append({
                    "occurrences": int(m.group(1)),
                    "error": m.group(2).strip(),
                })

    return errors
