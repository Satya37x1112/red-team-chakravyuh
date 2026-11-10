# CYBER CHAKRAVYUH — Technical Presentation & Defense Brief

**Document Version:** 2.0 (Post-Stage 6 Verification Baseline)  
**Date:** 2026-11-10  
**Context:** Academic Defense, Faculty Review, Technical Evaluation  
**Presenter Guidelines:** All factual claims are grounded directly in the verified codebase and automated test results. Differentiate completed features from proposed enhancements clearly.  

---

## 1. Executive Summary & Problem Formulation

### 1.1 The Operational Problem
Traditional offensive cybersecurity automation faces a critical dilemma:
1. **Scripted Automation**: Highly predictable and safe, but brittle, siloed, and incapable of contextual reasoning or dynamic tactical adaptation.
2. **Naive AI Agents**: Endowing a Large Language Model with direct shell execution, uncontrolled API access, or autonomous network targeting introduces catastrophic risks: hallucinations, runaway execution, unauthorized targeting, prompt injections, and compliance violations.

### 1.2 The Chakravyuh Thesis
**Can artificial intelligence provide strategic reasoning, contextual planning, and evidence analysis in offensive operations while deterministic software provably bounds, authorizes, and audits every physical action?**

CYBER CHAKRAVYUH resolves this challenge through a strict hybrid model:
> **"AI Proposes — Deterministic Code Decides."**

---

## 2. Platform Architecture: The 14-Stage Verified Pipeline

Walk the review panel through the verified data and control pipeline:

```
[1. Operator Objective] ────────► [2. React Dashboard] ────────► [3. FastAPI Orchestrator]
                                                                        │
[6. Structured Plan] ◄──────── [5. Central AI Planner] ◄─────── [4. Context Manager]
        │
        ▼
[7. Deterministic Safety Gateway] ── (Fail-Closed Reject) ──────► [HTTP 423 / Audit]
        │ (Approve with ID)
        ▼
[8. Operator Approval] ─────────► [9. Execution Registry] ──────► [10. Controlled Dispatcher]
                                                                        │
[13. Central Audit & DB] ◄────── [12. AI Analysis & Feedback] ◄── [11. Managed Process & Adapter]
        │
        ▼
[14. Real-Time WebSocket Hub] ──► [React Dashboard Updates]
```

### Key Architectural Invariants:
- **Single Brain**: One centralized AI planner coordinates all testing modules; no uncoordinated, competing multi-agent processes.
- **Fail-Closed Safety**: Any policy violation, missing credential, disabled module, or internal evaluation error results in immediate plan rejection.
- **Process Isolation**: Every security tool runs in a dedicated Linux process group (`start_new_session=True`), enabling comprehensive kill-switch termination.

---

## 3. The Hybrid Collaboration Model

Clearly delineate between cognitive and deterministic responsibilities:

```
┌──────────────────────────────────────┐      ┌──────────────────────────────────────┐
│           CLAUDE AI ENGINE           │      │         DETERMINISTIC PYTHON         │
│         (Cognitive / Soft)           │      │          (System / Hard)             │
├──────────────────────────────────────┤      ├──────────────────────────────────────┤
│ • Interprets natural language goal   │      │ • Enforces strict Pydantic schemas   │
│ • Proposes tactical modules & params │      │ • Binds targets to policy allowlists │
│ • Evaluates contextual telemetry     │      │ • Clamps parameters down to caps     │
│ • Separates facts from reasoning     │      │ • Authorizes execution in Gateway    │
│ • Recommends CONTINUE / MODIFY / STOP│      │ • Spawns isolated process groups     │
│ • Operates as ADVISORY ONLY          │      │ • Collects real socket measurements  │
│                                      │      │ • Redacts passwords & tokens         │
│                                      │      │ • Instantly terminates via KillSwitch│
└──────────────────────────────────────┘      └──────────────────────────────────────┘
```

### Resilience Under AI Outage (Condition B):
- When LLM credentials fail (HTTP 401), the platform **does not crash** and **never invents fake responses**.
- The planner engages deterministic fallback (`_fallback()`), emitting a bounded plan marked `source=PlanSource.system` and labeled `FALLBACK (NOT AI)` on the dashboard.
- Deterministic security controls remain 100% enforced.

---

## 4. Module Capabilities & Verification Status

Present the status of each security module honestly:

### 4.1 THC-Hydra (`bruteforce`)
- **Capability**: Bounded authentication testing against network services.
- **Safety Rails**: Caps on simultaneous tasks (`max_tasks=4`) and runtime (`max_run_seconds=30`). Disarmed by default. Passwords never returned or logged.
- **Status**: **MOCK-VERIFIED** · Live execution **BLOCKED** pending target-owner authorization.

### 4.2 Locust (`ddos`)
- **Capability**: HTTP service-load generation and capacity testing.
- **Safety Rails**: Caps on users (`max_users=50`), spawn rate (`10/s`), and duration (`60s`). Disarmed by default.
- **Status**: **MOCK-VERIFIED** · Live execution **BLOCKED** pending target-owner authorization.

