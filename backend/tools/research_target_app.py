"""CHAKRAVYUH DDoS-research HTTP target — zero-dependency, read-only.

Runs ON THE DEDICATED RESEARCH TARGET VM (not on Kali). Python 3 stdlib only, so
a minimal Alpine/Debian VM needs nothing but `python3`. It exposes a tiny,
clearly-identified research app for bounded, authorized HTTP load research.

Endpoints (all GET, read-only — no writes, no admin, no shell, no exploitable bug):
  /            -> 200 small HTML "research target UP"
  /health      -> 200 JSON {status, uptime_s}
  /test        -> 200 JSON deterministic payload; increments the request counter
  /metrics     -> 200 JSON counters + response-time percentiles + CPU/mem (from /proc)

Bind: default 0.0.0.0:8080 so it is reachable over the VM's Tailscale interface.
Tighten exposure with the target VM's host firewall (allow only the tailnet peer
+ this port). It contacts no external service and stores no data.
"""
from __future__ import annotations

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("RESEARCH_HOST", "0.0.0.0")
PORT = int(os.environ.get("RESEARCH_PORT", sys.argv[1] if len(sys.argv) > 1 else 8080))
_START = time.monotonic()

# In-memory research counters (reset on restart; no persistence).
_counters = {"requests": 0, "success": 0, "errors": 0}
_latencies: list[float] = []   # ms, capped ring buffer
_LAT_CAP = 5000


def _cpu_percent(sample: float = 0.1) -> float | None:
    """Instantaneous CPU utilisation from /proc/stat (Linux only)."""
    try:
        def snap():
            with open("/proc/stat") as f:
                parts = f.readline().split()[1:]
            vals = list(map(int, parts))
            idle = vals[3] + vals[4]
            return sum(vals), idle
        t1, i1 = snap(); time.sleep(sample); t2, i2 = snap()
        dt, di = t2 - t1, i2 - i1
        return round(100.0 * (1 - di / dt), 1) if dt else None
    except Exception:
        return None


def _mem_percent() -> float | None:
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.strip().split()[0])
        total, avail = info.get("MemTotal"), info.get("MemAvailable")
        return round(100.0 * (1 - avail / total), 1) if total and avail else None
    except Exception:
        return None


def _pct(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    k = min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1))))
    return round(s[k], 1)


class Handler(BaseHTTPRequestHandler):
    server_version = "CHAKRAVYUH-ResearchTarget/1.0"

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        t0 = time.perf_counter()
        path = self.path.split("?", 1)[0]
        try:
            if path == "/health":
                body = json.dumps({"status": "ok", "uptime_s": round(time.monotonic() - _START, 1)}).encode()
                self._send(200, body, "application/json")
            elif path == "/test":
                _counters["requests"] += 1
                body = json.dumps({"app": "chakravyuh-research-target", "ok": True, "seq": _counters["requests"]}).encode()
                self._send(200, body, "application/json")
                _counters["success"] += 1
            elif path == "/metrics":
                body = json.dumps({
                    "app": "chakravyuh-research-target",
                    "counters": dict(_counters),
                    "response_ms": {
                        "p50": _pct(_latencies, 50), "p95": _pct(_latencies, 95),
                        "p99": _pct(_latencies, 99), "samples": len(_latencies),
                    },
                    "cpu_percent": _cpu_percent(),
                    "mem_percent": _mem_percent(),
                    "uptime_s": round(time.monotonic() - _START, 1),
                }).encode()
                self._send(200, body, "application/json")
            elif path == "/":
                _counters["requests"] += 1
                body = (b"<!doctype html><meta charset=utf-8><title>CHAKRAVYUH Research Target</title>"
                        b"<body style='font-family:system-ui;background:#0b0f17;color:#e5e7eb;text-align:center;padding:3rem'>"
                        b"<h1>Research target is UP</h1><p>Authorized HTTP load-research target. Read-only.</p>")
                self._send(200, body, "text/html; charset=utf-8")
                _counters["success"] += 1
            else:
                _counters["requests"] += 1; _counters["errors"] += 1
                self._send(404, b'{"error":"not found"}', "application/json")
        finally:
            dt = (time.perf_counter() - t0) * 1000.0
            _latencies.append(dt)
            if len(_latencies) > _LAT_CAP:
                del _latencies[0:len(_latencies) - _LAT_CAP]

    def log_message(self, *a):  # quiet
        pass


if __name__ == "__main__":
    print(f"research target listening on http://{HOST}:{PORT}  (read-only; /health /test /metrics)")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
