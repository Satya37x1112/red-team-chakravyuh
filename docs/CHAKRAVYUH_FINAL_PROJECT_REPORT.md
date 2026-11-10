# CYBER CHAKRAVYUH — Final Engineering & Project Report

**Document Type:** Final Capstone Engineering & Architecture Report  
**Project Name:** CYBER CHAKRAVYUH (formerly VAJRAPRAHAAR)  
**Date:** 2026-11-10  
**Host Platform:** Kali Linux (VMware Guest, x86_64)  
**Repository Path:** `/home/kali/AI_red_Team/red-team-chakravyuh`  
**Git HEAD:** `8664b34` (Branch: `main`)  
**Project Classification:** Academic & Defensive AI-Assisted Red-Team Cyber Range  

---

## 1. Abstract

CYBER CHAKRAVYUH is an AI-assisted Red-Team cyber-range platform engineered to evaluate and automate defensive readiness in isolated laboratory environments. The platform addresses a fundamental challenge in artificial intelligence security: enabling an autonomous cognitive agent (Anthropic Claude via OpenRouter/OmniRoute) to understand high-level operational objectives, reason over real-time evidence, and propose tactical attack plans, while ensuring that all physical execution, authorization gating, parameter limits, and emergency terminations are controlled by deterministic, fail-closed software.

Following seven comprehensive development and verification stages, CYBER CHAKRAVYUH operates as a unified hybrid system with a 171-test automated backend test suite (100% pass rate), a typechecked and compiled React/TypeScript frontend dashboard, verified Tailscale network isolation, and a fail-closed Safety Gateway. All attack modules—including THC-Hydra authentication testing, Locust service-load testing, a zero-traffic DDoS simulation mode, NetExec credentialed remote administration, and blackbox TCP reconnaissance—are architecturally complete and verified through automated mock and local execution pipelines. Live offensive testing against the designated Windows target is responsibly halted and documented as requiring formal target-owner authorization.

---

## 2. Introduction & Background

Modern cybersecurity exercises require continuous, dynamic adversarial testing to validate detection engineering, Security Operations Center (SOC) alert fidelity, and incident response playbooks. Traditional automation relies on static shell scripts and hardcoded execution sequences that fail to adapt when defensive controls or network topologies change. Conversely, granting autonomous Large Language Models direct access to command shells or raw network interfaces introduces severe operational hazards, including hallucinations, unconstrained targeting, data destruction, and prompt injection vulnerabilities.

CYBER CHAKRAVYUH resolves this dichotomy by establishing a deterministic containment perimeter around an AI reasoning core. The platform allows security operators to define high-level adversarial scenarios while guaranteeing that every proposed action is validated against strict Pydantic schemas, authorized by a centralized Safety Gateway, executed within isolated Linux process groups, and logged in an immutable, secret-redacted audit database.

---

## 3. Problem Statement & Research Objectives

### 3.1 Problem Statement
How can modern Large Language Models be safely integrated into offensive cyber-range operations to provide dynamic tactical planning and evidence interpretation without relinquishing deterministic control over targeting, execution caps, and emergency halting?

### 3.2 Core Engineering Objectives
1. **Unified Architecture**: Replace fragmented, tool-specific scripts with a single centralized planning and execution spine.
2. **Deterministic Safety Enforcement**: Implement a fail-closed Safety Gateway outside the cognitive model that validates all plans against target allowlists, hard parameter caps, and operational states.
3. **Hybrid Division of Labor**: Partition cognitive tasks (objective mapping, strategy selection, feedback reasoning) to the LLM, and physical tasks (schema validation, process management, socket measurement, audit logging) to deterministic Python.
4. **Emergency Kill-Switch Authority**: Provide an instant, process-group-level halting mechanism that reliably terminates managed tools without interfering with host operating system tasks.
5. **Traceable Telemetry & Audit**: Maintain a complete, secret-redacted audit trail and provide honest separation between measured physical evidence and AI-generated interpretations.

---

## 4. System Architecture & End-to-End Pipeline

The platform follows a verified 14-stage data and control pipeline:

```
[ Operator / React Dashboard ]
              │  (HTTP / JSON via src/api.ts)
              ▼
[ FastAPI Orchestration Engine ] (app/main.py, app/api/*)
              │
              ▼
[ Scenario Context Manager ] (app/agent/context.py)
              │
              ▼
[ Central AI Planner ] (app/agent/planner.py & app/agent/llm.py)
              │
              ▼
[ Structured ExecutionPlan ] (app/safety/plan_schema.py)
              │
              ▼
[ Deterministic Safety Gateway ] (app/safety/gateway.py & policy.py)
              │  ├─ REJECT → HTTP 423 / Audit Logging
              ▼  └─ APPROVE (Generates execution_id)
[ Operator Approval / Direct Submission ] (app/api/execution.py)
              │
              ▼
[ Execution Registry ] (app/safety/registry.py)
              │
              ▼
[ Controlled Dispatcher ] (app/safety/dispatcher.py)
              │
              ▼
[ Managed Process Runner & Tool Adapters ] (app/safety/process.py, app/integrations/*)
              │
              ▼
[ Telemetry Collector & Service ] (app/telemetry/collector.py & service.py)
              │
              ▼
[ Post-Execution AI Analysis ] (app/agent/analysis.py)
              │
              ▼
[ AI Feedback Engine ] (app/agent/feedback.py)
              │
              ▼
[ Central Audit Persistence ] (app/safety/audit.py, app/models.py)
              │
              ▼
[ Real-Time WebSocket Hub ] (app/ws.py → frontend/src/useLive.ts)
```

