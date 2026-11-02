"""Real telemetry collection.

Two sources, chosen by TELEMETRY_SOURCE:

  LocalSource  — the collector runs on the Windows target itself. Uses psutil
                 for system metrics and, when pywin32 is present, reads the
                 Windows Event Log directly.
  WinRMSource  — the collector polls a remote Windows target over WinRM by
                 running read-only PowerShell and parsing the JSON it prints.

Both only READ state. Nothing here changes the target. If a value can't be
read it stays None; we never invent one. When TELEMETRY_SOURCE=none (no lab
wired yet) the collector reports available=False so the UI shows "unavailable".
"""
from __future__ import annotations

import json
import platform
from abc import ABC, abstractmethod

from ..config import settings
from .schema import (
    NetworkConnection,
    NetworkInterface,
    ProcessInfo,
    Telemetry,
    WindowsEvent,
)

TOP_PROCESS_LIMIT = 25
EVENT_LIMIT = 40


class TelemetrySource(ABC):
    name: str = "none"

    @abstractmethod
    def collect(self) -> Telemetry:
        """Return one snapshot of real state (or an unavailable marker)."""


class NullSource(TelemetrySource):
    """No lab wired. Honest 'unavailable' rather than fabricated numbers."""

    name = "none"

    def collect(self) -> Telemetry:
        return Telemetry.unavailable(
            "none",
            "No telemetry source configured (set TELEMETRY_SOURCE=local|winrm).",
        )


class LocalSource(TelemetrySource):
    """psutil-based collection on the machine the collector runs on."""

    name = "local"

    def collect(self) -> Telemetry:
        try:
            import psutil
        except ImportError:
            return Telemetry.unavailable("local", "psutil not installed")

        t = Telemetry(source="local", available=True)
        t.hostname = platform.node() or None
        t.os_name = f"{platform.system()} {platform.release()}".strip() or None

        try:
            t.uptime_seconds = max(0.0, _psutil_uptime(psutil))
        except Exception:
            t.uptime_seconds = None

        try:
            t.logged_in_user = next((u.name for u in psutil.users()), None)
        except Exception:
            t.logged_in_user = None

        # cpu_percent needs a short interval to be meaningful.
        try:
            t.cpu_percent = psutil.cpu_percent(interval=0.3)
        except Exception:
            t.cpu_percent = None

        try:
            vm = psutil.virtual_memory()
            t.memory_percent = vm.percent
            t.memory_total_mb = round(vm.total / 1_048_576, 1)
        except Exception:
            pass

        try:
            root = "C:\\" if platform.system() == "Windows" else "/"
            t.disk_percent = psutil.disk_usage(root).percent
        except Exception:
            t.disk_percent = None

        t.processes, t.process_count = _local_processes(psutil)
        t.interfaces = _local_interfaces(psutil)
        t.connections = _local_connections(psutil)
        t.windows_events = _local_windows_events()
        return t


class WinRMSource(TelemetrySource):
    """Remote read-only collection over WinRM (pywinrm)."""

    name = "winrm"

    # Read-only PowerShell: reports state, runs Get-WinEvent, changes nothing.
    PS_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
$os  = Get-CimInstance Win32_OperatingSystem
$cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
$cs  = Get-CimInstance Win32_ComputerSystem
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$procs = Get-Process | Sort-Object WS -Descending | Select-Object -First __PROC__ `
    @{N='pid';E={$_.Id}}, @{N='name';E={$_.ProcessName}}, `
    @{N='memory_mb';E={[math]::Round($_.WS/1MB,1)}}
$ifaces = Get-NetIPAddress -AddressFamily IPv4 |
    Group-Object InterfaceAlias |
    ForEach-Object { @{ name=$_.Name; addresses=@($_.Group.IPAddress) } }
$events = Get-WinEvent -FilterHashtable @{ LogName='Security'; Id=@(4624,4625,4688) } -MaxEvents __EVT__ |
    Select-Object @{N='time_created';E={$_.TimeCreated.ToString('o')}}, `
        @{N='event_id';E={$_.Id}}, @{N='channel';E={$_.LogName}}, `
        @{N='provider';E={$_.ProviderName}}, @{N='message';E={$_.Message -replace "\s+"," " }}
$mem = if ($os.TotalVisibleMemorySize) {
    [math]::Round((1 - $os.FreePhysicalMemory/$os.TotalVisibleMemorySize)*100,1) } else { $null }
