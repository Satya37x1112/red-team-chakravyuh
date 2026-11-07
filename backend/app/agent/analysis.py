"""Post-execution analysis.

Separates MEASURED FACTS (extracted only from the real execution record/result)
from INTERPRETATION (the AI's or a deterministic reading). It never invents a
metric and never claims success without evidence; a failed/empty execution is
analysed honestly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .context import ScenarioContext
from .llm import LLMComplete, default_llm
from ..safety.registry import ExecState, ExecutionRecord


@dataclass
class AnalysisResult:
    measured_facts: list[str]
    interpretation: str
    source: str                      # "ai" | "deterministic"
    model: str | None = None
    objective_met: bool = False
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "measured_facts": self.measured_facts,
            "interpretation": self.interpretation,
            "interpretation_source": self.source,
            "model": self.model,
            "objective_met": self.objective_met,
            "evidence": self.evidence,
        }


def _measured_facts(record: ExecutionRecord, result: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    """Deterministic, evidence-only facts. Nothing here is inferred."""
    facts: list[str] = [f"Execution state: {record.state.value}."]
    evidence: dict[str, Any] = {"state": record.state.value}
    if record.exit_code is not None:
        facts.append(f"Adapter exit code: {record.exit_code}.")
        evidence["exit_code"] = record.exit_code
    if record.error:
        facts.append(f"Recorded error: {record.error}.")
        evidence["error"] = record.error

    if record.module == "bruteforce" and isinstance(result, dict):
        n = result.get("found_count")
        if n is not None:
            facts.append(f"Hydra reported {n} valid credential pair(s).")
            evidence["found_count"] = n
        if result.get("attempts_made") is not None:
            facts.append(f"{result['attempts_made']} attempt(s) made.")
            evidence["attempts_made"] = result["attempts_made"]
        if result.get("message"):
            facts.append(f"Adapter message: {result['message']}")
        if result.get("timed_out"):
            facts.append("Hydra run hit the run-time cap (timed out).")
    elif record.module == "ddos" and isinstance(result, dict):
        totals = result.get("totals") or {}
        if totals:
            facts.append(
                f"Locust totals: {totals.get('requests')} requests, "
                f"{totals.get('failures')} failures (~{totals.get('rps')}/s)."
            )
            evidence["totals"] = totals
    return facts, evidence


def _objective_met(record: ExecutionRecord, result: dict[str, Any]) -> bool:
    """Evidence-based success only. No evidence => not met."""
    if record.state != ExecState.COMPLETED or not isinstance(result, dict):
        return False
    if record.module == "bruteforce":
        return bool(result.get("found_count"))
    if record.module == "ddos":
        totals = result.get("totals") or {}
        return bool(totals.get("failures"))  # observed failures = availability impact
    return False


def _deterministic_interpretation(record: ExecutionRecord, met: bool) -> str:
    if record.state == ExecState.FAILED:
        return "Deterministic reading: the execution failed; see the recorded error. No outcome can be claimed."
    if record.state == ExecState.TIMED_OUT:
        return "Deterministic reading: the execution hit its time cap before completing; results are partial."
    if record.state == ExecState.CANCELLED:
        return "Deterministic reading: the execution was cancelled; no complete outcome."
    if met:
        return "Deterministic reading: the measured evidence meets the objective's success condition."
    return "Deterministic reading: the execution completed but the measured evidence does not meet the objective."


def analyze(
    record: ExecutionRecord,
    result: dict[str, Any],
    context: ScenarioContext,
    *,
    llm: LLMComplete | None = None,
) -> AnalysisResult:
    facts, evidence = _measured_facts(record, result)
    met = _objective_met(record, result)
    tele = context.telemetry
    if not tele.get("available"):
        facts.append(f"Target telemetry: {tele.get('note')}")

    # Interpretation: try the LLM for a readable reading, else deterministic.
    interpretation = _deterministic_interpretation(record, met)
    source, model = "deterministic", None
    llm = llm or default_llm
    try:
        sys_p = (
            "You are a Red-Team analyst. Given MEASURED FACTS from one authorized-lab "
            "execution, write ONE short plain sentence of interpretation. Do NOT invent "
            "numbers, do NOT claim success without evidence, no markdown."
        )
        user_p = f"Objective: {context.objective}\nMeasured facts: {facts}\nState: {record.state.value}"
        text, m, _errs = llm(sys_p, user_p)
        cand = (text or "").strip().splitlines()[0].strip() if text else ""
        if cand and len(cand) <= 300:
            interpretation, source, model = cand, "ai", m
    except Exception:
        pass  # keep the deterministic interpretation

    return AnalysisResult(
        measured_facts=facts, interpretation=interpretation, source=source,
        model=model, objective_met=met, evidence=evidence,
    )