---

## 5. Hybrid AI & Scripting Methodology

The platform enforces a strict separation between cognitive reasoning and deterministic execution:

### 5.1 Cognitive Layer: Claude AI
- **Objective Understanding**: Analyzes natural language mission goals and identifies applicable adversary tactics.
- **Structured Planning**: Emits strict JSON structures defining a proposed module, bounded parameters, operational reasoning, and confidence metrics.
- **Evidence Analysis**: Interprets raw tool output and translates technical indicators into actionable intelligence.
- **Advisory Recommendations**: Recommends `CONTINUE`, `MODIFY`, or `STOP` actions based on operational evidence.
- **Strict Boundary**: The AI layer imports zero execution modules (`subprocess`, `socket`, `os.system`) and has no direct network access.

### 5.2 Deterministic Layer: Python Core
- **Schema Sanitization**: Validates data types and enforces regex boundaries to prevent shell metacharacter and command injection attacks.
- **Target Binding**: Deterministically binds targets to the policy allowlist; the AI is prohibited from specifying arbitrary target hosts.
- **Parameter Clamping**: Clamps requested execution parameters down to configured hard caps (e.g. `max_tasks`, `max_users`, `max_run_seconds`).
- **Authorization Gating**: Evaluates the kill switch, module enablement, tool availability, and concurrency limits prior to execution.
- **Process Management**: Spawns all external tools in dedicated process groups (`start_new_session=True`) to enable reliable signal propagation.
- **Secret Scrubbing**: Recursively sanitizes sensitive dictionary keys (`password`, `token`, `api_key`) to prevent credential leakage.

### 5.3 Behavior During AI Outages (Condition B)
When the cloud LLM provider is unreachable or returns authentication errors (e.g., HTTP 401), the platform:
1. Gracefully fails over to the deterministic fallback planner (`_fallback()`).
2. Constructs a bounded plan using default safe parameters and tags it with `source=PlanSource.system` and `status="fallback"`.
3. Labels the plan as `FALLBACK (NOT AI)` on the dashboard.
4. Generates zero synthetic or hallucinated AI commentary.
5. Maintains 100% of all Safety Gateway checks, process management rails, and audit logging.

---

## 6. Security Module Implementations

### 6.1 Authentication Testing: THC-Hydra (`app/integrations/hydra.py`)
- **Functionality**: Evaluates credential robustness across network protocols (SSH, SMB).
- **Safety Rails**: Hard caps enforced via `HYDRA_MAX_TASKS` (default: 4) and `HYDRA_MAX_RUN_SECONDS` (default: 30). Disarmed by default.
- **Privacy Assurance**: Found passwords and credential lists are redacted from results, logs, and database entries.
- **Status**: **MOCK-VERIFIED** (Live target execution blocked pending authorization).

### 6.2 Service Load Testing: Locust (`app/integrations/locust.py`)
- **Functionality**: Generates controlled HTTP traffic profiles to test application resiliency.
- **Safety Rails**: Caps on simulated users (`LOCUST_MAX_USERS`), spawn rate (`LOCUST_MAX_SPAWN_RATE`), and duration (`LOCUST_MAX_RUN_SECONDS`).
- **Status**: **MOCK-VERIFIED** (Live target execution blocked pending authorization).

### 6.3 Zero-Traffic DDoS Simulation (`app/integrations/locust_sim.py`)
- **Functionality**: Demonstrates the complete execution lifecycle (Gateway → Registry → Dispatcher → Kill Switch → Audit) using synthetic load curves.
- **Safety Rails**: Contacts zero external hosts, opens zero network sockets, and generates zero packets. Constantly polls kill-switch state every 250ms.
- **Status**: **LIVE-VERIFIED** on Kali host.

### 6.4 Credentialed Remote Administration: NetExec (`app/integrations/remote_access.py`)
- **Functionality**: Executes authorized remote administrative queries against Windows lab hosts as an alternative to an uncontrolled RAT.
- **Allowed Operations**: Strictly restricted to 5 read-only queries: `connectivity_check`, `whoami`, `hostname`, `os_info`, and `system_info`.
- **Safety Rails**: Operates without shell access or arbitrary command execution. Credentials are written to memory-backed `/dev/shm` files with strict `0600` permissions and unlinked immediately after use.
- **Status**: **MOCK-VERIFIED** (Live target execution blocked pending authorization).

