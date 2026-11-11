"""Network Discovery & Target Selection Service.

Provides:
  1. Active network-interface and subnet enumeration with safe categorization.
  2. Tailnet peer discovery via `tailscale status --json` (default scope).
  3. Bounded, strictly authorized lab-subnet TCP-connect discovery (disabled by default).
  4. Scope validation enforcing strict rejection of public IPs, loopback, and the
     shared hotspot subnet (10.81.189.0/24).
  5. Target Inventory management with explicit Target Selection and fail-closed
     authorization verification (discovered != authorized).
  6. Execution Registry and Unified Kill Switch integration at every step.
  7. Centralized audit logging for discovery milestones and target selection.
"""
from __future__ import annotations

import enum
import ipaddress
import logging
import socket
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import psutil

from ..config import settings
from ..db import SessionLocal
from ..models import Target
from ..safety import audit
from ..safety.killswitch import kill_switch
from ..safety.registry import ExecState, ExecutionRecord, registry
from ..telemetry.collector import _tailnet_peer_ips, authorize_recon_target

log = logging.getLogger(__name__)

# Strictly disallowed subnets that must never be scanned
DISALLOWED_SUBNETS = [
    "10.81.189.0/24",    # Operator shared hotspot network
    "127.0.0.0/8",       # Loopback
    "0.0.0.0/8",         # Broadcast / self
    "169.254.0.0/16",    # Link-local
    "224.0.0.0/4",       # Multicast
    "240.0.0.0/4",       # Reserved
    "255.255.255.255/32" # Global broadcast
]

# Permitted discovery ports and service mappings
PERMITTED_PORTS = [22, 80, 443, 445, 3389, 8080]

PORT_SERVICE_MAP: dict[int, str] = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    135: "MSRPC",
    139: "NetBIOS",
    143: "IMAP",
    389: "LDAP",
    443: "HTTPS",
    445: "SMB",
    1433: "MSSQL",
    1521: "Oracle",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    5985: "WinRM-HTTP",
    5986: "WinRM-HTTPS",
    8000: "HTTP-Alt",
    8080: "HTTP-Proxy",
    8443: "HTTPS-Alt",
}


