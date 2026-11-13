"""Centralized LLM completion over any OpenAI-compatible gateway.

Provider-independent (Stage 1): the endpoint, key, model and timeout come from
the generic LLM_* settings, which default to the OpenRouter settings — so
existing OpenRouter deployments are unchanged, and OmniRoute or any other
OpenAI-compatible gateway works by configuration alone.

It degrades honestly: with no/invalid config or any client error it returns
(None, None, [sanitized errors]); callers then report "AI unavailable" rather
than inventing output. The API key is never placed in an error, log, or result.
"""
from __future__ import annotations

import logging

from ..config import settings

log = logging.getLogger(__name__)

_STATUS_MESSAGES = {
    401: "authentication failed (HTTP 401) — check the API key",
    403: "forbidden (HTTP 403)",
    404: "model or endpoint not found (HTTP 404) — check LLM_MODEL / LLM_BASE_URL",
    429: "rate limited (HTTP 429)",
    500: "provider server error (HTTP 500)",
    502: "bad gateway (HTTP 502)",
    503: "provider unavailable (HTTP 503)",
}


def _make_client(base_url: str, api_key: str, timeout: int):
    """Build an OpenAI-compatible client, or None if the SDK is missing.
    Isolated so tests can monkeypatch it with a fake client."""
    try:
        from openai import OpenAI
    except ImportError:
        return None
    return OpenAI(
        base_url=base_url,
        api_key=api_key,
        default_headers={"X-Title": "CYBER CHAKRAVYUH"},
        timeout=timeout,
        max_retries=0,
    )


def _sanitize_error(exc: Exception, api_key: str) -> str:
    """A short, credential-free error string (maps HTTP status; redacts the key)."""
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    if status in _STATUS_MESSAGES:
        return _STATUS_MESSAGES[status]
    msg = str(exc)
    if api_key:
        msg = msg.replace(api_key, "«redacted»")
    low = msg.lower()
    if "timeout" in low or "timed out" in low:
        return "request timeout"
    if "connection" in low or "refused" in low or "could not connect" in low or "name or service" in low:
        return "connection refused / gateway unreachable"
    return msg[:160]


def complete(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> tuple[str | None, str | None, list[str]]:
    """Return (text, model_used, errors). text is None when no model answered."""
    valid, reason = settings.llm_config_validity()
    if not valid:
        return None, None, [reason]

    base_url = settings.llm_effective_base_url
    api_key = settings.llm_effective_api_key
    model = settings.llm_effective_model
    timeout = settings.llm_effective_timeout

    client = _make_client(base_url, api_key, timeout)
    if client is None:
        return None, None, ["openai package not installed."]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    errors: list[str] = []
    # The configured model first, then any provider fallback models.
    for m in [model, *settings.llm_effective_fallback_models]:
        try:
            resp = client.chat.completions.create(
                model=m, messages=messages, temperature=temperature, max_tokens=max_tokens,
            )
            content = (resp.choices[0].message.content or "").strip()
            if not content:
                raise ValueError("empty response")
            return content, m, errors
        except Exception as exc:  # noqa: BLE001 - report sanitized, don't crash
            errors.append(f"{m}: {_sanitize_error(exc, api_key)}")
            log.warning("LLM call to %s failed (provider=%s)", m, settings.llm_provider)
    return None, None, errors


# --- Phase F: harmless, backend-only connection test -------------------------

_PROBE_SYSTEM = "You are a connectivity probe for an authorized lab console."
_PROBE_USER = "Reply with CHAKRAVYUH LLM CONNECTION SUCCESS."


def test_connection() -> dict:
    """Run one harmless inference against the configured provider and report
    staged results (config valid / reachable / auth / model / inference).
    Secrets are never included. An HTTP health alone is NOT treated as success —
    this performs an actual (tiny) inference."""
    valid, reason = settings.llm_config_validity()
    result = {
        "provider": settings.llm_provider,
        "base_url": settings.llm_effective_base_url or None,
        "model": settings.llm_effective_model or None,
        "timeout": settings.llm_effective_timeout,
        "api_key_configured": bool(settings.llm_effective_api_key),
        "config_valid": valid,
        "gateway_reachable": None,
        "auth_ok": None,
        "inference_ok": False,
        "reply_excerpt": None,
        "reason": reason,
        "errors": [],
    }
    if not valid:
        return result

    text, model, errors = complete(_PROBE_SYSTEM, _PROBE_USER, max_tokens=256, temperature=0.0)
    result["errors"] = errors[:3]
    if text is not None:
        result.update(gateway_reachable=True, auth_ok=True, inference_ok=True,
                      model=model, reply_excerpt=text[:120], reason="inference succeeded")
        return result

    # Classify the first error for staged status (best-effort, honest).
    joined = " ".join(errors).lower()
    if "connection" in joined or "unreachable" in joined or "timeout" in joined:
        result.update(gateway_reachable=False, reason="gateway unreachable / timeout")
    elif "authentication" in joined or "401" in joined or "forbidden" in joined or "403" in joined:
        result.update(gateway_reachable=True, auth_ok=False, reason="authentication failed")
    elif "not found" in joined or "404" in joined:
        result.update(gateway_reachable=True, auth_ok=True, reason="model/endpoint not found")
    else:
        result.update(reason="provider error — inference did not succeed")
    return result
