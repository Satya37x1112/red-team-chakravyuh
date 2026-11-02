"""RAT + UBA SIMULATION module.

The UBA half is fully real: it baselines the lab user's actual endpoint activity
and scores deviations (see uba.py). The RAT half's execute() is a stub — this
repo deploys no implant, agent, or C2.
"""
from __future__ import annotations

from ..telemetry.schema import Telemetry
from .base import AnalysisReport, AttackModule, Observation, PlanResult, ProfileResult
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

    def execute(self, plan: PlanResult):
        # TODO: real adapter would plug in here.
        #
        # An authorized adapter would stream real endpoint telemetry from a
        # consented lab host (process/file/network/Windows events) into the UBA
        # engine. This repo does NOT deploy any implant, remote-access agent, or
        # command-and-control channel; telemetry arrives only via the read-only
        # collector in app/telemetry.
        raise NotImplementedError(
            "Connect an authorized, consented endpoint-telemetry feed here (read-only)."
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
