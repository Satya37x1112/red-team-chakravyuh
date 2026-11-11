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
    NetworkProbe,
    PortState,
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


# --- blackbox (agentless, IP-only) telemetry ---------------------------------

# Well-known TCP services for labelling probed ports (display only).
_WELL_KNOWN = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns", 80: "http",
    110: "pop3", 135: "msrpc", 139: "netbios-ssn", 143: "imap", 443: "https",
    445: "smb", 1433: "mssql", 3306: "mysql", 3389: "rdp", 5432: "postgresql",
    5985: "winrm", 5986: "winrm-ssl", 8080: "http-alt", 8443: "https-alt",
}


def _probe_port(host: str, port: int, timeout: float) -> tuple[bool, float | None, str]:
    """TCP-connect one port. Returns (open, latency_ms, note). No data is sent."""
    import socket
    import time

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    start = time.monotonic()
    try:
        s.connect((host, port))
        return True, round((time.monotonic() - start) * 1000, 1), "open"
    except ConnectionRefusedError:
        return False, round((time.monotonic() - start) * 1000, 1), "refused"
    except (OSError, Exception):  # timeout / filtered / unreachable
        return False, None, "no-response"
    finally:
        try:
            s.close()
        except OSError:
            pass


def _http_probe(host: str, port: int, https: bool, timeout: float) -> tuple[int | None, str | None]:
    """Best-effort HTTP(S) HEAD-like GET for status + Server banner. Honest on failure."""
    import urllib.error
    import urllib.request

    scheme = "https" if https else "http"
    url = f"{scheme}://{host}:{port}/"
    ctx = None
    if https:
        import ssl
        ctx = ssl._create_unverified_context()  # lab target may have a self-signed cert
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "chakravyuh-probe"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:  # noqa: S310
            return resp.status, resp.headers.get("Server")
    except urllib.error.HTTPError as exc:
        return exc.code, (exc.headers.get("Server") if exc.headers else None)
    except Exception:
        return None, None


def authorize_blackbox_target(target: str) -> tuple[bool, str]:
    """Deterministic, fail-closed authorization for a blackbox probe target.

    Address policy (no DNS is ever performed — IPv4 literals only):
      * must parse as an IPv4 address (hostnames / IPv6 / malformed are rejected);
      * must be RFC1918 private (public / global IPs are rejected);
      * loopback is rejected unless BLACKBOX_ALLOW_LOOPBACK is set (tests only);
      * must appear in the dedicated BLACKBOX_ALLOWLIST (kept separate from the
        attack-execution target policy).
    Returns (authorized, reason-if-not). No socket is opened here.
    """
    import ipaddress

    try:
        ip = ipaddress.IPv4Address(target)  # rejects hostnames, IPv6, and malformed; no DNS
    except (ipaddress.AddressValueError, ValueError):
        return False, (f"BLACKBOX_TARGET '{target}' is not a valid IPv4 literal "
                       "(hostnames and DNS resolution are not allowed).")
    if ip.is_loopback:
        if not settings.blackbox_allow_loopback:
            return False, "Loopback target is not allowed outside isolated test fixtures."
    elif ip.is_global or not ip.is_private:
        return False, (f"BLACKBOX_TARGET '{target}' is a public/non-private IP; only RFC1918 "
                       "private lab addresses are allowed.")
    if target not in settings.blackbox_allowlist_set:
        return False, (f"BLACKBOX_TARGET '{target}' is not in BLACKBOX_ALLOWLIST — refused "
                       "(fail-closed). Add the authorized lab IP to BLACKBOX_ALLOWLIST.")
    return True, ""

def run_probe(target: str):
    """Run the agentless TCP-connect probe against an ALREADY-AUTHORIZED target.
    IP only, no credentials, nothing installed on the target. Returns Telemetry."""
    import time
    from datetime import datetime, timezone

    timeout = max(0.2, min(settings.blackbox_timeout_seconds, 10.0))
    budget = max(0.05, min(settings.blackbox_total_budget_seconds, 300.0))
    ports = settings.blackbox_port_list

    probe = NetworkProbe(target=target, probed_at=datetime.now(timezone.utc).isoformat(),
                         ports_total=len(ports))
    latencies: list[float] = []
    host_responded = False
    started = time.monotonic()
    probed = 0
    for port in ports:
        if time.monotonic() - started > budget:
            probe.complete = False   # ran out of budget; remaining ports are UNPROBED (not closed)
            break
        is_open, latency, note = _probe_port(target, port, timeout)
        probed += 1
        if note in ("open", "refused"):
            host_responded = True
        if latency is not None:
            latencies.append(latency)
        if is_open:
            probe.open_ports.append(port)
        probe.ports.append(PortState(
            port=port, open=is_open, service=_WELL_KNOWN.get(port), latency_ms=latency,
        ))
    probe.ports_probed = probed
    probe.reachable = host_responded
    probe.latency_ms = round(min(latencies), 1) if latencies else None

    if settings.blackbox_http and (time.monotonic() - started) < budget:
        for p in (80, 8080):
            if p in probe.open_ports:
                probe.http_status, probe.http_server = _http_probe(target, p, False, timeout)
                break
        if probe.http_status is None and 443 in probe.open_ports:
            probe.http_status, probe.http_server = _http_probe(target, 443, True, timeout)

    t = Telemetry(source="blackbox", available=True)
    t.hostname = target
    t.network = probe
    return t