@{
    hostname        = $env:COMPUTERNAME
    os_name         = $os.Caption
    logged_in_user  = $cs.UserName
    uptime_seconds  = if ($os.LastBootUpTime) { [math]::Round(((Get-Date) - $os.LastBootUpTime).TotalSeconds) } else { $null }
    cpu_percent     = $cpu
    memory_percent  = $mem
    memory_total_mb = if ($os.TotalVisibleMemorySize) { [math]::Round($os.TotalVisibleMemorySize/1024,1) } else { $null }
    disk_percent    = if ($disk.Size) { [math]::Round((1 - $disk.FreeSpace/$disk.Size)*100,1) } else { $null }
    processes       = @($procs)
    process_count   = (Get-Process).Count
    interfaces      = @($ifaces)
    windows_events  = @($events)
} | ConvertTo-Json -Depth 5 -Compress
"""

    def collect(self) -> Telemetry:
        if not settings.winrm_endpoint or not settings.winrm_password:
            return Telemetry.unavailable("winrm", "WinRM endpoint/credentials not configured")
        try:
            import winrm
        except ImportError:
            return Telemetry.unavailable("winrm", "pywinrm not installed")

        script = self.PS_SCRIPT.replace("__PROC__", str(TOP_PROCESS_LIMIT)).replace(
            "__EVT__", str(EVENT_LIMIT)
        )
        try:
            session = winrm.Session(
                f"http://{settings.winrm_endpoint}:{settings.winrm_port}/wsman",
                auth=(settings.winrm_user, settings.winrm_password),
                transport=settings.winrm_transport,
            )
            result = session.run_ps(script)
        except Exception as exc:  # network/auth failure — stay honest
            return Telemetry.unavailable("winrm", f"WinRM error: {exc}")

        if result.status_code != 0:
            err = result.std_err.decode(errors="replace")[:400]
            return Telemetry.unavailable("winrm", f"PowerShell failed: {err}")

        try:
            raw = json.loads(result.std_out.decode(errors="replace") or "{}")
        except json.JSONDecodeError as exc:
            return Telemetry.unavailable("winrm", f"could not parse PowerShell JSON: {exc}")

        return _telemetry_from_ps(raw)


# --- local helpers -----------------------------------------------------------


def _psutil_uptime(psutil) -> float:
    import time

    return time.time() - psutil.boot_time()


def _local_processes(psutil) -> tuple[list[ProcessInfo], int | None]:
    procs: list[ProcessInfo] = []
    count = None
    try:
        all_procs = list(psutil.process_iter(["pid", "name", "username", "memory_info"]))
        count = len(all_procs)
        all_procs.sort(
            key=lambda p: getattr(p.info.get("memory_info"), "rss", 0) or 0, reverse=True
        )
        for p in all_procs[:TOP_PROCESS_LIMIT]:
            mi = p.info.get("memory_info")
            procs.append(
                ProcessInfo(
                    pid=p.info["pid"],
                    name=p.info.get("name") or "?",
                    username=p.info.get("username"),
                    memory_mb=round(mi.rss / 1_048_576, 1) if mi else None,
                )
            )
    except Exception:
        pass
    return procs, count


def _local_interfaces(psutil) -> list[NetworkInterface]:
    out: list[NetworkInterface] = []
    try:
        stats = psutil.net_if_stats()
        for name, addrs in psutil.net_if_addrs().items():
            out.append(
                NetworkInterface(
                    name=name,
                    addresses=[a.address for a in addrs if getattr(a, "address", None)],
                    is_up=stats[name].isup if name in stats else None,
                )
            )
    except Exception:
        pass
    return out


def _local_connections(psutil) -> list[NetworkConnection]:
    out: list[NetworkConnection] = []
    try:
        for c in psutil.net_connections(kind="inet")[:40]:
            out.append(
                NetworkConnection(
                    laddr=f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else None,
                    raddr=f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else None,
                    status=c.status,
                    pid=c.pid,
                )
            )
    except Exception:
        pass
    return out


def _local_windows_events() -> list[WindowsEvent]:
    """Read the Security log via pywin32. No-op (empty) on non-Windows."""
    if platform.system() != "Windows":
        return []
    try:
        import win32evtlog
    except ImportError:
        return []

    events: list[WindowsEvent] = []
    try:
        handle = win32evtlog.OpenEventLog(None, "Security")
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        records = win32evtlog.ReadEventLog(handle, flags, 0)
        for rec in records[:EVENT_LIMIT]:
            events.append(
                WindowsEvent(
                    time_created=rec.TimeGenerated.Format() if rec.TimeGenerated else None,
                    event_id=rec.EventID & 0xFFFF,
                    channel="Security",
                    provider=str(rec.SourceName),
                    message=" ".join(rec.StringInserts) if rec.StringInserts else None,
                )
            )
        win32evtlog.CloseEventLog(handle)
    except Exception:
        return events
    return events


def _telemetry_from_ps(raw: dict) -> Telemetry:
    def num(key: str) -> float | None:
        v = raw.get(key)
        return float(v) if isinstance(v, (int, float)) else None

    t = Telemetry(source="winrm", available=True)
    t.hostname = raw.get("hostname")
    t.os_name = raw.get("os_name")
    t.logged_in_user = raw.get("logged_in_user")
    t.uptime_seconds = num("uptime_seconds")
    t.cpu_percent = num("cpu_percent")
    t.memory_percent = num("memory_percent")
    t.memory_total_mb = num("memory_total_mb")
    t.disk_percent = num("disk_percent")
    t.process_count = int(raw["process_count"]) if isinstance(raw.get("process_count"), (int, float)) else None

    for p in _as_list(raw.get("processes")):
        t.processes.append(
            ProcessInfo(
                pid=int(p.get("pid", 0)),
                name=str(p.get("name", "?")),
                memory_mb=p.get("memory_mb"),
            )
        )
    for i in _as_list(raw.get("interfaces")):
        t.interfaces.append(
            NetworkInterface(name=str(i.get("name", "?")), addresses=_as_list(i.get("addresses")))
        )
    for e in _as_list(raw.get("windows_events")):
        t.windows_events.append(
            WindowsEvent(
                time_created=e.get("time_created"),
                event_id=e.get("event_id"),
                channel=e.get("channel"),
                provider=e.get("provider"),
                message=e.get("message"),
            )
        )
    return t


def _as_list(value) -> list:
    """PowerShell ConvertTo-Json emits a bare object for single-item arrays."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def build_source() -> TelemetrySource:
    return {"local": LocalSource, "winrm": WinRMSource}.get(
        settings.telemetry_source, NullSource
    )()
