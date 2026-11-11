# CYBER CHAKRAVYUH — Final Verified Architecture

**Document Version:** 2.0 (Post-Stage 6 Verification Baseline)  
**Date:** 2026-11-10  
**Host Environment:** Kali Linux (VMware Guest)  
**Repository Path:** `/home/kali/AI_red_Team/red-team-chakravyuh`  
**Git HEAD:** `8664b34`  
**Classification:** Academic / Defensive AI Red-Team Platform  

---

## 1. Architectural Overview & System Mission

CYBER CHAKRAVYUH is an AI-assisted Red-Team cyber-range platform designed exclusively for authorized, isolated lab environments. It implements a strict **hybrid AI/deterministic architecture** founded on a non-negotiable security principle:

> **"AI Proposes — Deterministic Code Decides."**

The platform decouples high-level probabilistic reasoning (planning, contextual interpretation, and iterative recommendations) from deterministic execution and safety enforcement (schema validation, allowlist gating, process-group management, telemetry collection, and kill-switch control). Under no circumstances is the Large Language Model (LLM) permitted to directly execute system commands, select arbitrary targets, modify safety limits, or bypass operational authorization.

---

## 2. Complete End-to-End Data and Control Flow

Every operation within the platform traverses a verified, single-spine execution pipeline:

```
[ Operator / React Dashboard ]
              │  (HTTP / JSON via src/api.ts)
              ▼
[ FastAPI Orchestrator ] (app/main.py, app/api/*)
              │
              ▼
[ Scenario Context Manager ] (app/agent/context.py)
   ├── Read-only environment evidence (telemetry, targets, active caps)
   ├── Discovers enabled modules & approved operation identifiers
   └── Enforces authorized target binding (AI never selects target)
              │
              ▼
[ Central AI Planner ] (app/agent/planner.py & app/agent/llm.py)
   ├── Single reasoning brain (Anthropic Claude via OpenRouter / OmniRoute)
   ├── Emits strict JSON: {module, params, reasoning, confidence}
   └── Honors honest fallback if AI is offline (PlanSource.system)
              │
              ▼
[ Structured ExecutionPlan ] (app/safety/plan_schema.py)
   ├── Strict Pydantic v2 contract (extra="forbid")
   └── Hard input sanitization (rejects metacharacters, injections, whitespace)
              │
              ▼
[ Deterministic Safety Gateway ] (app/safety/gateway.py & policy.py)
   ├── Order of evaluation (Fail-Closed):
   │     1. Kill Switch engaged? → REJECT (HTTP 423)
   │     2. Module enabled in config? → REJECT (HTTP 423)
   │     3. Adapter available on Kali host? → REJECT (HTTP 423)
   │     4. Target in explicit allowlist? → REJECT (HTTP 423)
   │     5. Operation ID in approved list? → REJECT (HTTP 423)
   │     6. Parameter clamping down to hard caps (never upward)
   │     7. Atomic concurrency check under thread lock
   └── Dry-Run Preview Mode: returns GatewayDecision without reserving ID
              │
              ▼ (Approved with Execution ID)
[ Operator Approval / Submission ] (app/api/execution.py, app/api/operations.py)
              │
              ▼
[ Execution Registry ] (app/safety/registry.py)
   ├── State machine: REQUESTED → VALIDATING → APPROVED → RUNNING
   └── Tracks terminal states: COMPLETED / FAILED / TIMED_OUT / CANCELLED
              │
              ▼
[ Controlled Dispatcher ] (app/safety/dispatcher.py)
   ├── Sole authorized invocation path from APPROVED record to adapter
   ├── Sets execution ID ContextVar for process attribution
   └── Traps exceptions & timeouts → maps to terminal registry states
              │
              ▼
[ Managed Process Runner & Python Adapter ] (app/safety/process.py, app/integrations/*)
   ├── Spawns child processes in isolated process groups (start_new_session=True)
   ├── PID registry tracks active process trees for kill-switch reachability
   └── Adapters: Hydra (auth), Locust (load), Locust Sim (synthetic), NetExec (remote admin)
              │
              ▼
[ Telemetry Collection ] (app/telemetry/collector.py & service.py)
   ├── Blackbox agentless probe: TCP-connect, open ports, latency
   └── WinRM / Local telemetry: CPU, RAM, processes (when available)
              │
              ▼
[ Post-Execution AI Analysis ] (app/agent/analysis.py)
   ├── Strictly separates MEASURED FACTS (evidence) from AI INTERPRETATION
   └── Determines evidence-based objective_met flag (no hallucinated success)
              │
              ▼
[ AI Feedback Engine ] (app/agent/feedback.py)
   ├── Evaluates deterministic guardrails FIRST (always win):
   │     - Kill switch active → STOP
   │     - Objective met → STOP
   │     - Iteration cap reached → STOP
   │     - Consecutive failure cap reached → STOP
   └── If safe: consults AI for advisory CONTINUE / MODIFY / STOP
              │
              ▼
[ Central Audit Persistence ] (app/safety/audit.py, app/models.py)
   ├── SQLite audit_records table captures every milestone & decision
   └── Recursive secret redaction: passwords, tokens, API keys → «redacted»
              │
              ▼
[ Real-Time WebSocket Hub ] (app/ws.py → frontend/src/useLive.ts)
   └── Broadcasts snapshots, state changes, and kill-switch events to Dashboard
```

