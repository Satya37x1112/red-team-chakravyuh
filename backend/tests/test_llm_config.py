"""Generic LLM configuration + provider abstraction (Stage 1).

All HTTP is mocked via a fake OpenAI-compatible client — no network, no provider
key required, no target contact. Mocked OmniRoute config does NOT prove live
OmniRoute connectivity (that needs an installed gateway)."""
from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient

from app.config import settings
from app.integrations import _llm
from app.main import app

client = TestClient(app)


# ---- fake OpenAI-compatible client -----------------------------------------

class _FakeResp:
    def __init__(self, content):
        msg = type("M", (), {"content": content})()
        self.choices = [type("C", (), {"message": msg})()]


class _FakeClient:
    def __init__(self, behavior):
        creator = self._make(behavior)
        self.chat = type("Chat", (), {"completions": type("Cmp", (), {"create": staticmethod(creator)})()})()

    @staticmethod
    def _make(behavior):
        def create(**kw):
            if isinstance(behavior, Exception):
                raise behavior
            return _FakeResp(behavior)
        return create


class _HTTPErr(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status} from provider")
        self.status_code = status


def _arm_llm(monkeypatch, *, provider="openrouter", base="", key="SEKRET-KEY-123",
             model="test-model", behavior="ok text"):
    monkeypatch.setattr(settings, "llm_provider", provider)
    monkeypatch.setattr(settings, "llm_base_url", base)
    monkeypatch.setattr(settings, "llm_api_key", key)
    monkeypatch.setattr(settings, "llm_model", model)
    monkeypatch.setattr(settings, "openrouter_api_key", "")  # ensure override is used
    monkeypatch.setattr(_llm, "_make_client", lambda b, k, t: _FakeClient(behavior))


# ---- provider abstraction / compatibility ----------------------------------

def test_openrouter_compatibility(monkeypatch):
    _arm_llm(monkeypatch, provider="openrouter", behavior="hello")
    text, model, errors = _llm.complete("s", "u")
    assert text == "hello" and model == "test-model" and errors == []


def test_generic_openai_compatible(monkeypatch):
    _arm_llm(monkeypatch, provider="openai_compatible", base="http://127.0.0.1:9000/v1", behavior="ok")
    assert settings.llm_effective_base_url == "http://127.0.0.1:9000/v1"
    assert _llm.complete("s", "u")[0] == "ok"


def test_omniroute_config_valid(monkeypatch):
    _arm_llm(monkeypatch, provider="omniroute", base="http://127.0.0.1:20128/v1", behavior="ok")
    assert settings.llm_config_validity()[0] is True
    assert _llm.complete("s", "u")[0] == "ok"   # MOCK only — not live proof


def test_custom_base_url_and_model(monkeypatch):
    _arm_llm(monkeypatch, provider="openai_compatible", base="http://10.0.0.5:8000/v1/", model="my/model")
    assert settings.llm_effective_base_url == "http://10.0.0.5:8000/v1"   # trailing slash trimmed
    assert settings.llm_effective_model == "my/model"
    # explicit model => no openrouter fallback models appended
    assert settings.llm_effective_fallback_models == []


# ---- configuration errors ---------------------------------------------------

def test_missing_api_key(monkeypatch):
    _arm_llm(monkeypatch, key="")
    text, _, errors = _llm.complete("s", "u")
    assert text is None and any("api key" in e.lower() for e in errors)


def test_invalid_provider(monkeypatch):
    _arm_llm(monkeypatch, provider="banana")
    valid, reason = settings.llm_config_validity()
    assert valid is False and "invalid" in reason.lower()
    assert _llm.complete("s", "u")[0] is None


def test_omniroute_without_base_url_invalid(monkeypatch):
    _arm_llm(monkeypatch, provider="omniroute", base="")
    assert settings.llm_config_validity()[0] is False
    assert _llm.complete("s", "u")[0] is None


def test_missing_model(monkeypatch):
    _arm_llm(monkeypatch, model="")
    monkeypatch.setattr(settings, "openrouter_model", "")
    assert settings.llm_config_validity()[0] is False


