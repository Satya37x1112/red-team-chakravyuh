# VAJRAPRAHAAR — AI Red Team Cyber Range Console

Academic project. An AI agent reads **real telemetry** from an isolated Windows
target VM, reasons over it with an LLM, and a dashboard shows three clearly
separated layers: **REAL LAB TELEMETRY**, **AGENT DECISION**, **ANALYSIS**.


## Layout

    backend/    FastAPI service: telemetry collector, DB, WebSocket, AI engine, module stubs
    frontend/   React + TypeScript + Tailwind dashboard
    docker-compose.yml

    caldera-ai-project-main/  MITRE Caldera report analyzer (integrated)
    locust-master/            Locust load-test framework (integrated, gated)
    vervet-main/              Rust signed-emulation CLI (integrated, read-only)
    PentestGPT-main/          LLM pentest agent (integrated, optional)

## Integrations

Four external red-team tools are wired into the console behind one optional
adapter interface (`backend/app/integrations/`), surfaced on the dashboard's
**Integrations** page and under `GET /api/integrations`. Each is optional and
degrades honestly — a missing toolchain, package, or key shows as "unavailable"
with a reason instead of breaking anything:

- **CALDERA analyzer** — turns a Caldera operation report into ATT&CK
  technique/tactic coverage, pass/fail stats, and an AI SOC narrative (via the
  same OpenRouter key the decision engine uses). Ships with sample reports.
- **Locust** — the real DDoS load driver behind the DDoS module. Fail-closed:
  inert until the operator sets `LOCUST_ENABLED=true` plus an authored locustfile
  and an authorized target; users/rate/duration are hard-capped by config.
- **vervet** — read-only `describe`/coverage from the signed-emulation CLI; the
  state-changing `emulate` verb is never invoked from the console.
- **PentestGPT** — detected if installed; engagements remain a deliberate,
  scoped CLI action.

Enable any of them by filling the relevant keys in `backend/.env` (see
`backend/.env.example`). The core console runs fully without any of them.

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
2. **Containers (recommended)** — in the repo root:

       cp .env.example .env               # set POSTGRES_PASSWORD
       cp backend/.env.example backend/.env   # set OPENROUTER_API_KEY*, TELEMETRY_SOURCE
       docker compose up -d --build

   Compose builds three services: Postgres, the backend, and an nginx container
   that serves the built dashboard and proxies `/api` + `/ws` to the backend.
   Open the dashboard at **http://localhost:8080**. The backend is only reachable
   inside the compose network (expose a port in `docker-compose.yml` if you need
   it directly).
3. **Frontend build (bare-metal)** — `cd frontend && npm ci && npm run build`
   produces static assets in `frontend/dist/`; serve them with any static host
   (nginx/Caddy — see `frontend/nginx.conf`) and reverse-proxy `/api` and `/ws`
   to the backend.
4. **Backend (bare-metal)** — run `uvicorn app.main:app --host 0.0.0.0 --port 8077`
   behind a process manager (systemd / a container restart policy). Use Postgres,
   not SQLite, for anything beyond a single-user demo.
5. **Telemetry** — set `TELEMETRY_SOURCE=local` on the Windows target itself, or
   `winrm` with `WINRM_*` creds to poll it remotely.
