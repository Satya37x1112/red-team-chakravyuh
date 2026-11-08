# CHAKRAVYUH — Stage 5.3: Deployment Readiness & Operational Verification

**Author:** Implementation engineer (Claude Code, on Kali) — verifier
**Date:** 2026-11-07
**Nature:** Verification + documentation. No source modified, no commits, no target contact, no real execution/scan, no live OpenRouter call. Dev servers preserved. This is an **academic, isolated cyber-range** app — production-grade security is explicitly **not** claimed.

Status vocabulary: `READY` · `READY WITH LIMITATIONS` · `NOT READY` · `BLOCKED` · `NOT VERIFIED`.

---

## 1. Environment Inventory

| Item | Value | Class |
|---|---|---|
| OS | Kali Linux (VMware) | AVAILABLE |
| Python | 3.13.12 | AVAILABLE (required) |
| Node.js | v22.11.0 (at `~/.local/node`) | AVAILABLE (required) — **not a system install; needs PATH** |
| npm | present at `~/.local/node/bin` | AVAILABLE — runs only with node on PATH |
| git | 2.53.0 | AVAILABLE |
| Hydra | `/usr/bin/hydra` | AVAILABLE (required for Hydra module) |
| Locust | `2.47.0` (backend venv) | AVAILABLE (required for Locust module) |
| NetExec (`nxc`/`netexec`) | `/usr/bin/nxc` | AVAILABLE (required for Remote Access) |
| Evil-WinRM | `/usr/bin/evil-winrm` | OPTIONAL (adapter uses nxc; evil-winrm is an alternate, unused) |
| `/dev/shm` | writable | AVAILABLE (used for the remote-access credential file) |
| Backend Python packages | installed in `backend/.venv` | AVAILABLE |
| Frontend deps | `frontend/node_modules` | AVAILABLE |
| OpenRouter — free model | reachable | AVAILABLE |
| OpenRouter — paid model (`claude-sonnet-4.5`) | out of credits | BLOCKED |

**Required runtime:** Python+venv, Node/npm (for the frontend), FastAPI/uvicorn, SQLite. **Optional integrations:** Hydra/Locust/NetExec (each disabled by default), WinRM telemetry, blackbox telemetry, OpenRouter AI.

---

## 2. Startup & Shutdown — **READY WITH LIMITATIONS**

Verified (actual commands, from `RUN_SERVERS.md` / `KALI.md`):
- **Backend:** `cd backend && source .venv/bin/activate && python -m uvicorn app.main:app --host 127.0.0.1 --port 8077` → `/api/health` = `{"status":"ok","telemetry_source":"none","halted":false}` ✓. Bind is **127.0.0.1 (loopback)** — not exposed. `init_db()` runs on startup (SQLite `dev.db`). No `--reload`/`debug` flags.
- **Frontend:** `cd frontend && npm run dev` (Vite) → HTTP 200 on `http://localhost:5173`. Proxy: `/api → localhost:8077`, `/ws → ws://localhost:8077` ✓.
- **Graceful shutdown:** FastAPI `lifespan` calls `service.stop()`; the unified kill switch terminates managed adapter process groups.

**Limitations (documented, not fixed — no scripts created per the brief):**
1. **No automated startup/shutdown script** — startup is manual per `RUN_SERVERS.md`.
2. **Node/npm not persistent on PATH** — a fresh shell needs `export PATH="$HOME/.local/node/bin:$PATH"` (or a proper Node install) before `npm`.
3. **No duplicate-process prevention / port-conflict guard** — a second backend on `:8077` simply fails to bind and exits (observed); no PID file.
4. **Vite binds `localhost`/IPv6 (`::1`)** — reachable at `http://localhost:5173`, not `http://127.0.0.1:5173` (IPv4).
5. **Ungraceful backend kill** (SIGKILL) can orphan an in-flight adapter subprocess group (normally none, since modules are disabled); a graceful stop or the kill switch handles cleanup.

---

## 3. Configuration Readiness — **READY**

