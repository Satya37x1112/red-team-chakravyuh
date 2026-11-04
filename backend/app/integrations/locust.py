"""Locust load-test adapter — the real DDoS driver behind `locust_file_path`.

This is the one integration with a real action path, so it is deliberately
narrow and fail-closed, matching the repo's safety boundary:

  * It does nothing unless LOCUST_ENABLED=true AND an operator-authored
    locustfile (LOCUST_FILE_PATH) AND a target (LOCUST_TARGET_URL) are set.
  * It only ever drives the operator's own locustfile against the one
    configured target — never an arbitrary host from a request.
  * Users / spawn-rate / duration are hard-capped by config (see config.py); a
    request can lower them but never exceed the caps.
  * It runs Locust headless as a subprocess (no shell) and returns parsed stats.

Run only against a machine you own or are authorized to test, on the isolated
lab network.
"""
from __future__ import annotations

import json
import os
from typing import Any

from ..config import settings
from .base import Integration, IntegrationStatus


def _locust_version() -> str | None:
    try:
        from importlib.metadata import version

        return version("locust")
    except Exception:
        return None


class LocustIntegration(Integration):
    name = "locust"
    title = "Locust Load Test"
    category = "load-test"
    repo = "locust-master"

    def status(self) -> IntegrationStatus:
        ver = _locust_version()
        bin_path = self._which("locust")
        if ver is None and bin_path is None:
            return self._unavailable(
                "Locust is not installed. `pip install locust` to enable the real "
                "load-test driver; the DDoS module stays simulation-only until then.",
            )
        file_ok = bool(settings.locust_file_path) and os.path.isfile(settings.locust_file_path)
        detail = {
            "version": ver,
            "binary": bin_path,
            "enabled": settings.locust_enabled,
            "locustfile": settings.locust_file_path or None,
            "locustfile_present": file_ok,
            "target_url": settings.locust_target_url or None,
            "caps": {
                "max_users": settings.locust_max_users,
                "max_spawn_rate": settings.locust_max_spawn_rate,
                "max_run_seconds": settings.locust_max_run_seconds,
            },
        }
        if not settings.locust_enabled:
            return self._ok(
                "Locust is installed but the runner is disabled. Set LOCUST_ENABLED=true "
                "(plus LOCUST_FILE_PATH and LOCUST_TARGET_URL) to arm it.",
                runnable=False,
                **detail,
            )
        if not file_ok:
            return self._ok(
                "Locust enabled but LOCUST_FILE_PATH is missing or not a file.",
                runnable=False,
                **detail,
            )
        if not settings.locust_target_url:
            return self._ok(
                "Locust enabled but LOCUST_TARGET_URL (the authorized target) is not set.",
                runnable=False,
                **detail,
            )
        return self._ok("Armed — operator locustfile and authorized target configured.", runnable=True, **detail)

    def preconditions(self) -> str | None:
        """Return a human reason the runner can't fire, or None if it can."""
        st = self.status()
        if not st.available:
            return st.reason
        if not st.detail.get("runnable"):
            return st.reason
        return None

    def run(self, *, users: int | None = None, spawn_rate: int | None = None, run_seconds: int | None = None) -> dict[str, Any]:
        """Drive the configured locustfile headless against the configured target.

        Caller-supplied values are clamped down to the configured caps; they can
        never raise them. Returns Locust's end-of-run JSON stats.
        """
        blocked = self.preconditions()
        if blocked:
            raise RuntimeError(blocked)

        u = max(1, min(users or settings.locust_max_users, settings.locust_max_users))
        r = max(1, min(spawn_rate or settings.locust_max_spawn_rate, settings.locust_max_spawn_rate))
        t = max(1, min(run_seconds or settings.locust_max_run_seconds, settings.locust_max_run_seconds))

        cmd = [
            self._which("locust") or "locust",
            "-f", settings.locust_file_path,
            "--host", settings.locust_target_url,
            "--headless",
            "-u", str(u),
            "-r", str(r),
            "-t", f"{t}s",
            "--json",
            "--only-summary",
        ]
        # Give the process a little slack beyond the run window to flush summary.
        proc = self._run(cmd, timeout=t + 30)
        stats: Any = None
        parse_error = None
        if proc.stdout.strip():
            try:
                stats = json.loads(proc.stdout)
            except json.JSONDecodeError as exc:
                parse_error = f"could not parse Locust JSON summary: {exc}"
        return {
            "params": {"users": u, "spawn_rate": r, "run_seconds": t, "target": settings.locust_target_url},
            "exit_code": proc.returncode,
            "stats": stats,
            "parse_error": parse_error,
            "stderr_tail": "\n".join(proc.stderr.splitlines()[-20:]) if proc.stderr else "",
        }
