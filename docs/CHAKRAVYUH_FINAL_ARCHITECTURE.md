# CHAKRAVYUH — Final Architecture

**Written for:** engineers and reviewers who want the verified, as-built architecture.
**Date:** 2026-11-07 · **Source of truth:** the actual code (not older docs).

CHAKRAVYUH is an AI-assisted Red-Team cyber-range console for an **authorized, isolated academic lab**. One centralized AI planner proposes bounded work; deterministic Python authorizes and executes it. The AI *reasons*; it never *acts* on its own.

---

## 1. The pipeline (verified, end-to-end)

```
User objective
  │  frontend (React/Vite) → src/api.ts (relative /api)
  ▼
FastAPI backend ............ app/main.py  (mounts routes; CORS→localhost:5173; init_db on startup)
  ▼
Context Manager ............ app/agent/context.py::build_context
  ▼
Centralized AI Planner ..... app/agent/planner.py::generate_plan
  ▼
Structured ExecutionPlan ... app/safety/plan_schema.py  (Pydantic, extra=forbid)
  ▼  schema validation (construction-time)
Safety Gateway ............. app/safety/gateway.py::evaluate   (deterministic, fail-closed)
  ├─ REJECT → audit + 423 ────────────────────────► adapter NEVER reached
  ▼ APPROVE
Execution Registry ......... app/safety/registry.py  (lifecycle state machine, thread-safe)
  ▼
Dispatcher ................. app/safety/dispatcher.py::run_execution  (requires APPROVED)
  ▼
Integration Adapter ........ app/integrations/{hydra,locust,remote_access}.py  (own hard caps; managed subprocess)
  ▼
Observation + Analysis ..... app/agent/analysis.py  (measured FACTS vs AI interpretation)
  ▼
AI Feedback ................ app/agent/feedback.py  (CONTINUE / MODIFY / STOP; deterministic guardrails win)
  ▼
Database / Audit ........... app/models.py (Operation, OperationIteration, AuditRecord) — secret-masked
  ▼
Dashboard .................. app/agent/operation.py::get_operation → GET /api/operations/{id}

Unified Kill Switch ........ app/safety/killswitch.py  — consulted by the Gateway; terminates managed
                             process groups of ALL adapters (SIGTERM→grace→SIGKILL)
Managed process runner ..... app/safety/process.py  — each subprocess in its own process group
```

The whole loop is driven by `app/agent/operation.py::run_operation`.

---

## 2. Components

| Component | File(s) | Purpose | AI or Deterministic |
|---|---|---|---|
| **Dashboard** | `frontend/src/pages/*` | Submit objective; view plan, gateway verdict, results, feedback, telemetry | — |
| **FastAPI backend** | `app/main.py`, `app/api/*` | Route requests; mount routers; lifespan (DB init, telemetry poller) | Deterministic |
| **Context Manager** | `app/agent/context.py` | Gather objective + module capabilities/availability/authorized-targets/approved-ops + scope-labelled telemetry + history | Deterministic (feeds the AI) |
| **Centralized AI Planner** | `app/agent/planner.py`, `app/agent/llm.py` | Propose ONE module + bounded params (+ operation id); honest fallback/unavailable | **AI** (proposes only) |
| **ExecutionPlan schema** | `app/safety/plan_schema.py` | Strict Pydantic contract; `operation` = safe token; **no cap/authorization fields** | Deterministic |
| **Safety Gateway** | `app/safety/gateway.py`, `app/safety/policy.py` | Authorize: kill-switch, module enabled, adapter available, target allowlist, operation allowlist (D2), concurrency, clamp-to-caps | **Deterministic** |
| **Execution Registry** | `app/safety/registry.py` | Track lifecycle (REQUESTED→…→COMPLETED/FAILED/TIMED_OUT/CANCELLED); concurrency | Deterministic |
| **Dispatcher** | `app/safety/dispatcher.py` | The ONLY path from an APPROVED record to an adapter | Deterministic |
| **Managed process runner** | `app/safety/process.py` | Launch subprocesses in own process groups; make them kill-switch-reachable | Deterministic |
| **Integration adapters** | `app/integrations/{hydra,locust,remote_access}.py` | Run the real tool with independent hard caps | Deterministic |
| **Observation/Analysis** | `app/agent/analysis.py` | Separate measured facts (real result) from AI interpretation; evidence-based `objective_met` | Mixed (facts deterministic, interpretation AI) |
| **Feedback Engine** | `app/agent/feedback.py` | CONTINUE/MODIFY/STOP; deterministic guardrails (max-iter, repeated-failure, kill-switch, objective-met) override the AI | **Deterministic guardrails + AI advisory** |
| **Audit/DB** | `app/models.py`, `app/db.py`, `app/safety/audit.py` | Persist operations, iterations, gateway/exec/kill events; mask secrets | Deterministic |
| **Kill Switch** | `app/safety/killswitch.py` | Halt new work; terminate managed process groups; token-gated reset | Deterministic |
| **Telemetry** | `app/telemetry/collector.py`, `service.py`, `schema.py` | none / local / winrm / blackbox sources; honest unavailable | Deterministic |

