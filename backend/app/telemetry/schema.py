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


class PortState(BaseModel):
    """One probed TCP port on the target (blackbox telemetry)."""
    port: int
    open: bool
    service: str | None = None       # best-effort well-known service name
    latency_ms: float | None = None


class NetworkProbe(BaseModel):
    """Agentless, IP-only observation of the target from Kali — no creds, no
    install. This is an EXTERNAL view; it says nothing about the host's insides."""
    target: str | None = None
    reachable: bool = False
    latency_ms: float | None = None  # fastest observed connect latency
    open_ports: list[int] = Field(default_factory=list)
    ports: list[PortState] = Field(default_factory=list)
    http_status: int | None = None
    http_server: str | None = None
    probed_at: str | None = None


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
    # Blackbox (agentless, IP-only) external observation of the target. Present
    # only when TELEMETRY_SOURCE=blackbox.
    network: NetworkProbe | None = None

    @classmethod
    def unavailable(cls, source: str, error: str) -> "Telemetry":
        return cls(source=source, available=False, error=error)
