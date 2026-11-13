"""AI decision engine.

Takes the latest REAL telemetry snapshot and asks an LLM (through OpenRouter's
OpenAI-compatible endpoint) to reason about a single controlled lab parameter.
It returns structured JSON: {decision, reasoning, ...}.

This is a pure read-and-reason step. It NEVER performs or triggers an action —
it only looks at observed state and explains a recommended parameter for the
operator to consider. All LLM traffic goes through OpenRouter; the native
anthropic SDK is intentionally not used anywhere in this project.
"""
from __future__ import annotations

import json
import logging
import random
import re
import time
from typing import Any

from ..config import settings
from ..telemetry.schema import Telemetry

log = logging.getLogger(__name__)

PRIMARY_MAX_TOKENS = 300
MIN_USEFUL_TOKENS = 160
FREE_MAX_TOKENS = 1200  # free models cost nothing; reasoning models need headroom
PRIMARY_COOLDOWN_S = 300

# When the paid model last returned 402; skip it until the cooldown passes.
_primary_blocked_until = 0.0

# What each module wants the model to decide. Kept read-only and bounded.
MODULE_BRIEFS: dict[str, dict[str, str]] = {
    "ddos": {
        "parameter": "recommended_sources",
        "ask": (
            "Recommend how many simulated load sources a CONTROLLED, authorized "
            "load test should use against this lab host, as an integer. Base it on "
            "observed CPU, memory and process load — a busier host warrants fewer "
            "sources. This is a safe load-test parameter for a lab you own, not an attack."
        ),
        "bounds": "Keep the integer between 1 and 12.",
    },
    "bruteforce": {
        "parameter": "recommended_attempt_rate",
        "ask": (
            "Recommend a conservative authentication-test attempt rate (attempts per "
            "minute, integer) for an authorized account-lockout test in this lab, based "
            "on the observed host responsiveness. Favour low, careful rates."
        ),
        "bounds": "Keep the integer between 1 and 30.",
    },
    "ratuba": {
        "parameter": "recommended_baseline_window_minutes",
        "ask": (
            "Recommend how many minutes of observed endpoint activity the UBA engine "
            "should use to build a user-behaviour baseline before flagging deviations, "
            "as an integer, based on how much process/logon/network activity is visible."
        ),
        "bounds": "Keep the integer between 5 and 120.",
    },
}

SYSTEM_PROMPT = (
    "You are the reasoning core of AI RED TEAM, a defensive cyber-range console for an "
    "isolated, authorized lab. You are given REAL telemetry observed from a lab host. "
    "Reason ONLY over the observed values. You never take actions; you only recommend a "
    "single numeric parameter and explain why from the data. If a value is null, say it "
    "was unavailable and reason conservatively. Keep reasoning to at most three short "
    "sentences. Respond with STRICT JSON only, no prose "
    'outside it, shaped exactly: {"decision": <integer>, "reasoning": <string>, '
    '"observations_used": [<string>, ...], "confidence": "low"|"medium"|"high"}.'
)


def _telemetry_digest(t: Telemetry) -> dict[str, Any]:
    """A compact, model-friendly view of the real snapshot."""
    return {
        "available": t.available,
        "hostname": t.hostname,
        "os_name": t.os_name,
        "logged_in_user": t.logged_in_user,
        "uptime_seconds": t.uptime_seconds,
        "cpu_percent": t.cpu_percent,
        "memory_percent": t.memory_percent,
        "disk_percent": t.disk_percent,
        "process_count": t.process_count,
        "top_processes": [
            {"name": p.name, "memory_mb": p.memory_mb} for p in t.processes[:10]
        ],
        "interface_count": len(t.interfaces),
        "connection_count": len(t.connections),
        "recent_windows_event_ids": [e.event_id for e in t.windows_events[:10]],
    }


def _unavailable(kind: str, reason: str) -> dict[str, Any]:
    brief = MODULE_BRIEFS.get(kind, {})
    return {
        "status": "llm_unavailable",
        "parameter": brief.get("parameter", "recommended_value"),
        "decision": None,
        "reasoning": reason,
        "observations_used": [],
        "confidence": "low",
        "model": None,
    }


