"""THC-Hydra adapter — the real credential-test driver behind the BruteForce module.

Like the Locust adapter, this is a real action path, so it is deliberately
narrow and fail-closed, matching the repo's safety boundary:

  * It does nothing unless HYDRA_ENABLED=true AND an authorized target
    (HYDRA_TARGET) AND an operator-provided username list (HYDRA_USERLIST_PATH)
    AND password list (HYDRA_PASSLIST_PATH) are all set.
  * It only ever runs that one list pair against that one configured target and
    service — never an arbitrary host, user, or password from a request.
  * users × passwords is hard-capped (HYDRA_MAX_ATTEMPTS); parallel tasks and
    wall-clock duration are capped too. A request can lower these but never
    raise them.
  * It runs hydra as a subprocess (no shell) with a hard timeout, exits on the
    first valid pair (-f), and returns parsed results — it never echoes the
    cracked password back to the UI.

Run only against a machine you own or are authorized to test, on the isolated
lab network.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from typing import Any

from ..config import settings
from .base import Integration, IntegrationStatus

# hydra success lines look like:
#   [22][ssh] host: 192.168.56.20   login: labadmin   password: Summer2026!
_HIT = re.compile(
    r"^\[(?P<port>\d+)\]\[(?P<service>[^\]]+)\]\s+host:\s*(?P<host>\S+)\s+"
    r"login:\s*(?P<login>\S+)\s+password:\s*(?P<password>.*)$"
)

# hydra -V attempt lines look like:
#   [ATTEMPT] target 127.0.0.1 - login "labadmin" - pass "Welcome1" - 6 of 24 [child 0] (0/0)
_ATTEMPT = re.compile(
    r'\[ATTEMPT\].*?login "(?P<login>[^"]*)" - pass "(?P<pass>[^"]*)"'
    r'(?:\s*-\s*(?P<n>\d+) of (?P<m>\d+))?'
)


def _count_lines(path: str) -> int | None:
    """Non-empty lines in a wordlist, or None if it can't be read."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return sum(1 for ln in fh if ln.strip())
    except OSError:
        return None


