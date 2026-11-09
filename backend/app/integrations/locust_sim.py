"""DDoS **SIMULATION** telemetry generator — NO network traffic.

This is the synthetic counterpart to the real Locust adapter (`locust.py`). It
deliberately shares NOTHING with it: it opens no socket, spawns no subprocess,
and contacts no host (not the Windows target, not Tailscale, not localhost). It
only computes clearly-labelled *simulated* demonstration metrics and returns
them. Every result carries BANNER so the UI/audit can never mistake it for real
measurements.

It still runs for the (clamped) duration in real time and polls the kill switch /
registry each step, so a Stop / kill-switch terminates it promptly — exactly like
a real execution, which is the point of the demonstration.
"""
from __future__ import annotations

import random
import time

from ..safety import process
from ..safety.killswitch import kill_switch
from ..safety.registry import registry

BANNER = "SIMULATION — NO NETWORK TRAFFIC GENERATED"

# Synthetic properties of an imaginary fragile target (used ONLY to shape the
# demo curves; they correspond to no real host).
_SATURATION_USERS = 25     # above this, simulated latency/errors climb
_PER_USER_RPS = 3.0        # simulated requests/sec each virtual user drives
_STEP = 0.25               # poll interval (s) — how often we check the kill switch


def _should_stop(exec_id: str | None) -> bool:
    if kill_switch.is_engaged():
        return True
    if exec_id:
        rec = registry.get(exec_id)
        if rec is not None and rec.cancel_requested:
            return True
    return False


def run_simulation(*, users=None, spawn_rate=None, run_seconds=None) -> dict:
    u = max(1, int(users or 1))
    r = max(1, int(spawn_rate or 1))
    secs = max(1, int(run_seconds or 1))
    exec_id = process.CURRENT_EXECUTION_ID.get()
    rng = random.Random(f"{u}:{r}:{secs}")

    timeline: list[dict] = []
    total_req = 0.0
    total_fail = 0.0
    lat_weighted = 0.0
    lat_weight = 0.0
    peak_latency = 0.0
    stopped_early = False

    start = time.monotonic()
    elapsed = 0.0
    cur_sec = -1
    bucket: dict | None = None

    while elapsed < secs:
        if _should_stop(exec_id):
            stopped_early = True
            break
        # Ramp active users at spawn_rate/sec, capped at the planned total.
        active = min(u, max(1, int(r * elapsed) + 1))
        congestion = max(0.0, (active - _SATURATION_USERS) / _SATURATION_USERS)
        rps = active * _PER_USER_RPS
        req = rps * _STEP
        avg_ms = 30.0 + 7.0 * active + 140.0 * congestion * congestion
        avg_ms *= 1.0 + rng.uniform(-0.05, 0.05)  # mild jitter
        err_frac = min(0.35, max(0.0, congestion * 0.4))
        fail = req * err_frac

        total_req += req
        total_fail += fail
        lat_weighted += avg_ms * req
        lat_weight += req
        peak_latency = max(peak_latency, avg_ms)

        sec = int(elapsed)
        if sec != cur_sec:
            if bucket is not None:
                timeline.append(bucket)
            cur_sec = sec
            bucket = {"t": sec, "active_users": active, "requests": 0.0,
                      "failures": 0.0, "avg_ms": avg_ms}
        bucket["active_users"] = active
        bucket["requests"] += req
        bucket["failures"] += fail
        bucket["avg_ms"] = avg_ms

        time.sleep(_STEP)
        elapsed = time.monotonic() - start

    if bucket is not None:
        timeline.append(bucket)

    actual_secs = max(0.001, elapsed)
    requests = int(round(total_req))
    failures = int(round(total_fail))
    successes = max(0, requests - failures)
    avg = (lat_weighted / lat_weight) if lat_weight else 0.0
    # Synthetic percentiles derived from the simulated mean/peak (labelled simulated).
    p50 = round(avg * 0.85, 1)
    p95 = round(min(peak_latency, avg * 1.9) if avg else 0.0, 1)
    rps = round(requests / actual_secs, 1)
    err_pct = round((failures / requests * 100.0) if requests else 0.0, 2)

    # Round the timeline for presentation.
    for b in timeline:
        b["requests"] = int(round(b["requests"]))
        b["failures"] = int(round(b["failures"]))
        b["avg_ms"] = round(b["avg_ms"], 1)

    return {
        "simulated": True,
        "banner": BANNER,
        "mode": "simulation",
        "stopped_early": stopped_early,
        "params": {"users": u, "spawn_rate": r, "run_seconds": secs,
                   "actual_seconds": round(actual_secs, 1)},
        "totals": {
            "requests": requests,
            "successes": successes,
            "failures": failures,
            "rps": rps,
            "error_pct": err_pct,
            "avg_ms": round(avg, 1),
            "median_ms": p50,
            "p95_ms": p95,
        },
        "timeline": timeline,
        # Nothing real was contacted — make that explicit in the payload too.
        "target": "simulation (no network traffic)",
    }
