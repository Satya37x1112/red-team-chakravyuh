"""Generic LLM provider configuration + harmless connection test (Stage 1).

Security:
  * The API key is NEVER returned by any endpoint (only an `api_key_configured`
    boolean). A key submitted here updates the in-memory setting ONLY — it is not
    written to disk or the database and is never echoed back or logged.
  * Runtime config changes are NON-PERSISTENT (reset on backend restart). For a
    durable key, set LLM_API_KEY / OPENROUTER_API_KEY in the gitignored .env.
This endpoint configures the ONE centralized LLM client; it does not create
per-module AI clients and cannot bypass the Safety Gateway.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..config import settings
from ..integrations import _llm

router = APIRouter(prefix="/api/llm")

# In-memory record of the most recent connection test (NON-persistent; reset on
# restart). Holds only sanitized, secret-free fields — the time of the last test,
# whether a real inference succeeded, the last successful-test time, and the last
# sanitized error. No API key, prompt, or reply body is stored here.
_LAST_TEST: dict | None = None


def _record_test(result: dict) -> None:
    """Fold a /test result into the last-test summary (secret-free)."""
    global _LAST_TEST
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prev = _LAST_TEST or {}
    ok = bool(result.get("inference_ok"))
    errors = result.get("errors") or []
    _LAST_TEST = {
        "at": now,
        "inference_ok": ok,
        "reason": result.get("reason"),
        # Preserve the last *successful* test time across later failures.
        "last_success_at": now if ok else prev.get("last_success_at"),
        # The most recent sanitized error (cleared on success).
        "last_error": None if ok else (errors[0] if errors else result.get("reason")),
    }


def _config_view() -> dict:
    valid, reason = settings.llm_config_validity()
    return {
        "provider": settings.llm_provider,
        "supported_providers": list(settings.LLM_PROVIDERS),
        "base_url": settings.llm_effective_base_url or None,
        "model": settings.llm_effective_model or None,
        "timeout": settings.llm_effective_timeout,
        "api_key_configured": bool(settings.llm_effective_api_key),  # boolean ONLY — never the key
        "config_valid": valid,
        "reason": reason,
        "persistent": False,  # runtime changes reset on restart; .env is the durable store
        "last_test": _LAST_TEST,  # sanitized last-test summary (no secret), or null
    }


@router.get("/config")
def get_llm_config() -> dict:
    """Current generic-LLM config. The API key is never included."""
    return _config_view()


class LLMConfigUpdate(BaseModel):
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    timeout: int | None = Field(default=None, ge=5, le=300)
    api_key: str | None = None  # applied to in-memory settings only; never returned/logged


@router.post("/config")
def update_llm_config(req: LLMConfigUpdate) -> dict:
    """Update the in-memory LLM config (non-persistent). The key, if given, is
    held in memory only and never returned."""
    if req.provider is not None:
        if req.provider not in settings.LLM_PROVIDERS:
            return {**_config_view(), "config_valid": False,
                    "reason": f"invalid provider '{req.provider}'"}
        settings.llm_provider = req.provider
    if req.base_url is not None:
        settings.llm_base_url = req.base_url.strip()
    if req.model is not None:
        settings.llm_model = req.model.strip()
    if req.timeout is not None:
        settings.llm_timeout = int(req.timeout)
    if req.api_key:  # non-empty only; stored in memory, never echoed
        settings.llm_api_key = req.api_key
    return _config_view()


@router.post("/test")
def test_llm_connection() -> dict:
    """Run one harmless inference ('CHAKRAVYUH LLM CONNECTION SUCCESS') against the
    configured provider and return staged, sanitized results. No secrets returned."""
    result = _llm.test_connection()
    _record_test(result)
    return result