All optional/dangerous features are **disabled-by-default and fail-closed** (`.env.example`): `TELEMETRY_SOURCE=none`, `HYDRA_ENABLED=false`, `LOCUST_ENABLED=false`, `REMOTE_ACCESS_ENABLED=false`, `SAFETY_ADMIN_TOKEN=` (empty → reset refused).

| Area | Readiness | Evidence |
|---|---|---|
| **AI (OpenRouter)** | READY WITH LIMITATIONS | honest `fallback`/`unavailable` with no/failed key; paid model BLOCKED (credits); key never printed/returned |
| **Hydra** | READY WITH LIMITATIONS | binary present; disabled-by-default; fail-closed `status()`; live NOT VERIFIED |
| **Locust** | READY WITH LIMITATIONS | module 2.47 present; caps (users/spawn/duration) clamp-down; disabled-by-default; live NOT VERIFIED |
| **Remote Access** | READY WITH LIMITATIONS | nxc present; `/dev/shm` writable (0600 cred file, cleaned every path, fail-closed if uncreatable); disabled-by-default; live NOT VERIFIED |
| **Telemetry** | READY WITH LIMITATIONS | `none` default; `blackbox` = IPv4+RFC1918+`BLACKBOX_ALLOWLIST`, auth-before-socket, time-budget, honest-unavailable; `winrm`/`local` present; live NOT VERIFIED |

No secret value is printed anywhere in config handling.

---

## 4. Security & Operational Readiness — **READY WITH LIMITATIONS** (academic isolated)

- **Secrets:** `.env` is **gitignored and untracked**; `.env.example` holds placeholders only; no secret in the repo. Remote-access password uses a 0600 `/dev/shm` file (never argv/logs/audit/API).
- **Bind / exposure:** backend `127.0.0.1`; CORS restricted to `http://localhost:5173` + `http://127.0.0.1:5173`. No `0.0.0.0` exposure.
- **No API auth** (by design — single-operator isolated lab). **Not production-secure; not claimed.**
- **Kill switch:** starts **not engaged** (`halted:false`); reset is **token-gated** (`SAFETY_ADMIN_TOKEN`) — fail-closed when unset (frontend rearm then 403, graceful).
- **Audit/DB:** `init_db()` auto-creates tables on startup; `Operation`/`OperationIteration`/`AuditRecord` persist (secret-masked). No Alembic migrations (fine for the lab).
- **Debug:** no `debug=True`/`--reload`.

---

## 5. Operational Recovery — **READY WITH LIMITATIONS**

Verified via the offline test suite + the running app (no target, no attack):
| Scenario | Result | Evidence |
|---|---|---|
| Missing AI key | honest fallback/unavailable | `test_planner.py::test_llm_unavailable_labeled_fallback` |
| Missing optional tool | honest `unavailable` | adapter `status()` tests |
| Missing env vars / config | disabled/unavailable (fail-closed) | `test_gateway.py`, `test_blackbox_telemetry.py::test_missing_config_unavailable` |
| Kill switch active → new ops blocked | rejected | `test_killswitch.py`, `test_operation_loop.py::test_killswitch_prevents_execution` |
| Execution timeout | `TIMED_OUT` recorded | `test_remote_access.py::test_timeout_maps_to_timed_out` |
| Adapter failure | `FAILED` recorded, no false success | `test_*::*adapter_failure*`, `test_execution_error_recorded_and_stops` |
| Temp credential-file cleanup | removed on success/timeout/failure | `test_credential_file_cleaned_up_on_*` |
| Restart with no active op | clean (health ok) | running app |
| No false success after failure | guaranteed (evidence-based `objective_met`) | `test_no_fabricated_metrics` |
| **Backend unavailable → frontend** | honest error states | frontend catches API errors (code-only) |
| **Database unavailable** | **NOT VERIFIED** | no explicit DB-outage test |

**Recovery limitation:** the execution registry + kill-switch state are **in-memory** — a backend restart clears them (the audit trail in SQLite persists). An interrupted execution's subprocess is not auto-resumed (by design; it is bounded/read-only).

---

## 6. Dashboard Operational Checks — **VERIFIED BY CODE ONLY**