### Key API responsibilities
- `POST /api/operations` — run the full AI loop (fail-closed). `POST /api/operations/plan` — dry-run plan preview. `GET /api/operations[/{id}]` — list/detail.
- `POST /api/integrations/{hydra,locust,remote_access}/run` — single gated execution of one module (Request → Gateway → Registry → Dispatcher → Adapter).
- `POST /api/execution/submit` — submit a structured plan; `GET /api/execution[/{id}]`; `POST /api/execution/{id}/cancel`; `GET /api/execution/killswitch`.
- `POST /api/killswitch` (engage) · `POST /api/killswitch/reset` (token-gated).
- `GET /api/telemetry/latest|history` · `GET /api/health`.

---

## 3. Safety boundaries (what the AI can and cannot do)

**The AI may:** read context; propose one module, bounded params, and (for remote access) an operation **identifier**; write reasoning/analysis.

**The AI may NOT (enforced by deterministic code):** pick a target (bound to the allowlist); set/raise caps (no cap fields in the schema; the gateway clamps); approve its own plan (only the gateway approves); run a shell/command/tool (the AI layer imports no subprocess/dispatcher — verified); change the allowlist/policy/kill-switch; bypass the gateway (every dispatch route calls `evaluate()` first and `run_execution` requires `APPROVED`); fabricate telemetry or claim success without evidence.

**Fail-closed everywhere:** missing key/tool/config/credential/authorization ⇒ honest `unavailable`/reject; any gateway internal error ⇒ reject.

---

## 4. Failure handling

- **Schema invalid** → `ValidationError` before the gateway (422/rejected).
- **Gateway reject** → audit + 423; no registry record; adapter never reached.
- **Adapter failure** → registry `FAILED`, error recorded (masked), no false success.
- **Timeout** → `TIMED_OUT`; subprocess killed by its process group.
- **Kill switch engaged** → new work rejected; in-flight managed process groups terminated; executions `CANCELLED` (or `FAILED` if a process can't be confirmed dead).
- **LLM unavailable** → labelled `fallback` (deterministic) or `unavailable` — never mislabelled as AI.

---

## 5. The modules

### 1) Hydra — Authentication Testing (`app/integrations/hydra.py`)
Bounded credential testing against one configured, authorized target/service. Hard caps (attempts/tasks/run-time); stops on first valid pair; **the cracked password is never returned** to the UI. Disabled by default.

### 2) Locust — Bounded Service Load Testing (`app/integrations/locust.py`)
Drives an operator locustfile against one authorized target URL. Hard caps on users / spawn-rate / duration (clamp-down only). **Bounded lab load testing — not unrestricted flooding.** Disabled by default.

### 3) NetExec — Credentialed Remote Access Demonstration (`app/integrations/remote_access.py`)
**This is NOT a conventional covert RAT.** No implant, no persistence, no stealth, no credential harvesting/dumping, no reverse shell, no arbitrary command execution, nothing that survives the session. It demonstrates **credentialed remote administration** via an approved interface (NetExec), limited to **five fixed, read-only operation identifiers** (`connectivity_check`, `whoami`, `hostname`, `os_info`, `system_info`), each mapping to one fixed argv. The password is written to a 0600 `/dev/shm` file (never on argv/logs/audit/API), cleaned up on every path, fail-closed if uncreatable. Disabled by default.

### 4) Blackbox Telemetry — Authorized, bounded TCP telemetry (`app/telemetry/collector.py::BlackboxSource`)
Agentless, IP-only external probe from Kali (no credentials, nothing on the target). Authorized before any socket (IPv4 + RFC1918 + dedicated `BLACKBOX_ALLOWLIST`); bounded by a total time budget; reports reachability/open-ports/latency/HTTP banner; **CPU/RAM stay unavailable** (external view). Honest partial results. Disabled by default (`TELEMETRY_SOURCE=none`).

### 5) WinRM Telemetry (`app/telemetry/collector.py::WinRMSource`)
Remote read-only PowerShell over an already-enabled, authorized WinRM interface (no install on the target). **Implemented; live-unverified** (no target contacted). `local` (psutil) is for the Kali host only and is never labelled as target telemetry.

---

## 6. Technology stack

Backend: Python 3.13, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy + SQLite, WebSocket. AI: OpenRouter (OpenAI-compatible), honest fallback. Frontend: React 18 + TypeScript + Vite + Tailwind. Native Kali tools: THC-Hydra, Locust, NetExec, (Evil-WinRM alternate). No Docker; Kali-native.

See also: `CHAKRAVYUH_FINAL_FEATURE_MATRIX.md`, `CHAKRAVYUH_DEMONSTRATION_GUIDE.md`, `CHAKRAVYUH_KALI_SETUP.md`, `CHAKRAVYUH_FINAL_PROJECT_REPORT.md`.