---

## 3. The Hybrid Model: Claude AI vs. Deterministic Python

The responsibilities of the system are partitioned between the probabilistic reasoning engine and the deterministic execution platform:

| Functional Responsibility | Assigned Layer | Implementation Mechanism & Boundary |
|---|---|---|
| **Objective Understanding** | Claude AI | Reads natural language operational objectives; maps intent to appropriate testing categories. |
| **High-Level Planning** | Claude AI | Proposes a single structured plan specifying module and parameters within bounded options. |
| **Contextual Reasoning** | Claude AI | Generates human-readable rationale (`reasoning`) and predicted telemetry outcomes. |
| **Result Interpretation** | Claude AI | Synthesizes complex tool output into clear operational analysis; advisory only. |
| **Iteration Recommendations** | Claude AI | Suggests tactical shifts (`CONTINUE`, `MODIFY`, `STOP`) when safe to proceed. |
| **Target Binding** | Python (Deterministic) | AI cannot pick a target; `ScenarioContext` binds `requested_target` from policy allowlists. |
| **Schema Validation** | Python (Deterministic) | Pydantic v2 rejects unauthorized fields, out-of-range types, and command-injection metachars. |
| **Authorization & Policy** | Python (Deterministic) | `SafetyGateway` evaluates kill switch, allowlists, enablement, and clamps parameters. |
| **Tool Execution** | Python (Deterministic) | AI layer has zero `subprocess` or socket imports; dispatcher invokes Python adapters. |
| **Process Group Isolation** | Python (Deterministic) | `process.py` executes commands in dedicated sessions (`setpgrp`) for complete tree management. |
| **Timeout & Limit Enforcement** | Python (Deterministic) | Independent hard caps in adapters and kernel-level subprocess timeout alarms. |
| **Telemetry Measurement** | Python (Deterministic) | Direct OS/socket measurement; never accepts synthetic metrics on real-network routes. |
| **Audit & Redaction** | Python (Deterministic) | Mandatory scrubbing of sensitive tokens prior to writing to the audit database. |
| **Emergency Halt (Kill Switch)**| Python (Deterministic) | Unified kill switch immediately sends SIGTERM/SIGKILL to tracked process groups. |

---

## 4. Behavior Under AI Provider Unavailability (Condition B)

The architecture is explicitly designed to remain fully functional, secure, and honest when the AI provider (OpenRouter / Claude / OmniRoute) is offline, unauthenticated (e.g., HTTP 401), or timing out:

1. **Detection & Failover**:
   - `generate_plan()` invokes the LLM client. Upon transport error, timeout, or authentication failure, an exception is caught and routed immediately to `_fallback()`.
