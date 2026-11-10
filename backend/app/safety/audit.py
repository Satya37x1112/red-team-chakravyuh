"""Audit logging for the execution-control layer.

Every authorization decision and lifecycle milestone is written to the
``audit_records`` table (see models.AuditRecord), reusing the existing DB — no
second database layer. Secrets are masked on the way in, so a password, API key,
token, or wordlist value can never land in the audit trail even if a caller
accidentally passes one.
"""
from __future__ import annotations

import logging
from typing import Any

from ..db import SessionLocal

log = logging.getLogger(__name__)

# Keys whose values are redacted anywhere they appear in an audit payload.
_SECRET_KEYS = {
    "password", "passwd", "pass", "pass_masked", "secret", "api_key", "apikey",
    "openrouter_api_key", "token", "authorization", "credential", "credentials",
    "winrm_password", "passlist", "userlist", "passwords", "usernames", "wordlist",
    "mock_passwords", "mock_usernames",
}
_REDACTED = "«redacted»"


def mask_secrets(value: Any) -> Any:
    """Recursively redact secret-looking keys in dicts/lists. Pure, no mutation."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if isinstance(k, str) and k.lower() in _SECRET_KEYS:
                out[k] = _REDACTED
            else:
                out[k] = mask_secrets(v)
        return out
    if isinstance(value, (list, tuple)):
        return [mask_secrets(v) for v in value]
    return value


# Audit event types (stable strings for querying).
REQUESTED = "EXECUTION_REQUESTED"
VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
GATEWAY_APPROVED = "GATEWAY_APPROVED"
GATEWAY_REJECTED = "GATEWAY_REJECTED"
EXECUTION_STARTED = "EXECUTION_STARTED"
EXECUTION_COMPLETED = "EXECUTION_COMPLETED"
EXECUTION_FAILED = "EXECUTION_FAILED"
EXECUTION_TIMED_OUT = "EXECUTION_TIMED_OUT"
KILLSWITCH_ENGAGED = "KILLSWITCH_ENGAGED"
KILLSWITCH_RESET = "KILLSWITCH_RESET"
CANCEL_REQUESTED = "CANCEL_REQUESTED"
CANCEL_CONFIRMED = "CANCEL_CONFIRMED"
CANCEL_FAILED = "CANCEL_FAILED"
# Recon routes (blackbox probe + SOC-signature) — outside the Gateway/Registry but
# audited centrally for execution identity + outcome.
RECON_PROBE = "RECON_PROBE"
RECON_SOC_ACTIVITY = "RECON_SOC_ACTIVITY"


def audit(
    event_type: str,
    *,
    execution_id: str | None = None,
    scenario_id: str | None = None,
    module: str | None = None,
    target: str | None = None,
    decision: str | None = None,
    reason: str | None = None,
    policy_id: str | None = None,
    payload: dict | None = None,
) -> None:
    """Persist one audit record. Never raises into the caller."""
    from ..models import AuditRecord  # local import to avoid import cycles

    safe_payload = mask_secrets(payload or {})
    db = SessionLocal()
    try:
        db.add(
            AuditRecord(
                event_type=event_type,
                execution_id=execution_id,
                scenario_id=scenario_id,
                module=module,
                target=target,
                decision=decision,
                reason=(reason or "")[:2000],
                policy_id=policy_id,
                payload=safe_payload,
            )
        )
        db.commit()
    except Exception as exc:  # audit must never break the request
        db.rollback()
        log.warning("audit write failed (%s): %s", event_type, exc)
    finally:
        db.close()
