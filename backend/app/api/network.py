"""API routes for Network Discovery & Target Selection."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..agent.orchestrator import orchestrator
from ..safety.killswitch import kill_switch
from ..services.discovery import (
    discovery_service,
    enumerate_interfaces,
    enumerate_subnets,
    enumerate_tailnet_peers,
    target_inventory,
)

router = APIRouter(prefix="/api/network", tags=["network"])


class DiscoveryStartRequest(BaseModel):
    mode: str = Field(default="tailnet", description="Discovery mode: 'tailnet' or 'lab_subnet'")
    subnet: Optional[str] = Field(default=None, description="Lab subnet CIDR (e.g. '192.168.100.0/24')")
    enable_lab_subnet: bool = Field(default=False, description="Explicit operator checkbox to authorize lab subnet discovery")
    max_hosts: int = Field(default=64, description="Maximum number of hosts to probe (clamped to 64)")
    timeout: float = Field(default=0.5, description="Connect timeout per port in seconds")


class TargetSelectRequest(BaseModel):
    ip: str = Field(..., description="Target IPv4 literal to authorize and select")
    hostname: Optional[str] = Field(default=None, description="Optional hostname")


@router.get("/interfaces")
def get_interfaces() -> list[dict[str, Any]]:
    """Enumerate active network interfaces with classification and scope policy."""
    return enumerate_interfaces()


@router.get("/subnets")
def get_subnets() -> list[dict[str, Any]]:
    """Enumerate discovered subnets with authorization status and safety reasons."""
    return enumerate_subnets()


@router.get("/tailnet")
def get_tailnet_peers() -> dict[str, Any]:
    """Enumerate Tailscale self device and peer nodes."""
    return enumerate_tailnet_peers()


@router.post("/discovery/start")
def start_discovery(req: DiscoveryStartRequest) -> dict[str, Any]:
    """Start a bounded discovery scan (tailnet peer enumeration or dedicated lab-subnet TCP sweep)."""
    if kill_switch.is_engaged() or orchestrator.halted:
        raise HTTPException(423, "Kill switch is engaged; network operations are blocked.")

    ok, reason, scan_data = discovery_service.start_scan(
        mode=req.mode,
        subnet=req.subnet,
        enable_lab_subnet=req.enable_lab_subnet,
        max_hosts=req.max_hosts,
        timeout=req.timeout,
    )
    if not ok:
        raise HTTPException(400, detail=reason)

    return scan_data


@router.get("/discovery/{scan_id}")
def get_discovery_status(scan_id: str) -> dict[str, Any]:
    """Poll discovery scan progress, state, and metrics."""
    scan = discovery_service.get_scan(scan_id)
    if not scan:
        raise HTTPException(404, detail=f"Discovery scan '{scan_id}' not found.")
    return scan.as_dict()


@router.get("/discovery/{scan_id}/hosts")
def get_discovery_hosts(scan_id: str) -> list[dict[str, Any]]:
    """List hosts discovered by a specific scan."""
    scan = discovery_service.get_scan(scan_id)
    if not scan:
        raise HTTPException(404, detail=f"Discovery scan '{scan_id}' not found.")
    return scan.found_hosts


@router.post("/discovery/{scan_id}/cancel")
def cancel_discovery(scan_id: str) -> dict[str, Any]:
    """Cancel an active discovery scan."""
    ok, msg = discovery_service.cancel_scan(scan_id)
    if not ok:
        raise HTTPException(400, detail=msg)
    return {"message": msg, "scan_id": scan_id}


@router.get("/targets")
def list_inventory_targets() -> list[dict[str, Any]]:
    """Return all discovered and manually registered targets in the inventory."""
    return target_inventory.get_all()


@router.post("/targets/select")
def select_target(req: TargetSelectRequest) -> dict[str, Any]:
    """Explicitly authorize and select a target.
    
    Discovered does not mean authorized. This endpoint executes fail-closed
    authorization (RFC1918 or current Tailnet peer check) before marking
    the target authorized and active.
    """
    ok, reason, target_dict = target_inventory.select(req.ip, req.hostname)
    if not ok:
        raise HTTPException(400, detail=f"Target authorization rejected: {reason}")
    return {
        "status": "authorized",
        "message": reason,
        "target": target_dict,
    }
