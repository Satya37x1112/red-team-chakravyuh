"""The deterministic Safety Gateway.

Independent of the AI model. Given an ExecutionPlan it answers one question —
*may this run?* — by checking, in order and fail-closed:

  A. kill-switch / operational state   (no new work while halted)
  B. module support + enabled          (bruteforce/ddos only; rat_related rejected)
  C. adapter availability              (the real tool is actually present)
  D. target authorization              (must match the configured allowlist)
  E. concurrency policy                (bounded simultaneous executions)
  F. parameter clamping                (down to configured caps, never up)

It then creates the execution's registry record and returns a GatewayDecision.
A rejected plan NEVER produces a runnable record, so it can never reach an
adapter. Any unexpected error => rejection (fail closed).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import audit, policy
from .killswitch import kill_switch
from .plan_schema import ExecutionPlan, ModuleId
from .registry import ExecState, ExecutionRecord, registry

POLICY_VERSION = "chakravyuh-safety-v1"

# Serialises the concurrency-check -> record-creation critical section so two
# simultaneous requests cannot both slip past the concurrency limit (TOCTOU).
_APPROVAL_LOCK = threading.Lock()

_ADAPTER_NAME = {ModuleId.bruteforce: "hydra", ModuleId.ddos: "locust"}


@dataclass
class GatewayDecision:
    approved: bool
    reason: str
    policy_id: str
    timestamp: str
    module: str
    target: str
    execution_id: str | None = None
    adapter: str | None = None
    validated_parameters: dict = field(default_factory=dict)

    @property
    def rejected(self) -> bool:
        return not self.approved

    def as_dict(self) -> dict:
        return {
            "approved": self.approved,
            "rejected": self.rejected,
            "reason": self.reason,
            "policy_id": self.policy_id,
            "execution_id": self.execution_id,
            "module": self.module,
            "target": self.target,
            "adapter": self.adapter,
            "validated_parameters": self.validated_parameters,
            "timestamp": self.timestamp,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reject(plan: ExecutionPlan, reason: str) -> GatewayDecision:
    policy_id = f"{POLICY_VERSION}:{plan.module.value}"
    audit.audit(
        audit.GATEWAY_REJECTED,
        scenario_id=plan.scenario_id,
        module=plan.module.value,
        target=plan.requested_target,
        decision="rejected",
        reason=reason,
        policy_id=policy_id,
        payload={"source": plan.source.value},
    )
    return GatewayDecision(
        approved=False,
        reason=reason,
        policy_id=policy_id,
        timestamp=_now_iso(),
        module=plan.module.value,
        target=plan.requested_target,
    )


def evaluate(plan: ExecutionPlan) -> GatewayDecision:
    """Evaluate a plan and, if approved, create its APPROVED registry record."""
    policy_id = f"{POLICY_VERSION}:{plan.module.value}"
    try:
        # A. operational state / kill switch
        if kill_switch.is_engaged():
            return _reject(plan, "Kill switch is engaged; the range is halted.")

        # B. module support + enabled
        if plan.module not in _ADAPTER_NAME:
            return _reject(plan, f"Module '{plan.module.value}' is not executable in this section.")
        if not policy.module_enabled(plan.module):
            return _reject(plan, f"Module '{plan.module.value}' is disabled (enable it in config to arm).")

        # C. adapter availability (honest)
        available, why = policy.integration_available(plan.module)
        if not available:
            return _reject(plan, f"Adapter unavailable: {why}")

        # D. target authorization — never trust a target supplied in the plan alone
        if not policy.is_target_authorized(plan.module, plan.requested_target):
            return _reject(
                plan,
                f"Target '{plan.requested_target}' is not in the authorized allowlist for "
                f"'{plan.module.value}'.",
            )

        # F. clamp parameters DOWN to configured caps
        validated = policy.clamp_params(plan.module, plan.params, plan.requested_duration_seconds)

        # E+create atomically: concurrency check and record creation under one lock
        # so simultaneous requests cannot both bypass the concurrency limit.
        with _APPROVAL_LOCK:
            if registry.active_count() >= policy.max_concurrent_executions():
                return _reject(plan, "Concurrency limit reached; too many active executions.")
            rec = ExecutionRecord(
                scenario_id=plan.scenario_id,
                module=plan.module.value,
                adapter=_ADAPTER_NAME[plan.module],
                target=plan.requested_target,
                source=plan.source.value,
                validated_parameters=validated,
            )
            registry.create(rec)
            registry.transition(rec.execution_id, ExecState.VALIDATING)
        decision = GatewayDecision(
            approved=True,
            reason="Plan approved within policy.",
            policy_id=policy_id,
            timestamp=_now_iso(),
            module=plan.module.value,
            target=plan.requested_target,
            execution_id=rec.execution_id,
            adapter=rec.adapter,
            validated_parameters=validated,
        )
        registry.transition(rec.execution_id, ExecState.APPROVED, gateway_decision=decision.as_dict())
        audit.audit(
            audit.GATEWAY_APPROVED,
            execution_id=rec.execution_id,
            scenario_id=plan.scenario_id,
            module=plan.module.value,
            target=plan.requested_target,
            decision="approved",
            reason=decision.reason,
            policy_id=policy_id,
            payload={"validated_parameters": validated, "source": plan.source.value},
        )
        return decision

    except Exception as exc:  # fail closed on ANY internal error
        return _reject(plan, f"Gateway internal error (fail-closed): {exc}")
