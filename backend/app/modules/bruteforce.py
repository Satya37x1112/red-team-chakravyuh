"""Brute-force / authentication-test SIMULATION module.

Real, read-only discover/profile/plan/observe/adapt/analyze. execute() is a
stub — no credentials are ever sent to any endpoint from this repo.
"""
from __future__ import annotations

from ..telemetry.schema import Telemetry
from .base import AttackModule, PlanResult, ProfileResult


class BruteForceModule(AttackModule):
    kind = "bruteforce"

    def profile(self, telemetry: Telemetry) -> ProfileResult:
        base = super().profile(telemetry)
        # Logon-related Security events (4624 success, 4625 failure) give context
        # for an authorized account-lockout test — read-only observation.
        logon_ids = {4624, 4625}
        logon_events = [e for e in telemetry.windows_events if e.event_id in logon_ids]
        base.facts["observed_logon_events"] = len(logon_events)
        base.facts["logged_in_user"] = telemetry.logged_in_user
        base.summary = f"Auth-test profile — {len(logon_events)} recent logon events observed"
        return base

    def execute(self, plan: PlanResult):
        # TODO: real adapter would plug in here.
        #
        # An authorized adapter would receive `plan` (parameter
        # "recommended_attempt_rate") and drive an approved, rate-limited
        # authentication test against a lab account you control (e.g. via a
        # tool like THC Hydra against your own lab host), returning lockout
        # timing and success/failure counts. This repo sends no credentials.
        raise NotImplementedError(
            "Connect an authorized, rate-limited authentication-test lab adapter here."
        )

    def _analysis_summary(self, profile: ProfileResult) -> str:
        return (
            "Brute-force simulation: the agent proposed a conservative attempt rate "
            "for an authorized account-lockout test, from observed logon telemetry."
        )
