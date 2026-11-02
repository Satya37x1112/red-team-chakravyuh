"""DDoS / service-load SIMULATION module.

discover/profile/plan/observe/adapt/analyze are real and read-only. execute()
is a bounded in-memory SIMULATION — it computes synthetic load-test metrics from
the real snapshot and opens no socket and sends no traffic.
"""
from __future__ import annotations

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
        total_requests = sources * req_per_source
        # Under more real load, the simulated host "absorbs" fewer of them.
        serviced_pct = round(headroom, 1)
        serviced = int(round(total_requests * headroom / 100.0))
        dropped = total_requests - serviced
        # Modelled peak load on the simulated target while "under" the load test.
        # Synthetic — this is the simulation's own number, not a real reading.
        simulated_peak_load_pct = min(96, 82 + sources)
        series = [
            {"source": f"sim-src-{i+1}", "requests": req_per_source,
             "serviced": int(round(req_per_source * headroom / 100.0))}
            for i in range(sources)
        ]
        return ExecutionResult(
            mode="simulation",
            summary=(f"Simulated {sources} load sources × {req_per_source} requests; modelled "
                     f"target load peaks at {simulated_peak_load_pct}% (synthetic — no real traffic)."),
            metrics={
                "simulated_sources": sources,
                "simulated_requests": total_requests,
                "simulated_serviced": serviced,
                "simulated_dropped": dropped,
                "serviced_pct": serviced_pct,
                "simulated_peak_load_pct": simulated_peak_load_pct,
                "grounded_on_cpu_percent": cpu,
            },
            series=series,
        )

    def _analysis_summary(self, profile: ProfileResult) -> str:
        return (
            "DDoS load-test simulation: the agent sized a controlled source count "
            f"from observed {profile.load_level} load on the lab host."
        )
