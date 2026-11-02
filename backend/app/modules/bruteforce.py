"""Brute-force / authentication-test SIMULATION module.

Real, read-only discover/profile/plan/observe/adapt/analyze. execute() is a
bounded in-memory SIMULATION — it models lockout metrics and sends no credentials
to any endpoint.
"""
from __future__ import annotations

from ..telemetry.schema import Telemetry
from .base import AttackModule, ExecutionResult, PlanResult, ProfileResult


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

    def execute(self, plan: PlanResult, telemetry: Telemetry) -> ExecutionResult:
        """SIMULATION ONLY — model an account-lockout test in memory.

        No credentials are sent and no authentication is attempted anywhere. The
        attempt rate is the agent's recommended value; the simulated attempt count
        and lockouts are derived arithmetically, grounded in the count of real
        logon events observed on the host.
        """
        rate = plan.value if plan.value is not None else 5
        rate = max(1, min(30, rate))
        window_min = 5                       # simulated test window
        lockout_threshold = 5                # simulated lab lockout policy
        attempts = rate * window_min
        simulated_lockouts = attempts // lockout_threshold
        # No real credential ever matches in a simulation — success is always 0.
        simulated_success = 0
        logon_ids = {4624, 4625}
        observed_logons = len([e for e in telemetry.windows_events if e.event_id in logon_ids])
        series = [
            {"minute": i + 1, "attempts": rate,
             "lockouts": (rate * (i + 1)) // lockout_threshold - (rate * i) // lockout_threshold}
            for i in range(window_min)
        ]
        return ExecutionResult(
            mode="simulation",
            summary=(f"Simulated {attempts} auth attempts over {window_min} min at {rate}/min; "
                     f"{simulated_lockouts} lockouts modelled (no credentials sent)."),
            metrics={
                "simulated_attempt_rate": rate,
                "simulated_window_minutes": window_min,
                "simulated_attempts": attempts,
                "simulated_lockouts": simulated_lockouts,
                "simulated_successful_logins": simulated_success,
                "grounded_on_observed_logon_events": observed_logons,
            },
            series=series,
        )

    def _analysis_summary(self, profile: ProfileResult) -> str:
        return (
            "Brute-force simulation: the agent proposed a conservative attempt rate "
            "for an authorized account-lockout test, from observed logon telemetry."
        )
