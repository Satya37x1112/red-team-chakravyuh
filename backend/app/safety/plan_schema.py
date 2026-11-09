"""Structured execution-plan schema.

This is the contract between any *proposer* of work (today: a manual API caller;
tomorrow: the centralized AI planner) and the deterministic Safety Gateway.

Design rules that the schema enforces structurally:

  * A plan carries only *requested* parameters. It has **no field that can set,
    raise, or disable a safety cap** — caps live in policy/config, never in a
    plan — so an AI (or any caller) cannot widen limits by crafting a plan.
  * A plan **cannot authorize itself**: there is no ``approved`` / ``policy_id``
    field here. Only the Gateway produces those (see gateway.GatewayDecision).
  * ``extra="forbid"`` => unexpected fields are rejected, not silently ignored.
  * Mandatory fields missing, wrong types, or out-of-sanity-range values raise
    ``pydantic.ValidationError`` before anything reaches the Gateway.

The schema validates *shape and sanity only*. The **authoritative** limits
(per-module caps, target allowlist, module-enabled, kill-switch state) are
enforced by the Gateway, deterministically, independent of this schema and of
the AI.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

# A remote-access operation IDENTIFIER (not a command). Strict token only — no
# shell metacharacters, chaining, substitution, or whitespace can ever appear.
_OP_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,40}$")


class ModuleId(str, enum.Enum):
    bruteforce = "bruteforce"
    ddos = "ddos"
    rat_related = "rat_related"   # reserved for a future section; Gateway rejects it now


class PlanSource(str, enum.Enum):
    ai = "ai"          # produced by the centralized AI planner (future)
    manual = "manual"  # submitted by a human operator / existing API call
    system = "system"  # produced internally (e.g. a test harness)


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ExecutionParams(BaseModel):
    """Requested, best-effort parameters. The Gateway clamps these DOWN to the
    configured caps; values here are desired, never guaranteed or authoritative."""

    model_config = ConfigDict(extra="forbid")

    # Brute-force (Hydra) requested knobs.
    tasks: int | None = Field(default=None, ge=1, le=64, description="parallel connects")
    # DDoS (Locust) requested knobs.
    users: int | None = Field(default=None, ge=1, le=10_000)
    spawn_rate: int | None = Field(default=None, ge=1, le=10_000)
    # Shared.
    run_seconds: int | None = Field(default=None, ge=1, le=86_400)
    # Remote-access (RAT alternative): a hardcoded operation IDENTIFIER the
    # adapter maps to its own fixed implementation. NEVER a command string. The
    # membership check (is it an APPROVED op) is enforced by the Safety Gateway.
    operation: str | None = Field(default=None, max_length=41)

    @field_validator("operation")
    @classmethod
    def _operation_is_safe_token(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _OP_ID_RE.match(v):
            raise ValueError("operation must be a safe identifier token [a-z][a-z0-9_]* (no commands)")
        return v


class ExecutionPlan(BaseModel):
    """One proposed, bounded unit of work for a single module.

    Reusable verbatim by the future AI planner: it will construct ExecutionPlan
    objects (source=ai) exactly as a manual caller does today.
    """

    model_config = ConfigDict(extra="forbid")

    # --- identity / provenance ---
    plan_id: str = Field(default_factory=_new_id)
    scenario_id: str = Field(min_length=1, max_length=120)
    # execution_id is assigned by the system/registry, NOT the proposer. If a
    # proposer sets it, the Gateway ignores it and issues its own.
    execution_id: str | None = Field(default=None)

    module: ModuleId
    source: PlanSource = PlanSource.manual

    # Demonstration SIMULATION mode (ddos only). When True the Gateway routes the
    # approved record to the synthetic 'locust_sim' adapter, which generates NO
    # network traffic. It is a shape flag, never a cap, and cannot widen limits.
    simulate: bool = False

    # --- scope ---
    requested_target: str = Field(min_length=1, max_length=255)

    # --- requested work (never caps) ---
    params: ExecutionParams = Field(default_factory=ExecutionParams)
    requested_duration_seconds: int | None = Field(default=None, ge=1, le=86_400)

    # --- provenance / audit ---
    created_at: datetime = Field(default_factory=_now)
    reasoning: str = Field(default="", max_length=4000)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("requested_target")
    @classmethod
    def _target_no_whitespace(cls, v: str) -> str:
        v = v.strip()
        if not v or any(c.isspace() for c in v):
            raise ValueError("requested_target must be a single non-empty token (no whitespace)")
        return v

    @field_validator("metadata")
    @classmethod
    def _metadata_not_secret(cls, v: dict[str, str]) -> dict[str, str]:
        # Defence in depth: refuse obviously-sensitive metadata keys so secrets
        # never ride along inside a plan into the audit log.
        banned = {"password", "passwd", "secret", "api_key", "apikey", "token", "credential"}
        for key in v:
            if key.lower() in banned:
                raise ValueError(f"metadata key '{key}' is not allowed (possible secret)")
        return v


__all__ = ["ModuleId", "PlanSource", "ExecutionParams", "ExecutionPlan"]
