"""Centralized AI Planner — the reasoning brain of CHAKRAVYUH.

ONE planner that reads the scenario context and proposes a single structured
ExecutionPlan (the Section-2 schema). It replaces the per-module integer
recommender (agent/decision.py, now legacy, kept only for the simulation path)
as the authoritative AI for the real controlled-execution pipeline.

Boundaries (deterministic, outside the LLM):
  * The AI never picks a target freely — requested_target is bound to the
    authorized scope from the context (policy allowlist).
  * The AI cannot set or raise caps; params are clamped to schema sanity here
    and clamped again to configured caps by the Safety Gateway.
  * The AI never authorizes execution — the Gateway does.
  * On any LLM failure or malformed output, a clearly-labelled DETERMINISTIC
    fallback plan is produced (source=system) — never mislabelled as AI output.
  * If no module is runnable, an honest 'unavailable' result is returned.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import settings
from .context import ScenarioContext
from .llm import LLMComplete, default_llm, extract_json
from ..safety.plan_schema import ExecutionParams, ExecutionPlan, ModuleId, PlanSource

# Schema sanity bounds (NOT the policy caps) — used to clamp AI params so the
# plan constructs; the Gateway then clamps down to the real configured caps.
_SCHEMA_BOUNDS = {"tasks": (1, 64), "users": (1, 10_000), "spawn_rate": (1, 10_000),
                  "run_seconds": (1, 86_400)}
_MODULE_PARAM_KEYS = {"bruteforce": ("tasks", "run_seconds"), "ddos": ("users", "spawn_rate", "run_seconds")}

SYSTEM_PROMPT = (
    "You are the centralized planning brain of CHAKRAVYUH, an AUTHORIZED cyber-range "
    "console. You coordinate bounded Red-Team modules against an isolated, authorized "
    "lab target. You NEVER choose a target (the system binds it) and you NEVER set hard "
    "limits (the system enforces them). Reason over the provided context and recommend "
    "ONE module and bounded parameters. Respond with STRICT JSON only, shaped exactly: "
    '{"module": "bruteforce"|"ddos", "params": {<relevant bounded ints>}, '
    '"reasoning": <short string>, "expected_observations": <short string>, '
    '"confidence": "low"|"medium"|"high"}.'
)


@dataclass
class PlanningResult:
    status: str                      # "ai" | "fallback" | "unavailable"
    plan: ExecutionPlan | None
    reasoning: str
    prompt_version: str
    model: str | None = None
    ai_raw: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def is_ai(self) -> bool:
        return self.status == "ai"


def _clamp_schema(key: str, value: Any) -> int | None:
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    lo, hi = _SCHEMA_BOUNDS[key]
    return max(lo, min(hi, v))


def _params_for(module: str, raw: dict[str, Any] | None) -> ExecutionParams:
    raw = raw or {}
    kwargs: dict[str, int] = {}
    for key in _MODULE_PARAM_KEYS.get(module, ()):
        if key in raw and raw[key] is not None:
            clamped = _clamp_schema(key, raw[key])
            if clamped is not None:
                kwargs[key] = clamped
    return ExecutionParams(**kwargs)


def _build_plan(context: ScenarioContext, module: str, params: ExecutionParams,
                source: PlanSource, reasoning: str, model: str | None,
                expected: str, confidence: str) -> ExecutionPlan | None:
    target = context.authorized_target_for(module)
    if not target:
        return None  # no authorized target -> cannot plan for this module
    meta = {
        "prompt_version": settings.ai_prompt_version,
        "expected_observations": (expected or "")[:500],
        "confidence": (confidence or "")[:20],
    }
    if model:
        meta["model"] = model[:120]
    try:
        return ExecutionPlan(
            scenario_id=context.scenario_id,
            module=ModuleId(module),
            source=source,
            requested_target=target,          # bound to authorized scope, NOT the AI
            params=params,
            reasoning=reasoning[:4000],
            metadata=meta,
        )
    except Exception:  # pydantic validation guard
        return None


def _fallback(context: ScenarioContext, note: str, model: str | None = None,
              errors: list[str] | None = None) -> PlanningResult:
    """A deterministic, clearly-labelled plan used when the LLM can't be trusted."""
    runnable = context.runnable_modules()
    if not runnable:
        return PlanningResult(
            status="unavailable", plan=None,
            reasoning=f"No runnable module (enabled + adapter available + authorized target). {note}",
            prompt_version=settings.ai_prompt_version, errors=errors or [],
        )
    module = context.module_hint if context.module_hint in runnable else runnable[0]
    reasoning = (f"Deterministic fallback (NOT AI-generated): {note} "
                 f"Selected '{module}' from runnable modules with default bounded parameters "
                 f"(the Safety Gateway will clamp to configured caps).")
    plan = _build_plan(context, module, ExecutionParams(), PlanSource.system, reasoning,
                       None, "", "low")
    if plan is None:
        return PlanningResult(status="unavailable", plan=None,
                              reasoning=f"Fallback could not build a valid plan. {note}",
                              prompt_version=settings.ai_prompt_version, errors=errors or [])
    return PlanningResult(status="fallback", plan=plan, reasoning=reasoning,
                          prompt_version=settings.ai_prompt_version, model=None,
                          ai_raw={}, errors=errors or [])