def _tailnet_peer_ips() -> set[str]:
    """Current tailnet peer IPv4s from `tailscale status` (empty on any failure)."""
    import subprocess
    try:
        out = subprocess.run(["tailscale", "status"], capture_output=True, text=True, timeout=8)
        ips: set[str] = set()
        for line in out.stdout.splitlines():
            tok = line.split()
            if tok and tok[0].count(".") == 3:
                ips.add(tok[0])
        return ips
    except Exception:
        return set()


def _default_route_subnet():
    """The live shared/default-route IPv4 subnet (the hotspot/LAN Kali is on), or None."""
    import ipaddress, re, subprocess
    try:
        r = subprocess.run(["ip", "-o", "-4", "route", "show", "default"],
                           capture_output=True, text=True, timeout=3)
        parts = r.stdout.split()
        dev = parts[parts.index("dev") + 1] if "dev" in parts else None
        if not dev:
            return None
        a = subprocess.run(["ip", "-o", "-4", "addr", "show", "dev", dev],
                           capture_output=True, text=True, timeout=3)
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+/\d+)", a.stdout)
        return ipaddress.ip_network(m.group(1), strict=False) if m else None
    except Exception:
        return None


def prohibited_networks() -> set:
    """Subnets that recon/discovery may NEVER target: configured prohibited CIDRs
    PLUS the live shared/default-route subnet (so we never scan the Wi-Fi/hotspot
    Kali itself is attached to, with third-party devices on it)."""
    import ipaddress
    nets = set()
    for tok in (settings.discovery_prohibited_subnets or "").split(","):
        tok = tok.strip()
        if tok:
            try:
                nets.add(ipaddress.ip_network(tok, strict=False))
            except Exception:
                pass
    shared = _default_route_subnet()
    if shared is not None:
        nets.add(shared)
    return nets


def authorize_recon_target(target: str) -> tuple[bool, str]:
    """Fail-closed authorization for an on-demand recon probe entered in the UI.

    Allows ONLY: a valid IPv4 that is (a) RFC1918 private lab space, OR (b) a
    current Tailscale PEER in the CGNAT range 100.64.0.0/10 (i.e. one of your own
    tailnet devices). PUBLIC/global IPs are always rejected, so the dashboard can
    never be pointed at an arbitrary internet host. This is non-destructive recon;
    the operator entering the IP is the explicit per-run authorization (audited)."""
    import ipaddress
    target = (target or "").strip()
    try:
        ip = ipaddress.IPv4Address(target)
    except (ipaddress.AddressValueError, ValueError):
        return False, f"'{target}' is not a valid IPv4 literal (no hostnames/DNS/IPv6)."
    if ip.is_loopback:
        return False, "Loopback is not a valid recon target."
    # Prohibited subnets (shared hotspot/LAN) are rejected BEFORE the RFC1918 allow.
    # Fail closed if policy evaluation raises.
    try:
        for net in prohibited_networks():
            if ip in net:
                return False, (f"'{target}' is in a prohibited subnet ({net}); shared "
                               f"hotspot/LAN networks are not scannable.")
    except Exception:
        return False, "authorization policy evaluation failed (fail-closed)."
    if ip.is_private:
        return True, ""  # RFC1918 lab space
    # Tailscale CGNAT range: allow only if it is an actual current tailnet peer.
    if ipaddress.IPv4Address("100.64.0.0") <= ip <= ipaddress.IPv4Address("100.127.255.255"):
        if target in _tailnet_peer_ips():
            return True, ""
        return False, f"'{target}' is in the Tailscale range but is not a current tailnet peer."
    return False, f"'{target}' is a public/non-lab IP; only RFC1918 or your tailnet peers may be probed."


def probe_on_demand(target: str):
    """Authorize + probe a UI-supplied target. Returns Telemetry (unavailable on refusal)."""
    ok, reason = authorize_recon_target(target)
    if not ok:
        return Telemetry.unavailable("blackbox", reason)
    return run_probe(target.strip())



class BlackboxSource(TelemetrySource):
    """Agentless external probe of the target from Kali — IP only, no credentials,
    nothing installed on the target. Reports reachability / open ports / latency /
    HTTP banner. It CANNOT see inside the host, so CPU/RAM stay unavailable.

    Fail-closed: the target is authorized (IPv4 + RFC1918 + allowlist) BEFORE any
    socket is opened, and a total time budget bounds the whole sweep."""

    name = "blackbox"

    def collect(self) -> Telemetry:
        import time
        from datetime import datetime, timezone

        target = settings.blackbox_target.strip()
        if not target:
            return Telemetry.unavailable("blackbox", "BLACKBOX_TARGET not configured (set an authorized lab IPv4).")

        # Authorize BEFORE opening any socket — fail closed if not authorized.
        ok, reason = authorize_blackbox_target(target)
        if not ok:
            return Telemetry.unavailable("blackbox", reason)

        return run_probe(target)


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
    return {"local": LocalSource, "winrm": WinRMSource, "blackbox": BlackboxSource}.get(
        settings.telemetry_source, NullSource
    )()