Pages inspected (relative `/api` wiring, honest states, no secrets): **AI Planner**, **Integrations** (Hydra/Locust panels), **Remote Access** (approved ops, no shell, kill-switch aware), **Target Recon** (IP → open ports → telemetry, "partial probe" banner, CPU/RAM "not visible"), **Operations**, kill-switch controls in `Layout`. Telemetry labels honest (`windows_target_external`/`kali_host`/`unavailable`). Disabled modules present honestly (status reason shown).
- `npm run typecheck` ✓ · `npm run build` ✓. **No browser click-through performed** (not claimed).
- Known: Hydra/Locust have no dedicated pages (via Integrations/AI Planner); rearm token wiring pending.

---

## 7. Automated Test Results

```
cd backend && source .venv/bin/activate
python -m pytest tests/ -q --deselect "tests/test_live_llm.py::test_live_structured_plan_validates_and_is_bound"
→ 140 passed, 1 deselected, 1 warning in ~5s
```
- **Passed 140 · Failed 0 · Skipped 0 · Deselected 1** (the live OpenRouter test — only network-dependent test, isolated transparently, not modified). **Warnings 1** (upstream Starlette deprecation).
- **Network-dependent:** 1 (deselected). All other 140 are mock/offline. Frontend: typecheck ✓, build ✓.

---

## 8. Deployment Readiness Matrix

| Area | Status | Note |
|---|---|---|
| STARTUP | READY WITH LIMITATIONS | works; manual (no script), Node-PATH friction, no dup-guard |
| SHUTDOWN | READY WITH LIMITATIONS | lifespan stop ok; orphan-child risk on SIGKILL |
| BACKEND | READY | boots, health ok, 140 tests |
| FRONTEND | READY WITH LIMITATIONS | typecheck+build ok; Node not persistent; binds `localhost`/IPv6 |
| DATABASE | READY WITH LIMITATIONS | SQLite auto-init; no migrations; DB-outage recovery NOT VERIFIED |
| CONFIGURATION | READY | fail-closed defaults, documented |
| AI PROVIDER | READY WITH LIMITATIONS | honest fallback; paid model BLOCKED (credits) |
| HYDRA | READY WITH LIMITATIONS | present, disabled-by-default, mock-verified; live NOT VERIFIED |
| LOCUST | READY WITH LIMITATIONS | present, disabled, mock-verified; live NOT VERIFIED |
| REMOTE ACCESS | READY WITH LIMITATIONS | present, disabled, hardened, mock-verified; live NOT VERIFIED |
| TELEMETRY | READY WITH LIMITATIONS | none default; blackbox authorized+bounded (mock); winrm/live NOT VERIFIED |
| SAFETY GATEWAY | READY | verified by code + tests |
| KILL SWITCH | READY | verified; not-engaged at startup; token-gated reset |
| AUDIT LOGGING | READY | secret-masked persistence verified |
| SECURITY | READY WITH LIMITATIONS | academic isolated; .env safe; no API auth (by design); rearm token wiring pending |
| RECOVERY | READY WITH LIMITATIONS | restart clean; in-memory state resets; DB-outage NOT VERIFIED |

---

## 9. Remaining Blockers / Live-Unverified

- **Live-unverified:** real Hydra/Locust/NetExec/WinRM/blackbox against a target; frontend browser click-through.
- **BLOCKED:** paid-model AI (OpenRouter credits).
- **Operational gaps (non-blocking):** no startup script, Node PATH not persistent, no duplicate-process guard, DB-outage recovery untested, rearm UI token wiring.
- None of these block a **mock/demo** run; they bound a **live** demonstration.

---

## 10. Final Readiness Statement

CHAKRAVYUH **starts reliably on Kali** (manual commands), the **frontend talks to the backend** (Vite proxy verified), all **required dependencies are available** (Node needs PATH), optional integrations **degrade honestly** when unavailable, **secrets are protected**, the **kill switch and audit/DB are operational**, and the app **recovers** from the tested failure modes. It is **READY WITH LIMITATIONS for demonstration preparation**, and **NOT YET live-verified** against a real target.

See `docs/CHAKRAVYUH_MASTER_PROGRESS.md` for the cumulative record (Stage 5.3 entry added).
