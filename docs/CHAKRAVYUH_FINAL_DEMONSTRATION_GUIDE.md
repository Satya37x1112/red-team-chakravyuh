# CYBER CHAKRAVYUH — Final Project Demonstration Runbook

**Document Version:** 2.0 (Verified Technical Demonstration Guide)  
**Date:** 2026-11-10  
**Target Audience:** Academic Reviewers, Defense Evaluators, Technical Stakeholders  
**Demonstration Mode:** Hybrid Mock / Local Simulation / Offline Fallback  
**Security Posture:** Non-destructive; no live external attacks; zero unauthorized target interference.  

---

## 1. Demonstration Principles & Honesty Mandate

When demonstrating CYBER CHAKRAVYUH to reviewers or evaluators, adhere strictly to the following disclosure rules:

> ⚠️ **MANDATORY DISCLOSURE:** All attack module outputs shown during standard demonstrations are **mocked or simulated**. Real external attacks against the Windows target are authorization-gated and deliberately disarmed. Never misrepresent synthetic metrics or mock outputs as live exploitation results. Always vocalize: *"This demonstration exercises the end-to-end architecture, safety gating, and telemetry pipeline using verified local simulations and mocks."*

---

## 2. Pre-Demonstration Setup (5 Minutes)

### Step 1: Start Services
Follow the procedures in `docs/CHAKRAVYUH_FINAL_DEPLOYMENT_GUIDE.md`:
1. Launch the FastAPI backend on `http://127.0.0.1:8077`.
2. Launch the React dashboard on `http://localhost:5173`.
3. Open a browser to `http://localhost:5173`.

### Step 2: Confirm System Health
1. Verify the status indicator in the top navigation bar displays **"Telemetry live"** (green dot).
2. Confirm the range status pill displays **"ARMED"** (green).
3. Verify that the current target is set to the authorized lab address `100.80.167.51`.

---

## 3. Step-by-Step Demonstration Walkthrough

### Part A: The Hybrid Architecture & Safety Philosophy (3 Mins)
- **Concept to Explain**: Traditional AI security tooling either naively gives an LLM direct shell access (an uncontrollable hazard) or isolates the LLM into an irrelevant chat silo.
- **The Chakravyuh Solution**: **"AI Proposes — Deterministic Code Decides."**
- **Architecture Flow**: Walk the audience through the 14-stage pipeline documented in `docs/CHAKRAVYUH_FINAL_ARCHITECTURE.md`:
  `Operator Objective → Context Manager → Central Planner → Pydantic Schema → Safety Gateway → Operator Approval → Registry → Dispatcher → Process Manager → Adapter → Telemetry → AI Analysis → Feedback → Audit`.

### Part B: AI Planner & Honest Fallback Demonstration (5 Mins)
1. Navigate to **Agent → AI Planner** (`/planner`).
2. **Submit Objective**: Enter an operational objective:
   `"Conduct bounded reconnaissance and credential testing against authorized lab server."`
3. **Click "Preview Plan"**:
   - Point out that this triggers `POST /api/operations/plan`, which executes a **Dry-Run Gateway Evaluation**.
   - **Show Condition B (Honest Fallback)**:
     - The AI provider returns HTTP 401 (auth failure).
     - Point out the amber **`FALLBACK (NOT AI)`** pill.
     - Highlight the reasoning text: *"Deterministic fallback (NOT AI-generated): LLM unavailable..."*
     - Point out that zero fake AI text was invented.
     - Show the **Gateway Line**: `GATEWAY APPROVED (dry run)` with server-clamped parameters.
4. **Explain Boundary**: Note that the plan preview reserved no execution ID and executed no adapters. The operator retains full control.

### Part C: Deterministic Target Authorization & Rejection (3 Mins)
1. Open a terminal and run the automated test demonstrating unauthorized target rejection:
   ```bash
   cd backend && SP="$PWD/.venv/lib/python3.13/site-packages" \
   PYTHONPATH="$SP" /usr/bin/python3.13 -m pytest tests/test_gateway.py -k "test_unauthorized_target_rejected" -v
   ```
2. Explain the mechanism: If an operator or compromised AI proposes an attack against an arbitrary target (e.g. `http://evil.com` or `8.8.8.8`), the `SafetyGateway` immediately rejects the plan with HTTP 423.
3. Show that rejected plans never create execution records and can never reach adapters.

### Part D: DDoS Simulation Mode (Real-Time Lifecycle Demo) (5 Mins)
1. Navigate to **Integrations → Locust Load Test** (`/integrations`).
2. Locate the dedicated **Simulation mode — no network traffic** panel.
3. Point out the amber warning: *"Demonstrates the full execution lifecycle (Safety Gateway · Registry · Kill Switch · audit) with synthetic telemetry. Sends nothing — no target is contacted."*
4. Click **"Run simulation"**:
   - Show the dynamic progress updates and real-time synthetic RPS / latency / failure curve.
   - Point out that this execution was assigned an official `execution_id` by the central `ExecutionRegistry` and generated full audit logs.
   - Show the prominent banner: `SIMULATION — NO NETWORK TRAFFIC GENERATED`.