# ---- transport / HTTP error handling (sanitized) ---------------------------

@pytest.mark.parametrize("exc,expect", [
    (ConnectionError("Connection refused"), "connection refused"),
    (TimeoutError("Request timed out"), "request timeout"),
    (_HTTPErr(401), "authentication failed"),
    (_HTTPErr(403), "forbidden"),
    (_HTTPErr(404), "not found"),
    (_HTTPErr(429), "rate limited"),
    (_HTTPErr(500), "server error"),
    (_HTTPErr(502), "bad gateway"),
])
def test_http_errors_are_sanitized(monkeypatch, exc, expect):
    _arm_llm(monkeypatch, behavior=exc)
    text, _, errors = _llm.complete("s", "u")
    assert text is None
    assert any(expect in e.lower() for e in errors)


def test_invalid_response_structure(monkeypatch):
    # choices access fails -> caught, not crashed
    class _Bad:
        choices = []
    _arm_llm(monkeypatch)
    monkeypatch.setattr(_llm, "_make_client", lambda b, k, t: type(
        "C", (), {"chat": type("Ch", (), {"completions": type(
            "Cmp", (), {"create": staticmethod(lambda **kw: _Bad())})()})()})())
    assert _llm.complete("s", "u")[0] is None


def test_empty_response(monkeypatch):
    _arm_llm(monkeypatch, behavior="")   # empty content
    text, _, errors = _llm.complete("s", "u")
    assert text is None and any("empty" in e.lower() for e in errors)


def test_secret_never_in_errors(monkeypatch):
    # An exception whose text contains the key must be redacted.
    _arm_llm(monkeypatch, key="SUPERSECRET999", behavior=Exception("boom key=SUPERSECRET999 at host"))
    _, _, errors = _llm.complete("s", "u")
    assert all("SUPERSECRET999" not in e for e in errors)
    assert any("redacted" in e for e in errors)


# ---- connection test --------------------------------------------------------

def test_connection_success(monkeypatch):
    _arm_llm(monkeypatch, behavior="CHAKRAVYUH LLM CONNECTION SUCCESS")
    r = _llm.test_connection()
    assert r["config_valid"] and r["inference_ok"] and r["auth_ok"] and r["gateway_reachable"]
    assert "SUCCESS" in (r["reply_excerpt"] or "")
    assert "api_key" not in json.dumps(r).lower() or r["api_key_configured"] is True  # only the bool
    assert "SEKRET" not in json.dumps(r)   # key value never present


def test_connection_auth_failure(monkeypatch):
    _arm_llm(monkeypatch, behavior=_HTTPErr(401))
    r = _llm.test_connection()
    assert r["inference_ok"] is False and r["auth_ok"] is False


def test_connection_unreachable(monkeypatch):
    _arm_llm(monkeypatch, behavior=ConnectionError("Connection refused"))
    r = _llm.test_connection()
    assert r["inference_ok"] is False and r["gateway_reachable"] is False


# ---- API endpoints ----------------------------------------------------------

def test_api_get_config_never_returns_key(monkeypatch):
    _arm_llm(monkeypatch, key="SEKRET-API-XYZ")
    body = client.get("/api/llm/config").json()
    assert body["api_key_configured"] is True
    assert "SEKRET-API-XYZ" not in json.dumps(body)
    assert "api_key" not in body or body.get("api_key") is None


def test_api_post_config_updates_without_echoing_key(monkeypatch):
    r = client.post("/api/llm/config", json={"provider": "openai_compatible",
                                             "base_url": "http://127.0.0.1:20128/v1",
                                             "model": "m1", "timeout": 45, "api_key": "NEWSECRET"})
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "openai_compatible" and body["timeout"] == 45
    assert "NEWSECRET" not in json.dumps(body)
    assert body["api_key_configured"] is True


def test_api_test_endpoint_mocked(monkeypatch):
    _arm_llm(monkeypatch, behavior="CHAKRAVYUH LLM CONNECTION SUCCESS")
    r = client.post("/api/llm/test").json()
    assert r["inference_ok"] is True
    assert "SEKRET" not in json.dumps(r)
