"""SQLAlchemy models.

telemetry_snapshots holds the real collected values with timestamps — this is
the ground truth the agent reasons over. Nothing in here is fabricated; a
missing metric is stored as JSON null.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AttackKind(str, enum.Enum):
    ddos = "ddos"
    bruteforce = "bruteforce"
    ratuba = "ratuba"


class SessionState(str, enum.Enum):
    """Agent lifecycle state machine."""

    DISCOVER = "DISCOVER"
    PROFILE = "PROFILE"
    PLAN = "PLAN"
    PREPARE = "PREPARE"
    OBSERVE = "OBSERVE"
    ADAPT = "ADAPT"
    ANALYZE = "ANALYZE"
    RESULT = "RESULT"
    KILLED = "KILLED"
    FAILED = "FAILED"


class Target(Base):
    """An authorized lab host. address is a host-only / RFC1918 lab address."""

    __tablename__ = "targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(120))
    os_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role_label: Mapped[str] = mapped_column(String(60), default="target")
    authorized: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    snapshots: Mapped[list["TelemetrySnapshot"]] = relationship(back_populates="target")
    sessions: Mapped[list["AttackSession"]] = relationship(back_populates="target")


class TelemetrySnapshot(Base):
    """One poll of real state from a target. `data` is the full normalized blob."""

    __tablename__ = "telemetry_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    target_id: Mapped[str] = mapped_column(ForeignKey("targets.id"))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    source: Mapped[str] = mapped_column(String(20))  # local | winrm | none
    available: Mapped[bool] = mapped_column(default=True)

    # Headline metrics pulled out for quick querying; null when unavailable.
    hostname: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    memory_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    disk_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    process_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    data: Mapped[dict] = mapped_column(JSON, default=dict)

    target: Mapped["Target"] = relationship(back_populates="snapshots")


class AttackSession(Base):
    __tablename__ = "attack_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    label: Mapped[str] = mapped_column(String(80))  # e.g. RT-2026-0142
    kind: Mapped[AttackKind] = mapped_column(Enum(AttackKind))
    target_id: Mapped[str] = mapped_column(ForeignKey("targets.id"))
    state: Mapped[SessionState] = mapped_column(Enum(SessionState), default=SessionState.DISCOVER)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    target: Mapped["Target"] = relationship(back_populates="sessions")
    events: Mapped[list["AgentEvent"]] = relationship(back_populates="session", order_by="AgentEvent.created_at")


class AgentEvent(Base):
    """One lifecycle transition / WebSocket event, persisted for the audit trail."""

    __tablename__ = "agent_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("attack_sessions.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    event_type: Mapped[str] = mapped_column(String(60))  # DISCOVERY_STARTED, ...
    phase: Mapped[str | None] = mapped_column(String(30), nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    session: Mapped["AttackSession"] = relationship(back_populates="events")


class AttackResult(Base):
    """Final analysis for a session: what the agent concluded from real observations."""

    __tablename__ = "attack_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("attack_sessions.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    summary: Mapped[str] = mapped_column(Text, default="")
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision: Mapped[dict] = mapped_column(JSON, default=dict)   # the AGENT DECISION blob
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)   # ANALYSIS blob


class IntegrationArtifact(Base):
    """One persisted output from an external-tool integration.

    This is the central store for everything the integrations produce — a CALDERA
    ATT&CK analysis, a Locust load-test result, a vervet coverage/describe, a
    PentestGPT run summary — so the Operations Center can show it all in one place.
    `payload` holds the full structured output; `summary` is a one-line digest.
    """

    __tablename__ = "integration_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    integration: Mapped[str] = mapped_column(String(40), index=True)  # caldera | locust | vervet | pentestgpt
    kind: Mapped[str] = mapped_column(String(40))  # analysis | load_test | describe | run
    title: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditRecord(Base):
    """One auditable decision or lifecycle milestone from the execution-control
    layer (Section 2). Payloads are secret-masked before they are written here
    (see app/safety/audit.py) — no plaintext password, API key, token, or
    credential list is ever stored."""

    __tablename__ = "audit_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)  # GATEWAY_APPROVED, ...
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    scenario_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    module: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(20), nullable=True)  # approved | rejected
    reason: Mapped[str] = mapped_column(Text, default="")
    policy_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)  # already secret-masked


class SimulationMetric(Base):
    """A single synthetic metric produced by a module's SIMULATION execute().

    These are generated in-memory from the real telemetry snapshot — no network,
    credential, or process activity is involved. Grounded, not fabricated: each
    value is derived from observed state (e.g. simulated source count scaled by
    real CPU/memory load)."""

    __tablename__ = "simulation_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("attack_sessions.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    kind: Mapped[AttackKind] = mapped_column(Enum(AttackKind))
    name: Mapped[str] = mapped_column(String(80))
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(30), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
