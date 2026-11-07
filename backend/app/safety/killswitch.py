"""Unified kill switch.

One authority over whether the range will accept new executions, and the single
mechanism that actually stops in-flight managed work:

  engage():  mark STOPPING -> signal every active registry record ->
             terminate every managed child process group (SIGTERM, grace,
             SIGKILL) -> record outcomes -> mark CANCELLED -> mark STOPPED.
  reset():   requires an explicit admin token; clears the halt so new
             executions are accepted again.

It is the source of truth for ``is_engaged()``; the orchestrator's ``halted``
property delegates here, and the Gateway consults it, so a single engage covers
BOTH the simulation path and the real integration path.

Idempotent: repeated engage() is safe; it re-sweeps for any newly-tracked
process and returns a fresh report. It never terminates a process the
application did not launch (see process.py).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from ..config import settings
from . import audit, process
from .registry import ExecState, registry


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class KillReport:
    engaged: bool
    engaged_at: Optional[str]
    reason: str
    processes_terminated: list[dict] = field(default_factory=list)
    processes_failed: list[dict] = field(default_factory=list)
    executions_cancelled: list[str] = field(default_factory=list)
    sessions_terminated: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "engaged": self.engaged,
            "engaged_at": self.engaged_at,
            "reason": self.reason,
            "processes_terminated": self.processes_terminated,
            "processes_failed": self.processes_failed,
            "executions_cancelled": self.executions_cancelled,
            "sessions_terminated": self.sessions_terminated,
        }


class KillSwitch:
    def __init__(self) -> None:
        self._engaged = False
        self._engaged_at: Optional[datetime] = None
        self._reason = ""
        self._lock = threading.RLock()
        # Optional extra terminators (e.g. the orchestrator's sim-session killer).
        self._terminators: list[Callable[[], list[str]]] = []

    # --- state ---------------------------------------------------------------

    def is_engaged(self) -> bool:
        with self._lock:
            return self._engaged

    def register_terminator(self, fn: Callable[[], list[str]]) -> None:
        """Register a callback invoked on engage (returns ids it terminated)."""
        with self._lock:
            if fn not in self._terminators:
                self._terminators.append(fn)

    def state(self) -> dict:
        with self._lock:
            return {
                "engaged": self._engaged,
                "engaged_at": self._engaged_at.isoformat() if self._engaged_at else None,
                "reason": self._reason,
                "active_executions": registry.active_count(),
                "tracked_processes": process.active_processes(),
            }

    # --- engage / reset ------------------------------------------------------

    def engage(self, reason: str = "operator kill switch") -> KillReport:
        """Halt the range and stop all managed work. Idempotent."""
        grace = float(settings.killswitch_grace_seconds)
        with self._lock:
            self._engaged = True
            if self._engaged_at is None:
                self._engaged_at = _now()
            self._reason = reason

            # 1) Signal active registry records (so status reflects intent).
            active = registry.list(active_only=True)
            for rec in active:
                registry.request_cancel(rec.execution_id)

        # 2) Terminate managed child process groups (outside the lock; may block
        #    up to the grace period).
        outcomes = process.terminate_all(grace_seconds=grace)
        terminated = [o.__dict__ for o in outcomes if o.stopped]
        failed = [o.__dict__ for o in outcomes if not o.stopped]

        # 3) Mark cancelled executions terminal and record the outcome per record.
        cancelled_ids: list[str] = []
        for rec in registry.list(active_only=True):
            stopped_ok = any(o.execution_id == rec.execution_id and o.stopped for o in outcomes)
            had_proc = any(o.execution_id == rec.execution_id for o in outcomes)
            try:
                if had_proc and not stopped_ok:
                    registry.transition(rec.execution_id, ExecState.FAILED,
                                        error="process could not be terminated by kill switch")
                    audit.audit(audit.CANCEL_FAILED, execution_id=rec.execution_id,
                                module=rec.module, reason="SIGKILL did not confirm termination")
                else:
                    registry.transition(rec.execution_id, ExecState.CANCELLED)
                    cancelled_ids.append(rec.execution_id)
                    audit.audit(audit.CANCEL_CONFIRMED, execution_id=rec.execution_id, module=rec.module)
            except Exception:
                pass

        # 4) Run any registered extra terminators (e.g. simulation sessions).
        sessions_terminated: list[str] = []
        for fn in list(self._terminators):
            try:
                ids = fn()
                if ids:
                    sessions_terminated.extend(ids)
            except Exception:
                pass

        report = KillReport(
            engaged=True,
            engaged_at=self._engaged_at.isoformat() if self._engaged_at else None,
            reason=reason,
            processes_terminated=terminated,
            processes_failed=failed,
            executions_cancelled=cancelled_ids,
            sessions_terminated=sessions_terminated,
        )
        audit.audit(
            audit.KILLSWITCH_ENGAGED,
            reason=reason,
            payload={
                "terminated": len(terminated),
                "failed": len(failed),
                "executions_cancelled": cancelled_ids,
            },
        )
        return report

    def reset(self, token: str | None) -> tuple[bool, str]:
        """Re-arm the range. Requires the configured admin token.

        Fail-closed: if SAFETY_ADMIN_TOKEN is unset, reset is refused (there is
        no unauthenticated reset path).
        """
        configured = (settings.safety_admin_token or "").strip()
        if not configured:
            return False, ("Reset refused: SAFETY_ADMIN_TOKEN is not configured. Set it in "
                           ".env to enable authorized reset (no unauthenticated reset exists).")
        if not token or token != configured:
            audit.audit(audit.KILLSWITCH_RESET, decision="rejected", reason="invalid admin token")
            return False, "Reset refused: invalid admin token."
        with self._lock:
            self._engaged = False
            self._engaged_at = None
            self._reason = ""
        audit.audit(audit.KILLSWITCH_RESET, decision="approved", reason="authorized reset")
        return True, "Range re-armed."


kill_switch = KillSwitch()