def _user_prompt(context: ScenarioContext) -> str:
    import json
    runnable = context.runnable_modules()
    return (
        f"OBJECTIVE: {context.objective}\n"
        f"SCENARIO: {context.scenario_id}\n"
        f"RUNNABLE MODULES (choose exactly one of these): {runnable or 'NONE'}\n\n"
        f"CONTEXT (read-only evidence):\n{json.dumps(context.as_dict(), indent=2, default=str)[:6000]}\n\n"
        "Pick one runnable module and bounded params. Do not choose a disabled/unavailable "
        "module. Do not specify a target. Respond with STRICT JSON only."
    )


def generate_plan(context: ScenarioContext, *, llm: LLMComplete | None = None) -> PlanningResult:
    """Produce a PlanningResult for the current context (AI, fallback, or unavailable)."""
    llm = llm or default_llm

    runnable = context.runnable_modules()
    if not runnable:
        return PlanningResult(
            status="unavailable", plan=None,
            reasoning="No module is runnable (none enabled with an available adapter and an "
                      "authorized target). The AI has nothing it can safely plan.",
            prompt_version=settings.ai_prompt_version,
        )

    try:
        text, model, errors = llm(SYSTEM_PROMPT, _user_prompt(context))
    except Exception as exc:  # treat any LLM transport error as unavailable -> fallback
        return _fallback(context, f"LLM call failed ({type(exc).__name__}).", errors=[str(exc)[:160]])

    if not text:
        return _fallback(context, "LLM unavailable (no response).", model, errors=errors)

    parsed = extract_json(text)
    if parsed is None:
        return _fallback(context, "LLM returned malformed/non-JSON output.", model, errors=errors)

    module = parsed.get("module")
    if module not in runnable:
        return _fallback(
            context,
            f"LLM proposed module '{module}', not in the runnable set {runnable}.",
            model, errors=errors,
        )

    params = _params_for(module, parsed.get("params"))
    reasoning = str(parsed.get("reasoning", "")).strip() or "(no reasoning provided)"
    plan = _build_plan(context, module, params, PlanSource.ai, reasoning, model,
                       str(parsed.get("expected_observations", "")),
                       str(parsed.get("confidence", "medium")))
    if plan is None:
        return _fallback(context, "AI plan failed schema/target validation.", model, errors=errors)

    return PlanningResult(
        status="ai", plan=plan, reasoning=reasoning,
        prompt_version=settings.ai_prompt_version, model=model,
        ai_raw={k: parsed.get(k) for k in ("module", "params", "confidence", "expected_observations")},
        errors=errors,
    )
