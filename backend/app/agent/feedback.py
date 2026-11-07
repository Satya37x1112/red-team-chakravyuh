"""AI Feedback Engine.

Produces one recommendation — CONTINUE / MODIFY / STOP — after each iteration.

Critical design: recommendations are ADVISORY. Deterministic guardrails (max
iterations, repeated-failure stop, kill-switch, objective-met) are evaluated
FIRST and always win, so the AI can never force execution to continue past a
configured limit. The AI is consulted only when it is already safe to proceed,
and even then every proposed next plan must re-pass schema validation and the
Safety Gateway.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import settings
from .analysis import AnalysisResult
from .context import ScenarioContext
from .llm import LLMComplete, default_llm

CONTINUE, MODIFY, STOP = "CONTINUE", "MODIFY", "STOP"
_VALID = {CONTINUE, MODIFY, STOP}


@dataclass
class FeedbackRecommendation:
    action: str                      # CONTINUE | MODIFY | STOP
    reasoning: str
    source: str                      # "deterministic" | "ai"
    evidence: dict[str, Any] = field(default_factory=dict)
    model: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reasoning": self.reasoning,
            "source": self.source,
            "evidence": self.evidence,
            "model": self.model,
        }


def decide(
    analysis: AnalysisResult,
    context: ScenarioContext,
    *,
    iteration: int,
    max_iterations: int,
    consecutive_failures: int,
    last_state: str,
    llm: LLMComplete | None = None,
) -> FeedbackRecommendation:
    ev = {
        "iteration": iteration,
        "max_iterations": max_iterations,
        "consecutive_failures": consecutive_failures,
        "last_state": last_state,
        "objective_met": analysis.objective_met,
    }

    # --- deterministic guardrails (always win) ---
    if context.safety.get("kill_switch_engaged"):
        return FeedbackRecommendation(STOP, "Kill switch engaged; stopping.", "deterministic", ev)
    if analysis.objective_met:
        return FeedbackRecommendation(STOP, "Objective met by measured evidence; stopping.", "deterministic", ev)
    if iteration + 1 >= max_iterations:
        return FeedbackRecommendation(
            STOP, f"Reached the deterministic max of {max_iterations} iteration(s); stopping.",
            "deterministic", ev)
    if consecutive_failures >= settings.ai_consecutive_failure_stop:
        return FeedbackRecommendation(
            STOP, f"{consecutive_failures} consecutive failed/timed-out execution(s); stopping.",
            "deterministic", ev)

    # --- safe to proceed: ask the AI for CONTINUE vs MODIFY (vs voluntary STOP) ---
    llm = llm or default_llm
    try:
        sys_p = (
            "You are a Red-Team planner deciding the next step of an authorized-lab "
            "operation. Reply with ONE word only: CONTINUE, MODIFY, or STOP. CONTINUE = "
            "repeat the approach; MODIFY = a different bounded approved approach is better; "
            "STOP = no value in continuing."
        )
        user_p = (f"Objective: {context.objective}\nLast state: {last_state}\n"
                  f"Measured facts: {analysis.measured_facts}\nInterpretation: {analysis.interpretation}")
        text, model, _errs = llm(sys_p, user_p)
        word = (text or "").strip().upper().split()[0].strip(".,!") if text else ""
        if word in _VALID:
            reason = f"AI recommendation based on this iteration's evidence ({word.lower()})."
            return FeedbackRecommendation(word, reason, "ai", ev, model)
    except Exception:
        pass

    # --- deterministic default when the AI is unavailable/invalid ---
    if last_state in ("FAILED", "TIMED_OUT", "CANCELLED"):
        return FeedbackRecommendation(
            MODIFY, "Deterministic default: last execution did not complete cleanly; try a revised "
            "bounded approach.", "deterministic", ev)
    return FeedbackRecommendation(
        CONTINUE, "Deterministic default: execution completed without meeting the objective; another "
        "bounded iteration is warranted.", "deterministic", ev)
