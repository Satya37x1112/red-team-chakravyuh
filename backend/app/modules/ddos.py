"""DDoS / service-load SIMULATION module.

discover/profile/plan/observe/adapt/analyze are real and read-only. execute()
is a bounded in-memory SIMULATION — it computes synthetic load-test metrics from
the real snapshot and opens no socket and sends no traffic.
"""
from __future__ import annotations

import math

from ..telemetry.schema import Telemetry
from .base import AttackModule, ExecutionResult, PlanResult, ProfileResult


class DDoSModule(AttackModule):
    kind = "ddos"

    def profile(self, telemetry: Telemetry) -> ProfileResult:
        base = super().profile(telemetry)
        base.facts["interface_count"] = len(telemetry.interfaces)
        base.facts["connection_count"] = len(telemetry.connections)
        base.summary = f"Load-test profile — observed load {base.load_level}"
        return base

    def execute(self, plan: PlanResult, telemetry: Telemetry) -> ExecutionResult:
        """SIMULATION ONLY — generate synthetic load-test metrics in memory.

        No socket is opened and no traffic is sent anywhere. The synthetic source
        count is the agent's recommended value, and per-source throughput is scaled
        by the host's real observed headroom (100 - CPU%), so the numbers are
        grounded in actual state rather than fixed.
        """
        sources = plan.value if plan.value is not None else 3
        sources = max(1, min(12, sources))
        cpu = telemetry.cpu_percent if telemetry.cpu_percent is not None else 0.0
        headroom = max(0.0, 100.0 - cpu)
        # Synthetic, bounded per-source request model (no real requests are made).
        req_per_source = 50
        serviced_pct = round(headroom, 1)
        # Modelled peak load on the simulated target while "under" the load test.
        simulated_peak_load_pct = min(96, 82 + sources)
        # Uneven per-source volume (deterministic) so the traffic distribution is
        # realistic rather than perfectly uniform.
        per_source = [req_per_source + ((i * 7 + 13) % 17) - 8 for i in range(sources)]
        per_source = [max(1, r) for r in per_source]
        total_requests = sum(per_source)
        serviced = int(round(total_requests * headroom / 100.0))
        dropped = total_requests - serviced
        series = [
            {"source": f"sim-src-{i+1}", "requests": per_source[i],
             "serviced": int(round(per_source[i] * headroom / 100.0))}
            for i in range(sources)
        ]
        # --- DDoS detection metrics (blue-team side) ---
        window_s = 10
        rps = round(total_requests / window_s, 1)
        probs = [r / total_requests for r in per_source]
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        entropy_max = math.log2(sources) if sources > 1 else 1.0
        entropy_norm = round(entropy / entropy_max, 3) if entropy_max else 1.0
        entropy = round(entropy, 3)
        return ExecutionResult(
            mode="simulation",
            summary=(f"Simulated {sources} load sources × {req_per_source} requests; modelled "
                     f"target load peaks at {simulated_peak_load_pct}%."),
            metrics={
                "simulated_sources": sources,
                "simulated_requests": total_requests,
                "simulated_serviced": serviced,
                "simulated_dropped": dropped,
                "serviced_pct": serviced_pct,
                "simulated_peak_load_pct": simulated_peak_load_pct,
                "requests_per_second": rps,
                "shannon_entropy": entropy,
                "entropy_normalized": entropy_norm,
                "grounded_on_cpu_percent": cpu,
            },
            series=series,
        )

    def _analysis_summary(self, profile: ProfileResult) -> str:
        return (
            "DDoS load-test simulation: the agent sized a controlled source count "
            f"from observed {profile.load_level} load on the lab host."
        )
