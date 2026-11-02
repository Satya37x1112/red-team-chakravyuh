"""The AttackModule abstraction.

Every step except execute() is a real, read-only operation: it looks at
telemetry and the agent's decision and produces a structured result. execute()
is deliberately NOT implemented — it raises NotImplementedError. Wiring a real,
authorized lab adapter happens outside this codebase.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..agent.decision import decide
from ..telemetry.schema import Telemetry


@dataclass
class DiscoveryResult:
    reachable: bool
    hostname: str | None
    os_name: str | None
    notes: list[str] = field(default_factory=list)


@dataclass
class ProfileResult:
    summary: str
    load_level: str  # "low" | "moderate" | "high" | "unknown"
    facts: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanResult:
    parameter: str
    value: int | None
    reasoning: str
    source: str  # "llm" | "llm_unavailable"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Observation:
    before: dict[str, Any]
    after: dict[str, Any]
    deltas: dict[str, Any]


@dataclass
class AdaptedPlan:
    changed: bool
    parameter: str
    value: int | None
    reasoning: str


@dataclass
class AnalysisReport:
    summary: str
    risk_score: float | None
    findings: list[str] = field(default_factory=list)


class AttackModule(ABC):
    """Base for all simulation modules. kind matches AttackKind in models."""

    kind: str = "base"

    # ---- real, read-only steps --------------------------------------------

    def discover(self, telemetry: Telemetry) -> DiscoveryResult:
        notes = []
        if not telemetry.available:
            notes.append(telemetry.error or "target telemetry unavailable")
        return DiscoveryResult(
            reachable=telemetry.available,
            hostname=telemetry.hostname,
            os_name=telemetry.os_name,
            notes=notes,
        )

    def profile(self, telemetry: Telemetry) -> ProfileResult:
        """Classify observed load. Subclasses add module-specific facts."""
        level = _load_level(telemetry)
        return ProfileResult(
            summary=f"Observed load: {level}",
            load_level=level,
            facts={
                "cpu_percent": telemetry.cpu_percent,
                "memory_percent": telemetry.memory_percent,
                "process_count": telemetry.process_count,
            },
        )

    def plan(self, telemetry: Telemetry) -> PlanResult:
        """Ask the AI engine for a controlled parameter from the real snapshot."""
        d = decide(self.kind, telemetry)
        return PlanResult(
            parameter=d["parameter"],
            value=d["decision"],
            reasoning=d["reasoning"],
            source="llm" if d["status"] == "ok" else "llm_unavailable",
            raw=d,
        )

    @abstractmethod
    def execute(self, plan: PlanResult):
        """NOT IMPLEMENTED. Wire an authorized lab adapter here, outside this repo."""
        raise NotImplementedError

    def observe(self, before: Telemetry, after: Telemetry) -> Observation:
        """Compare two real snapshots taken around a controlled operation."""
        b = _metrics(before)
        a = _metrics(after)
        deltas = {
            k: (None if a[k] is None or b[k] is None else round(a[k] - b[k], 2))
            for k in b
        }
        return Observation(before=b, after=a, deltas=deltas)

    def adapt(self, observation: Observation, plan: PlanResult) -> AdaptedPlan:
        """Nudge the parameter based on what really changed. Conservative."""
        cpu_delta = observation.deltas.get("cpu_percent")
        value = plan.value
        changed = False
        reasoning = "No telemetry change observed; keeping the parameter."
        if value is not None and cpu_delta is not None:
            if cpu_delta > 25:
                value = max(1, value - 1)
                changed = True
                reasoning = f"CPU rose {cpu_delta:.0f} points; reducing to stay within safe lab limits."
            elif cpu_delta < 5:
                reasoning = f"CPU barely moved ({cpu_delta:.0f} points); parameter looks safe."
        return AdaptedPlan(changed=changed, parameter=plan.parameter, value=value, reasoning=reasoning)

    def analyze(self, profile: ProfileResult, observation: Observation | None) -> AnalysisReport:
        findings = [profile.summary]
        if observation:
            moved = {k: v for k, v in observation.deltas.items() if v}
            findings.append(
                f"Telemetry moved: {moved}" if moved else "No measurable telemetry change."
            )
        return AnalysisReport(summary=self._analysis_summary(profile), risk_score=None, findings=findings)

    def _analysis_summary(self, profile: ProfileResult) -> str:
        return f"{self.kind}: profiled target at {profile.load_level} load."


# --- helpers -----------------------------------------------------------------


def _metrics(t: Telemetry) -> dict[str, float | None]:
    return {
        "cpu_percent": t.cpu_percent,
        "memory_percent": t.memory_percent,
        "disk_percent": t.disk_percent,
        "process_count": float(t.process_count) if t.process_count is not None else None,
    }


def _load_level(t: Telemetry) -> str:
    if t.cpu_percent is None and t.memory_percent is None:
        return "unknown"
    cpu = t.cpu_percent or 0
    mem = t.memory_percent or 0
    peak = max(cpu, mem)
    if peak >= 80:
        return "high"
    if peak >= 45:
        return "moderate"
    return "low"
