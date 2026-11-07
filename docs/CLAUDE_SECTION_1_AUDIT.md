# CHAKRAVYUH — Section 1: Complete Repository Audit

**Author:** Implementation engineer (Claude Code, on Kali)
**Date:** 2026-11-07
**Repository:** `/home/kali/AI_red_Team/red-team-chakravyuh/`
**Git:** branch `main`, HEAD `b7e7621` ("Add project status / update summary"), working tree clean, up to date with `origin/main`.
**Scope of this document:** read-only audit only. No features implemented, no dependencies installed for the app, no attack tools launched, no network connection made to any Windows target. (Node.js was installed locally earlier in the session to run the frontend dev server; that is noted in §12, not part of this audit's changes.)

> **Evidence convention.** Claims are tagged `[FACT]` when verified by reading the file / running a read-only check, and `[ASSUMPTION]` when inferred. File references use `path:line`.

---

## 1. Executive Summary

CHAKRAVYUH (previously **VAJRAPRAHAAR** — the name is still in the code, e.g. `backend/app/main.py:28`) is a FastAPI + React cyber-range console with a genuinely well-engineered, **honest, fail-closed** foundation. The code never fabricates telemetry or outcomes, degrades gracefully when a tool/key is missing, and masks secrets (e.g. Hydra never returns a cracked password). That discipline is the project's biggest asset and matches your "real data, labelled evidence" requirement closely.

**However, the single most important thing to understand is that the repository today is actually _two disconnected systems_:**

1. **The "agent" path** (`/api/attacks/start` → `orchestrator` → `modules`): a lifecycle state-machine that reads **real** telemetry but whose `execute()` step is **SIMULATION ONLY** for all three modules. The "AI" here recommends **one bounded integer per module** (e.g. "use 7 load sources") and nothing executes for real.
2. **The "integrations" path** (`/api/integrations/*/run` → adapters): this is where **real** tools run — Hydra and Locust actually execute against a configured target. But this path has **no AI planner, no orchestrator, no kill-switch gating, and no feedback loop**.

Your vision — *one centralized AI brain that understands an objective, plans, is validated by a schema, gated by a deterministic Safety Gateway, dispatched to a module, executed for real, observed, analyzed, and fed back* — **does not yet exist as one integrated pipeline.** The pieces exist in isolation; the spine that connects "AI decision" → "validation" → "safety gateway" → "real execution" → "evidence" → "next AI decision" is missing.

**Readiness vs. your vision: ~35–40%.** Strong foundation (telemetry, two real tool adapters, UBA, dashboard, fail-closed safety primitives), but the centralized planner, the schema validator, the standalone Safety Gateway, the dispatcher that routes AI plans to real adapters, the real Module-3 remote-access capability, and the feedback loop are all missing or partial.

---

## 2. My Original Project Vision (restated for alignment)

From your master instructions, the intended system is:

- **One centralized AI planner** (not three independent agents) that takes a **user objective**, analyzes recon + telemetry, and emits a **structured, machine-readable execution plan** with bounded parameters.
- A **schema validator** on the AI output.
- A **deterministic Safety Gateway** (independent of the AI) that validates scope, authorization, and limits.
- A **Scenario Dispatcher** → one of three modules (Brute Force / DDoS / RAT-related).
- Real **execution adapters** that independently enforce hard caps.
- An **Observation Engine** → **Result Analyzer** → **AI feedback loop** (continue / modify / stop).
- Full **audit** of every decision, gateway verdict, execution, and result.
- **Kali-only**, **no Docker**, **no VS Code**, **nothing installed on the Windows target**, **real evidence only**.

This audit measures the current repo against exactly that.

---

## 3. Existing Repository Overview `[FACT]`

Top-level layout (vendored upstream tool repos included in-tree):

```
red-team-chakravyuh/
├── backend/            FastAPI app (the project backend)        ← primary work
├── frontend/           React + TypeScript + Vite dashboard      ← primary work
├── caldera-ai-project-main/   vendored: Caldera report analyzer source + sample data
├── locust-master/      vendored: upstream Locust (load-test engine + its own tests)
├── thc-hydra-master/   vendored: upstream THC-Hydra source
├── vervet-main/        vendored: vervet Rust adversary-emulation CLI source
├── PentestGPT-main/    vendored: PentestGPT agent source
├── docker-compose.yml, */Dockerfile      ← present but CONTRADICT the "no Docker" directive
├── KALI.md, RUN_SERVERS.md, WINDOWS_VM_SETUP.md, WORKLOG_*.md, PROJECT_STATUS.md, README.md
└── docs/CLAUDE_SECTION_1_AUDIT.md         ← this file (created by Section 1)
```

Backend source size `[FACT]` (project code only, excluding vendored repos): **~4,222 lines of Python** across 30 files. Frontend: **~5,269 lines of TS/TSX** across 34 files.

---

## 4. Current Technical Architecture (as-built, not as-envisioned) `[FACT]`

### Path A — the "agent / simulation" pipeline
```
POST /api/attacks/start (routes.py:85)
   → orchestrator.run()  (agent/orchestrator.py:170)
       DISCOVER → PROFILE → PLAN → PREPARE → EXECUTE → OBSERVE → ADAPT → ANALYZE → RESULT
                            │                    │
                            │                    └── module.execute()  = SIMULATION ONLY
                            │                         (modules/base.py:116 docstring,
                            │                          ddos.py:25, bruteforce.py:109, ratuba.py:33)
                            └── module.plan() → agent/decision.py:decide()
                                  = ONE bounded integer per module (not a plan)
   → persists AgentEvent + SimulationMetric + AttackResult
   → broadcasts over WebSocket (ws.py)
```
Real telemetry is read before/after (`service.collect_once`), so OBSERVE/ADAPT/ANALYZE are grounded — but **no real attack happens on this path.**

### Path B — the "integrations" pipeline (the real tools)
```
POST /api/integrations/hydra/run   (api/integrations.py:251) → HydraIntegration.run()  → REAL hydra subprocess
POST /api/integrations/locust/run  (api/integrations.py:212) → LocustIntegration.run() → REAL locust subprocess
POST /api/integrations/vervet/emulate (api/integrations.py:157) → REAL vervet scan (if built)
POST /api/integrations/caldera/analyze → read-only report analysis
   → persists IntegrationArtifact (central store)
   → /api/central/* aggregates artifacts into Operations Center + report
```
**This path has no AI planner, no Safety-Gateway object, and is NOT covered by the kill switch** (see §11).

### The gap
There is **no component** that connects Path A's AI decision to Path B's real execution. The AI never drives a real tool; the real tools never consult the AI, the gateway, or the kill switch.

---

## 5. Backend Audit (component by component)

| Component | File | Status | Notes |
|---|---|---|---|
| FastAPI app / lifespan | `app/main.py` | **IMPLEMENTED AND VERIFIED** | App boots; `/api/health` returned `{"status":"ok"}` when run this session `[FACT]`. Title still "VAJRAPRAHAAR" (`main.py:28`). CORS locked to `localhost:5173` (`main.py:32`). |
| REST routes | `app/api/routes.py` | **IMPLEMENTED BUT UNVERIFIED** | Sessions, telemetry, decision, kill switch, analytics endpoints present. Logic read, not exercised. |
| Integrations API | `app/api/integrations.py` | **IMPLEMENTED BUT UNVERIFIED** | Clean REST surface; real-action endpoints gated behind `preconditions()` returning HTTP 423. |
| Central/Operations API | `app/api/central.py` | **IMPLEMENTED BUT UNVERIFIED** | Aggregates artifacts into a pentest report + port-intel analysis (`central.py:230` `_PORT_INTEL`). Read-only. |
| AI decision engine | `app/agent/decision.py` | **PARTIALLY IMPLEMENTED** (vs. vision) | Per-module single integer, honest fallback. Not a centralized planner. See §7. |
| Orchestrator | `app/agent/orchestrator.py` | **IMPLEMENTED BUT UNVERIFIED** | Drives the lifecycle + persistence + WS. `execute()` is simulation (`orchestrator.py:218`). |
| Config | `app/config.py` | **IMPLEMENTED AND VERIFIED** | Pydantic settings, all caps + fail-closed flags. Loads `.env` `[FACT]`. |
| DB engine | `app/db.py` | **IMPLEMENTED AND VERIFIED** | SQLAlchemy; SQLite default (`dev.db` exists `[FACT]`); `create_all` (no Alembic — comment at `db.py:38`). |
| Models | `app/models.py` | **IMPLEMENTED AND VERIFIED** | Target, TelemetrySnapshot, AttackSession, AgentEvent, AttackResult, IntegrationArtifact, SimulationMetric. `Target.authorized` column exists (`models.py:67`) but is **not enforced anywhere** `[FACT]`. |
| Telemetry collector | `app/telemetry/collector.py` | **IMPLEMENTED BUT UNVERIFIED** | local (psutil) / winrm (pywinrm) / none. See §10. |
| Telemetry service | `app/telemetry/service.py` | **IMPLEMENTED AND VERIFIED** | Background poller + ring buffer; started on boot `[FACT]`. |
| WebSocket hub | `app/ws.py` | **IMPLEMENTED BUT UNVERIFIED** | Single broadcast channel, dead-socket reaping. |
| Observation/Analyzer | `app/modules/base.py` | **PARTIALLY IMPLEMENTED** | `observe()` compares two real snapshots (real); `adapt()` is a trivial ±1 nudge (`base.py:137`). No standalone "Result Analyzer" / "Observation Engine" objects — logic lives inside the module + orchestrator. |
| Audit logging | (via `AgentEvent` + `IntegrationArtifact`) | **PARTIALLY IMPLEMENTED** | See §11. |

---

## 6. Frontend Audit `[FACT]`

- **Stack:** React 18 + TypeScript + Vite 5 + Tailwind 3 (`frontend/package.json`). Dev server proxies `/api` and `/ws` to `:8077` (`vite.config.ts`), so no CORS/base-URL config needed in dev.
- **Data source discipline:** a grep for `Math.random` / `mock` / `placeholder` / `fake` / `dummy` across `frontend/src` found **no fabricated data** — the only hits are a form placeholder string and comments explicitly stating data is *not* mocked (`components/RatDetectionsPanel.tsx:7`, `components/charts.tsx:257`). **Status: good — the UI renders real API/WS data.**
- **Pages/panels present:** Dashboard, OperationsCenter, Operation, Integrations (593 lines — the largest, drives Caldera/vervet/Locust/Hydra), History, Reports/Report, Range, AgentActivity, plus charts, telemetry, RAT intel/detection, host-load, wordlist panels.
- **API client:** `src/api.ts` exposes `hydraRun`, `locustRun`, `vervetEmulate`, `calderaAnalyze`, `killSwitch`, etc. — the frontend **can** trigger the real integration runs.
- **Missing vs. vision:** **no objective-input UI** (the user cannot "provide an objective"; the UI starts a fixed `kind`). **No remote-access / Module-3-real UI** — a grep for `remote.access|netexec|evil-winrm|nxc|impacket` in `frontend/src` returned nothing `[FACT]`.

**Status: IMPLEMENTED BUT UNVERIFIED** (pages render from real endpoints; not click-tested in this audit).

---

## 7. AI Engine Audit (the heart — most important) `[FACT]`

File: `app/agent/decision.py` (293 lines), plus text helper `app/integrations/_llm.py`.

**What it is:** `decide(kind, telemetry)` asks an OpenRouter LLM to return **one bounded integer** for the given module:
- `ddos` → `recommended_sources` (1–12) — `decision.py:36`
- `bruteforce` → `recommended_attempt_rate` (1–30) — `decision.py:46`
- `ratuba` → `recommended_baseline_window_minutes` (5–120) — `decision.py:55`

**Strengths `[FACT]`:**
- **Honest fallback chain:** no key → `llm_unavailable` (`decision.py:126`); model out of credits/errors → transparent, telemetry-grounded **heuristic** clearly labelled `status: "heuristic"` (`decision.py:239`). It never invents a number silently.
- **Read-only by construction:** docstring and design forbid actions (`decision.py:1`).
- **Output is bounded** by `_clamp()` against the brief's min/max (`decision.py:216`).
- All LLM traffic routes through OpenRouter (OpenAI-compatible), per your stack.

**Gaps vs. your vision — measured against §E of your brief:**
| Requirement | Present? | Evidence |
|---|---|---|
| One centralized AI engine | **No** — it's one function keyed by `kind`, called per-module | `modules/base.py:105` `plan()` calls `decide(self.kind, …)` |
| Receives actual telemetry | **Yes** | `_telemetry_digest()` `decision.py:78` |
| Receives execution *results* for re-planning | **No** — it only sees telemetry, never the prior execution result | `decide()` signature takes only telemetry |
| Produces a **structured execution plan** | **No** — it returns `{decision:int, reasoning, confidence}` | `decision.py:160` |
| Output validation (schema) | **Partial** — a clamp + int-coerce, not a schema validator | `decision.py:159`, `_coerce_int` |
| Deterministic safety checks on AI output | **No** — no gateway consumes the AI output | (none) |
| Fallback decisions labelled | **Yes** | `status` ∈ `{ok, heuristic, llm_unavailable}` |
| AI feedback genuinely connected to next decision | **No** — `adapt()` is a fixed ±1 CPU-delta nudge, not an AI re-plan | `modules/base.py:137` |

**Status: PARTIALLY IMPLEMENTED.** The honest-degradation engineering is excellent and reusable, but this is a *parameter recommender*, not the *centralized planner* your vision requires, and it is wired **only** to the simulation path, never to real execution.

---

## 8. Three-Module Implementation Audit

### Module 1 — Brute Force / Authentication Testing
- **Real adapter:** `app/integrations/hydra.py` (262 lines). **Fail-closed and well-built** `[FACT]`: requires `HYDRA_ENABLED=true` + target + userlist + passlist, caps `attempts`/`tasks`/`run_seconds`, runs `hydra` with **no shell** (`-f -V`), **never returns the cracked password** (masks to dots, `hydra.py:218`), callers can only *lower* caps (`hydra.py:152`).
- **Binary:** `hydra` present at `/usr/bin/hydra` `[FACT]`.
- **Simulation twin:** `app/modules/bruteforce.py` models lockouts in memory (sends no creds).
- **Wiring:** exposed at `POST /api/integrations/hydra/run`; **not** connected to the AI planner, orchestrator, or kill switch.
- **Status: IMPLEMENTED BUT UNVERIFIED** (not run against a target in this audit).

### Module 2 — DDoS / Service Load Testing
- **Real adapter:** `app/integrations/locust.py` (134 lines). **Fail-closed** `[FACT]`: requires `LOCUST_ENABLED=true` + operator locustfile + target URL; caps users/spawn-rate/duration; headless subprocess, no shell; caller can only lower caps (`locust.py:104`).
- **Engine:** `locust` is **not on system PATH** but **is installed in the backend venv** this session `[FACT]`; `_which()` also searches the interpreter's bindir (`base.py:66`) so the adapter can find it.
- **Simulation twin:** `app/modules/ddos.py` (synthetic sources + Shannon-entropy detection metric).
- **Status: IMPLEMENTED BUT UNVERIFIED.**

### Module 3 — RAT-related
- **What exists:** `app/modules/ratuba.py` — `execute()` is an **in-memory SIMULATION** ("no implant, agent, or C2 channel", `ratuba.py:33`), plus a **real read-only UBA** scorer `app/modules/uba.py` that baselines real snapshots and scores deviations.
- **What does NOT exist:** any **real remote-access adapter**. There is no `remote_access` integration, and no reference to `netexec`/`nxc`/`evil-winrm`/`impacket` anywhere in `backend/app` or `frontend/src` `[FACT]`. The tools themselves ARE present on Kali (`/usr/bin/nxc`, `/usr/bin/evil-winrm`, `/usr/bin/impacket-wmiexec`) `[FACT]` — they are just not wired in.
- **Honest technical read (per your §3 request):** credentialed WinRM/SMB command execution via NetExec/Evil-WinRM is **credentialed remote administration**, *not* a conventional RAT (no implant, no persistence, no stealth, no credential theft). It is the technically-defensible way to preserve a "remote access / control" capability in an authorized lab without installing anything on the target. KALI.md §9/§14 already frames it this way; the code to do it is simply not written yet.
- **Status: STUB / PLACEHOLDER** for the real capability (UBA half is real; RAT execution is simulation only). **This is the main functional gap in the three modules.**

---

## 9. Integration Audit `[FACT]`

Registry: `app/integrations/__init__.py:17` → `caldera, locust, hydra, vervet, pentestgpt`.

| Integration | File | Role | Real action? | Status |
|---|---|---|---|---|
| **THC-Hydra** | `hydra.py` | credential test | **Yes** (gated) | **IMPLEMENTED BUT UNVERIFIED** — binary present, fail-closed. |
| **Locust** | `locust.py` | load test | **Yes** (gated) | **IMPLEMENTED BUT UNVERIFIED** — engine in venv, fail-closed. |
| **Caldera** | `caldera.py` | ATT&CK report analysis | No (read-only) | **IMPLEMENTED AND VERIFIED (code path)** — vendored sample reports present (`caldera-ai-project-main/.../data/*.json`); optional AI SOC narrative degrades honestly. |
| **vervet** | `vervet.py` | signed adversary-emulation (T1046 discovery) | **Yes** (if built) | **PARTIALLY IMPLEMENTED / UNAVAILABLE** — `cargo` is **NOT installed** `[FACT]`, so the Rust binary can't be built; adapter will report unavailable. Validates IPv4 + technique allowlist + Ed25519-signed scope (`vervet.py:111`). |
| **PentestGPT** | `pentestgpt.py` | LLM pentest reasoning agent | No (status + run ingest only) | **STUB / PLACEHOLDER** — detects the console script (not installed); does not auto-run. |

All adapters share the honest `status()` → available/reason contract (`base.py`), which is a genuinely good design to build on.

---

## 10. Telemetry Audit `[FACT]`

File: `app/telemetry/collector.py` (326 lines), schema `telemetry/schema.py`.

- **Three sources** via `build_source()` (`collector.py:323`): `local` (psutil, runs *on* the host), `winrm` (remote read-only PowerShell over pywinrm, `collector.py:145`), `none` (`NullSource` → honest "unavailable").
- **Honest unavailability:** every failure path returns `Telemetry.unavailable(...)` rather than a fake number; missing metrics stay `None` (`schema.py` docstring; `collector.py:147/164/168/173`).
- **Synthetic vs. real separation:** real polls persist to `telemetry_snapshots` with `available` + `source`; simulation outputs persist to the separate `simulation_metrics` table (`models.py:162`) explicitly labelled synthetic. **Good — they are distinguishable in storage and API.**
- **⚠️ Compliance note (your §8 "nothing on the Windows target"):** the `local` source would require the collector to run **on the target**, which **violates** your constraint. For a remote Windows target the only compliant settings are **`winrm`** (already-enabled, authorized management interface) or **`none`**. Current `.env` is `TELEMETRY_SOURCE=none` `[FACT]`, which is compliant. **Recommendation:** keep `local` for the Kali host only, and never label Kali host telemetry as "Windows target" telemetry.
- **Dashboard metrics originate from real snapshots** (via `/api/telemetry/*` and WS `TELEMETRY_UPDATE`).

**Status: IMPLEMENTED BUT UNVERIFIED** (WinRM path not exercised — no target contacted, by design of this audit).

---

## 11. Safety & Security Audit

| Control (your §9) | State | Evidence |
|---|---|---|
| Target allowlisting | **PARTIAL** | Each real tool is pinned to **one** configured target (`HYDRA_TARGET`, `LOCUST_TARGET_URL`) and cannot take an arbitrary host from a request (`hydra.py:9`, `locust.py:8`) — a strong *de-facto* single-target lock. But there is **no multi-host allowlist** and `Target.authorized` (`models.py:67`) is **never checked** `[FACT]`. vervet validates IPv4 + technique allowlist (`vervet.py:120`). |
| Bounded execution params | **YES** | Caps in `config.py`; adapters clamp *down* only (`hydra.py:152`, `locust.py:104`). |
| Rate / time / resource limits | **YES** | `*_MAX_TASKS/ATTEMPTS/RUN_SECONDS/USERS`; subprocess hard `timeout`. |
| Fail-closed behaviour | **YES** | `preconditions()` → HTTP 423 before any run (`api/integrations.py:216/255`). |
| Secret masking | **YES** | Hydra omits the password from its payload (`hydra.py:198`); `.env` holds secrets; audit printed **variable names only** here. |
| **Kill switch** | **REQUIRES SECURITY CORRECTION** | `orchestrator.engage_kill_switch()` (`orchestrator.py:122`) only flips `halted` and marks **simulation sessions** KILLED. `POST /api/attacks/start` checks `halted` (`routes.py:87`), **but `POST /api/integrations/hydra/run` and `/locust/run` do NOT** `[FACT]`. So the kill switch **does not stop or prevent the real tool runs**, and there is **no child-process termination** of an in-flight hydra/locust subprocess. |
| Cancellation stops active work | **PARTIAL** | Simulation steps check `_check_kill` between phases; a running real subprocess cannot be cancelled mid-flight (only its `timeout` bounds it). |
| AI cannot bypass execution limits | **YES (trivially)** | The AI output is a clamped integer and is **not in the real-execution path at all**, so it cannot widen any cap. (The flip side: the AI also isn't *driving* real execution.) |
| Deterministic Safety Gateway (separate component) | **NOT IMPLEMENTED** | Safety is distributed inside each adapter; there is no independent gateway object that validates scope/authorization/limits for every execution. |

**Summary:** the *adapter-level* safety is genuinely strong and fail-closed. The *system-level* safety your vision requires — one deterministic gateway in front of all execution, plus a kill switch that actually halts real tools — is missing. **The kill-switch gap is the one item I'd flag as a real security correction.**

---

## 12. Kali Deployment Compatibility `[FACT]`

| Item | Result |
|---|---|
| Python | 3.13.12 — backend deps install & import cleanly; app booted this session. |
| Backend venv | Present at `backend/.venv`; `requirements.txt` + `locust` installed. |
| Node.js / npm | **Not system-installed.** Installed locally this session to `~/.local/node` (v22.11.0 / npm 10.9.0) to run the Vite dev server. **Not on PATH persistently** — a new shell needs `export PATH="$HOME/.local/node/bin:$PATH"`, or a proper install. |
| Git | 2.53.0. |
| Native offensive tools | `hydra`, `nmap`, `nxc`, `netexec`, `evil-winrm`, `impacket-wmiexec` all present in `/usr/bin` ✓. `locust` not on system PATH (in venv). `cargo` **absent** → vervet can't be built. |
| Docker | `docker-compose.yml` + `Dockerfile`s exist but are **not needed** and contradict your "no Docker" directive — native path works. |
| `.env` | Present; contains the expected variable names (listed by name only); `OPENROUTER_API_KEY` is blank, so the AI runs in labelled-fallback mode. |

**No dependencies were installed for the application during this audit.** (Node install predates Section 1 and is called out here for honesty.)

---

## 13. Dependency & Environment Issues

1. **Node toolchain is not persistent** — needs a real install or a PATH export to rebuild/run the frontend in a fresh shell. `[FACT]`
2. **`cargo` missing** → vervet integration will always report unavailable until Rust is installed and the crate is built (`vervet.py:75`). `[FACT]`
3. **Docker artifacts present** but directive forbids Docker — recommend removing/ignoring `docker-compose*.yml` and the `Dockerfile`s in a later cleanup section (not now). `[FACT]`
4. **`db.py`/`config.py` comments reference "PostgreSQL in Docker"** (`db.py:18`) — cosmetic contradiction with the Kali-native, SQLite-default reality. `[FACT]`
5. **`psycopg2-binary` pinned** in `requirements.txt` though SQLite is the default — harmless, installs fine on Kali. `[FACT]`
6. **Branding drift:** app title, prompts, and `X-Title` headers still say "VAJRAPRAHAAR" (`main.py:28`, `decision.py:67/139`). Rename is a later, low-risk task. `[FACT]`
7. **No Alembic migrations** — `create_all` only (`db.py:38`); fine for the lab, noted for completeness.

---

## 14. Existing Code Worth Preserving (do **not** discard)

- **Telemetry subsystem** (`collector.py`, `service.py`, `schema.py`) — the honest `none/winrm/local` model with `None`-means-unavailable is exactly your "real evidence" requirement. **Keep.**
- **Integration adapter pattern** (`integrations/base.py`) — uniform `status()` + `available/reason` + `_which()` + no-shell `_run()`. **This is the spine to build real execution on. Keep and extend.**
- **Hydra & Locust real adapters** — fail-closed, capped, secret-masking. **Keep; later route them through the new gateway/dispatcher.**
- **UBA engine** (`modules/uba.py`) — real read-only behavioural scoring. **Keep.**
- **Caldera analyzer** (`caldera.py`) + vendored samples — working read-only ATT&CK rollup. **Keep.**
- **DB models + WebSocket hub + frontend dashboard/charts/API layer** — solid, real-data-driven. **Keep.**
- **The honest-fallback LLM plumbing** (`decision.py` fallback chain, `_llm.complete`). **Keep the degradation logic; restructure the role into the centralized planner.**

---

## 15. Missing Functionality (vs. your vision)

1. **Centralized AI planner** that ingests an **objective** + recon + telemetry and emits a **structured multi-step execution plan** (not one integer per module).
2. **Plan schema + validator** (e.g. Pydantic model for the AI plan) that rejects malformed/over-scope plans.
3. **Deterministic Safety Gateway** as an independent component in front of **all** execution (scope, authorization, caps, kill-switch state).
4. **Scenario Dispatcher** that maps a validated plan step → the correct **real** adapter.
5. **Real Module-3 remote-access adapter** (NetExec/Evil-WinRM credentialed admin — no implant).
6. **Observation Engine + Result Analyzer** that feed **real execution results** back to the AI for a **continue/modify/stop** decision (the feedback loop).
7. **Kill switch that halts real tool runs** and terminates child processes.
8. **Objective-input UI** + unified audit view across the real path.
9. **Unified audit record** capturing (per your §10): scenario ID, scope, AI model + prompt version, AI recommendation, validation result, gateway verdict, exec params, start/finish, observed results, errors, cancellation, final analysis — **linked across one operation**.
10. **Project tests** — none exist for the backend or frontend `[FACT]` (the only `test_*.py` found are inside vendored `locust-master`).

---

## 16. Technical Debt

- Two parallel execution paths (simulation vs. integrations) with overlapping concepts (both "attack") but no shared contract — will cause confusion and duplicated logic.
- `adapt()` (`base.py:137`) masquerades as a "feedback loop" but is a fixed heuristic nudge — misleading relative to the vision.
- `Target.authorized` column exists but is dead (never enforced).
- Branding/name drift (VAJRAPRAHAAR vs CHAKRAVYUH).
- Docker/Postgres references contradicting the Kali-native directive.
- No schema/validation layer between AI output and anything downstream.

---

## 17. Differences Between My Vision and Current Implementation

| Vision | Current reality | Delta |
|---|---|---|
| One AI brain understands a scenario & plans | One function returns one integer per module | **Large** |
| Objective in → structured plan out | No objective input; fixed `kind`; integer out | **Large** |
| Schema validator on AI output | Clamp + int-coerce only | **Medium** |
| Deterministic Safety Gateway (independent) | Safety distributed in adapters; no gateway | **Large** |
| Dispatcher → real module execution | AI path executes **simulation**; real tools run on a **separate** manual path | **Large** |
| AI feedback loop (continue/modify/stop) | Fixed ±1 nudge, simulation-only | **Large** |
| Three real attack capabilities | 2 real adapters (Hydra, Locust) + 1 simulation/UBA (RAT) | **Medium** |
| Kill switch stops everything | Stops simulations only; real runs unaffected | **Security gap** |
| Full linked audit | Partial (two separate stores) | **Medium** |

---

## 18. Recommended Implementation Architecture (target)

Build the **missing spine** and route the **existing real adapters** through it, rather than rewriting what works:

```
Objective (UI) ─► /api/operations  ─► CentralPlanner (LLM, OpenRouter, honest fallback)
                                          │  emits  ExecutionPlan {steps:[{module, target_ref, params}]}
                                          ▼
                                   PlanSchema (Pydantic)  ── reject if malformed/over-scope
                                          ▼
                                   SafetyGateway (deterministic, AI-independent)
                                     • scope/allowlist check (enforce Target.authorized)
                                     • cap clamp (re-assert config caps)
                                     • kill-switch / halted check   ◄── now covers REAL execution
                                          │ approve / reject (recorded)
                                          ▼
                                   ScenarioDispatcher ─► existing adapters:
                                     • bruteforce → HydraIntegration.run()   (real)
                                     • ddos       → LocustIntegration.run()  (real)
                                     • remote     → RemoteAccessIntegration.run()  (NEW: NetExec/Evil-WinRM)
                                          ▼
                                   ObservationEngine (telemetry before/after + tool evidence)
                                          ▼
                                   ResultAnalyzer ─► back to CentralPlanner (continue/modify/stop)
                                          ▼
                                   AuditLogger (one linked record per operation)
```

Design rules to honour your constraints: Safety Gateway is **pure Python, deterministic, independent of the AI**; adapters keep their own hard caps (defence in depth); kill-switch state is consulted **in the gateway** so it covers every execution; remote-access uses credentialed WinRM/SMB only (no implant, nothing installed on the target); every synthetic value stays labelled.

---

## 19. Recommended Section-by-Section Roadmap

- **Section 2 (recommended next): the deterministic spine — Safety Gateway + Plan schema + kill-switch unification.** Build `SafetyGateway` + a Pydantic `ExecutionPlan`/`PlanStep` schema, enforce `Target.authorized` + caps + `halted`, and **route the existing Hydra/Locust run endpoints through the gateway** so the kill switch finally covers real execution. Highest value, lowest risk, fixes the one security gap, and unblocks everything after it. *No new attack capability is added — it only wraps what already runs.*
- **Section 3:** Centralized AI Planner (objective → validated structured plan) + wire it to the dispatcher (real execution replacing the per-module integer).
- **Section 4:** Real **Module-3 remote-access** adapter (NetExec/Evil-WinRM credentialed admin), fail-closed like Hydra, behind the gateway + a UI panel.
- **Section 5:** Observation Engine + Result Analyzer + the real AI **feedback loop** (continue/modify/stop).
- **Section 6:** Unified audit record + objective-input UI + Operations Center linkage.
- **Section 7 (cleanup):** rename VAJRAPRAHAAR→CHAKRAVYUH, remove Docker/Postgres artifacts, add backend tests.

*(You decide the order; this is my recommendation, not a commitment to proceed.)*

---

## 20. Exact Files Expected to Change in Subsequent Sections

**Section 2 (spine):**
- **New:** `backend/app/safety/gateway.py`, `backend/app/safety/plan_schema.py` (+ `backend/app/safety/__init__.py`)
- **Edit:** `backend/app/api/integrations.py` (route `hydra_run`/`locust_run` through the gateway; consult `orchestrator.halted`), `backend/app/agent/orchestrator.py` (share kill-switch state), `backend/app/config.py` (any new gateway caps)
- **New (tests):** `backend/tests/test_gateway.py`

**Section 3 (planner):**
- **Edit/rework:** `backend/app/agent/decision.py` → `backend/app/agent/planner.py` (structured plan), `backend/app/api/routes.py` (new `/api/operations`), `backend/app/modules/*` (execute via dispatcher)
- **New:** `backend/app/agent/dispatcher.py`; **Frontend:** objective-input UI in `frontend/src/pages/OperationsCenter.tsx` + `frontend/src/api.ts`

**Section 4 (remote access):**
- **New:** `backend/app/integrations/remote_access.py` (NetExec/Evil-WinRM, fail-closed), register in `backend/app/integrations/__init__.py`, endpoint in `backend/app/api/integrations.py`, config in `backend/app/config.py`; **Frontend:** new panel in `frontend/src/pages/Integrations.tsx` + `frontend/src/api.ts` + `frontend/src/types.ts`

**Section 5 (feedback loop):**
- **New:** `backend/app/agent/observation.py`, `backend/app/agent/analyzer.py`; **Edit:** `backend/app/agent/orchestrator.py`

**Section 6 (audit/UI):**
- **New:** `backend/app/audit/` (linked audit model + writer), model additions in `backend/app/models.py`; **Frontend:** audit views in `frontend/src/pages/Report*.tsx`

---

## Final Section-1 Statement

- **Current state:** a disciplined, honest, fail-closed console with real telemetry, two working real tool adapters (Hydra, Locust), a real UBA scorer, and a real-data dashboard — but the AI is a per-module integer recommender wired only to a **simulation** path, while real tools run on a **separate** manual path with no AI, no gateway, and no kill-switch coverage.
- **Biggest blockers:** (1) no centralized planner / structured plan; (2) no deterministic Safety Gateway; (3) the two execution paths are disconnected; (4) **kill switch does not stop real tool runs** (security correction); (5) Module-3 real remote-access is unbuilt.
- **Reusable:** telemetry subsystem, adapter pattern, Hydra/Locust adapters, UBA, Caldera analyzer, DB models, WS hub, frontend. (See §14.)
- **Must be corrected:** kill-switch coverage of real execution; enforce `Target.authorized`; add a validation layer before execution.
- **Closeness to vision:** ~35–40% — strong foundation, missing spine.
- **Recommended Section 2:** the deterministic spine (Safety Gateway + plan schema + unified kill switch), routing existing real adapters through it.
- **Files created this section:** `docs/CLAUDE_SECTION_1_AUDIT.md` (this file) — **no code changed.**
- **Checks actually performed:** `git` status/branch/log; full backend + frontend source read; `frontend/src` grep for fabricated data (none) and for remote-access refs (none); environment presence checks for python/node/git/hydra/nmap/nxc/netexec/evil-winrm/impacket/locust/cargo; `.env` variable-name listing (no secret values printed); confirmed backend boots + `/api/health` OK earlier this session.
- **Failures / unknowns reported honestly:** no app dependencies installed and **no target contacted**, so WinRM telemetry, Hydra, Locust, and vervet are classified **UNVERIFIED** (not run); `cargo` absent so vervet is currently unavailable; node is not persistently on PATH.

**Stopping here. Awaiting your instruction for Section 2 — no attack modules implemented, no dependencies installed, no target touched.**
