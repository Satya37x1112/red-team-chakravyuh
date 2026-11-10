# CYBER CHAKRAVYUH — Comprehensive Known Limitations Catalog

**Document Version:** 2.0 (Post-Stage 6 Baseline Verification)  
**Date:** 2026-11-10  
**Repository Path:** `/home/kali/AI_red_Team/red-team-chakravyuh`  
**Git HEAD:** `8664b34`  
**Purpose:** Honest, technical disclosure of platform constraints, unverified items, and operational boundaries.  

---

## 1. Summary of Identified Limitations

In accordance with strict verification integrity, the following limitations have been verified and documented. They are preserved honestly without evasion:

| Ref ID | Limitation Title | Category | Operational Impact | Remediation Prerequisite |
|---|---|---|---|---|
| **LIM-01** | OpenRouter API Key Authentication Failure | External Credential | Cloud LLM inference returns HTTP 401; planner operates in deterministic fallback mode. | Rotate/update `OPENROUTER_API_KEY` in `backend/.env`. |
| **LIM-02** | Target-Owner Authorization for Live Testing | Legal / Governance | Live execution of Hydra, Locust, and NetExec against `100.80.167.51` is halted. | Obtain documented authorization from account `onlymahibhatt@`. |
| **LIM-03** | Nmap Network Scanner Not Implemented | Architectural Scope | No Nmap CLI adapter exists in codebase; network scanning limited to TCP connect probes. | Retain as documented; design/implement future Nmap wrapper if required. |
| **LIM-04** | Recon Routes Untracked in Execution Registry | Architectural Scope | `/telemetry/probe` and `/attacks/soc-activity` audit centrally but bypass Registry state machine. | Retain as audited direct routes or migrate into Registry lifecycle in Stage 7+. |
| **LIM-05** | Browser Click-Through Automation Unverified | QA / Automation | Frontend verified by TypeScript typecheck & Vite build; interactive UI click-through unverified. | Install and configure Playwright/Puppeteer headless test harness. |
| **LIM-06** | Python 3.13 Explicit Invocation Requirement | Runtime Environment | System Python upgraded to 3.14 while `.venv` libraries reside in `python3.13/site-packages`. | Rebuild `.venv` under Python 3.14 (`python3.14 -m venv .venv`). |
| **LIM-07** | In-Memory Execution Registry Lifecycle | Data Persistence | Registry state and active execution tracking reset upon backend restart. | Back Registry state with persistent SQLite / Redis store if needed. |
| **LIM-08** | Windows VM Externally Managed | Environmental Scope | Target Windows host is managed externally; no host agents can be installed. | Continue using agentless blackbox TCP and remote SMB interfaces. |

---

## 2. Detailed Technical Analysis of Limitations

### LIM-01: OpenRouter Authentication Failure (HTTP 401)
- **Technical Description**: Calls to OpenRouter `/v1/chat/completions` fail with `HTTP 401 Unauthorized`. The configured model is `anthropic/claude-sonnet-4.5`.
- **System Behavior**: The central planner detects the 401 response and safely transitions to `_fallback()`. The plan is emitted with `source=PlanSource.system`, `status="fallback"`, and `is_ai=False`. The UI displays `FALLBACK (NOT AI)`. No fake AI output is generated.
- **Impact**: AI-assisted autonomous planning and natural language analysis are currently offline; the system operates on deterministic planning rules.
- **Required Remediation**: The project owner must update the `backend/.env` file with a valid, funded OpenRouter or OpenAI-compatible API key.

### LIM-02: Documented Target Authorization Required for Live Attacks
- **Technical Description**: Target machine `100.80.167.51` (`opensoc-windows`) is reachable over Tailscale table 52, but belongs to a different Tailscale account (`onlymahibhatt@`) than Kali (`manoharisatyasarthak@`).
- **System Behavior**: Live attack modules (Hydra, Locust, NetExec) are disabled in config by default. Automated tests verify their logic using mock adapters and process controls.
- **Impact**: Live offensive operations cannot be conducted ethically or legally without verified written authorization from the target owner.
- **Required Remediation**: Secure explicit written authorization and lab rules of engagement from `onlymahibhatt@` specifying permitted time windows, port bounds, and target accounts.

