"""RAT + UBA SIMULATION module.

The UBA half is fully real: it baselines the lab user's actual endpoint activity
and scores deviations (see uba.py). The RAT half's execute() is a bounded
in-memory SIMULATION — this repo deploys no implant, agent, or C2 channel.
"""
from __future__ import annotations

from ..telemetry.schema import Telemetry
from .base import AnalysisReport, AttackModule, ExecutionResult, Observation, PlanResult, ProfileResult
from .uba import Baseline, build_baseline, risk_score, score_snapshot


class RATUBAModule(AttackModule):
    kind = "ratuba"

    def __init__(self) -> None:
        self._baseline: Baseline | None = None

    def profile(self, telemetry: Telemetry) -> ProfileResult:
        base = super().profile(telemetry)
        base.facts["distinct_processes"] = len({p.name for p in telemetry.processes})
        base.facts["windows_event_count"] = len(telemetry.windows_events)
        base.summary = "Endpoint/UBA profile from real session telemetry"
        return base

    def baseline_from(self, history: list[Telemetry]) -> Baseline:
        """Establish the user-behaviour baseline from real snapshots."""
        self._baseline = build_baseline(history)
        return self._baseline

    def execute(self, plan: PlanResult, telemetry: Telemetry) -> ExecutionResult:
        """SIMULATION ONLY — model an adversary-emulation run in memory.

        No implant, agent, or C2 channel is deployed and no host is contacted. The
        number of simulated emulated techniques is grounded in the variety of real
        processes observed; the real UBA scoring of the live snapshot happens
        separately in the orchestrator and is genuine read-only analysis.
        """
        window = plan.value if plan.value is not None else 30
        window = max(5, min(120, window))
        distinct_processes = len({p.name for p in telemetry.processes})
        event_count = len(telemetry.windows_events)
        # Synthetic count of emulated techniques, bounded and grounded in real variety.
        simulated_techniques = max(1, min(10, distinct_processes // 10 or 1))
        simulated_checkins = window // 5
        series = [
            {"technique": f"sim-TTP-{i+1}", "status": "emulated", "artifacts": 1}
            for i in range(simulated_techniques)
        ]
        return ExecutionResult(
            mode="simulation",
            summary=(f"Simulated {simulated_techniques} emulated techniques over a "
                     f"{window}-min baseline window (no implant or C2 deployed)."),
            metrics={
                "simulated_baseline_window_minutes": window,
                "simulated_techniques": simulated_techniques,
                "simulated_checkins": simulated_checkins,
                "grounded_on_distinct_processes": distinct_processes,
                "grounded_on_windows_event_count": event_count,
            },
            series=series,
        )

    def analyze(self, profile: ProfileResult, observation: Observation | None) -> AnalysisReport:
        findings = [profile.summary]
        score = None
        if self._baseline and observation:
            findings.append(f"UBA baseline built from {self._baseline.samples} real snapshots.")
        return AnalysisReport(
            summary="RAT simulation: baselined the lab user's real activity and scored deviations.",
            risk_score=score,
            findings=findings,
        )

    def score_latest(self, telemetry: Telemetry) -> dict:
        """Score one real snapshot against the current baseline (for the UI)."""
        if not self._baseline:
            return {"ready": False, "anomalies": [], "risk_score": 0.0}
        anomalies = score_snapshot(self._baseline, telemetry)
        return {
            "ready": self._baseline.ready,
            "anomalies": [a.__dict__ for a in anomalies],
            "risk_score": risk_score(anomalies),
        }


def get_module(kind: str):
    """Fresh module instance per kind."""
    from .bruteforce import BruteForceModule
    from .ddos import DDoSModule

    factory = {"ddos": DDoSModule, "bruteforce": BruteForceModule, "ratuba": RATUBAModule}
    cls = factory.get(kind)
    return cls() if cls else None
