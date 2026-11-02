# CHAKRAVYUH backend

FastAPI service: real telemetry collector, Postgres models, AI decision engine
(via OpenRouter), attack-module stubs, and a WebSocket event stream.

## Run locally (no Docker)

    python -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env            # then edit — keys go here, never in source

    # Quick dev run with SQLite and local-machine telemetry:
    DATABASE_URL="sqlite:///./dev.db" TELEMETRY_SOURCE=local \
      uvicorn app.main:app --reload --port 8077

## Telemetry sources (TELEMETRY_SOURCE)

- `local` — collector runs on the Windows target; psutil + (optional) pywin32.
- `winrm` — poll a remote Windows target over WinRM; set WINRM_* in `.env`.
- `none`  — nothing wired; the API honestly reports `available: false`.

Unavailable metrics are returned as `null`, never fabricated.

## AI decision engine

All LLM calls route through OpenRouter's OpenAI-compatible endpoint (the native
`anthropic` SDK is not used). Put `OPENROUTER_API_KEY` in `.env` (gitignored)
and optionally set `OPENROUTER_MODEL` (default `anthropic/claude-sonnet-4.5`).
With no key, the engine returns a labelled `llm_unavailable` result instead of
inventing a value.

## execute() is a stub

Every module's `execute()` raises `NotImplementedError`. The orchestrator runs
the full lifecycle (discover → profile → plan → prepare → observe → adapt →
analyze → result) over real telemetry, and records that execution is deferred to
an authorized lab adapter. No traffic, credentials, or implants originate here.

## Key endpoints

    GET  /api/health
    GET  /api/telemetry/latest
    GET  /api/decision/{ddos|bruteforce|ratuba}   # AGENT DECISION, read-and-reason
    POST /api/attacks/start   {kind}
    POST /api/attacks/{session_id}/kill
    GET  /api/sessions · /api/sessions/{id} · /api/results/{id}
    WS   /ws
