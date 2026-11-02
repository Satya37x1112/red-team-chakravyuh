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
        """Stub for an authorized, controlled Locust load-test adapter.

        Intentionally unimplemented. Nothing in this repo opens sockets or
        generates traffic; the body stays a NotImplementedError. The notes below
        describe the shape an operator would wire in later for a lab host they own.

        Intended integration (operator to implement):
          - Invoke Locust in headless mode via ``subprocess.run([...],
            capture_output=True, text=True, timeout=...)`` — arguments as a list,
            never ``shell=True`` — roughly::

                locust -f <locustfile> --headless -u <user_count> -r <spawn_rate>
                       --host <target_url> --csv results

          - Take the locustfile path from config / ``.env`` (see LOCUST_FILE_PATH);
            the locustfile itself is authored separately by the operator and is not
            part of this repo.
          - Map the agent's ``recommended_sources`` from ``plan`` to ``--users`` /
            ``--spawn-rate`` so load stays within the planned bound.
          - Parse the generated ``results_stats.csv`` (requests, failures, p95
            latency) into ``simulation_metrics`` on the ExecutionResult.

        The adapter must only ever target a lab host the operator owns and has
        written authorization to load-test.
        """
        raise NotImplementedError(
            "Connect an authorized Locust lab adapter here."
        )

    def _analysis_summary(self, profile: ProfileResult) -> str:
        return (
            "DDoS load-test simulation: the agent sized a controlled source count "
            f"from observed {profile.load_level} load on the lab host."
        )
