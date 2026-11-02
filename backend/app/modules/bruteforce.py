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

    # Obviously-synthetic weak passwords for a lab wordlist. These are generic
    # example strings used in security training — never real or leaked creds, and
    # never used against any service. Display-only.
    _MOCK_PASSWORDS = [
        "Password123!", "Welcome1", "Summer2024!", "P@ssw0rd", "changeme",
        "admin123", "letmein", "Qwerty123", "Company@2024", "Winter2025!",
    ]

    def _suggest_mock_wordlist(self, telemetry: Telemetry, size_hint: int) -> dict:
        """Suggest a MOCK (synthetic) wordlist shaped by observed state.

        Grounded in telemetry — OS flavour and the observed account name drive the
        candidate usernames — but every value is synthetic and for display only.
        Nothing here is written to a usable file or sent to any service.
        """
        os_name = (telemetry.os_name or "").lower()
        if "windows" in os_name:
            usernames = ["Administrator", "Guest", "labadmin", "svc-backup"]
        elif "linux" in os_name:
            usernames = ["root", "admin", "labuser", "svc"]
        else:
            usernames = ["admin", "user", "test"]
        # Include the observed local account (their own lab host) as realistic context.
        if telemetry.logged_in_user:
            account = telemetry.logged_in_user.split("\\")[-1]
            if account and account not in usernames:
                usernames.insert(0, account)
        # More observed logon activity -> a slightly larger suggested wordlist.
        logon_ids = {4624, 4625}
        observed = len([e for e in telemetry.windows_events if e.event_id in logon_ids])
        pw_count = max(3, min(len(self._MOCK_PASSWORDS), (size_hint // 5) + 3 + observed // 5))
        passwords = self._MOCK_PASSWORDS[:pw_count]
        preview = [f"{u}:{p}" for u in usernames[:2] for p in passwords[:3]]
        return {
            "usernames": usernames,
            "passwords": passwords,
            "size": len(usernames) * len(passwords),
            "preview": preview,
            "note": "SYNTHETIC mock wordlist — display only, never used against any service.",
        }

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
        wordlist = self._suggest_mock_wordlist(telemetry, rate)
        series = [
            {"minute": i + 1, "attempts": rate,
             "lockouts": (rate * (i + 1)) // lockout_threshold - (rate * i) // lockout_threshold}
            for i in range(window_min)
        ]
        return ExecutionResult(
            mode="simulation",
            summary=(f"Simulated {attempts} auth attempts over {window_min} min at {rate}/min; "
                     f"{simulated_lockouts} lockouts modelled against a {wordlist['size']}-entry "
                     f"synthetic wordlist (no credentials sent)."),
            metrics={
                "simulated_attempt_rate": rate,
                "simulated_window_minutes": window_min,
                "simulated_attempts": attempts,
                "simulated_lockouts": simulated_lockouts,
                "simulated_successful_logins": simulated_success,
                "grounded_on_observed_logon_events": observed_logons,
                "mock_wordlist_size": wordlist["size"],
                "mock_usernames": wordlist["usernames"],
                "mock_passwords": wordlist["passwords"],
                "mock_wordlist_preview": wordlist["preview"],
                "mock_wordlist_note": wordlist["note"],
            },
            series=series,
        )

    def _analysis_summary(self, profile: ProfileResult) -> str:
        return (
            "Brute-force simulation: the agent proposed a conservative attempt rate "
            "for an authorized account-lockout test, from observed logon telemetry."
        )
