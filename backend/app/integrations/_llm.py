"""Free-form text completion over OpenRouter, shared by text-generating adapters.

This mirrors the client/fallback approach in app/agent/decision.py (all LLM
traffic goes through OpenRouter's OpenAI-compatible API) but returns prose
instead of a parsed JSON decision. It degrades honestly: with no key or on any
client error it returns (None, None, [errors]) and the caller reports the tool
as "AI analysis unavailable" rather than inventing a report.
"""
from __future__ import annotations

import logging

from ..config import settings

log = logging.getLogger(__name__)


def complete(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> tuple[str | None, str | None, list[str]]:
    """Return (text, model_used, errors). text is None when no model answered."""
    api_key = settings.openrouter_api_key
    if not api_key:
        return None, None, ["No OpenRouter API key is set (OPENROUTER_API_KEY)."]

    try:
        from openai import OpenAI
    except ImportError:
        return None, None, ["openai package not installed."]

    client = OpenAI(
        base_url=settings.openrouter_base_url,
        api_key=api_key,
        default_headers={"X-Title": "VAJRAPRAHAAR Cyber Range"},
        timeout=60,
        max_retries=0,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    errors: list[str] = []
    # Try the configured model first, then each free fallback model.
    for model in [settings.openrouter_model, *settings.fallback_models]:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = (resp.choices[0].message.content or "").strip()
            if not content:
                raise ValueError("empty response")
            return content, model, errors
        except Exception as exc:  # noqa: BLE001 - report, don't crash
            msg = str(exc)
            errors.append(f"{model}: {msg[:160]}")
            log.warning("integration LLM call to %s failed: %s", model, msg)
    return None, None, errors
