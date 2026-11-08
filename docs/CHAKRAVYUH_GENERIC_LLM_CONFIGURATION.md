# CYBER CHAKRAVYUH — Generic LLM Configuration (Stage 1)

**Date:** 2026-11-08 · Incremental enhancement. The centralized AI planner is now **provider-independent**: it works with OpenRouter, a self-hosted OmniRoute, or any OpenAI-compatible `/v1/chat/completions` gateway — by configuration alone. No rebuild; existing OpenRouter behaviour is preserved by defaulting.

---

## 1. Architecture
One centralized LLM client (`backend/app/integrations/_llm.py::complete`), used by the planner/analysis/feedback via `backend/app/agent/llm.py::default_llm`. No per-module AI clients were added; the planner remains the only AI authority, and every plan still passes Pydantic validation + the deterministic Safety Gateway. The client resolves generic `LLM_*` settings (which fall back to the `OPENROUTER_*` settings), builds an OpenAI-compatible request, sends it with a bounded timeout, parses `choices[0].message.content`, and returns `(text, model, errors)` — honest fallback on any failure.

## 2. Configuration variables (`backend/.env`, gitignored)
| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `openrouter` | `openrouter` \| `openai_compatible` \| `omniroute` |
| `LLM_BASE_URL` | *(empty)* | gateway base URL; empty = provider default (OpenRouter) |
| `LLM_API_KEY` | *(empty)* | **SECRET**; empty = `OPENROUTER_API_KEY` |
| `LLM_MODEL` | *(empty)* | model id; empty = `OPENROUTER_MODEL` |
| `LLM_TIMEOUT` | `60` | request timeout, clamped 5–300s |

Effective resolution (in `config.py`): `llm_effective_base_url/api_key/model/timeout`, `llm_effective_fallback_models` (OpenRouter free-tier fallbacks apply only to the `openrouter` provider with no explicit model), and `llm_config_validity() -> (valid, reason)`.

## 3. Supported provider modes
- **openrouter** (default): base URL defaults to `https://openrouter.ai/api/v1`; existing deployments unchanged.
- **openai_compatible**: any `/v1` endpoint; **requires** `LLM_BASE_URL`.
- **omniroute**: a self-hosted OmniRoute gateway (OpenAI-compatible at `/v1`); **requires** `LLM_BASE_URL` (e.g. `http://127.0.0.1:20128/v1` — confirm the actual port after install; **OmniRoute is not installed in this stage**).

## 4. Base URL format
An OpenAI-style base ending in `/v1` (trailing slash is trimmed). Example OmniRoute: `http://127.0.0.1:<verified-port>/v1`.

## 5. Authentication
`Authorization: Bearer <LLM_API_KEY>` via the OpenAI SDK. The key is **backend-only**.

## 6. Model & timeout
`LLM_MODEL` selects the planner's model (falls back to `OPENROUTER_MODEL`). `LLM_TIMEOUT` bounds each request (5–300s; invalid values coerced to a safe default).

## 7. Connection testing
`POST /api/llm/test` runs one **harmless real inference** — prompt: *"Reply with CHAKRAVYUH LLM CONNECTION SUCCESS."* — and returns **staged** results: `config_valid`, `gateway_reachable`, `auth_ok`, `inference_ok`, a short `reply_excerpt`, and sanitized `errors`. An HTTP health alone is **not** treated as proof; an actual inference must succeed. No secret is returned.

## 8. Security considerations
- **API key never leaves the backend:** `GET /api/llm/config` returns only `api_key_configured` (boolean) — never the key. `POST /api/llm/config` accepts a new key into the **in-memory** setting only (never persisted to DB/file, never echoed, never logged). The frontend field is a **write-only masked** input, cleared after save, never stored in the browser.
- **Error sanitization:** `_sanitize_error` maps HTTP status (401/403/404/429/5xx) to clean messages and **redacts the key** from any exception text; timeouts/connection errors are labelled generically.
- **Limitation (documented, not worked around):** web-entered config/keys are **non-persistent** (reset on backend restart). For durable secrets, set `LLM_API_KEY`/`OPENROUTER_API_KEY` in the gitignored `.env`. This keeps secrets out of the database and browser by design.

## 9. Error handling (all covered)
Missing key / invalid provider / missing model / missing base URL → `llm_config_validity()` false, honest unavailable. Connection refused / timeout / 401 / 403 / 404 / 429 / 500 / 502 / invalid JSON / unexpected structure / empty response → sanitized error, `(None, None, errors)`, **no fabricated AI output**. The caller distinguishes real AI output vs offline fallback vs provider error vs invalid config.

## 10. OpenRouter compatibility — **IMPLEMENTED, MOCK VERIFIED + LIVE CONNECTION CONFIRMED**
With defaults (`LLM_PROVIDER=openrouter`, empty overrides) the client behaves exactly as before. Regression suite green (mock). Additionally, a **live `POST /api/llm/test` against OpenRouter succeeded** during Stage-1 verification — the harmless probe returned a reply via the free fallback model (`inference_ok=true`), confirming the generic client talks to OpenRouter end-to-end. (The paid model remains credit-limited; the free fallback answered.)

## 11. OmniRoute readiness — **IMPLEMENTED (config path), NOT LIVE VERIFIED**
Setting `LLM_PROVIDER=omniroute` + `LLM_BASE_URL=http://127.0.0.1:<port>/v1` + a key routes the planner through OmniRoute. **OmniRoute itself is NOT installed in this stage**, so this is config-ready only — **not** live-verified. Mocked tests prove the config/abstraction, not live OmniRoute connectivity.

## 12. API endpoints
- `GET /api/llm/config` — current config (no key).
- `POST /api/llm/config` — update provider/base_url/model/timeout (+ optional key, in-memory only).
- `POST /api/llm/test` — harmless staged connection test.

## 13. Tests — **MOCK VERIFIED**
`backend/tests/test_llm_config.py` (25 tests, all HTTP mocked): OpenRouter/openai_compatible/omniroute config; custom base URL + model; missing key/model; invalid provider; connection refused; timeout; 401/403/404/429/500/502; invalid structure; empty response; **secret never in errors**; connection test success/auth-failure/unreachable; API GET never returns the key; POST doesn't echo the key; test endpoint mocked. Backend total: **165 passed, 1 deselected (live OpenRouter), 1 warning**. Frontend typecheck + build clean.

## 14. Known limitations
- Live provider calls (including OmniRoute) are **not verified** here (mock only).
- Runtime config is non-persistent (`.env` is the durable store).
- The legacy simulation client (`agent/decision.py`) still uses its own OpenRouter settings; it is not the centralized planner path and was intentionally left unchanged.
