"""Scenario Context Manager.

Collects and organises everything the centralized planner is allowed to reason
over, with honest provenance labels. Reuses the existing telemetry service,
safety policy, and execution registry — it introduces no new data source.

Hard honesty rules:
  * Telemetry is labelled by SCOPE: 'windows_target' (remote WinRM), 'kali_host'
    (local psutil — the attacker box, NEVER the target), or 'unavailable'.
  * Missing telemetry is reported as unavailable, never as zero-valued metrics.
  * The planner may read this context but may NOT change caps, allowlists, or
    kill-switch state (those live in policy/config/killswitch).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import settings
from ..safety import policy
from ..safety.killswitch import kill_switch
from ..safety.plan_schema import ModuleId
from ..telemetry.service import service

# Static capability descriptions (what each module does + its real status source).
_MODULE_CAPABILITIES: dict[str, dict[str, str]] = {
    "bruteforce": {
        "title": "Authentication / credential testing",
        "engine": "THC-Hydra",
        "description": "Bounded authentication testing against an authorized login service.",
    },
    "ddos": {
        "title": "Controlled service-load testing",
        "engine": "Locust",
        "description": "Bounded concurrent load against an authorized web service to observe availability.",
    },
    "rat_related": {
        "title": "Remote-access / UBA (reserved)",
        "engine": "n/a",
        "description": "NOT implemented in this section; the planner must not select it.",
    },
}


def _telemetry_view() -> dict[str, Any]:
    """An honest, scope-labelled view of the latest telemetry snapshot."""
    snap = service.latest
    if snap is None or not snap.available:
        reason = (snap.error if snap else None) or "no telemetry source configured"
        return {
            "scope": "unavailable",
            "available": False,
            "source": snap.source if snap else settings.telemetry_source,
            "note": f"Telemetry unavailable: {reason}. Not substituting any values.",
            "metrics": None,
        }
    # Available: label the scope by source so Kali host is never passed off as the target.
    if snap.source == "winrm":
        scope, note = "windows_target", "Remote Windows target telemetry over authorized WinRM."
    elif snap.source == "local":
        scope, note = "kali_host", "Kali ATTACKER host telemetry (psutil) — NOT the Windows target."
    else:
        scope, note = "unavailable", "Unrecognised telemetry source; treating as unavailable."
    return {
        "scope": scope,
        "available": scope != "unavailable",
        "source": snap.source,
        "note": note,
        "metrics": {
            "hostname": snap.hostname,
            "os_name": snap.os_name,
            "cpu_percent": snap.cpu_percent,
            "memory_percent": snap.memory_percent,
            "disk_percent": snap.disk_percent,
            "process_count": snap.process_count,
        },
    }


def _modules_view() -> list[dict[str, Any]]:
    out = []
    for mid in (ModuleId.bruteforce, ModuleId.ddos, ModuleId.rat_related):
        cap = _MODULE_CAPABILITIES[mid.value]
        if mid is ModuleId.rat_related:
            enabled, available, reason = False, False, "reserved; not implemented in this section"
            targets: list[str] = []
        else:
            enabled = policy.module_enabled(mid)
            available, reason = policy.integration_available(mid)
            targets = sorted(policy.authorized_targets(mid))
        out.append({
            "module": mid.value,
            "title": cap["title"],
            "engine": cap["engine"],
            "description": cap["description"],
            "enabled": enabled,
            "adapter_available": available,
            "status_reason": reason,
            "authorized_targets": targets,
            "caps": _caps_view(mid),
        })
    return out


def _caps_view(mid: ModuleId) -> dict[str, Any]:
    c = policy.caps_for(mid)
    d: dict[str, Any] = {"max_run_seconds": c.max_run_seconds}
    if c.max_tasks is not None:
        d["max_tasks"] = c.max_tasks
    if c.max_users is not None:
        d["max_users"] = c.max_users
    if c.max_spawn_rate is not None:
        d["max_spawn_rate"] = c.max_spawn_rate
    return d


@dataclass
class ScenarioContext:
    objective: str
    scenario_id: str
    module_hint: str | None
    modules: list[dict[str, Any]]
    telemetry: dict[str, Any]
    history: list[dict[str, Any]] = field(default_factory=list)
    safety: dict[str, Any] = field(default_factory=dict)

    def authorized_target_for(self, module: str) -> str | None:
        """The first authorized target for a module, or None. The AI NEVER picks
        a target freely — it is bound to this authorized scope."""
        for m in self.modules:
            if m["module"] == module and m["authorized_targets"]:
                return m["authorized_targets"][0]
        return None

    def runnable_modules(self) -> list[str]:
        return [m["module"] for m in self.modules
                if m["enabled"] and m["adapter_available"] and m["authorized_targets"]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "scenario_id": self.scenario_id,
            "module_hint": self.module_hint,
            "modules": self.modules,
            "telemetry": self.telemetry,
            "history": self.history,
            "safety": self.safety,
        }


def build_context(
    objective: str,
    *,
    scenario_id: str,
    module_hint: str | None = None,
    history: list[dict[str, Any]] | None = None,
) -> ScenarioContext:
    return ScenarioContext(
        objective=objective,
        scenario_id=scenario_id,
        module_hint=module_hint,
        modules=_modules_view(),
        telemetry=_telemetry_view(),
        history=history or [],
        safety={
            "kill_switch_engaged": kill_switch.is_engaged(),
            "max_feedback_iterations": settings.ai_max_feedback_iterations,
            "note": "Caps, allowlists, and kill-switch state are deterministic and NOT AI-controllable.",
        },
    )
