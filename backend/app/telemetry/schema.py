"""The normalized telemetry shape the rest of the app consumes.

Every field is optional. A collector that cannot read a value leaves it as
None — callers must treat None as "unavailable", never substitute a number.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ProcessInfo(BaseModel):
    pid: int
    name: str
    username: str | None = None
    cpu_percent: float | None = None
    memory_mb: float | None = None


class NetworkInterface(BaseModel):
    name: str
    addresses: list[str] = Field(default_factory=list)
    is_up: bool | None = None


class NetworkConnection(BaseModel):
    laddr: str | None = None
    raddr: str | None = None
    status: str | None = None
    pid: int | None = None


class WindowsEvent(BaseModel):
    time_created: str | None = None
    event_id: int | None = None
    channel: str | None = None  # Security, System, ...
    provider: str | None = None
    message: str | None = None


class Telemetry(BaseModel):
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "none"
    available: bool = False
    error: str | None = None

    hostname: str | None = None
    os_name: str | None = None
    logged_in_user: str | None = None
    uptime_seconds: float | None = None

    cpu_percent: float | None = None
    memory_percent: float | None = None
    memory_total_mb: float | None = None
    disk_percent: float | None = None

    processes: list[ProcessInfo] = Field(default_factory=list)
    process_count: int | None = None
    interfaces: list[NetworkInterface] = Field(default_factory=list)
    connections: list[NetworkConnection] = Field(default_factory=list)
    windows_events: list[WindowsEvent] = Field(default_factory=list)

    @classmethod
    def unavailable(cls, source: str, error: str) -> "Telemetry":
        return cls(source=source, available=False, error=error)
