"""REST API endpoints for Operator-Controlled Remote Data Transfer.

Provides endpoints to:
  - Check Windows receiver connectivity and authentication status
  - Perform authenticated file transfers with pre/post SHA-256 verification
  - List approved operator transfer files
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..safety import policy
from ..safety.killswitch import kill_switch
from ..safety.plan_schema import ModuleId
from ..services.transfer import DEFAULT_MAX_FILE_BYTES, transfer_service

router = APIRouter(prefix="/api/transfer", tags=["transfer"])


class ReceiverCheckRequest(BaseModel):
    target_url: str = Field(min_length=1, max_length=255)
    auth_token: str | None = None


class TransferSendRequest(BaseModel):
    file_path: str = Field(min_length=1, max_length=512)
    target_url: str = Field(min_length=1, max_length=255)
    auth_token: str = Field(min_length=1, max_length=256)
    destination_filename: str | None = Field(default=None, max_length=120)


@router.post("/receiver/check")
def check_receiver(req: ReceiverCheckRequest) -> dict[str, Any]:
    """Test reachability and authentication with the Windows-side receiving service."""
    if kill_switch.is_engaged():
        raise HTTPException(423, "Kill switch is engaged; range is halted.")

    # Target allowlist validation via central Safety Gateway policy
    target_clean = req.target_url.strip()
    # Strip protocol & port to check host/IP
    host_match = target_clean.replace("http://", "").replace("https://", "").split(":")[0]
    if not (
        policy.is_target_authorized(ModuleId.rat_related, target_clean)
        or policy.is_target_authorized(ModuleId.rat_related, host_match)
    ):
        raise HTTPException(
            423,
            f"Target URL '{target_clean}' is not in the authorized allowlist for 'rat_related'. "
            f"Authorized targets: {list(policy.authorized_targets(ModuleId.rat_related)) or 'none'}",
        )

    return transfer_service.check_receiver(target_clean, req.auth_token)


@router.get("/files")
def list_transferrable_files() -> list[dict[str, Any]]:
    """List operator-approved files available on Kali for lab transfer demonstration."""
    candidates_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../tools"))
    files: list[dict[str, Any]] = []

    if os.path.isdir(candidates_dir):
        for entry in os.scandir(candidates_dir):
            if entry.is_file() and not entry.name.startswith("."):
                size = entry.stat().st_size
                if size <= DEFAULT_MAX_FILE_BYTES:
                    files.append({
                        "name": entry.name,
                        "path": entry.path,
                        "size_bytes": size,
                    })

    # Also include a sample demo file if list is empty
    sample_file = os.path.join(candidates_dir, "sample_transfer_artifact.txt")
    if not os.path.exists(sample_file):
        try:
            with open(sample_file, "w", encoding="utf-8") as f:
                f.write(
                    "CYBER CHAKRAVYUH — Authorized Laboratory Transfer Artifact\n"
                    "Integrity Verification Payload (SHA-256 Tested)\n"
                )
            files.append({
                "name": "sample_transfer_artifact.txt",
                "path": sample_file,
                "size_bytes": os.path.getsize(sample_file),
            })
        except OSError:
            pass

    return files


@router.post("/send")
def send_file_transfer(req: TransferSendRequest) -> dict[str, Any]:
    """Execute authenticated file transfer with SHA-256 integrity verification."""
    if kill_switch.is_engaged():
        raise HTTPException(423, "Kill switch is engaged; data transfer is blocked.")

    # Target allowlist validation via central Safety Gateway policy
    target_clean = req.target_url.strip()
    host_match = target_clean.replace("http://", "").replace("https://", "").split(":")[0]
    if not (
        policy.is_target_authorized(ModuleId.rat_related, target_clean)
        or policy.is_target_authorized(ModuleId.rat_related, host_match)
    ):
        raise HTTPException(
            423,
            f"Target URL '{target_clean}' is not in the authorized allowlist for 'rat_related'. "
            f"Authorized targets: {list(policy.authorized_targets(ModuleId.rat_related)) or 'none'}",
        )

    try:
        result = transfer_service.transfer_file(
            local_path=req.file_path,
            target_url=target_clean,
            auth_token=req.auth_token,
            custom_filename=req.destination_filename,
        )
        return result
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Transfer execution failed: {exc}") from exc
