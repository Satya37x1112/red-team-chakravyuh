# CHAKRAVYUH — Kali Setup & Operational Guide

**Date:** 2026-11-07 · Commands below are the **actual** ones used in this repository. Never put real secrets in these files; `.env` is gitignored.

Base path used throughout: `/home/kali/AI_red_Team/red-team-chakravyuh/`.

---

## 1. Kali requirements (already present in this environment)

| Tool | Check |
|---|---|
| Python 3.13 | `python3 --version` |
| Node.js v22 (at `~/.local/node`) | `~/.local/node/bin/node --version` |
| git | `git --version` |
| Hydra | `command -v hydra` → `/usr/bin/hydra` |
| NetExec | `command -v nxc` → `/usr/bin/nxc` |
| Evil-WinRM (optional) | `command -v evil-winrm` |
| `/dev/shm` writable | `[ -w /dev/shm ] && echo yes` |

Native attack tools are **optional integrations** — each module is disabled by default and only needed when you arm it.

## 2. Python environment (backend)

```bash
cd /home/kali/AI_red_Team/red-team-chakravyuh/backend
python3 -m venv .venv                 # already created in this environment
source .venv/bin/activate
pip install -r requirements.txt       # already installed
pip install locust                    # the DDoS driver (already installed: 2.47.0)
[ -f .env ] || cp .env.example .env   # create local config (gitignored)
```

## 3. Node.js PATH setup (frontend)

Node is installed under `~/.local/node` and is **not on PATH by default**. In every new shell before using `npm`:
```bash
export PATH="$HOME/.local/node/bin:$PATH"
node --version   # v22.11.0
npm --version
```

## 4. Backend startup

```bash
cd /home/kali/AI_red_Team/red-team-chakravyuh/backend
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8077
```
- Binds to **127.0.0.1** (loopback — not exposed on the network).
- On startup it initialises the SQLite DB and starts the telemetry poller.

**Health check:** `curl -s http://127.0.0.1:8077/api/health` → `{"status":"ok","telemetry_source":"none","halted":false}`.

## 5. Frontend startup

```bash
cd /home/kali/AI_red_Team/red-team-chakravyuh/frontend
export PATH="$HOME/.local/node/bin:$PATH"
npm install        # already installed (node_modules present)
npm run dev        # Vite dev server on port 5173
```

## 6. Browser URL

Open **http://localhost:5173** (Vite binds `localhost`/IPv6 — use `localhost`, not `127.0.0.1`). Sidebar: **AI Planner**, **Integrations**, **Remote Access**, **Target Recon**, **Operations**, kill switch.

The frontend proxies `/api → http://localhost:8077` and `/ws → ws://localhost:8077` (see `frontend/vite.config.ts`).

## 7. Environment configuration (`backend/.env`)

Everything is **disabled and fail-closed by default**. Fill in only what you arm. **Never commit real values** (the file is gitignored). Variable names only shown here:

**AI (optional):** `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_FALLBACK_MODELS`. Empty key ⇒ honest fallback.

**Hydra (optional attack):** `HYDRA_ENABLED=false`, `HYDRA_TARGET`, `HYDRA_SERVICE`, `HYDRA_PORT`, `HYDRA_USERLIST_PATH`, `HYDRA_PASSLIST_PATH`, `HYDRA_MAX_*` caps.

**Locust (optional attack):** `LOCUST_ENABLED=false`, `LOCUST_TARGET_URL`, `LOCUST_FILE_PATH`, `LOCUST_MAX_USERS/SPAWN_RATE/RUN_SECONDS`.

**Remote Access (optional attack):** `REMOTE_ACCESS_ENABLED=false`, `REMOTE_ACCESS_TARGET`, `REMOTE_ACCESS_USER`, `REMOTE_ACCESS_PASSWORD` (secret), `REMOTE_ACCESS_DOMAIN`, `REMOTE_ACCESS_MAX_RUN_SECONDS`.

**Telemetry (optional):** `TELEMETRY_SOURCE=none|local|winrm|blackbox`. For blackbox: `BLACKBOX_TARGET` (RFC1918 IPv4), `BLACKBOX_ALLOWLIST` (must contain the target), `BLACKBOX_PORTS`, `BLACKBOX_TIMEOUT_SECONDS`, `BLACKBOX_TOTAL_BUDGET_SECONDS`. For winrm: `WINRM_ENDPOINT/USER/PASSWORD`.

**Safety:** `SAFETY_TARGET_ALLOWLIST` (attack targets), `SAFETY_ADMIN_TOKEN` (required to reset the kill switch), `SAFETY_MAX_CONCURRENT_EXECUTIONS`, `KILLSWITCH_GRACE_SECONDS`.

> **Arming note (authorized lab only):** to run a module you must set its `*_ENABLED=true`, add the target to the relevant allowlist, and provide its inputs (wordlists / locustfile / credentials). Do recon first (`nmap -sV -Pn <TARGET_IP>`).

## 8. Optional native dependencies

Hydra / NetExec are on the Kali PATH; Locust is in the venv; Evil-WinRM is present but unused (NetExec is the adapter's engine). vervet (Rust) and PentestGPT are optional extras and degrade honestly if absent.

## 9. Safe shutdown

- **Graceful:** `Ctrl-C` in the uvicorn / `npm run dev` terminals (FastAPI lifespan stops the telemetry poller).
- Avoid `kill -9` on the backend while a module is armed and running — a managed adapter subprocess group could orphan; a graceful stop or the kill switch cleans it up.
- To stop only this project's servers precisely, kill by PID (`pgrep -af "uvicorn app.main"` / `pgrep -af vite`) — do not blanket-kill unrelated processes.

## 10. Kill-switch behaviour

- Starts **not engaged** (`halted:false`).
- Engage: `POST /api/killswitch` (or **Win+Alt+K** in the dashboard) → blocks new work and terminates managed adapter process groups.
- **Reset is token-gated:** `POST /api/killswitch/reset` requires `{"admin_token":"<SAFETY_ADMIN_TOKEN>"}`. With no token configured, reset is refused (fail-closed). *(The dashboard rearm button is not yet wired to send the token.)*

## 11. Database location & persistence

- SQLite at `backend/dev.db` (default `DATABASE_URL=sqlite:///./dev.db`). Tables auto-created on startup.
- The **audit trail persists** across restarts; the **execution registry + kill-switch state are in-memory** and reset on restart.

## 12. Troubleshooting

| Problem | Fix |
|---|---|
| `npm: command not found` | `export PATH="$HOME/.local/node/bin:$PATH"` |
| Backend won't bind `:8077` | another process holds the port — `pgrep -af "uvicorn app.main"`, stop it by PID |
| Frontend not at `127.0.0.1:5173` | use **`http://localhost:5173`** (Vite binds IPv6 localhost) |
| AI shows "unavailable / fallback" | no/failed `OPENROUTER_API_KEY`, or paid model out of credits (free fallback still works) |
| A module shows "not armed" / 423 | it's disabled by default — arm it in `.env` (authorized lab only) |
| Kill-switch reset refused (403) | set `SAFETY_ADMIN_TOKEN` and pass it in the reset body |
| Blackbox telemetry "unavailable" | target not configured / not IPv4-private / not in `BLACKBOX_ALLOWLIST` |

Run the test suite any time (offline, no target):
```bash
cd backend && source .venv/bin/activate
python -m pytest tests/ -q --deselect "tests/test_live_llm.py::test_live_structured_plan_validates_and_is_bound"
```
