"""Deterministic execution policy.

Pure, AI-independent rules that answer four questions for a module:

  * Is the module enabled?            (module_enabled)
  * Is its real adapter available?    (integration_available)
  * Is a target authorized?           (is_target_authorized / authorized_targets)
  * What are the clamped parameters?  (clamp_params)

Everything here reads from ``settings`` (config.py) and the adapters' own
``status()``. It NEVER reads from or trusts a plan's requested caps — the caps
are the configured ones, full stop. The AI cannot change anything in this file
by crafting a plan.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import settings
from .plan_schema import ExecutionParams, ModuleId


@dataclass(frozen=True)
class ModuleCaps:
    """The authoritative hard caps for a module (from config, never from a plan)."""

    max_run_seconds: int
    # brute force
    max_tasks: int | None = None
    # ddos
    max_users: int | None = None
    max_spawn_rate: int | None = None


def caps_for(module: ModuleId) -> ModuleCaps:
    if module is ModuleId.bruteforce:
        return ModuleCaps(
            max_run_seconds=settings.hydra_max_run_seconds,
            max_tasks=settings.hydra_max_tasks,
        )
    if module is ModuleId.ddos:
        return ModuleCaps(
            max_run_seconds=settings.locust_max_run_seconds,
            max_users=settings.locust_max_users,
            max_spawn_rate=settings.locust_max_spawn_rate,
        )
    # rat_related and anything else: no caps defined => not runnable.
    return ModuleCaps(max_run_seconds=0)


def module_enabled(module: ModuleId) -> bool:
    if module is ModuleId.bruteforce:
        return bool(settings.hydra_enabled)
    if module is ModuleId.ddos:
        return bool(settings.locust_enabled)
    return False  # rat_related: not implemented in this section


def integration_available(module: ModuleId) -> tuple[bool, str]:
    """Ask the real adapter whether it is present/runnable, honestly."""
    try:
        if module is ModuleId.bruteforce:
            from ..integrations.hydra import HydraIntegration

            st = HydraIntegration().status()
            return bool(st.available), st.reason
        if module is ModuleId.ddos:
            from ..integrations.locust import LocustIntegration

            st = LocustIntegration().status()
            return bool(st.available), st.reason
    except Exception as exc:  # fail closed on any adapter error
        return False, f"adapter status check failed: {exc}"
    return False, f"module '{module.value}' has no execution adapter in this section"


def _split_allowlist(raw: str) -> set[str]:
    return {t.strip() for t in raw.split(",") if t.strip()}


def authorized_targets(module: ModuleId) -> set[str]:
    """The explicit set of targets this module may run against.

    = the module's single configured target (Hydra target / Locust target URL)
    PLUS any entries in SAFETY_TARGET_ALLOWLIST. Nothing else is authorized.
    """
    allow = _split_allowlist(settings.safety_target_allowlist)
    if module is ModuleId.bruteforce and settings.hydra_target:
        allow.add(settings.hydra_target.strip())
    if module is ModuleId.ddos and settings.locust_target_url:
        allow.add(settings.locust_target_url.strip())
    return allow


def is_target_authorized(module: ModuleId, target: str) -> bool:
    return target.strip() in authorized_targets(module)


def clamp_params(module: ModuleId, requested: ExecutionParams, requested_duration: int | None) -> dict:
    """Return the validated, clamped-DOWN parameters actually permitted.

    A request can only lower a value; it can never exceed a configured cap. The
    result is what the Gateway hands to the adapter — defence in depth, since the
    adapter clamps again independently.
    """
    caps = caps_for(module)
    out: dict[str, int] = {}

    # Duration: the smaller of (requested params.run_seconds, requested_duration,
    # cap). Defaults to the cap when nothing is requested.
    wanted_secs = [v for v in (requested.run_seconds, requested_duration) if v is not None]
    run_seconds = min([*wanted_secs, caps.max_run_seconds]) if wanted_secs else caps.max_run_seconds
    out["run_seconds"] = max(1, min(run_seconds, caps.max_run_seconds))

    if module is ModuleId.bruteforce:
        assert caps.max_tasks is not None
        tasks = requested.tasks if requested.tasks is not None else caps.max_tasks
        out["tasks"] = max(1, min(tasks, caps.max_tasks))
    elif module is ModuleId.ddos:
        assert caps.max_users is not None and caps.max_spawn_rate is not None
        users = requested.users if requested.users is not None else caps.max_users
        spawn = requested.spawn_rate if requested.spawn_rate is not None else caps.max_spawn_rate
        out["users"] = max(1, min(users, caps.max_users))
        out["spawn_rate"] = max(1, min(spawn, caps.max_spawn_rate))

    return out


def max_concurrent_executions() -> int:
    return max(1, int(settings.safety_max_concurrent_executions))
