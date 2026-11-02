# CHAKRAVYUH — AI Red Team Cyber Range Console

Academic project. An AI agent reads **real telemetry** from an isolated Windows
target VM, reasons over it with an LLM, and a dashboard shows three clearly
separated layers: **REAL LAB TELEMETRY**, **AGENT DECISION**, **ANALYSIS**.

## Safety boundary (read this)

This repository contains **no offensive execution code**. It does not open raw
sockets, generate traffic floods, perform credential stuffing against any
endpoint, or deploy any persistence / C2 mechanism.

- Every attack module's `execute()` is an explicit `NotImplementedError` stub.
  Wiring a real, authorized lab adapter is done by the operator *outside* this
  codebase.
- `discover / profile / plan / observe / adapt / analyze` only **read** real
  telemetry and reason about it. They never attack.
- The telemetry collector only **reads** system state (the same data Task
  Manager or `Get-WinEvent` shows). If a value is unavailable it returns
  `null` / `"unavailable"` — it never fabricates a number.

Run only against a machine you own or are authorized to monitor, on an isolated
host-only network.

## Layout

    backend/    FastAPI service: telemetry collector, DB, WebSocket, AI engine, module stubs
    frontend/   React + TypeScript + Tailwind dashboard
    docker-compose.yml

See `backend/README.md` for setup. For Docker, copy `.env.example` to `.env` and set
`POSTGRES_PASSWORD` before `docker compose up`.

## Run locally

Two terminals. Backend first (see `backend/README.md` for detail):

    cd backend
    python -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env     # put OpenRouter key(s) here; file is gitignored
    DATABASE_URL="sqlite:///./dev.db" TELEMETRY_SOURCE=local \
      uvicorn app.main:app --reload --port 8077

Then the dashboard (Vite dev server proxies `/api` and `/ws` to :8077):

    cd frontend
    npm install
    npm run dev        # http://localhost:5173

Kill switch: the header button or **Win+Alt+K** (Ctrl+Alt+K fallback) halts the
range; new sessions are refused until you re-arm. Theme toggle is in the header.

## Deployment

This is a lab console for an isolated, host-only network — not an
internet-facing service. Keep it on the lab network, behind auth if exposed.

1. **Config** — copy `.env.example` to `.env` on the host and fill
   `OPENROUTER_API_KEY` (or the per-module `OPENROUTER_API_KEY_*`), `DATABASE_URL`,
   and `TELEMETRY_SOURCE`. Never commit `.env`.
2. **Containers (recommended)** — `cp .env.example .env`, set `POSTGRES_PASSWORD`,
   then `docker compose up -d --build`. Compose brings up Postgres, the API
   (`:8077`), and the dashboard.
3. **Frontend build (bare-metal)** — `cd frontend && npm ci && npm run build`
   produces static assets in `frontend/dist/`; serve them with any static host
   (nginx/Caddy) and reverse-proxy `/api` and `/ws` to the backend.
4. **Backend (bare-metal)** — run `uvicorn app.main:app --host 0.0.0.0 --port 8077`
   behind a process manager (systemd / a container restart policy). Use Postgres,
   not SQLite, for anything beyond a single-user demo.
5. **Telemetry** — set `TELEMETRY_SOURCE=local` on the Windows target itself, or
   `winrm` with `WINRM_*` creds to poll it remotely.