### Part E: Unified Kill Switch & Managed Process Termination (4 Mins)
1. **Engage Kill Switch**:
   - While the simulation or an activity is running, press the global hotkey: **`Win + Alt + K`** (or click the red **Kill Switch** button in the top navigation bar).
   - Show the modal notification: Range halted; active executions cancelled.
   - Point out the red **`RANGE HALTED`** pill on the dashboard.
   - Observe that the **RUN ATTACK** and **Run load test** buttons are now disabled.
2. **Show Process Safety**:
   - Explain that `process.py` executes all tools in dedicated Linux process groups (`setpgrp`).
   - Run the automated test verifying that the kill switch kills managed child processes while leaving unrelated OS processes completely untouched:
     ```bash
     cd backend && SP="$PWD/.venv/lib/python3.13/site-packages" \
     PYTHONPATH="$SP" /usr/bin/python3.13 -m pytest tests/test_killswitch.py -k "test_unrelated_process_not_terminated" -v
     ```
3. **Re-arm the Range**:
   - Click **Re-arm Range**.
   - Enter the administrator token (`SAFETY_ADMIN_TOKEN`).
   - Show the confirmation toast: *"Range re-armed by authorized operator."* The status returns to **`ARMED`**.

### Part F: Target Recon & Blackbox Telemetry (3 Mins)
1. Navigate to **Lab → Target Recon** (`/recon`).
2. In the target box, enter the lab target: `100.80.167.51`.
3. Click **"Run recon probe"**:
   - Show the non-destructive TCP-connect scan results.
   - Point out the open port table and the SOC proof note:
     *"Recon complete — TCP connection attempts sent to 100.80.167.51 from 100.80.154.42... The target's SOC logs these as reconnaissance: your proof."*
   - Point out the honesty of the display: Host internals (CPU/RAM) are clearly marked **"not visible"** because an external blackbox probe cannot see inside the target.

### Part G: Central Audit Records & Secret Redaction (2 Mins)
1. Show that every authorization decision, dry run, simulation, and kill-switch event is recorded in SQLite.
2. Run the automated test proving secrets are scrubbed:
   ```bash
   cd backend && SP="$PWD/.venv/lib/python3.13/site-packages" \
   PYTHONPATH="$PWD:$SP" /usr/bin/python3.13 -m pytest tests/test_execution_flow.py -k "test_secrets_never_leak_to_result_or_audit" -v
   ```
3. Explain that passwords and API keys are recursively sanitized into `«redacted»` before hitting disk.

### Part H: Authentication Testing & RockYou Auditing (4 Mins)
1. Navigate to **Integrations → Password Auditing & Wordlist Console** (`/integrations` or Operation view).
2. **RockYou Wordlist Inspection**:
   - Tab 1 ("RockYou Wordlist"): Shows discovery of `/usr/share/wordlists/rockyou.txt.gz` (50.9 MB, ~14.3M canonical lines).
   - Demonstrates that passwords are never returned raw or logged, and alternate wordlists are never silently substituted.
3. **Offline Hash Auditing**:
   - Tab 2 ("Offline Hash Audit"): Enter a target hash (e.g. NTLM, MD5, SHA-256, or bcrypt).
   - Click "Identify Algorithm" → Automatically identifies format.
   - Click "Audit Hash Against RockYou" → Performs bounded dictionary comparison against RockYou streaming entries.
   - Shows matched vs unmatched confirmation with execution timing.
4. **Live Authentication Validation**:
   - Tab 3 ("Live Auth Validation"): Enter authorized target and non-admin account.
   - Enter candidate passwords (clamped to max 3 attempts per run).
   - Demonstrates immediate halt on success or lockout warning (`STATUS_ACCOUNT_LOCKED_OUT`), with masked account identifier (`la****r`).

### Part I: Real Availability & HTTP Load Testing (Locust) (4 Mins)
1. Navigate to **Integrations → Locust Load Test & Availability** (`/integrations`).
2. Show the difference between:
   - **Simulation Mode**: Generates synthetic load curve with zero packets sent; displays prominent amber banner `SIMULATION — NO NETWORK TRAFFIC GENERATED`.
   - **Genuine Load Test**: Generates real HTTP traffic within backend caps (≤50 users, ≤120s duration).
