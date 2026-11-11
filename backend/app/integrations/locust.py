"""Locust load-test adapter — genuine HTTP traffic generator for DDoS & availability testing.

Features:
  - Strict bounded real HTTP load generation against authorized lab endpoints.
  - Headless execution with hard backend limits (max 50 users, max 120s duration).
  - Accurate calculation of request counts, failure counts, RPS, average latency,
    median (p50) latency, and 95th-percentile (p95) latency.
  - Pre-test and post-test HTTP target reachability/availability measurement.
  - Transparent target-side resource metrics (explicitly reporting 'Unavailable'
    when target host telemetry is not collected; never fabricating measurements).
  - Full registration with the unified process table and fail-closed kill switch.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from ..config import settings
from ..services.availability import (
    calculate_latency_percentiles,
    parse_locust_errors_from_text,
    probe_target_availability,
)
from .base import Integration, IntegrationStatus


def _locust_version() -> str | None:
    try:
        from importlib.metadata import version

        return version("locust")
    except Exception:
        return None


def resolve_locustfile() -> str | None:
    """Locate the operator-authored locustfile, falling back to vendored demo."""
    if settings.locust_file_path and os.path.isfile(settings.locust_file_path):
        return settings.locust_file_path

    # Standard locations for the demo locustfile
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    candidates = [
        os.path.join(base_dir, "tools/locustfile_demo.py"),
        os.path.abspath("backend/tools/locustfile_demo.py"),
        os.path.abspath("tools/locustfile_demo.py"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


class LocustIntegration(Integration):
    name = "locust"
    title = "Locust Load Test"
    category = "load-test"
    repo = "locust-master"

    def status(self) -> IntegrationStatus:
        ver = _locust_version()
        bin_path = self._which("locust")
        if ver is None and bin_path is None:
            return self._unavailable(
                "Locust is not installed. `pip install locust` to enable the real "
                "load-test driver; the DDoS module stays simulation-only until then.",
            )
        locustfile = resolve_locustfile()
        file_ok = bool(locustfile)

        detail = {
            "version": ver,
            "binary": bin_path,
            "enabled": settings.locust_enabled,
            "locustfile": locustfile,
            "locustfile_present": file_ok,
            "target_url": settings.locust_target_url or None,
            "caps": {
                "max_users": settings.locust_max_users,
                "max_spawn_rate": settings.locust_max_spawn_rate,
                "max_run_seconds": settings.locust_max_run_seconds,
            },
        }
        if not settings.locust_enabled:
            return self._ok(
                "Locust is installed but the runner is disabled. Set LOCUST_ENABLED=true "
                "(plus target URL) to arm it.",
                runnable=False,
                **detail,
            )
        if not file_ok:
            return self._ok(
                "Locust enabled but no valid locustfile found (set LOCUST_FILE_PATH).",
                runnable=False,
                **detail,
            )
        if not settings.locust_target_url:
            return self._ok(
                "Locust enabled but LOCUST_TARGET_URL (the authorized target) is not set.",
                runnable=False,
                **detail,
            )
        return self._ok(
            f"Armed — {settings.locust_target_url} (users ≤{settings.locust_max_users}, "
            f"duration ≤{settings.locust_max_run_seconds}s).",
            runnable=True,
            **detail,
        )

    def preconditions(self, target_url: str | None = None) -> str | None:
        """Return a human reason the runner can't fire, or None if it can."""
        st = self.status()
        if not st.available:
            return st.reason
        effective_target = target_url or settings.locust_target_url
        if not effective_target:
            return "No authorized target URL configured for load testing."
        locustfile = resolve_locustfile()
        if not locustfile:
            return "No locustfile found on host."
        return None

    def run(
        self,
        *,
        users: int | None = None,
        spawn_rate: int | None = None,
        run_seconds: int | None = None,
        target_url: str | None = None,
    ) -> dict[str, Any]:
        """Drive Locust headless to generate genuine HTTP traffic against authorized target."""
        effective_target = (target_url or settings.locust_target_url or "").strip()
        blocked = self.preconditions(effective_target)
        if blocked:
            raise RuntimeError(blocked)

        locustfile = resolve_locustfile()
        assert locustfile is not None

        # Clamp parameters to configured safety bounds
        u = max(1, min(users or settings.locust_max_users, settings.locust_max_users))
        r = max(1, min(spawn_rate or settings.locust_max_spawn_rate, settings.locust_max_spawn_rate))
        t = max(1, min(run_seconds or settings.locust_max_run_seconds, settings.locust_max_run_seconds))

        bin_path = self._which("locust") or "locust"

        # 1. Pre-test target availability probe
        pre_probe = probe_target_availability(effective_target, timeout=2.5)

        cmd = [
            bin_path,
            "-f", locustfile,
            "--host", effective_target,
            "--headless",
            "-u", str(u),
            "-r", str(r),
            "-t", f"{t}s",
            "--json",
            "--only-summary",
        ]

        started = time.monotonic()
        timed_out = False
        # Give the process a little slack beyond the run window to flush summary
        proc = self._run(cmd, timeout=t + 20)
        actual_duration = round(time.monotonic() - started, 2)

        # 2. Post-test target availability probe
        post_probe = probe_target_availability(effective_target, timeout=2.5)

        # 3. Parse Locust JSON summary
        stats_rows: list[dict[str, Any]] = []
        parse_error = None
        if proc.stdout.strip():
            try:
                raw_json = json.loads(proc.stdout)
                if isinstance(raw_json, list):
                    stats_rows = raw_json
                elif isinstance(raw_json, dict):
                    stats_rows = [raw_json]
            except json.JSONDecodeError as exc:
                parse_error = f"could not parse Locust JSON summary: {exc}"

        # 4. Extract total requests, failures, response times
        total_reqs = 0
        total_fails = 0
        total_resp_time_ms = 0.0
        combined_response_times: dict[str, int] = {}
        min_lat: float | None = None
        max_lat: float | None = None

        for row in stats_rows:
            name = row.get("name")
            reqs = int(row.get("num_requests") or 0)
            fails = int(row.get("num_failures") or 0)
            resp_time = float(row.get("total_response_time") or 0.0)

            total_reqs += reqs
            total_fails += fails
            total_resp_time_ms += resp_time

            row_min = row.get("min_response_time")
            if row_min is not None:
                min_lat = min(min_lat, float(row_min)) if min_lat is not None else float(row_min)
            row_max = row.get("max_response_time")
            if row_max is not None:
                max_lat = max(max_lat, float(row_max)) if max_lat is not None else float(row_max)

            # Accumulate histogram
            hist = row.get("response_times") or {}
            for lat_bin, count in hist.items():
                combined_response_times[str(lat_bin)] = combined_response_times.get(str(lat_bin), 0) + count

        percentiles = calculate_latency_percentiles(combined_response_times)
        avg_lat = round(total_resp_time_ms / total_reqs, 2) if total_reqs > 0 else 0.0
        rps = round(total_reqs / actual_duration, 2) if actual_duration > 0 else float(total_reqs)
        success_reqs = max(0, total_reqs - total_fails)

        # 5. Extract errors from stderr/stdout text
        combined_output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        errors = parse_locust_errors_from_text(combined_output)

        totals = {
            "requests": total_reqs,
            "success": success_reqs,
            "failures": total_fails,
            "rps": rps,
            "avg_latency_ms": avg_lat,
            "median_latency_ms": percentiles["p50_ms"],
            "p95_latency_ms": percentiles["p95_ms"],
            "min_latency_ms": min_lat if min_lat is not None else 0.0,
            "max_latency_ms": max_lat if max_lat is not None else 0.0,
            "error_pct": round((total_fails / total_reqs) * 100, 1) if total_reqs > 0 else 0.0,
        }

        return {
            "params": {
                "users": u,
                "spawn_rate": r,
                "run_seconds": t,
                "target": effective_target,
                "actual_duration_seconds": actual_duration,
            },
            "totals": totals,
            "stats": stats_rows,
            "errors": errors,
            "target_availability": {
                "pre_test": pre_probe,
                "post_test": post_probe,
                "service_remained_up": bool(post_probe.get("available")),
                "latency_increase_ms": (
                    round(post_probe["latency_ms"] - pre_probe["latency_ms"], 2)
                    if (post_probe.get("latency_ms") is not None and pre_probe.get("latency_ms") is not None)
                    else None
                ),
            },
            # Explicit target-side resource status (never fabricated)
            "target_host_metrics": {
                "cpu": "Unavailable",
                "ram": "Unavailable",
                "telemetry_source": "none (target host agent not present)",
            },
            "exit_code": proc.returncode,
            "parse_error": parse_error,
            "simulated": False,
            "banner": "REAL HTTP LOAD TEST — GENUINE NETWORK TRAFFIC GENERATED",
            "stderr_tail": "\n".join(proc.stderr.splitlines()[-20:]) if proc.stderr else "",
        }
