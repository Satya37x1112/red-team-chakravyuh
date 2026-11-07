"""Unified execution registry.

One concurrency-safe in-memory record of every controlled execution and its
lifecycle. The Gateway creates a record when it approves (or rejects) a plan;
the dispatcher advances it through RUNNING → COMPLETED/FAILED/…; the kill switch
flips active records to CANCELLED.

No secret ever lives here: only clamped, non-sensitive parameters, PIDs, states,
timestamps, and error strings (which callers must pre-mask).
"""
from __future__ import annotations

import enum
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


class ExecState(str, enum.Enum):
    REQUESTED = "REQUESTED"
    VALIDATING = "VALIDATING"
    APPROVED = "APPROVED"
    RUNNING = "RUNNING"
    OBSERVING = "OBSERVING"
    COMPLETED = "COMPLETED"
    # terminal / off-happy-path
    REJECTED = "REJECTED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


_TERMINAL = {
    ExecState.COMPLETED,
    ExecState.REJECTED,
    ExecState.CANCELLED,
    ExecState.FAILED,
    ExecState.TIMED_OUT,
}

# Allowed forward transitions. Any record may always move to CANCEL_REQUESTED or
# CANCELLED (kill switch) unless already terminal, and to FAILED on error.
_ALLOWED: dict[ExecState, set[ExecState]] = {
    ExecState.REQUESTED: {ExecState.VALIDATING, ExecState.REJECTED, ExecState.FAILED},
    ExecState.VALIDATING: {ExecState.APPROVED, ExecState.REJECTED, ExecState.FAILED},
    ExecState.APPROVED: {ExecState.RUNNING, ExecState.CANCEL_REQUESTED, ExecState.CANCELLED, ExecState.FAILED},
    ExecState.RUNNING: {
        ExecState.OBSERVING, ExecState.COMPLETED, ExecState.FAILED,
        ExecState.TIMED_OUT, ExecState.CANCEL_REQUESTED, ExecState.CANCELLED,
    },
    ExecState.OBSERVING: {ExecState.COMPLETED, ExecState.FAILED, ExecState.CANCEL_REQUESTED, ExecState.CANCELLED},
    ExecState.CANCEL_REQUESTED: {ExecState.CANCELLED, ExecState.FAILED, ExecState.COMPLETED},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InvalidTransition(Exception):
    pass


@dataclass
class ExecutionRecord:
    scenario_id: str
    module: str
    adapter: str
    target: str
    source: str
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: ExecState = ExecState.REQUESTED
    created_at: datetime = field(default_factory=_now)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    pid: Optional[int] = None
    cancel_requested: bool = False
    exit_code: Optional[int] = None
    error: Optional[str] = None
    gateway_decision: dict = field(default_factory=dict)
    validated_parameters: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "scenario_id": self.scenario_id,
            "module": self.module,
            "adapter": self.adapter,
            "target": self.target,
            "source": self.source,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "pid": self.pid,
            "cancel_requested": self.cancel_requested,
            "exit_code": self.exit_code,
            "error": self.error,
            "validated_parameters": self.validated_parameters,
            "gateway_decision": self.gateway_decision,
        }


class ExecutionRegistry:
    def __init__(self) -> None:
        self._records: dict[str, ExecutionRecord] = {}
        self._lock = threading.RLock()

    def create(self, record: ExecutionRecord) -> ExecutionRecord:
        with self._lock:
            self._records[record.execution_id] = record
            return record

    def get(self, execution_id: str) -> Optional[ExecutionRecord]:
        with self._lock:
            return self._records.get(execution_id)

    def list(self, *, active_only: bool = False) -> list[ExecutionRecord]:
        with self._lock:
            recs = list(self._records.values())
        if active_only:
            recs = [r for r in recs if r.state not in _TERMINAL]
        return sorted(recs, key=lambda r: r.created_at)

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for r in self._records.values() if r.state not in _TERMINAL)

    def transition(self, execution_id: str, new_state: ExecState, **updates) -> ExecutionRecord:
        """Move a record to ``new_state`` if the transition is allowed, applying
        field updates atomically. Raises InvalidTransition otherwise."""
        with self._lock:
            rec = self._records.get(execution_id)
            if rec is None:
                raise KeyError(execution_id)
            if new_state != rec.state:
                if rec.state in _TERMINAL:
                    raise InvalidTransition(f"{execution_id}: {rec.state.value} is terminal")
                if new_state not in _ALLOWED.get(rec.state, set()):
                    raise InvalidTransition(
                        f"{execution_id}: {rec.state.value} -> {new_state.value} not allowed"
                    )
                rec.state = new_state
            for k, v in updates.items():
                setattr(rec, k, v)
            if new_state == ExecState.RUNNING and rec.started_at is None:
                rec.started_at = _now()
            if new_state in _TERMINAL and rec.ended_at is None:
                rec.ended_at = _now()
            return rec

    def request_cancel(self, execution_id: str) -> Optional[ExecutionRecord]:
        """Mark a record as cancel-requested if it is still active (idempotent)."""
        with self._lock:
            rec = self._records.get(execution_id)
            if rec is None or rec.state in _TERMINAL:
                return rec
            rec.cancel_requested = True
            if rec.state in _ALLOWED and ExecState.CANCEL_REQUESTED in _ALLOWED.get(rec.state, set()):
                rec.state = ExecState.CANCEL_REQUESTED
            return rec


registry = ExecutionRegistry()