2. **Deterministic Fallback Generation**:
   - The fallback planner inspects `context.runnable_modules()`.
   - It selects the first enabled, authorized module with default bounded baseline parameters.
   - The plan is tagged with `source=PlanSource.system`, `status="fallback"`, `is_ai=False`.
   - The reasoning field honestly documents: `"Deterministic fallback (NOT AI-generated): LLM unavailable..."`.
3. **No Fabrication**:
   - The system strictly forbids generating fake AI responses or hallucinated text.
   - The frontend renders the plan with the amber `FALLBACK (NOT AI)` badge.
4. **Uncompromised Safety Enforcement**:
   - The fallback plan is subjected to the exact same Safety Gateway validation as an AI plan.
   - All deterministic safety checks (allowlist, caps, kill switch, concurrency) remain enforced.
   - The Python execution layer, telemetry collector, and audit logger operate identically.

---

## 5. Subsystem Component Breakdown

### 5.1 Presentation Layer (React 18 + TypeScript + Vite)
- **`src/pages/AIPlanner.tsx`**: Operator interface for submitting objectives, previewing dry-run gateway verdicts, and tracking iterative feedback loops.
- **`src/pages/TargetRecon.tsx`**: Blackbox reconnaissance interface; executes non-destructive TCP probes against authorized lab/tailnet IPs and displays open ports and SOC proof notes.
- **`src/pages/Integrations.tsx`**: Tool management console showing armed/disarmed status, server caps, granular Locust load test metrics (p50/p95 latency, availability probe, host metrics, error breakdown), and dedicated DDoS Simulation controls with prominent warning banners.
- **`src/components/WordlistPanel.tsx`**: Dedicated password auditing console with RockYou wordlist metadata inspector, multi-format offline hash auditing (NTLM, MD5, SHA-1, SHA-256, SHA-512, bcrypt), and bounded live auth testing (max 3 attempts).
- **`src/pages/RemoteAccess.tsx`**: Credentialed remote management and authenticated file transfer interface; verifies Windows receiver connectivity, SHA-256 pre/post integrity badges, and UBA anomaly reporting.
- **`src/components/QuickAttack.tsx`**: Dashboard one-click SOC detection-signature launcher enforcing mandatory target IP input and kill-switch lockout.
- **`src/useLive.ts`**: Resilient WebSocket client that receives real-time telemetry updates and event broadcasts, with exponential backoff auto-reconnect.

### 5.2 API Orchestration Layer (FastAPI)
- **`app/main.py`**: Application entry point, CORS middleware, database lifespan management, and `/ws` WebSocket endpoint.
- **`app/api/operations.py`**: AI operations interface (`/plan` dry-run preview, `/` iterative execution loop, `/{id}` detail history).
- **`app/api/execution.py`**: Direct execution submission front door (`/submit`, `/{id}`, `/{id}/cancel`, `/killswitch`).
- **`app/api/auth.py`**: Authentication testing routes: `GET /api/auth/rockyou/status`, `POST /api/auth/identify-hash`, `POST /api/auth/offline-audit`, `POST /api/auth/live-validate`.
- **`app/api/transfer.py`**: Remote data transfer routes: `POST /api/transfer/receiver/check`, `GET /api/transfer/files`, `POST /api/transfer/send`.
- **`app/api/integrations.py`**: Tool-specific execution routes for Hydra, Locust (with dynamic target URLs), Locust Simulation, and Remote Access.
- **`app/api/routes.py`**: Legacy attack runner wrapped through `ExecutionPlan` -> `SafetyGateway` -> `ExecutionRegistry` (`/attacks/start`), recon probe (`/telemetry/probe`), purple-team SOC signatures (`/attacks/soc-activity`), and kill switch (`/killswitch`, `/killswitch/reset`).
- **`app/api/llm.py`**: In-memory generic LLM provider configuration and sanitized connection testing.

