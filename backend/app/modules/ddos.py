"""DDoS / service-load SIMULATION module.

discover/profile/plan/observe/adapt/analyze are real and read-only. execute()
is a stub. The eventual authorized adapter is expected to drive a legitimate
load-testing tool (Locust) against a lab host you own.
"""
from __future__ import annotations

from ..telemetry.schema import Telemetry
from .base import AttackModule, PlanResult, ProfileResult


class DDoSModule(AttackModule):
    kind = "ddos"

    def profile(self, telemetry: Telemetry) -> ProfileResult:
        base = super().profile(telemetry)
        base.facts["interface_count"] = len(telemetry.interfaces)
        base.facts["connection_count"] = len(telemetry.connections)
        base.summary = f"Load-test profile — observed load {base.load_level}"
        return base

    def execute(self, plan: PlanResult):
        # TODO: real adapter would plug in here.
        #
        # An authorized lab adapter would receive `plan` (parameter
        # "recommended_sources" + integer value) and launch a CONTROLLED Locust
        # load test against a lab host you own, then return an ExecutionResult
        # with the run id and raw Locust stats. Nothing in this repo opens
        # sockets or generates traffic.
        raise NotImplementedError(
            "Connect an authorized Locust lab adapter here."
        )

    def _analysis_summary(self, profile: ProfileResult) -> str:
        return (
            "DDoS load-test simulation: the agent sized a controlled source count "
            f"from observed {profile.load_level} load on the lab host."
        )
