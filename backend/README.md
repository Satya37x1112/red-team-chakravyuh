# VAJRAPRAHAAR backend

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

## External tool integrations

`app/integrations/` wires four red-team tools in behind one optional interface
(`app/integrations/base.py`). Every adapter degrades honestly: if its binary,
package, key, or config is missing, `status()` reports `available: false` with a
reason — it never crashes the server, matching the telemetry collector's posture.

- **caldera** (`caldera-ai-project`, pure Python) — parses a MITRE Caldera
  operation report into ATT&CK technique/tactic coverage + pass/fail stats, then
  an optional OpenRouter SOC narrative (reuses `OPENROUTER_API_KEY`, never Groq).
- **locust** (`locust-master`) — the real DDoS load driver. Fail-closed: runs
  only when `LOCUST_ENABLED=true` and an operator `LOCUST_FILE_PATH` +
  `LOCUST_TARGET_URL` are set, and only that locustfile against that one target,
  with users/spawn-rate/duration hard-capped by config.
- **vervet** (Rust CLI) — read-only `describe` / coverage. Never fires `emulate`
  (vervet itself refuses it without an Ed25519-signed scope manifest).
- **pentestgpt** — detects the installed agent and reports how to enable it;
  engagements stay a deliberate CLI action inside an authorized scope.

## Key endpoints

    GET  /api/health
    GET  /api/telemetry/latest
    GET  /api/decision/{ddos|bruteforce|ratuba}   # AGENT DECISION, read-and-reason
    POST /api/attacks/start   {kind}
    POST /api/attacks/{session_id}/kill
    GET  /api/sessions · /api/sessions/{id} · /api/results/{id}
    WS   /ws

    GET  /api/integrations                         # status of all four adapters
    GET  /api/integrations/{name}
    GET  /api/integrations/caldera/samples
    POST /api/integrations/caldera/analyze  {sample|reports, ai}
    GET  /api/integrations/vervet/describe
    POST /api/integrations/locust/run       {users?, spawn_rate?, run_seconds?}  # gated