class ScanState(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -----------------------------------------------------------------------------
# Interface & Subnet Enumeration
# -----------------------------------------------------------------------------

def enumerate_interfaces() -> list[dict[str, Any]]:
    """Enumerate all active local network interfaces with classification and scope safety."""
    interfaces: list[dict[str, Any]] = []
    
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    
    hotspot_net = ipaddress.ip_network("10.81.189.0/24")

    for iface_name, addr_list in addrs.items():
        iface_stat = stats.get(iface_name)
        is_up = iface_stat.isup if iface_stat else False
        speed = iface_stat.speed if iface_stat else 0
        mtu = iface_stat.mtu if iface_stat else 0
        
        mac = None
        ipv4_addrs = []
        
        for addr in addr_list:
            # Check MAC address
            if hasattr(psutil, "AF_LINK") and addr.family == psutil.AF_LINK:
                mac = addr.address
            elif hasattr(socket, "AF_PACKET") and addr.family == socket.AF_PACKET:
                mac = addr.address
            
            # Check IPv4
            if addr.family == socket.AF_INET and addr.address:
                ipv4_addrs.append({
                    "address": addr.address,
                    "netmask": addr.netmask,
                    "broadcast": addr.broadcast,
                })

        for ip_info in ipv4_addrs:
            ip_str = ip_info["address"]
            mask_str = ip_info.get("netmask") or "255.255.255.255"
            try:
                ip_obj = ipaddress.IPv4Address(ip_str)
                net_obj = ipaddress.IPv4Network(f"{ip_str}/{mask_str}", strict=False)
                cidr = str(net_obj)
            except Exception:
                ip_obj = None
                net_obj = None
                cidr = f"{ip_str}/32"

            # Determine category & discovery authorization
            if ip_obj and ip_obj.is_loopback:
                category = "loopback"
                auth = False
                reason = "Loopback interface is disallowed for network discovery."
            elif iface_name.startswith("tailscale") or (ip_obj and ipaddress.IPv4Address("100.64.0.0") <= ip_obj <= ipaddress.IPv4Address("100.127.255.255")):
                category = "tailnet"
                auth = True
                reason = "Tailnet peer discovery is authorized by default."
            elif net_obj and net_obj.overlaps(hotspot_net):
                category = "hotspot_disallowed"
                auth = False
                reason = "Local shared hotspot network (10.81.189.0/24) is strictly disallowed."
            elif ip_obj and ip_obj.is_private:
                category = "rfc1918_lab"
                auth = False  # Disabled by default; requires explicit operator declaration
                reason = "Dedicated lab subnet discovery is disabled by default; requires explicit declaration."
            else:
                category = "public_disallowed"
                auth = False
                reason = "Public IP ranges are strictly prohibited from scanning."

            interfaces.append({
                "interface": iface_name,
                "ip": ip_str,
                "netmask": mask_str,
                "broadcast": ip_info.get("broadcast"),
                "cidr": cidr,
                "mac": mac,
                "is_up": is_up,
                "speed_mbps": speed,
                "mtu": mtu,
                "category": category,
                "authorized_for_discovery": auth,
                "rejection_reason": reason,
            })

    return interfaces


def enumerate_subnets() -> list[dict[str, Any]]:
    """Return consolidated subnets identified from active interfaces with policy flags."""
    ifaces = enumerate_interfaces()
    subnets_map: dict[str, dict[str, Any]] = {}

    for iface in ifaces:
        cidr = iface["cidr"]
        if cidr not in subnets_map:
            subnets_map[cidr] = {
                "subnet": cidr,
                "interface": iface["interface"],
                "category": iface["category"],
                "authorized_for_discovery": iface["authorized_for_discovery"],
                "rejection_reason": iface["rejection_reason"],
                "host_ip": iface["ip"],
            }

    return list(subnets_map.values())


# -----------------------------------------------------------------------------
# Tailnet Peer Enumeration
# -----------------------------------------------------------------------------

def enumerate_tailnet_peers() -> dict[str, Any]:
    """Enumerate Tailscale peers via `tailscale status --json` with fallback."""
    peers: list[dict[str, Any]] = []
    self_info: dict[str, Any] = {}

    try:
        proc = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            import json
            data = json.loads(proc.stdout)
            
            s = data.get("Self", {})
            self_ips = s.get("TailscaleIPs", [])
            primary_self_ip = self_ips[0] if self_ips else ""
            self_info = {
                "hostname": s.get("HostName", "").rstrip("."),
                "dns_name": s.get("DNSName", "").rstrip("."),
                "tailscale_ip": primary_self_ip,
                "os": s.get("OS", ""),
                "online": s.get("Online", True),
            }

            peer_map = data.get("Peer", {})
            for _, p in peer_map.items():
                p_ips = p.get("TailscaleIPs", [])
                p_ipv4 = next((ip for ip in p_ips if "." in ip), None)
                if not p_ipv4:
                    continue

                online = bool(p.get("Online", False))
                peers.append({
                    "ip": p_ipv4,
                    "hostname": p.get("HostName", "").rstrip("."),
                    "dns_name": p.get("DNSName", "").rstrip("."),
                    "os": p.get("OS", "unknown"),
                    "online": online,
                    "last_seen": p.get("LastSeen"),
                    "reachability_status": "reachable" if online else "unreachable",
                    "discovery_source": "tailnet",
                    "authorization_status": "pending",
                })
            
            return {
                "available": True,
                "self": self_info,
                "peers": peers,
                "total_peers": len(peers),
                "error": None,
            }
    except Exception as exc:
        log.warning("tailscale status --json failed: %s; trying table fallback", exc)

    # Fallback to plain table parsing if json failed
    try:
        proc = subprocess.run(
            ["tailscale", "status"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                tok = line.split()
                if tok and tok[0].count(".") == 3:
                    ip = tok[0]
                    hostname = tok[1] if len(tok) > 1 else ip
                    os_str = tok[2] if len(tok) > 2 else "unknown"
                    peers.append({
                        "ip": ip,
                        "hostname": hostname,
                        "dns_name": f"{hostname}.tailnet",
                        "os": os_str,
                        "online": "offline" not in line.lower(),
                        "last_seen": None,
                        "reachability_status": "unreachable" if "offline" in line.lower() else "reachable",
                        "discovery_source": "tailnet",
                        "authorization_status": "pending",
                    })
            return {
                "available": True,
                "self": self_info,
                "peers": peers,
                "total_peers": len(peers),
                "error": None,
            }
    except Exception as exc2:
        return {
            "available": False,
            "self": {},
            "peers": [],
            "total_peers": 0,
            "error": f"Tailscale status unavailable: {exc2}",
        }

    return {
        "available": False,
        "self": {},
        "peers": [],
        "total_peers": 0,
        "error": "Tailscale service not responding",
    }


# -----------------------------------------------------------------------------
# Scope Policy & Validation
# -----------------------------------------------------------------------------

def validate_discovery_scope(
    mode: str,
    subnet: Optional[str] = None,
    enable_lab_subnet: bool = False,
    authorized_subnets: Optional[list[str]] = None,
) -> tuple[bool, str]:
    """Enforce fail-closed validation on discovery scope.
    
    Default: Tailnet discovery.
    Optional: Lab subnet discovery (requires explicit authorization & allowlisting).
    Rejects: Public networks, shared hotspot (10.81.189.0/24), loopbacks, and oversized ranges.
    """
    mode = (mode or "").strip().lower()
    if mode == "tailnet":
        return True, ""

    if mode == "lab_subnet":
        if not enable_lab_subnet:
            return False, "Dedicated lab-subnet discovery is disabled by default. Explicit authorization checkbox required."
        
        if not subnet or not subnet.strip():
            return False, "Subnet CIDR is required for lab-subnet discovery."
        
        subnet_clean = subnet.strip()
        try:
            net = ipaddress.ip_network(subnet_clean, strict=False)
        except ValueError:
            return False, f"'{subnet_clean}' is not a valid IP network CIDR notation (e.g. 192.168.100.0/24)."

        if net.version != 4:
            return False, "Only IPv4 subnets are supported for lab discovery."

        if not net.is_private:
            return False, f"Subnet {subnet_clean} is a public/non-RFC1918 network. Public IP scanning is strictly forbidden."

        # Reject loopback
        if net.overlaps(ipaddress.ip_network("127.0.0.0/8")):
            return False, "Loopback subnet (127.0.0.0/8) cannot be scanned."

        # Strictly reject shared hotspot network
        hotspot_net = ipaddress.ip_network("10.81.189.0/24")
        if net.overlaps(hotspot_net):
            return False, f"Subnet {subnet_clean} overlaps with the shared hotspot network (10.81.189.0/24), which is strictly disallowed."

        # Bound subnet size to max /24 (256 addresses)
        if net.prefixlen < 24:
            return False, f"Subnet scope /{net.prefixlen} is too large. Maximum permitted range is a /24 (up to 254 usable hosts)."

        # Check explicit authorized subnets list if configured
        allowed = authorized_subnets or []
        if settings.discovery_authorized_subnets:
            allowed.extend([s.strip() for s in settings.discovery_authorized_subnets.split(",") if s.strip()])
        
        if allowed:
            is_allowlisted = False
            for allowed_sub in allowed:
                try:
                    if net.subnet_of(ipaddress.ip_network(allowed_sub, strict=False)):
                        is_allowlisted = True
                        break
                except Exception:
                    pass
            if not is_allowlisted:
                return False, f"Subnet {subnet_clean} is not in the declared lab allowlist ({', '.join(allowed)})."

        return True, ""

    return False, f"Invalid discovery mode '{mode}'. Supported modes are 'tailnet' and 'lab_subnet'."


# -----------------------------------------------------------------------------
# Target Inventory Manager
# -----------------------------------------------------------------------------

class TargetInventory:
    """Concurrency-safe inventory of discovered and selected lab targets."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._targets: dict[str, dict[str, Any]] = {}

    def get_all(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._targets.values())

    def get(self, ip: str) -> Optional[dict[str, Any]]:
        with self._lock:
            return self._targets.get(ip)

    def upsert(
        self,
        ip: str,
        hostname: Optional[str] = None,
        interface: str = "unknown",
        subnet: str = "unknown",
        discovery_source: str = "manual",
        reachability_status: str = "unknown",
        detected_ports: Optional[list[int]] = None,
        services: Optional[list[dict[str, Any]]] = None,
        authorization_status: str = "pending",
        authorization_reason: str = "",
    ) -> dict[str, Any]:
        with self._lock:
            existing = self._targets.get(ip, {})
            record = {
                "ip": ip,
                "hostname": hostname or existing.get("hostname") or ip,
                "interface": interface or existing.get("interface") or "unknown",
                "subnet": subnet or existing.get("subnet") or "unknown",
                "discovery_source": discovery_source or existing.get("discovery_source") or "manual",
                "reachability_status": reachability_status or existing.get("reachability_status") or "unknown",
                "detected_ports": sorted(list(set((detected_ports or []) + (existing.get("detected_ports") or [])))),
                "services": services if services is not None else existing.get("services") or [],
                "discovery_timestamp": existing.get("discovery_timestamp") or _now_iso(),
                "authorization_status": authorization_status or existing.get("authorization_status") or "pending",
                "authorization_reason": authorization_reason or existing.get("authorization_reason") or "",
                "selected": existing.get("selected", False),
            }
            self._targets[ip] = record
            return dict(record)

    def select(self, ip: str, hostname: Optional[str] = None) -> tuple[bool, str, dict[str, Any]]:
        """Explicitly authorize and select a target. Discovered != Authorized."""
        ip = (ip or "").strip()
        ok, reason = authorize_recon_target(ip)

        with self._lock:
            existing = self._targets.get(ip)
            if not existing:
                existing = {
                    "ip": ip,
                    "hostname": hostname or ip,
                    "interface": "unknown",
                    "subnet": "unknown",
                    "discovery_source": "manual",
                    "reachability_status": "unknown",
                    "detected_ports": [],
                    "services": [],
                    "discovery_timestamp": _now_iso(),
                    "selected": False,
                }
                self._targets[ip] = existing

            if not ok:
                existing["authorization_status"] = "unauthorized"
                existing["authorization_reason"] = reason
                existing["selected"] = False
                audit.audit(
                    audit.TARGET_SELECTION_REJECTED,
                    target=ip,
                    decision="rejected",
                    reason=reason,
                    payload={"ip": ip, "reason": reason},
                )
                return False, reason, dict(existing)

            # Mark all others as unselected
            for item in self._targets.values():
                item["selected"] = False

            existing["authorization_status"] = "authorized"
            existing["authorization_reason"] = "Verified RFC1918 / Tailnet lab target"
            existing["selected"] = True

            # Sync with DB Target table so existing modules recognize it
            try:
                db = SessionLocal()
                try:
                    db_target = db.query(Target).filter(Target.address == ip).first()
                    if not db_target:
                        db_target = Target(
                            name=existing.get("hostname") or ip,
                            address=ip,
                            role_label="selected_target",
                            authorized=True,
                        )
                        db.add(db_target)
                    else:
                        db_target.authorized = True
                        db_target.name = existing.get("hostname") or db_target.name
                    db.commit()
                finally:
                    db.close()
            except Exception as db_err:
                log.warning("Failed to sync Target to DB: %s", db_err)

            audit.audit(
                audit.TARGET_SELECTED,
                target=ip,
                decision="authorized",
                reason="Target explicitly selected and verified against authorization policy",
                payload={"ip": ip, "hostname": existing.get("hostname"), "source": existing.get("discovery_source")},
            )
            return True, "Target authorized and selected successfully.", dict(existing)


target_inventory = TargetInventory()


# -----------------------------------------------------------------------------
# Discovery Scan Engine
# -----------------------------------------------------------------------------

class DiscoveryScan:
    """Represents a bounded active discovery scan task."""

    def __init__(
        self,
        scan_id: str,
        mode: str,
        subnet: Optional[str] = None,
        max_hosts: int = 64,
        timeout: float = 0.5,
    ) -> None:
        self.scan_id = scan_id
        self.mode = mode
        self.subnet = subnet
        self.max_hosts = min(max(1, max_hosts), 64)
        self.timeout = min(max(0.1, timeout), 2.0)
        
        self.state = ScanState.PENDING
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.total_hosts = 0
        self.scanned_hosts = 0
        self.current_host = ""
        self.found_hosts: list[dict[str, Any]] = []
        self.error: Optional[str] = None
        self.cancel_requested = False
        self.execution_id: Optional[str] = None
        self._thread: Optional[threading.Thread] = None

    def as_dict(self) -> dict[str, Any]:
        progress = 0.0
        if self.total_hosts > 0:
            progress = round((self.scanned_hosts / self.total_hosts) * 100, 1)
        elif self.state == ScanState.COMPLETED:
            progress = 100.0

        return {
            "scan_id": self.scan_id,
            "mode": self.mode,
            "subnet": self.subnet,
            "state": self.state.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_hosts": self.total_hosts,
            "scanned_hosts": self.scanned_hosts,
            "current_host": self.current_host,
            "found_count": len(self.found_hosts),
            "progress_percent": progress,
            "error": self.error,
            "execution_id": self.execution_id,
        }


class DiscoveryService:
    """Central service managing network discovery lifecycle and target selection."""

    def __init__(self) -> None:
        self._scans: dict[str, DiscoveryScan] = {}
        self._lock = threading.Lock()

    def get_scan(self, scan_id: str) -> Optional[DiscoveryScan]:
        with self._lock:
            return self._scans.get(scan_id)

    def cancel_scan(self, scan_id: str) -> tuple[bool, str]:
        with self._lock:
            scan = self._scans.get(scan_id)
            if not scan:
                return False, f"Scan {scan_id} not found."
            if scan.state in (ScanState.COMPLETED, ScanState.CANCELLED, ScanState.STOPPED, ScanState.FAILED):
                return False, f"Scan {scan_id} is already in terminal state {scan.state.value}."
            scan.cancel_requested = True
            scan.state = ScanState.CANCELLED
            scan.completed_at = _now_iso()

            if scan.execution_id:
                try:
                    registry.transition(scan.execution_id, ExecState.CANCELLED)
                except Exception:
                    pass

            audit.audit(
                audit.DISCOVERY_CANCELLED,
                execution_id=scan.execution_id,
                module="discovery",
                target=scan.subnet or "tailnet",
                decision="cancelled",
                reason="Operator cancelled discovery scan",
                payload={"scan_id": scan.scan_id},
            )
            return True, f"Scan {scan_id} cancelled."

    def start_scan(
        self,
        mode: str = "tailnet",
        subnet: Optional[str] = None,
        enable_lab_subnet: bool = False,
        max_hosts: int = 64,
        timeout: float = 0.5,
    ) -> tuple[bool, str, dict[str, Any]]:
        """Validate scope and trigger background discovery scan."""
        if kill_switch.is_engaged():
            return False, "Kill switch is engaged. Range is halted.", {}

        # 1. Enforce scope validation
        ok, reason = validate_discovery_scope(mode, subnet, enable_lab_subnet)
        if not ok:
            return False, reason, {}

        scan_id = str(uuid.uuid4())
        scan = DiscoveryScan(
            scan_id=scan_id,
            mode=mode,
            subnet=subnet,
            max_hosts=max_hosts,
            timeout=timeout,
        )

        # 2. Register in ExecutionRegistry
        rec = ExecutionRecord(
            scenario_id=f"discovery-{scan_id[:8]}",
            module="discovery",
            adapter="tcp_connect" if mode == "lab_subnet" else "tailnet_peer_enum",
            target=subnet or "tailnet",
            source="dashboard",
            state=ExecState.RUNNING,
        )
        registry.create(rec)
        scan.execution_id = rec.execution_id

        audit.audit(
            audit.DISCOVERY_STARTED,
            execution_id=rec.execution_id,
            module="discovery",
            target=subnet or "tailnet",
            decision="started",
            reason=f"Network discovery scan started in mode '{mode}'",
            payload={"scan_id": scan_id, "mode": mode, "subnet": subnet, "max_hosts": max_hosts},
        )

        with self._lock:
            self._scans[scan_id] = scan

        # Launch background runner thread
        t = threading.Thread(target=self._run_scan_thread, args=(scan,), daemon=True)
        scan._thread = t
        t.start()

        return True, "Discovery scan started.", scan.as_dict()

    def _run_scan_thread(self, scan: DiscoveryScan) -> None:
        scan.started_at = _now_iso()
        scan.state = ScanState.RUNNING

        try:
            if scan.mode == "tailnet":
                self._execute_tailnet_discovery(scan)
            elif scan.mode == "lab_subnet":
                self._execute_lab_subnet_discovery(scan)
            else:
                scan.error = f"Unsupported mode: {scan.mode}"
                scan.state = ScanState.FAILED

            if scan.state == ScanState.RUNNING:
                scan.state = ScanState.COMPLETED
                if scan.execution_id:
                    try:
                        registry.transition(scan.execution_id, ExecState.COMPLETED)
                    except Exception:
                        pass
                audit.audit(
                    audit.DISCOVERY_COMPLETED,
                    execution_id=scan.execution_id,
                    module="discovery",
                    target=scan.subnet or "tailnet",
                    decision="completed",
                    reason=f"Discovery completed with {len(scan.found_hosts)} hosts discovered",
                    payload={"scan_id": scan.scan_id, "found_count": len(scan.found_hosts)},
                )

        except Exception as exc:
            log.exception("Discovery scan %s failed: %s", scan.scan_id, exc)
            scan.error = str(exc)
            scan.state = ScanState.FAILED
            if scan.execution_id:
                try:
                    registry.transition(scan.execution_id, ExecState.FAILED, error=str(exc))
                except Exception:
                    pass
            audit.audit(
                audit.DISCOVERY_FAILED,
                execution_id=scan.execution_id,
                module="discovery",
                target=scan.subnet or "tailnet",
                decision="failed",
                reason=str(exc),
                payload={"scan_id": scan.scan_id, "error": str(exc)},
            )
        finally:
            scan.completed_at = _now_iso()

    def _execute_tailnet_discovery(self, scan: DiscoveryScan) -> None:
        """Tailnet peer listing + non-destructive reachability verification."""
        peer_data = enumerate_tailnet_peers()
        peers = peer_data.get("peers", [])
        scan.total_hosts = len(peers)

        for p in peers:
            if scan.cancel_requested:
                scan.state = ScanState.CANCELLED
                return
            if kill_switch.is_engaged():
                scan.state = ScanState.STOPPED
                if scan.execution_id:
                    try:
                        registry.transition(scan.execution_id, ExecState.CANCELLED)
                    except Exception:
                        pass
                audit.audit(
                    audit.DISCOVERY_STOPPED,
                    execution_id=scan.execution_id,
                    module="discovery",
                    target="tailnet",
                    decision="halted",
                    reason="Unified Kill Switch engaged during tailnet discovery",
                )
                return

            ip = p["ip"]
            scan.current_host = ip

            # Quick permitted port check for discovered peer
            open_ports = []
            service_details = []
            
            # Reachability probe
            is_reachable = p.get("online", False)
            for port in PERMITTED_PORTS:
                if kill_switch.is_engaged() or scan.cancel_requested:
                    break
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(scan.timeout)
                try:
                    res = s.connect_ex((ip, port))
                    if res == 0:
                        open_ports.append(port)
                        svc_name = PORT_SERVICE_MAP.get(port, "unknown")
                        service_details.append({
                            "port": port,
                            "service": svc_name,
                            "confidence": "high",
                        })
                        is_reachable = True
                except Exception:
                    pass
                finally:
                    s.close()

            reach_status = "reachable" if is_reachable else "unreachable"
            
            host_dict = {
                "ip": ip,
                "hostname": p.get("hostname", ip),
                "interface": "tailscale0",
                "subnet": "100.64.0.0/10",
                "discovery_source": "tailnet",
                "reachability_status": reach_status,
                "detected_ports": open_ports,
                "services": service_details,
                "discovery_timestamp": _now_iso(),
                "authorization_status": "pending",
                "authorization_reason": "Discovered tailnet peer (pending explicit selection)",
            }

            # Update inventory & scan records
            target_inventory.upsert(
                ip=ip,
                hostname=p.get("hostname"),
                interface="tailscale0",
                subnet="100.64.0.0/10",
                discovery_source="tailnet",
                reachability_status=reach_status,
                detected_ports=open_ports,
                services=service_details,
                authorization_status="pending",
                authorization_reason="Discovered tailnet peer",
            )
            scan.found_hosts.append(host_dict)
            scan.scanned_hosts += 1

    def _execute_lab_subnet_discovery(self, scan: DiscoveryScan) -> None:
        """Bounded TCP-connect scan for authorized lab subnet."""
        net = ipaddress.ip_network(scan.subnet, strict=False)
        host_list = [str(h) for h in net.hosts()][:scan.max_hosts]
        scan.total_hosts = len(host_list)

        for ip in host_list:
            if scan.cancel_requested:
                scan.state = ScanState.CANCELLED
                return
            if kill_switch.is_engaged():
                scan.state = ScanState.STOPPED
                if scan.execution_id:
                    try:
                        registry.transition(scan.execution_id, ExecState.CANCELLED)
                    except Exception:
                        pass
                audit.audit(
                    audit.DISCOVERY_STOPPED,
                    execution_id=scan.execution_id,
                    module="discovery",
                    target=scan.subnet,
                    decision="halted",
                    reason="Unified Kill Switch engaged during lab-subnet discovery",
                )
                return

            scan.current_host = ip
            open_ports = []
            service_details = []
            host_responded = False

            for port in PERMITTED_PORTS:
                if kill_switch.is_engaged() or scan.cancel_requested:
                    break
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(scan.timeout)
                try:
                    res = s.connect_ex((ip, port))
                    if res == 0:
                        open_ports.append(port)
                        svc_name = PORT_SERVICE_MAP.get(port, "unknown")
                        service_details.append({
                            "port": port,
                            "service": svc_name,
                            "confidence": "high",
                        })
                        host_responded = True
                    elif res in (111, 10061):  # ECONNREFUSED
                        # RST packet received: host is active!
                        host_responded = True
                except Exception:
                    pass
                finally:
                    s.close()

            if host_responded:
                # Attempt quick reverse hostname resolution
                host_name = ip
                try:
                    host_name = socket.gethostbyaddr(ip)[0]
                except Exception:
                    pass

                reach_status = "reachable"
                host_dict = {
                    "ip": ip,
                    "hostname": host_name,
                    "interface": "lab",
                    "subnet": str(net),
                    "discovery_source": "lab_subnet",
                    "reachability_status": reach_status,
                    "detected_ports": open_ports,
                    "services": service_details,
                    "discovery_timestamp": _now_iso(),
                    "authorization_status": "pending",
                    "authorization_reason": "Discovered in authorized lab subnet",
                }

                target_inventory.upsert(
                    ip=ip,
                    hostname=host_name,
                    interface="lab",
                    subnet=str(net),
                    discovery_source="lab_subnet",
                    reachability_status=reach_status,
                    detected_ports=open_ports,
                    services=service_details,
                    authorization_status="pending",
                    authorization_reason="Discovered in authorized lab subnet",
                )
                scan.found_hosts.append(host_dict)

            scan.scanned_hosts += 1


discovery_service = DiscoveryService()
