"""Shared LLM access for the centralized planner, analyzer and feedback engine.

One injectable completion interface so production routes through the existing
OpenRouter plumbing (app/integrations/_llm.py) while tests inject a mock and
never touch the network.

    LLMComplete(system_prompt, user_prompt) -> (text | None, model | None, errors)

text is None when no model answered (no key, timeout, rate-limited, …) — callers
then degrade honestly and NEVER label the result as AI-generated.
"""
from __future__ import annotations

import json
from typing import Any, Callable

LLMComplete = Callable[[str, str], "tuple[str | None, str | None, list[str]]"]


def default_llm(system_prompt: str, user_prompt: str) -> "tuple[str | None, str | None, list[str]]":
    """Production LLM via OpenRouter; honest (None, None, errors) when unavailable."""
    from ..integrations import _llm

    return _llm.complete(system_prompt, user_prompt, max_tokens=700, temperature=0.2)


def extract_json(text: str | None) -> dict[str, Any] | None:
    """Pull a JSON object out of a model reply (handles ``` fences and prose)."""
    if not text:
        return None
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if s.count("```") >= 2 else s.strip("`")
        if s.lstrip().lower().startswith("json"):
            s = s.lstrip()[4:]
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        obj = json.loads(s[start : end + 1])
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None