### 5.3 Safety & Execution Core
- **`app/safety/gateway.py`**: Central deterministic authorization gateway implementing fail-closed checks, multi-category simulation plans, parameter clamping, and dry-run evaluation.
- **`app/safety/policy.py`**: Static rule definitions, hard caps, module enablement status, and target/operation allowlists.
- **`app/safety/plan_schema.py`**: Pydantic v2 schemas defining `ExecutionPlan`, `ExecutionParams`, and strict input bounds.
- **`app/safety/registry.py`**: Thread-safe in-memory lifecycle state machine managing execution records and concurrency bounds.
- **`app/safety/dispatcher.py`**: Invocation coordinator linking approved records to adapters; manages cancellation, timeouts, and target URLs.
- **`app/safety/process.py`**: Process management engine executing CLI tools in isolated process groups and registering PIDs.
- **`app/safety/killswitch.py`**: Central halt authority dispatching process termination signals and enforcing admin-token re-arming.
- **`app/safety/audit.py`**: Central audit recording with recursive masking of passwords, keys, and tokens.

### 5.4 Adapters, Services & Telemetry Engines
- **`app/services/wordlist.py`**: RockYou wordlist discovery service; supports `.gz` streaming and plain `.txt`, calculates entry metadata, masks secrets, and ensures integrity.
- **`app/services/hash_audit.py`**: Offline password hash auditing service; identifies hash algorithms (NTLM, MD5, SHA-1, SHA-256, SHA-512, bcrypt) and performs bounded dictionary comparison against RockYou.
- **`app/services/availability.py`**: Target availability probe service; pre/post HTTP latency measurement, Locust response-time histogram percentile calculations (p50/p95), and text error parsing.
- **`app/services/transfer.py`**: Authenticated remote file transfer client; pre-transfer SHA-256 hashing, HTTP transfer with `X-Chakravyuh-Auth`, post-receipt SHA-256 comparison, and UBA event scoring.
- **`tools/windows_receiver.py`**: Visible, operator-controlled Python HTTP receiver for the Windows lab target (port 8090); token authentication, path traversal sanitization, 10MB size cap, post-receipt SHA-256 hashing.
- **`app/integrations/hydra.py`**: THC-Hydra CLI wrapper and live auth validation engine; enforces 3-attempt limits, detects lockout signatures, and parses login attempts.
- **`app/integrations/locust.py`**: Real Locust load driver executing operator locustfiles against authorized targets with genuine percentile and availability metrics.
- **`app/integrations/locust_sim.py`**: Zero-traffic DDoS simulator generating synthetic load curves through the full gateway/registry lifecycle.
- **`app/integrations/remote_access.py`**: NetExec remote administration wrapper supporting 5 read-only operations via temporary `/dev/shm` credentials.
- **`app/telemetry/collector.py`**: Non-destructive blackbox TCP-connect probe and host telemetry collectors.
- **`app/integrations/activity_gen.py`**: Bounded purple-team SOC detection-signature generator for DDoS, brute-force, and RAT activities.

---

## 6. Network Architecture & Isolation Model

All operations originate from Kali Linux and interface with the target environment across strictly controlled network boundaries:

```
[ Kali Linux Attacker Host ]
   ├── eth0: 10.238.79.204/24 (DHCP default gateway → Internet)
   └── tailscale0: 100.80.154.42/32 (Encrypted Tailnet Mesh)
            │
            │ (Kernel Routing Table 52: 100.80.167.51 dev tailscale0)
            ▼
[ Encrypted Tailscale Tunnel ]
            │
            ▼
[ Target Host: opensoc-windows ] (100.80.167.51)
   ├── Accounts: Kali (manoharisatyasarthak@) vs Windows (onlymahibhatt@)
   └── Boundary: Separate Tailscale account ownership requires explicit authorization
```

### Network Enforcement Properties:
1. **Routing Table Isolation**: Linux policy routing rule (`from all lookup 52`) directs all traffic destined for `100.80.167.51` exclusively through `tailscale0`. No lab packets leak to `eth0` or the public internet.
2. **Recon Target Authorization**: `collector.authorize_recon_target()` permits only IPv4 literals in RFC1918 private space or active Tailscale peer addresses (`100.64.0.0/10`). All public/global IPs and hostnames are rejected.
3. **Authorization Boundary**: Network reachability via Tailscale ping does **not** grant authorization. Live attack testing against `100.80.167.51` remains blocked pending formal permission from the target owner account (`onlymahibhatt@`).