### 6.5 Blackbox Reconnaissance & Purple-Team Signatures
- **Functionality**: Conducts agentless, non-destructive TCP port probes and bounded SOC detection bursts (≤40 TCP connects, ≤5 bogus SMB attempts).
- **Safety Rails**: Refuses all public/global IPs and hostnames; permits only RFC1918 private lab space and verified Tailscale peer addresses (`100.64.0.0/10`).
- **Status**: **LIVE-VERIFIED** locally and across Tailscale.

### 6.6 Nmap Network Scanner
- **Status**: **NOT IMPLEMENTED**. Acknowledged architectural boundary; reconnaissance is fulfilled via native socket probes.

---

## 7. Safety, Kill Switch & Network Architecture

### 7.1 Deterministic Safety Gateway
The gateway (`app/safety/gateway.py`) evaluates requests fail-closed in sequential order:
1. Operational State / Kill Switch (rejects if halted).
2. Module Support and Enablement (rejects if disabled).
3. Integration Adapter Availability (rejects if binary missing).
4. Target Authorization (rejects if not on allowlist).
5. Operation Allowlist (rejects unapproved remote access tokens).
6. Parameter Clamping (clamps values down to configured caps).
7. Concurrency Check (atomically reserves execution slot under thread lock).

### 7.2 Unified Emergency Kill Switch
- **Scope**: Unified control over both simulation loops and real integration adapters.
- **Mechanism**: Initiates `os.killpg(pgid, signal.SIGTERM)`, waits for a 5-second grace period, and escalates to `signal.SIGKILL` if processes remain active.
- **Non-Interference**: Maintains an internal process registry (`_TABLE`); strictly verifies that processes not spawned by `run_managed` are untouched.
- **Authorization**: Re-arming requires the operator to provide the configured `SAFETY_ADMIN_TOKEN`.

### 7.3 Tailscale Network Isolation
- **Local Endpoint**: Kali host at `100.80.154.42` (`manoharisatyasarthak@`).
- **Target Endpoint**: Windows lab VM at `100.80.167.51` (`onlymahibhatt@`).
- **Routing Isolation**: Linux kernel policy routing rule (`from all lookup 52`) directs all traffic destined for `100.80.167.51` exclusively through `tailscale0`. No lab packets route through the default gateway (`eth0`).
- **Authorization Separation**: Network connectivity does not imply operational authorization. The ownership boundary requires explicit written consent from `onlymahibhatt@` before executing live attacks.

---

## 8. Verification Results & Test Evidence

### 8.1 Backend Test Regression
- **Command**:
  ```bash
  SP="$PWD/.venv/lib/python3.13/site-packages" PYTHONPATH="$SP" /usr/bin/python3.13 -m pytest -v
  ```
- **Exit Code**: `0`
- **Results**: **171 Passed**, **0 Failed**, **0 Skipped**, **0 Deselected**, **1 Warning** (upstream Starlette `BlockingPortal` deprecation).
- **Duration**: `11.37s`.

### 8.2 Frontend Static Analysis & Production Build
- **Typecheck Command**: `PATH="$HOME/.local/node/bin:$PATH" npx tsc -b` (Exit Code: `0`).
- **Build Command**: `PATH="$HOME/.local/node/bin:$PATH" npm run build` (Exit Code: `0`).
- **Artifacts Generated**: HTML, CSS (24.69 kB), JS bundle (805.61 kB) across 73 transformed modules.

---

## 9. Limitations & Unverified Functionality

In accordance with strict verification standards, the following items are acknowledged:
1. **OpenRouter Authentication (HTTP 401)**: Cloud LLM calls currently fail authentication. The platform operates honestly in deterministic fallback mode until credentials are rotated.
2. **Live External Attack Authorization**: Live execution of Hydra, Locust, and NetExec against `100.80.167.51` remains blocked pending target-owner authorization.
3. **Nmap Scanner**: Nmap integration is not implemented.
4. **Browser Automation**: Automated UI click-through testing is unverified due to the lack of headless browser test runners on Kali.
5. **Execution Registry Persistence**: The execution registry operates in-memory and resets upon backend restart.
6. **Python Runtime**: Backend execution requires an explicit Python 3.13 invocation due to external system upgrades.

---

## 10. Future Enhancements

1. **Supervised Live Target Validation**: Conduct an authorized live test against `100.80.167.51` following receipt of written owner consent.
2. **Persistent Registry**: Store execution records in SQLite to preserve lifecycle history across restarts.
3. **Headless Browser Test Harness**: Integrate Playwright to automate end-to-end frontend regression testing.
4. **Credential Refresh**: Update OpenRouter keys to restore live Claude inference.
5. **Nmap Module**: Develop a standardized `NmapIntegration` adapter.

---

## 11. Final Readiness Assessment & Conclusion

### Final Readiness Classification:
**READY FOR AUTHORIZED LAB TESTING**

### Conclusion
CYBER CHAKRAVYUH successfully establishes a technically defensible, safe, and robust architecture for AI-assisted offensive security operations. By enforcing the principle of **"AI Proposes — Deterministic Code Decides,"** the platform eliminates the catastrophic risks of runaway AI execution while maintaining strategic cognitive planning capabilities. The platform is structurally complete, fully regression-verified, and ready for authorized operational testing.
