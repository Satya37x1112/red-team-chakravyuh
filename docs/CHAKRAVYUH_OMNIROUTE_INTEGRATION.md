# CYBER CHAKRAVYUH — OmniRoute Integration (Stage 2)

**Date:** 2026-11-09 · How the local OmniRoute gateway plugs into CHAKRAVYUH's
**one** centralized LLM client, with live verification results. No secrets shown.

---

## 1. Design — no new client, config only
CHAKRAVYUH already routes every AI call through a single provider-independent client
(`backend/app/integrations/_llm.py`, used by `backend/app/agent/llm.py`). It resolves
the generic `LLM_*` settings (`backend/app/config.py`), which **fall back to the
OpenRouter settings**, so existing OpenRouter deployments are unchanged.

Pointing CHAKRAVYUH at OmniRoute therefore needs **zero code changes** — only config:
```
LLM_PROVIDER=omniroute
LLM_BASE_URL=http://127.0.0.1:20128/v1
LLM_API_KEY=<OmniRoute client key>     # loopback-only bearer; SECRET (gitignored .env)
LLM_MODEL=openrouter/auto
```
These are present (commented, pre-filled) in `backend/.env`; OpenRouter stays the
**active default** so nothing breaks if the gateway is off. See the runbook to activate.

Preserved exactly (unchanged by Stage 2):
- Centralized LLM client (reused, not duplicated).
- AI Planner / analyzer / feedback interfaces.
- Pydantic execution-plan validation, Safety Gateway, kill switch, attack adapters.

## 2. Secret handling
- `LLM_API_KEY` is **never** returned by any API (`GET /api/llm/config` exposes only
  `api_key_configured: bool`), never logged, never placed in an error/audit record
  (the client sanitizes errors and redacts the key). The frontend holds no key.
- OmniRoute's upstream provider key lives encrypted in `~/.omniroute/storage.sqlite`.

## 3. Frontend (Phase 7)
`frontend/src/pages/Settings.tsx` (the existing Settings page — no duplicate) shows:
Provider, Model, staged **gateway connection state** (config valid / gateway reachable /
auth ok / inference ok), configuration validity, and errors. Stage 2 added a persisted
**last test** summary surfaced from `GET /api/llm/config` → `last_test`:
`last_success_at` ("Last successful connection test") and `last_error` ("Last error"),
so they survive a page reload. The key stays write-only and is never displayed.

Backend change: `backend/app/api/llm.py` records a sanitized, secret-free `_LAST_TEST`
on each `POST /api/llm/test` and returns it in the config view.

## 4. Live verification results (2026-11-09, through the SECURED gateway)
Gateway: `127.0.0.1:20128`, headless, `REQUIRE_API_KEY=true`.

| # | Check | Result |
|---|---|---|
| 1 | OmniRoute process starts | ✅ v3.8.53, "OmniRoute is running!" |
| 2 | Listens on loopback only | ✅ `ss` → `127.0.0.1:20128` (not `0.0.0.0`) |
| 3 | Authentication works | ✅ valid client key → `GET /v1/models` 200 (1045 models); `/v1/chat/completions` 200 |
| 4 | Model discovery | ✅ `GET /v1/models` → 1045 models |
| 5 | Invalid credentials rejected | ✅ no key / bad key → **HTTP 401** on inference endpoint |
| 6 | Harmless chat completion | ✅ reply "CHAKRAVYUH OMNIROUTE CONNECTION SUCCESS." (`omniroute chat` and raw `/v1`) |
| 7 | CHAKRAVYUH client → OmniRoute | ✅ `_llm.test_connection()` with `provider=omniroute` → `inference_ok: true`, "CHAKRAVYUH LLM CONNECTION SUCCESS." |
| 8 | OpenRouter still works | ✅ default config → `inference_ok: true` (live, model `anthropic/claude-sonnet-4.5`) |
| 9 | Failures handled honestly | ✅ bad key → `auth_ok:false`, sanitized "authentication failed (HTTP 401)", no secret; gateway-down → "gateway unreachable" |
| 10 | Restart / recovery | ✅ `omniroute stop` + relaunch via launcher comes back loopback+auth |

All AI distinctions are honest: a green state means a **real** tiny inference
succeeded, not merely that fields are filled or an HTTP health passed.

## 5. Mock vs live
- **Mocked** (offline, no network, no key): the backend test-suite LLM tests
  (`tests/test_llm_config.py`, incl. `test_omniroute_config_valid`) — prove config
  resolution and secret-safety only.
- **Live** (this document, section 4): real inference through the running gateway.