### 4.3 DDoS Simulation Mode (`locust_sim`)
- **Capability**: Real-time demonstration of the full execution lifecycle with synthetic telemetry.
- **Safety Rails**: Zero network traffic; opens no sockets; contacts no external hosts. Polled by kill switch every 250ms.
- **Status**: **LIVE-VERIFIED** on Kali host.

### 4.4 NetExec Remote Administration (`remote_access`)
- **Capability**: Credentialed remote administration (defensive alternative to an uncontrolled RAT).
- **Safety Rails**: Strictly limited to 5 read-only operations (`connectivity_check`, `whoami`, `hostname`, `os_info`, `system_info`). No command execution, no shell, no persistence, no implant. Credentials stored temporarily in memory-backed `/dev/shm` (`0600`) and wiped immediately.
- **Status**: **MOCK-VERIFIED** · Live execution **BLOCKED** pending target-owner authorization.

### 4.5 Blackbox Reconnaissance & SOC Signatures
- **Capability**: Non-destructive TCP connectivity probe and purple-team SOC detection signatures.
- **Safety Rails**: Fail-closed IP gating (RFC1918 private lab space and Tailscale peers only; public IPs refused). Bounded activity (≤40 TCP connects, ≤5 bogus SMB auths). Audited centrally.
- **Status**: **LIVE-VERIFIED** locally and across Tailscale.

### 4.6 Nmap Network Scanner
- **Status**: **NOT IMPLEMENTED**. Acknowledged limitation; TCP connect probing handled by Blackbox probe.

---

## 5. Security & Safety Mechanisms

### 5.1 Deterministic Safety Gateway
Evaluates seven checks in sequential order:
1. Kill switch state (engaged → reject).
2. Module enablement in configuration (disabled → reject).
3. Tool binary availability on Kali (missing → reject).
4. Target presence in allowlist (unauthorized → reject).
5. Operation ID in approved list (unauthorized → reject).
6. Parameter clamping down to configured caps (never upward).
7. Thread-safe atomic concurrency limit enforcement.

### 5.2 Unified Kill Switch
- Operates across both simulation sessions and real execution adapters.
- Triggers `killpg` across tracked process groups with progressive escalation (`SIGTERM` → 5s grace → `SIGKILL`).
- Verified non-interference: system processes not spawned by `run_managed` are completely untouched.
- Re-arming is strictly token-gated via `SAFETY_ADMIN_TOKEN`.

### 5.3 Credential & Secret Protection
- Recursive redaction engine (`mask_secrets`) sweeps dictionary keys and list items for password/key patterns.
- Passwords never appear in API responses, WebSocket streams, logs, or SQLite database tables.

---

## 6. Testing & Quality Assurance Methodology

- **Total Backend Tests**: **171 Passed** (0 Failed, 0 Skipped, 0 Deselected, 1 Deprecation Warning).
- **Frontend Verification**: TypeScript strict mode passed (`tsc -b`, exit 0); Vite production build passed (`vite build`, exit 0).
- **Testing Approach**: Isolates logic and safety verification using mock adapters and canned responses. Proves pipeline robustness without launching uncontrolled network attacks.

---

## 7. Known Limitations & Technical Defensibility

Be prepared to defend known limitations with transparent technical rationale:

| Reviewer Question | Grounded Technical Defense |
|---|---|
| **Why is OpenRouter failing with HTTP 401?** | *"The API key expired or was rotated. The platform demonstrates defensive resilience: instead of failing or faking AI output, it gracefully degrades to deterministic fallback planning and labels the plan `FALLBACK (NOT AI)` on the console."* |
| **Why hasn't live Hydra testing been executed against the target?** | *"The target host `100.80.167.51` belongs to a separate Tailscale account (`onlymahibhatt@`). In professional cybersecurity practice, network reachability is not legal authorization. Live attacks remain disarmed until formal written rules of engagement are established."* |
| **Why is Nmap missing from the platform?** | *"Nmap was excluded from early development phases in favor of a lightweight, zero-dependency Python TCP connect probe (`collector.py`). Its absence is documented, and blackbox reconnaissance is fully functional via native sockets."* |
| **Is the frontend tested end-to-end?** | *"The frontend is verified via TypeScript strict typecheck and production bundle build. Interactive browser click-through is documented as unverified due to the absence of a headless browser automation harness on Kali."* |

---

## 8. Recommended Future Scope

1. **Supervised Live Target Testing**: Execute authorized, supervised live testing against `100.80.167.51` once target-owner approval is documented.
2. **Credential Refresh**: Provide updated OpenRouter credentials to restore live Claude inference.
3. **Headless UI Testing**: Integrate Playwright or Puppeteer for automated browser click-through regression testing.
4. **Persistent Execution Registry**: Back the in-memory execution registry with SQLite or Redis for persistence across server restarts.
5. **Nmap Integration**: Develop an `NmapIntegration` adapter adhering to the established `Integration` base class.