3. Execute real load test against an authorized endpoint:
   - Performs automated pre-test reachability probe (HTTP status code, baseline latency).
   - Collects real request counts, successful requests, failures, and throughput (req/s).
   - Displays real latency percentiles: Average, Median (p50), and 95th Percentile (p95).
   - Performs post-test reachability probe and computes latency delta to verify target service remained up.
   - Shows explicit target host resource status: `CPU: Unavailable`, `RAM: Unavailable` (honestly reporting no target-side agent rather than fabricating metrics).
   - Displays HTTP status and connection error breakdown table.

### Part J: Authenticated Remote Data Transfer & Windows Receiver (4 Mins)
1. Navigate to **Access → Authenticated Remote File Transfer** (`/remote`).
2. **Windows Receiver Setup**:
   - On the Windows lab machine, launch the visible Python receiver:
     ```cmd
     python tools\windows_receiver.py --port 8090 --token lab-transfer-secret-2026 --dir C:\LabData
     ```
   - Emphasize that this is transparent and operator-controlled: visible console window, strict token authentication, and path traversal prevention.
3. **Connectivity Probe**:
   - On Kali dashboard, enter target `http://100.80.167.51:8090` and token `lab-transfer-secret-2026`.
   - Click "Check Receiver Connectivity" → verifies online state and authorization.
4. **Initiate Transfer & SHA-256 Integrity Verification**:
   - Select an approved lab test artifact.
   - Click "Transfer File".
   - Platform calculates pre-transfer SHA-256 hash.
   - Receiver saves file and calculates post-receipt SHA-256 hash.
   - Console displays **SHA-256 Integrity Verified** match badge.
   - Platform routes transfer event into the UBA engine and displays anomaly scoring.

### Part K: One-Click Orchestrated Assessment & Target VM Open Ports (3 Mins)
1. Navigate to the **Main Operations Overview (Dashboard)** (`/`).
2. Locate the **One-Click Orchestrated Assessment** console.
3. **Target IP & Hash Input**:
   - The target IP defaults to the authorized lab Windows host (`100.80.167.51`).
   - (Optional) Click "Sample Hash" to populate the MD5 hash of `'password'` (`5f4dcc3b5aa765d61d8327deb882cf99`).
4. **Click "RUN ASSESSMENT"**:
   - In a single click, the platform runs the sequence:
     1. Target validation (RFC1918 / Tailnet peer check; rejects public IPs fail-closed).
     2. Target reachability check (TCP connect / Tailscale ping; stops early if target is offline to avoid fabricating results).
     3. Non-destructive port recon (discovers open ports e.g. 80 HTTP, 445 SMB, 3389 RDP).
     4. DDoS SOC detection signature (bounded 40 connects, max 8s).
     5. Brute Force SOC signature (emits 5 bogus logons; automatically skips if port 445 is closed).
     6. RAT SOC signature (read-only SMB enumeration; automatically skips if port 445 is closed).
     7. Offline RockYou hash audit (recovers plaintext password locally without touching target).
     8. Live tools notices (honestly marks real Locust and Remote File Transfer as "Requires Setup").
5. **View Results**:
   - **Target VM Open Ports & Services**: Shows green badges for every detected open port, service protocol, and response latency.
   - **Execution Checklist**: Renders live per-step statuses (`DONE`, `SKIPPED`, `UNAVAILABLE`, `BLOCKED`, `STOPPED`) with execution timing and verifiable audit trail records.
   - **Kill Switch Integration**: Pressing `Win + Alt + K` or clicking Stop mid-sequence immediately halts all remaining steps.

---

## 4. Addressing Reviewer Inquiries

**Q: Why don't you run live Hydra password cracking against the Windows VM right now?**  
> *"Because the Windows machine `100.80.167.51` belongs to a different Tailscale account (`onlymahibhatt@`). In accordance with professional cybersecurity ethics, technical network reachability does NOT equal authorization. The attack module logic, parameter clamping, and credential redaction are 100% verified via automated mock suites, but live attacks remain disarmed until formal written target authorization is documented."*

**Q: If the AI is offline, how is this an AI platform?**  
> *"The platform is hybrid by design. When AI credentials are active, Claude provides autonomous planning, contextual reasoning, and post-execution feedback. When AI credentials are unconfigured or failing, the platform exhibits defensive resilience: it degrades gracefully to deterministic fallback planning, reports its status honestly, and never halts safety enforcement."*

**Q: Could a compromised LLM execute `rm -rf /` or attack an external government server?**  
> *"Mathematically impossible within this architecture. The AI layer contains zero subprocess or socket execution imports. It only outputs JSON. The Safety Gateway strictly verifies the target against a hardcoded allowlist and verifies remote operations against a 5-item read-only dictionary. Even if the AI hallucinated command injections, Pydantic v2 rejects them with HTTP 422 before the gateway is even reached."*
