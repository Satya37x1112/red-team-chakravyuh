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

_ADAPTER_NAME = {
    ModuleId.bruteforce: "hydra",
    ModuleId.ddos: "locust",
    ModuleId.rat_related: "remote_access",
}


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


def _evaluate_simulation(plan: ExecutionPlan, policy_id: str, *, dry_run: bool) -> GatewayDecision:
    """Authorize a DDoS **simulation** (no network traffic).

    It still passes through the same safety spine — kill switch, parameter caps,
    concurrency, Execution Registry, audit — but SKIPS the real-tool checks
    (module-enabled / adapter-available / target-allowlist) because it contacts
    nothing. The approved record is bound to the dedicated ``locust_sim`` adapter,
    so a simulation can never invoke the real Locust adapter.
    """
    # A. kill switch still blocks new work (even simulated).
    if kill_switch.is_engaged():
        return _reject(plan, "Kill switch is engaged; the range is halted.")

    sim_adapters = {
        ModuleId.ddos: "locust_sim",
        ModuleId.bruteforce: "bruteforce_sim",
        ModuleId.rat_related: "ratuba_sim",
    }
    sim_adapter = sim_adapters.get(plan.module, "generic_sim")

    # F. clamp the requested knobs DOWN to the module caps.
    validated = policy.clamp_params(plan.module, plan.params, plan.requested_duration_seconds)
    validated["simulated"] = True

    if dry_run:
        if registry.active_count() >= policy.max_concurrent_executions():
            return _reject(plan, "Concurrency limit reached; too many active executions.")
        return GatewayDecision(
            approved=True, reason="Simulation would be approved (dry run).", policy_id=policy_id,
            timestamp=_now_iso(), module=plan.module.value, target=plan.requested_target,
            execution_id=None, adapter=sim_adapter, validated_parameters=validated,
        )

    with _APPROVAL_LOCK:
        if registry.active_count() >= policy.max_concurrent_executions():
            return _reject(plan, "Concurrency limit reached; too many active executions.")
        rec = ExecutionRecord(
            scenario_id=plan.scenario_id,
            module=plan.module.value,
            adapter=sim_adapter,
            target=plan.requested_target,
            source=plan.source.value,
            validated_parameters=validated,
        )
        registry.create(rec)
        registry.transition(rec.execution_id, ExecState.VALIDATING)
    decision = GatewayDecision(
        approved=True, reason="Simulation approved within policy (no network traffic).",
        policy_id=policy_id, timestamp=_now_iso(), module=plan.module.value,
        target=plan.requested_target, execution_id=rec.execution_id, adapter=rec.adapter,
        validated_parameters=validated,
    )
    registry.transition(rec.execution_id, ExecState.APPROVED, gateway_decision=decision.as_dict())
    audit.audit(
        audit.GATEWAY_APPROVED, execution_id=rec.execution_id, scenario_id=plan.scenario_id,
        module=plan.module.value, target=plan.requested_target, decision="approved",
        reason=decision.reason, policy_id=policy_id,
        payload={"validated_parameters": validated, "source": plan.source.value, "simulation": True},
    )
    return decision


def evaluate(plan: ExecutionPlan, *, dry_run: bool = False) -> GatewayDecision:
    """Evaluate a plan and, if approved, create its APPROVED registry record.

    dry_run=True runs every authorization check but creates NO registry record
    (execution_id stays None) — for a safe plan preview that cannot be executed.
    """
    policy_id = f"{POLICY_VERSION}:{plan.module.value}"
    try:
        # Demonstration simulation (no network traffic) takes a dedicated path
        # that still enforces the kill switch, caps, concurrency, registry + audit.
        if getattr(plan, "simulate", False):
            return _evaluate_simulation(plan, policy_id, dry_run=dry_run)

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

        # D2. operation allowlist — for modules that take an operation identifier
        # (remote access), it must be one of the hardcoded approved operations.
        # The AI/API never supplies a command string; only an approved id runs.
        if policy.requires_operation(plan.module):
            if not policy.is_operation_allowed(plan.module, plan.params.operation):
                return _reject(
                    plan,
                    f"Operation '{plan.params.operation}' is not in the approved allowlist for "
                    f"'{plan.module.value}' (allowed: {', '.join(policy.approved_operations(plan.module))}).",
                )

        # F. clamp parameters DOWN to configured caps
        validated = policy.clamp_params(plan.module, plan.params, plan.requested_duration_seconds)

        # Dry run: all checks passed; report approval WITHOUT reserving a record.
        if dry_run:
            if registry.active_count() >= policy.max_concurrent_executions():
                return _reject(plan, "Concurrency limit reached; too many active executions.")
            return GatewayDecision(
                approved=True, reason="Plan would be approved (dry run).", policy_id=policy_id,
                timestamp=_now_iso(), module=plan.module.value, target=plan.requested_target,
                execution_id=None, adapter=_ADAPTER_NAME[plan.module], validated_parameters=validated,
            )

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
