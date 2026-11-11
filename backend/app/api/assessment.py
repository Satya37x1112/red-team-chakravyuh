"""API endpoint for One-Click Orchestrated Assessment."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..agent.orchestrator import orchestrator
from ..safety.killswitch import kill_switch
from ..services.assessment import assessment_service

router = APIRouter(prefix="/api/assessment", tags=["assessment"])


class AssessmentRunRequest(BaseModel):
    target: str = Field(..., description="Target IPv4 literal (RFC1918 or Tailnet peer)")
    password_hash: str | None = Field(default=None, description="Optional authorized hash to audit offline against RockYou")


@router.post("/run")
def run_assessment(req: AssessmentRunRequest) -> dict[str, Any]:
    """Execute the bounded, authorized assessment sequence.
    
    Sequence:
      1. Target authorization validation (fail-closed, public IPs refused -> BLOCKED).
      2. Target reachability check (if offline -> UNAVAILABLE, stops early).
      3. Non-destructive recon probe (open ports, baseline latency).
      4. Bounded purple-team SOC signatures (DDoS, Brute Force, RAT).
      5. Offline password hash audit (RockYou dictionary matching).
      6. Live tools notice (real Locust & file transfer marked 'requires setup').
      7. Central audit trail and ExecutionRegistry persistence.
    """
    if kill_switch.is_engaged() or orchestrator.halted:
        raise HTTPException(423, "Kill switch is engaged; the range is halted.")

    return assessment_service.run(
        target=req.target.strip(),
        password_hash=req.password_hash.strip() if req.password_hash else None,
    )


@router.get("/latest")
def get_latest_assessment() -> dict[str, Any] | None:
    """Return the most recently executed assessment result, if any."""
    return assessment_service.latest
