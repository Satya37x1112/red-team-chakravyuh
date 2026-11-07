"""Managed subprocess execution and termination.

The integration adapters (Hydra, Locust, vervet, …) shell out through
``Integration._run``. This module is the single place those subprocesses are
actually launched, so that:

  * every child is started in its **own process group** (``start_new_session``),
    which lets the kill switch terminate the whole tree with one ``killpg`` —
    not just the Python handler that is waiting on it;
  * every live child is **registered** in a process table keyed by PID and
    tagged with the current execution id (via a context variable), so the
    unified kill switch can find exactly the processes a given execution spawned;
  * the call still returns a plain ``subprocess.CompletedProcess`` and still
    raises ``subprocess.TimeoutExpired`` on timeout — identical to
    ``subprocess.run`` — so the existing adapters keep working unchanged.

Nothing here knows anything about attacks; it is generic, auditable process
management. It never terminates a process it did not launch.
"""
from __future__ import annotations

import contextvars
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

# The execution id the current thread is running under, if any. The controlled
# execution path sets this (see dispatcher.execution_context); run_managed reads
# it so a spawned process can be attributed to its execution.
CURRENT_EXECUTION_ID: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_execution_id", default=None
)

_IS_POSIX = os.name == "posix"


@dataclass
class _ProcEntry:
    pid: int
    pgid: Optional[int]
    cmd: list[str]
    execution_id: Optional[str]
    started_at: float = field(default_factory=time.monotonic)
    popen: Optional[subprocess.Popen] = None


@dataclass
class TerminationOutcome:
    pid: int
    execution_id: Optional[str]
    cmd: str
    stopped: bool
    method: str          # "sigterm" | "sigkill" | "already-exited" | "error"
    detail: str = ""


class _ProcessTable:
    """Thread-safe registry of the subprocesses this application has launched."""

    def __init__(self) -> None:
        self._procs: dict[int, _ProcEntry] = {}
        self._lock = threading.Lock()

    def register(self, entry: _ProcEntry) -> None:
        with self._lock:
            self._procs[entry.pid] = entry

    def deregister(self, pid: int) -> None:
        with self._lock:
            self._procs.pop(pid, None)

    def snapshot(self) -> list[_ProcEntry]:
        with self._lock:
            return list(self._procs.values())

    def for_execution(self, execution_id: str) -> list[_ProcEntry]:
        with self._lock:
            return [e for e in self._procs.values() if e.execution_id == execution_id]


_TABLE = _ProcessTable()


# --- public introspection ----------------------------------------------------

def active_processes() -> list[dict]:
    """A redacted view of currently-tracked child processes (for status APIs)."""
    out = []
    for e in _TABLE.snapshot():
        out.append(
            {
                "pid": e.pid,
                "pgid": e.pgid,
                "execution_id": e.execution_id,
                "program": e.cmd[0] if e.cmd else None,
                "age_seconds": round(time.monotonic() - e.started_at, 1),
            }
        )
    return out


# --- launching ---------------------------------------------------------------

def run_managed(cmd: list[str], *, timeout: float = 30, cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run ``cmd`` as a managed child and return a CompletedProcess.

    Behaviourally a drop-in for ``subprocess.run(cmd, capture_output=True,
    text=True, timeout=timeout, cwd=cwd, shell=False)`` — same return type, and
    it raises ``subprocess.TimeoutExpired`` on timeout — but the child runs in
    its own process group and is registered for the lifetime of the call so the
    kill switch can reach it.
    """
    popen_kwargs: dict = dict(
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
    )
    if _IS_POSIX:
        # New session => child is its own process-group leader (pgid == pid).
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **popen_kwargs)  # noqa: S603 - no shell, fixed argv
    pgid: Optional[int] = None
    if _IS_POSIX:
        try:
            pgid = os.getpgid(proc.pid)
        except OSError:
            pgid = proc.pid
    entry = _ProcEntry(
        pid=proc.pid,
        pgid=pgid,
        cmd=list(cmd),
        execution_id=CURRENT_EXECUTION_ID.get(),
        popen=proc,
    )
    _TABLE.register(entry)
    try:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
        except subprocess.TimeoutExpired:
            # Match subprocess.run: kill the child (here: the whole group), drain,
            # then re-raise TimeoutExpired with whatever output was captured.
            _kill_group(proc, pgid, signal.SIGKILL)
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except Exception:
                stdout, stderr = "", ""
            raise subprocess.TimeoutExpired(cmd, timeout, output=stdout, stderr=stderr)
    finally:
        _TABLE.deregister(proc.pid)


# --- termination -------------------------------------------------------------

def _kill_group(proc: subprocess.Popen, pgid: Optional[int], sig: int) -> None:
    """Send ``sig`` to the child's process group (POSIX) or the child (fallback)."""
    if proc.poll() is not None:
        return
    try:
        if _IS_POSIX and pgid is not None:
            os.killpg(pgid, sig)
        else:
            proc.send_signal(sig)
    except (ProcessLookupError, OSError):
        pass


def _terminate_entry(entry: _ProcEntry, grace_seconds: float) -> TerminationOutcome:
    proc = entry.popen
    cmd_str = " ".join(entry.cmd[:3])
    if proc is None:
        return TerminationOutcome(entry.pid, entry.execution_id, cmd_str, False, "error", "no handle")
    if proc.poll() is not None:
        return TerminationOutcome(entry.pid, entry.execution_id, cmd_str, True, "already-exited")

    # Graceful first.
    _kill_group(proc, entry.pgid, signal.SIGTERM)
    deadline = time.monotonic() + max(0.1, grace_seconds)
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return TerminationOutcome(entry.pid, entry.execution_id, cmd_str, True, "sigterm")
        time.sleep(0.05)

    # Escalate only if it is still alive.
    _kill_group(proc, entry.pgid, signal.SIGKILL)
    hard_deadline = time.monotonic() + 3.0
    while time.monotonic() < hard_deadline:
        if proc.poll() is not None:
            return TerminationOutcome(entry.pid, entry.execution_id, cmd_str, True, "sigkill")
        time.sleep(0.05)

    return TerminationOutcome(
        entry.pid, entry.execution_id, cmd_str, False, "error", "still alive after SIGKILL"
    )


def terminate_execution(execution_id: str, *, grace_seconds: float = 5.0) -> list[TerminationOutcome]:
    """Terminate every tracked process belonging to one execution."""
    return [_terminate_entry(e, grace_seconds) for e in _TABLE.for_execution(execution_id)]


def terminate_all(*, grace_seconds: float = 5.0) -> list[TerminationOutcome]:
    """Terminate every tracked managed process (used by the kill switch)."""
    return [_terminate_entry(e, grace_seconds) for e in _TABLE.snapshot()]