### LIM-03: Nmap Scanner Not Implemented
- **Technical Description**: Although network reconnaissance is supported via the Blackbox TCP probe (`app/telemetry/collector.py`) and SOC signature generator (`app/integrations/activity_gen.py`), no genuine Nmap adapter or subprocess wrapper exists in `backend/app`.
- **System Behavior**: Target reconnaissance is limited to bounded, multi-threaded TCP connection probes across specified port arrays (`21, 22, 80, 443, 445, 3389, 8080, 8443`).
- **Impact**: Advanced scanning capabilities (OS fingerprinting, NSE scripts, UDP scanning) are unavailable.
- **Required Remediation**: A future development phase may introduce an `NmapIntegration` wrapper conforming to the `Integration` base class.

### LIM-04: Recon Routes Not Tracked in Execution Registry
- **Technical Description**: The on-demand recon probe (`POST /api/telemetry/probe`) and purple-team activity generator (`POST /api/attacks/soc-activity`) enforce IP authorization and check kill-switch status, and record audit entries via `audit.RECON_PROBE` and `audit.RECON_SOC_ACTIVITY`. However, they execute synchronously and do not create records in `ExecutionRegistry`.
- **System Behavior**: These actions do not appear in `GET /api/execution` listings and cannot be individually cancelled via `/api/execution/{id}/cancel` (though they are blocked globally if the kill switch is engaged).
- **Impact**: Reconnaissance activities are audited in SQLite but do not share the active concurrency tracking of attack modules.
- **Required Remediation**: Refactor recon endpoints to submit transient `ExecutionPlan` instances through `gateway.evaluate()` if full registry tracking is desired.

### LIM-05: Browser Click-Through Automation Unverified
- **Technical Description**: Automated browser testing (driving the DOM, verifying button clicks, validating toasts interactively) is not configured in the test harness.
- **System Behavior**: Frontend verification relies on TypeScript strict typechecking (`tsc -b`) and Vite production bundle compilation (`vite build`), both of which pass with exit code 0.
- **Impact**: Visual layout anomalies, CSS rendering quirks, or client-side browser runtime errors could theoretically evade automated detection until manually observed.
- **Required Remediation**: Add a Playwright or Cypress test suite in `frontend/` to execute headless browser click-through testing.

### LIM-06: Python Virtual Environment Mismatch
- **Technical Description**: The Kali system Python was upgraded externally from 3.13 to 3.14. The interpreter symlink in `backend/.venv/bin/python` points to 3.14, but installed wheel packages reside in `.venv/lib/python3.13/site-packages`.
- **System Behavior**: Running `pytest` directly via the venv interpreter fails to locate packages. Running tests with explicit `PYTHONPATH` and Python 3.13 (`SP="$PWD/.venv/lib/python3.13/site-packages" PYTHONPATH="$SP" /usr/bin/python3.13 -m pytest`) passes 100% (171/171).
- **Impact**: Developers and operators must use the documented Python 3.13 invocation script to start servers and run tests.
- **Required Remediation**: The project owner can choose to execute a clean virtual environment rebuild under Python 3.14 (`rm -rf backend/.venv && python3.14 -m venv backend/.venv && pip install -r backend/requirements.txt`).

### LIM-07: In-Memory Execution Registry State
- **Technical Description**: The `ExecutionRegistry` stores execution records, timestamps, and active state transitions in a Python dictionary protected by a `threading.Lock`.
- **System Behavior**: If the Uvicorn backend process restarts or crashes, the history of in-memory active executions is cleared (though permanent audit logs remain preserved in the SQLite `audit_records` table).
- **Impact**: Past execution records cannot be queried via `GET /api/execution/{id}` after a server reboot.
- **Required Remediation**: Persist `ExecutionRecord` instances directly to SQLite via SQLAlchemy alongside `AuditRecord`.
