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
        """Stub for an authorized, rate-limited account-lockout test adapter.

        Intentionally unimplemented. This repo sends no credentials and runs no
        tool; the body stays a NotImplementedError. The notes below describe the
        shape an operator would wire in later for a lab they are authorized to test.

        Intended integration (operator to implement):
          - Shell out to THC Hydra with ``subprocess.run([...], capture_output=True,
            text=True, timeout=...)`` — arguments as a list, never ``shell=True``.
          - Read ``target_ip``, ``service``, and the wordlist paths from ``plan``,
            which is sourced from config / ``.env`` (see HYDRA_WORDLIST_DIR) — never
            hardcoded in source and never taken from untrusted user input.
          - Honour the agent's ``recommended_attempt_rate`` from ``plan`` as Hydra's
            task/rate limit so the test stays conservative.
          - Capture ``stdout`` and parse the recovered ``login: password`` pairs and
            lockout timing into the ExecutionResult. Treat a non-zero exit as a failed
            run, not a crash.

        The adapter must only ever target a lab account/host the operator owns and
        has written authorization to test.
        """
        raise NotImplementedError(
            "Connect an authorized, rate-limited authentication-test lab adapter here."
        )

    def _analysis_summary(self, profile: ProfileResult) -> str:
        return (
            "Brute-force simulation: the agent proposed a conservative attempt rate "
            "for an authorized account-lockout test, from observed logon telemetry."
        )