class HydraIntegration(Integration):
    name = "hydra"
    title = "THC-Hydra Login Cracker"
    category = "credential-test"
    repo = "thc-hydra-master"

    def status(self) -> IntegrationStatus:
        bin_path = self._which(settings.hydra_bin)
        if bin_path is None:
            return self._unavailable(
                "hydra binary not found. Build/install THC-Hydra and set HYDRA_BIN "
                "(or put `hydra` on PATH); the BruteForce module stays "
                "simulation-only until then.",
            )
        user_n = _count_lines(settings.hydra_userlist_path) if settings.hydra_userlist_path else None
        pass_n = _count_lines(settings.hydra_passlist_path) if settings.hydra_passlist_path else None
        attempts = (user_n or 0) * (pass_n or 0)
        detail: dict[str, Any] = {
            "binary": bin_path,
            "enabled": settings.hydra_enabled,
            "target": settings.hydra_target or None,
            "service": settings.hydra_service or None,
            "port": settings.hydra_port or None,
            "userlist": settings.hydra_userlist_path or None,
            "passlist": settings.hydra_passlist_path or None,
            "userlist_count": user_n,
            "passlist_count": pass_n,
            "planned_attempts": attempts or None,
            "caps": {
                "max_tasks": settings.hydra_max_tasks,
                "max_attempts": settings.hydra_max_attempts,
                "max_run_seconds": settings.hydra_max_run_seconds,
            },
        }
        if not settings.hydra_enabled:
            return self._ok(
                "hydra is installed but the runner is disabled. Set HYDRA_ENABLED=true "
                "(plus HYDRA_TARGET, HYDRA_USERLIST_PATH, HYDRA_PASSLIST_PATH) to arm it.",
                runnable=False,
                **detail,
            )
        if not settings.hydra_target:
            return self._ok(
                "hydra enabled but HYDRA_TARGET (the authorized lab host) is not set.",
                runnable=False,
                **detail,
            )
        if not (settings.hydra_userlist_path and os.path.isfile(settings.hydra_userlist_path)):
            return self._ok(
                "hydra enabled but HYDRA_USERLIST_PATH is missing or not a file.",
                runnable=False,
                **detail,
            )
        if not (settings.hydra_passlist_path and os.path.isfile(settings.hydra_passlist_path)):
            return self._ok(
                "hydra enabled but HYDRA_PASSLIST_PATH is missing or not a file.",
                runnable=False,
                **detail,
            )
        if attempts > settings.hydra_max_attempts:
            return self._ok(
                f"hydra armed but the list pair is {attempts} attempts, over the "
                f"HYDRA_MAX_ATTEMPTS cap of {settings.hydra_max_attempts}. Trim the "
                "wordlists or raise the cap.",
                runnable=False,
                **detail,
            )
        return self._ok(
            f"Armed — {settings.hydra_service}://{settings.hydra_target}, "
            f"{attempts} attempts within caps.",
            runnable=True,
            **detail,
        )

    def preconditions(self) -> str | None:
        """Return a human reason the runner can't fire, or None if it can."""
        st = self.status()
        if not st.available:
            return st.reason
        if not st.detail.get("runnable"):
            return st.reason
        return None

    def run(self, *, tasks: int | None = None, run_seconds: int | None = None) -> dict[str, Any]:
        """Run the configured list pair against the configured target.

        Caller-supplied values are clamped down to the configured caps; they can
        never raise them. Returns parsed hydra results. The cracked password
        itself is never returned to the caller — only that a pair was found and
        for which login — so the console reports a finding without surfacing the
        secret.
        """
        blocked = self.preconditions()
        if blocked:
            raise RuntimeError(blocked)

        t = max(1, min(tasks or settings.hydra_max_tasks, settings.hydra_max_tasks))
        secs = max(1, min(run_seconds or settings.hydra_max_run_seconds, settings.hydra_max_run_seconds))

        cmd = [
            self._which(settings.hydra_bin) or settings.hydra_bin,
            "-L", settings.hydra_userlist_path,
            "-P", settings.hydra_passlist_path,
            "-t", str(t),
            "-f",            # stop after the first valid pair is found
            "-V",            # verbose: emit one [ATTEMPT] line per guess (for the live feed)
        ]
        if settings.hydra_port:
            cmd += ["-s", str(settings.hydra_port)]   # non-default service port
        cmd += [
            settings.hydra_target,
            settings.hydra_service,
        ]

        timed_out = False
        stdout = ""
        stderr = ""
        returncode: int | None = None
        started = time.monotonic()
        try:
            # hydra has no self-terminating duration flag, so the subprocess
            # timeout is the enforced wall-clock bound; a little slack to flush.
            proc = self._run(cmd, timeout=secs + 15)
            stdout, stderr, returncode = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        duration = round(time.monotonic() - started, 2)

        combined = stdout + "\n" + stderr
        found: list[dict[str, Any]] = []
        notes: list[str] = []
        attempts: list[dict[str, Any]] = []   # masked per-guess feed for the UI
        total_space: int | None = None
        for raw in combined.splitlines():
            line = raw.strip()
            if not line:
                continue
            m = _HIT.match(line)
            if m:
                # Deliberately omit the password value from the returned payload.
                found.append(
                    {
                        "host": m.group("host"),
                        "port": int(m.group("port")),
                        "service": m.group("service"),
                        "login": m.group("login"),
                        "password_found": True,
                    }
                )
                continue
            a = _ATTEMPT.search(line)
            if a:
                # The tried password is shown only as its length (dots) — never the
                # value itself, consistent with never surfacing a cracked secret.
                pw = a.group("pass") or ""
                if a.group("m"):
                    total_space = int(a.group("m"))
                attempts.append(
                    {
                        "n": int(a.group("n")) if a.group("n") else len(attempts) + 1,
                        "login": a.group("login"),
                        "pass_masked": "•" * min(len(pw), 16),
                    }
                )
                continue
            if any(k in line for k in ("[ERROR]", "[WARNING]", "invalid reply", "could not connect", "does not support")):
                notes.append(line)

        # The guess that matched is the last attempt before hydra stopped (-f).
        cracked_at = attempts[-1]["n"] if (found and attempts) else None

        # Honest, human-readable outcome — especially when 0 found but hydra
        # errored (e.g. a module that can't negotiate with the target), so the
        # console never shows a bare "0 found" with no reason.
        if found:
            message = f"{len(found)} valid pair(s) found."
        elif notes:
            message = f"No valid pairs — hydra reported: {notes[-1]}"
        elif timed_out:
            message = "No valid pairs within the run-time cap (timed out)."
        else:
            message = "Completed — no valid pairs found in the list pair."

        return {
            "params": {
                "target": settings.hydra_target,
                "service": settings.hydra_service,
                "port": settings.hydra_port or None,
                "tasks": t,
                "run_seconds": secs,
            },
            "exit_code": returncode,
            "timed_out": timed_out,
            "found_count": len(found),
            "found": found,
            "message": message,
            "notes": notes[-10:],
            # Visualization payload for the dashboard's brute-force view.
            "attempts_made": len(attempts),
            "attempt_space": total_space,
            "cracked_at": cracked_at,
            "duration_seconds": duration,
            "attempt_feed": attempts[-60:],   # last N masked guesses for the live feed
            "stderr_tail": "\n".join(stderr.splitlines()[-20:]) if stderr else "",
        }
