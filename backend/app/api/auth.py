"""REST API endpoints for Authentication Testing and Password Auditing.

Includes:
- RockYou wordlist discovery and metadata
- Format identification for cryptographic hashes
- Bounded offline password hash auditing
- Controlled live authentication validation against authorized lab targets
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..agent.orchestrator import orchestrator
from ..integrations.hydra import HydraIntegration
from ..safety import audit, policy
from ..safety.killswitch import kill_switch
from ..safety.plan_schema import ModuleId
from ..services.hash_audit import hash_auditor, identify_hash_formats
from ..services.wordlist import wordlist_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


class IdentifyHashRequest(BaseModel):
    hash: str = Field(min_length=1, max_length=256)


class OfflineAuditRequest(BaseModel):
    hash: str = Field(min_length=1, max_length=256)
    algorithm: str | None = None
    max_candidates: int | None = Field(default=100_000, ge=1, le=500_000)
    timeout_seconds: float | None = Field(default=30.0, ge=1.0, le=120.0)


class LiveAuthValidateRequest(BaseModel):
    target: str = Field(min_length=1, max_length=255)
    service: str = Field(default="smb", max_length=20)
    account: str = Field(default="labuser", min_length=1, max_length=64)
    passwords: list[str] | None = Field(default=None)
    port: int | None = Field(default=None, ge=1, le=65535)


@router.get("/rockyou/status")
def rockyou_status() -> dict[str, Any]:
    """Retrieve RockYou wordlist availability and metadata without exposing entries."""
    meta = wordlist_service.get_metadata(force_refresh=True)
    return meta


@router.post("/identify-hash")
def identify_hash(req: IdentifyHashRequest) -> dict[str, Any]:
    """Identify matching cryptographic hash algorithms based on format and length."""
    h = req.hash.strip()
    detected = identify_hash_formats(h)
    return {
        "hash_length": len(h),
        "detected_algorithms": detected,
        "is_supported": len(detected) > 0,
        "supported_algorithms": ["NTLM", "MD5", "SHA-1", "SHA-256", "SHA-512"],
    }


@router.post("/offline-audit")
def offline_password_audit(req: OfflineAuditRequest) -> dict[str, Any]:
    """Perform bounded offline password auditing against authorized password hashes."""
    if kill_switch.is_engaged():
        raise HTTPException(423, "Kill switch is engaged; range is halted.")

    try:
        result = hash_auditor.audit(
            target_hash=req.hash,
            algorithm=req.algorithm,
            max_candidates=req.max_candidates or 100_000,
            timeout_seconds=req.timeout_seconds or 30.0,
            cancel_check=lambda: kill_switch.is_engaged(),
        )
        return result
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Offline auditing error: {exc}") from exc


_FORBIDDEN_LIVE_ACCOUNTS = {"administrator", "root", "system", "krbtgt"}


@router.post("/live-validate")
def live_auth_validate(req: LiveAuthValidateRequest) -> dict[str, Any]:
    """Execute bounded live authentication validation against the designated Windows target.

    Hard security bounds:
      - Bounded by Central Safety Gateway: requires authorized target allowlist match.
      - Disallowed against administrative accounts (Administrator, root, SYSTEM).
      - Maximum 3 attempts per approved account per run.
      - Stops immediately on success or lockout warning.
    """
    if kill_switch.is_engaged():
        raise HTTPException(423, "Kill switch is engaged; the range is halted.")

    # Safety check: test account only
    if req.account.strip().lower() in _FORBIDDEN_LIVE_ACCOUNTS:
        raise HTTPException(400, f"Account '{req.account}' is administrative. Live testing is restricted to dedicated test accounts.")

    # Target allowlist validation
    if not policy.is_target_authorized(ModuleId.bruteforce, req.target):
        raise HTTPException(
            423,
            f"Target '{req.target}' is not in the authorized allowlist for 'bruteforce'. "
            f"Configured authorized targets: {list(policy.authorized_targets(ModuleId.bruteforce)) or 'none'}"
        )

    # Clean service string (ssh, smb, rdp, http-get, etc.)
    svc = req.service.strip().lower()
    allowed_services = {"smb", "ssh", "rdp", "http-get", "ftp", "winrm"}
    if svc not in allowed_services:
        raise HTTPException(400, f"Service '{req.service}' not supported for live validation. Allowed: {sorted(allowed_services)}")

    hydra = HydraIntegration()
    st = hydra.status()
    if not st.available:
        raise HTTPException(503, f"Hydra binary unavailable: {st.reason}")

    # Clamping candidate passwords strictly to max 3
    clamped_passwords = (req.passwords or [])[:3]

    try:
        result = hydra.validate_live_auth(
            target=req.target.strip(),
            service=svc,
            account=req.account.strip(),
            passwords=clamped_passwords,
            port=req.port,
            max_attempts=3,
            run_seconds=30,
        )

        audit_id = audit.audit(
            event_type="LIVE_AUTH_VALIDATION",
            module="bruteforce",
            target=req.target.strip(),
            decision="completed" if result.get("authenticated") else "rejected",
            reason=f"Live auth validation ({svc}://{req.target}) - {result.get('stop_reason')}",
            payload={
                "service": svc,
                "account_masked": result.get("account_masked"),
                "attempt_count": result.get("attempt_count"),
                "authenticated": result.get("authenticated"),
                "stop_reason": result.get("stop_reason"),
                "outcome": result.get("outcome"),
            },
        )
        result["audit_reference"] = audit_id
        return result

    except Exception as exc:
        raise HTTPException(500, f"Live authentication test error: {exc}") from exc