def decide(kind: str, telemetry: Telemetry) -> dict[str, Any]:
    """Return an AGENT DECISION for `kind` based on the real snapshot.

    Degrades honestly: with no API key, or on any client error, it returns a
    clearly-labelled `llm_unavailable` result instead of inventing a number.
    """
    brief = MODULE_BRIEFS.get(kind)
    if brief is None:
        return _unavailable(kind, f"Unknown module '{kind}'.")
    if not telemetry.available:
        return _unavailable(
            kind, f"No real telemetry to reason over ({telemetry.error or 'unavailable'})."
        )
    api_key = settings.api_key_for(kind)
    if not api_key:
        return _unavailable(
            kind, "No OpenRouter API key is set, so no LLM reasoning was performed."
        )

    try:
        from openai import OpenAI
    except ImportError:
        return _unavailable(kind, "openai package not installed.")

    client = OpenAI(
        base_url=settings.openrouter_base_url,
        api_key=api_key,
        default_headers={"X-Title": "AI RED TEAM Cyber Range"},
        timeout=30,
        max_retries=0,
    )

    user_prompt = (
        f"Module: {kind}\nTask: {brief['ask']}\nConstraint: {brief['bounds']}\n\n"
        f"REAL TELEMETRY (observed now):\n{json.dumps(_telemetry_digest(telemetry), indent=2)}"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    parsed, model, errors = _ask_with_fallback(client, messages)
    if parsed is None:
        # LLM unavailable (no credits / rate limited): don't give up — fall back to a
        # transparent rule-based recommendation grounded in the real snapshot.
        return _heuristic_decision(kind, telemetry, note=" | ".join(errors))

    decision = _clamp(_coerce_int(parsed.get("decision")), brief["bounds"])
    return {
        "status": "ok" if decision is not None else "llm_unavailable",
        "parameter": brief["parameter"],
        "decision": decision,
        "reasoning": str(parsed.get("reasoning", "")).strip(),
        "observations_used": parsed.get("observations_used", []),
        "confidence": parsed.get("confidence", "medium"),
        "model": model,
    }


def _ask_with_fallback(client: Any, messages: list[dict]) -> tuple[dict | None, str | None, list[str]]:
    """Try the configured model, shrinking max_tokens to what credits allow, then free models."""
    global _primary_blocked_until
    errors: list[str] = []
    attempts: list[tuple[str, int]] = []
    if time.monotonic() >= _primary_blocked_until:
        attempts.append((settings.openrouter_model, PRIMARY_MAX_TOKENS))
    else:
        errors.append(f"{settings.openrouter_model}: skipped, out of credits (retrying in "
                      f"{int(_primary_blocked_until - time.monotonic())}s)")
    attempts += [(m, FREE_MAX_TOKENS) for m in settings.fallback_models]

    i = 0
    while i < len(attempts):
        model, max_tokens = attempts[i]
        i += 1
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            content = (resp.choices[0].message.content or "").strip()
            if not content:
                raise ValueError("empty response")
            parsed = json.loads(_extract_json(content))
            if _coerce_int(parsed.get("decision")) is None:
                raise ValueError("no numeric decision in response")
            return parsed, model, errors
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            msg = str(exc)
            errors.append(f"{model}: {msg[:160]}")
            log.warning("decision call to %s failed: %s", model, msg)
            if status == 402 and model == settings.openrouter_model:
                affordable = _affordable_tokens(msg)
                if affordable and affordable - 10 >= MIN_USEFUL_TOKENS and affordable - 10 < max_tokens:
                    attempts.insert(i, (model, affordable - 10))
                else:
                    _primary_blocked_until = time.monotonic() + PRIMARY_COOLDOWN_S
    return None, None, errors


def _clamp(value: int | None, bounds: str) -> int | None:
    lo, hi = (int(n) for n in re.findall(r"\d+", bounds)[:2])
    return None if value is None else max(lo, min(hi, value))


def _affordable_tokens(message: str) -> int | None:
    m = re.search(r"can only afford (\d+)", message)
    return int(m.group(1)) if m else None


_HEURISTIC_REASON = {
    "ddos": ("Rule-based fallback (LLM unavailable). With CPU at {cpu} and memory at "
             "{mem}, a load test should use about {value} sources to stay within safe "
             "lab headroom — fewer when the host is already busy."),
    "bruteforce": ("Rule-based fallback (LLM unavailable). Given CPU {cpu}, memory {mem} "
                   "and {logons} recent logon events, a conservative ~{value} attempts/min "
                   "keeps the authorized lockout test careful and avoids hammering the host."),
    "ratuba": ("Rule-based fallback (LLM unavailable). With {procs} distinct processes and "
               "CPU {cpu}, a ~{value}-minute baseline window captures enough endpoint "
               "behaviour before scoring deviations."),
}


def _heuristic_decision(kind: str, telemetry: Telemetry, note: str = "") -> dict[str, Any]:
    """A transparent, telemetry-grounded recommendation used when the LLM is down.

    Not fabricated telemetry — it is a rule-based *recommendation* derived from the
    real snapshot, clearly labelled, with a little run-to-run variation so repeated
    runs explore the safe band rather than returning an identical number."""
    brief = MODULE_BRIEFS[kind]
    nums = re.findall(r"\d+", brief["bounds"])
    lo, hi = int(nums[0]), int(nums[1])
    span = hi - lo
    cpu = telemetry.cpu_percent if telemetry.cpu_percent is not None else 0.0
    mem = telemetry.memory_percent if telemetry.memory_percent is not None else 0.0
    load = max(cpu, mem)
    # Busier host -> more conservative (nearer the low bound).
    base = hi - (load / 100.0) * span
    jitter = random.uniform(-0.15, 0.15) * (span or 1)
    value = int(round(base + jitter))
    value = max(lo, min(hi, value))
    logons = len([e for e in telemetry.windows_events if e.event_id in (4624, 4625)])
    procs = len({p.name for p in telemetry.processes})
    reasoning = _HEURISTIC_REASON[kind].format(
        cpu=f"{cpu:.0f}%", mem=f"{mem:.0f}%", logons=logons, procs=procs, value=value
    )
    obs = [f"cpu_percent={cpu:.0f}", f"memory_percent={mem:.0f}"]
    if kind == "bruteforce":
        obs.append(f"recent_logon_events={logons}")
    if kind == "ratuba":
        obs.append(f"distinct_processes={procs}")
    return {
        "status": "heuristic",
        "parameter": brief["parameter"],
        "decision": value,
        "reasoning": reasoning + (f" [{note}]" if note else ""),
        "observations_used": obs,
        "confidence": "low",
        "model": "heuristic (local rules)",
    }


def _extract_json(content: str) -> str:
    """Models often wrap JSON in ```json fences; pull out the object itself."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end != -1 else text.strip()


def _coerce_int(value: Any) -> int | None:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None
