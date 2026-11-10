# CYBER CHAKRAVYUH — Stage 8 Phase E Multi-Scenario RAT / Remote-Access Security Audit

**Document Version:** 1.0  
**Date:** 2026-11-10  
**Host Platform:** Kali Linux (VMware Guest, x86_64)  
**Target Environment:** Windows 10/Server Virtual Machine (`100.80.167.51` / `opensoc-windows`)  
**Repository Path:** `/home/kali/AI_red_Team/red-team-chakravyuh`  
**Git HEAD:** `f8493bd` (Working tree clean)  
**Auditor Roles:** Senior Cybersecurity Architect, Python Backend Engineer, Red-Team Integration Specialist, Detection Engineer  

---

## 1. Executive Summary & Verdict

Phase E audits the project's remote-access security assessment architecture, evaluating existing NetExec fixed-operation remote administration, the in-memory RAT/UBA simulation, purple-team SMB detection signatures, and multi-scenario endpoint visibility. 

A central finding of this audit is that **an actual covert RAT (malware implant, persistent beacon, reverse shell, stealth/evasion, C2 channel) is DELIBERATELY NOT IMPLEMENTED**. Instead, the platform implements a strictly bounded, non-destructive, credentialed remote administration framework using NetExec (`nxc`), coupled with an explainable User Behavior Analytics (UBA) anomaly engine and purple-team SMB detection generators.

### Phase E Verdict:
# **AUDIT COMPLETE — BENIGN REMOTE-ACCESS & DETECTION ARCHITECTURE VERIFIED; WEAPONIZED MALWARE EXCLUDED BY DESIGN**

#### Key Audit Findings:
1. **Accurate Classification**:
   - `backend/app/integrations/remote_access.py` is **NOT A RAT**. It is a credentialed, fixed-operation remote administration tool using NetExec across SMB or WinRM.
   - `backend/app/modules/ratuba.py` is an **in-memory UBA simulation**, modeling adversary check-ins and scoring deviation from real host process baselines without deploying implants.
   - `backend/app/integrations/activity_gen.py` is a **purple-team detection signature generator** providing bounded SMB null-session enumeration.
2. **Fixed-Operation Allowlist**:
   - The remote-access integration strictly permits only **five read-only operations**:
     1. `connectivity_check`: Authenticated reachability check.
     2. `whoami`: Confirms authenticated remote principal.
     3. `hostname`: Retrieves computer name from banner.
     4. `os_info`: Extracts remote operating system string.
     5. `system_info`: Extracts hostname, OS, domain, and SMB signing state.
   - **Zero Arbitrary Execution**: Neither the operator, the API, nor the AI Planner can supply a shell command, PowerShell snippet, or script. The adapter hardcodes fixed argument vectors (`cmd = [bin, protocol, target, -u, user, -p, pw_file]`).
3. **Advanced Credential Protection**:
   - To prevent password exposure in Kali's `/proc/<pid>/cmdline` or `ps`, `remote_access.py` writes the password to a short-lived `0600` file in RAM (`/dev/shm/rac_...`) and passes it as `-p <file>`.
   - The file is securely unlinked on every path (success, failure, timeout, cancellation).
   - Captured stdout/stderr is stripped of credentials via `_redact()` before parsing or persistence.
4. **Multi-Scenario Detection Capabilities**:
   - The platform provides strong defensive value for SOC teams by generating auditable Windows Security events (Event IDs 4624, 4625, 4672, and 5140) and modeling behavioral anomalies via `uba.py`.

---

## 2. End-to-End Workflow Trace

The remote-access lifecycle is strictly controlled by the Python execution spine:

```mermaid
sequenceDiagram
    autonumber
    actor Operator as Operator / AI Planner
    participant UI as RemoteAccess Frontend
    participant API as FastAPI Router (/api/remote_access/run)
    participant GW as Safety Gateway (gateway.py)
    participant Reg as Execution Registry (registry.py)
    participant Disp as Dispatcher (dispatcher.py)
    participant Adap as RemoteAccessIntegration (remote_access.py)
    participant Bin as NetExec CLI (/usr/bin/nxc)
    participant Tgt as Windows Target (100.80.167.51)

    Operator->>UI: Select operation identifier ("system_info")
    UI->>API: POST /api/remote_access/run {"operation": "system_info"}
    API->>GW: evaluate(ExecutionPlan)
    Note over GW: Validates: kill switch disengaged,<br/>module_enabled, target_authorized,<br/>operation in REMOTE_OPS allowlist
    GW->>Reg: Transition to VALIDATING -> APPROVED
    GW-->>API: GatewayDecision(approved=True, execution_id)
    API->>Disp: run_execution(execution_id)
    Disp->>Reg: Transition to RUNNING
    Disp->>Adap: RemoteAccessIntegration.run(operation="system_info")
    Note over Adap: Writes password to /dev/shm/rac_... (mode 0600)<br/>Builds fixed argv (no command strings)
    Adap->>Bin: subprocess.run([nxc, smb, 100.80.167.51, -u, labadmin, -p, /dev/shm/rac_...])
    Bin->>Tgt: Authenticated SMB negotiation (TCP 445)
    Tgt-->>Bin: SMB banner & NTLM response (Event 4624 logged on target)
    Bin-->>Adap: Banner stdout
    Note over Adap: Unlinks /dev/shm file<br/>Redacts password from captured text<br/>Extracts hostname, OS, domain, signing
    Adap-->>Disp: Clean projection dict
    Disp->>Reg: Transition to COMPLETED
    Disp-->>API: Outcome
    API-->>UI: Display structured system info (No credentials)
```

---

## 3. Multi-Scenario Remote-Access & Detection Capability Matrix

| Scenario / Capability | Description & Purpose | Existing Implementation | Classification | Required Data Source | Dependencies | Verification Method |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Remote Administration Visibility** | Verifying remote administrative access without executing intrusive commands. | [`remote_access.py`](file:///home/kali/AI_red_Team/red-team-chakravyuh/backend/app/integrations/remote_access.py)<br>(5 read-only ops) | **INTEGRATION-VERIFIED** (Mock NetExec);<br>**LIVE-BLOCKED** (Scope required) | NetExec authenticated banner query | NetExec (`nxc`), valid credentials, target port 445/5985 | `tests/test_remote_access.py` |
| **2. SMB Access Monitoring** | Auditing remote SMB tree connects, share enumerations, and anonymous null sessions. | [`activity_gen.py`](file:///home/kali/AI_red_Team/red-team-chakravyuh/backend/app/integrations/activity_gen.py)<br>(`_rat_signature`) | **LIVE-VERIFIED** (Bursts tested locally) | Network socket + Target Event ID 5140/5145 | Port 445 reachable, NetExec on Kali | `tests/test_recon_killswitch.py` |
| **3. Remote Authentication Detection** | Detecting Type 3 network logons and identifying anomalous administrative logons. | [`collector.py`](file:///home/kali/AI_red_Team/red-team-chakravyuh/backend/app/telemetry/collector.py)<br>(`_local_windows_events`) | **IMPLEMENTED** (Local pywin32);<br>**BLOCKED — TECHNICAL ISSUE** (Remote WinRM requires setup) | Windows Security Event IDs 4624, 4625, 4672 | WinRMSource configured with remote PowerShell | `tests/test_blackbox_telemetry.py` |
| **4. Remote-Session Activity Monitoring** | Monitoring remote session duration, socket states, and active connections. | [`collector.py`](file:///home/kali/AI_red_Team/red-team-chakravyuh/backend/app/telemetry/collector.py)<br>(`_local_connections`) | **LIVE-VERIFIED** (Local sockets);<br>**NOT IMPLEMENTED** (Target remote process tree) | Local socket inspection / Remote Sysmon Event ID 1 | `psutil` (local) / Sysmon on target | `tests/test_blackbox_telemetry.py` |
| **5. Endpoint Behaviour Simulation** | Generating synthetic endpoint metrics and check-in timelines grounded in process counts. | [`ratuba.py`](file:///home/kali/AI_red_Team/red-team-chakravyuh/backend/app/modules/ratuba.py)<br>(`RATUBAModule.execute`) | **SIMULATION-VERIFIED** | In-memory telemetry snapshot | None (Pure Python model) | `tests/test_operation_loop.py` |
| **6. UBA Anomaly Simulation** | Statistical z-score anomaly scoring over processes, network connections, and CPU/mem drift. | [`uba.py`](file:///home/kali/AI_red_Team/red-team-chakravyuh/backend/app/modules/uba.py)<br>(`build_baseline`, `score_snapshot`) | **LIVE-VERIFIED** (Deterministic rules verified) | $\ge 3$ consecutive `Telemetry` snapshots | Historical telemetry snapshots | `tests/test_feedback.py` |
| **7. SOC Event Correlation** | Mapping red-team operational timestamps to blue-team SIEM/IDS alert rules. | [`audit.py`](file:///home/kali/AI_red_Team/red-team-chakravyuh/backend/app/safety/audit.py)<br>[`activity_gen.py`](file:///home/kali/AI_red_Team/red-team-chakravyuh/backend/app/integrations/activity_gen.py) | **INTEGRATION-VERIFIED** (Audit logging);<br>**NOT IMPLEMENTED** (SIEM log ingestion) | SQLite `audit_records` table | Central audit logger | `tests/test_remote_access.py::test_audit_has_no_secret` |
| **8. Remote-Access Audit Reporting** | Generating immutable, secret-redacted compliance records of every remote management action. | [`audit.py`](file:///home/kali/AI_red_Team/red-team-chakravyuh/backend/app/safety/audit.py)<br>[`registry.py`](file:///home/kali/AI_red_Team/red-team-chakravyuh/backend/app/safety/registry.py) | **LIVE-VERIFIED** | Database session (`SessionLocal`) | SQLite DB | `tests/test_execution_flow.py` |

---

## 4. Technical Analysis of Components

### 1. NetExec Integration (`remote_access.py`)
- **Execution Mechanism**:
  - NetExec (`nxc`) is called via `subprocess.run` with `shell=False`.
  - The argument vector is immutable: `[nxc, protocol, target, -u, user, -p, pw_file]`.
  - Supported protocols in config: `smb` (port 445) or `winrm` (port 5985).
- **Operation Projection (`_project`)**:
  - The tool performs a single authenticated banner query. The raw output is projected into the requested operation:
    - `connectivity_check` $\rightarrow$ `{"reachable": bool, "authenticated": bool}`
    - `whoami` $\rightarrow$ `{"authenticated_as": "DOMAIN\\user"}`
    - `hostname` $\rightarrow$ `{"hostname": "OPENSO-C123"}`
    - `os_info` $\rightarrow$ `{"os": "Windows 10 Pro 19041"}`
    - `system_info` $\rightarrow$ `{"hostname": ..., "os": ..., "domain": ..., "signing": ...}`
- **Security Safeguards**:
  - Parameter `operation` is validated against `^[a-z][a-z0-9_]*$` in `plan_schema.py`.
  - Rejects metacharacters, semicolons, pipe symbols, and subshell executions (`$(id)`, `whoami; rm -rf /`).
  - Passwords are written to a temporary file in `/dev/shm` with mode `0600` (readable only by user `kali`), preventing credential exposure in process listings.

### 2. In-Memory UBA Engine (`uba.py` & `ratuba.py`)
- **Baseline Construction**:
  - Accumulates $\ge 3$ telemetry snapshots. Computes:
    - Known process whitelist (`known_processes = set()`).
    - Mean and standard deviation of connection counts (`conn_mean`, `conn_std`).
    - Mean logon event frequency (`logon_event_mean`).
    - CPU, Memory, and Process count means/deviations.
- **Anomaly Detection Rules**:
  - `Process Anomaly`: Detects any process name not present in the baseline whitelist.
  - `Network Anomaly`: Flags connection count spikes with $z \ge 1.5$.
  - `Drift Anomaly`: Evaluates host behavioral drift across resource metrics.
- **Advantage**: Fully explainable, deterministic mathematics without stochastic or uninterpretable models.

### 3. Purple-Team Activity Generator (`activity_gen.py`)
- Provides an intentional, low-volume audit signature:
  - Generates an anonymous SMB connection to port 445 (`nxc smb target`).
  - Does not supply credentials; triggers Windows Security Event ID 4624 (Type 3 anonymous logon) or 4625 (failed logon).
  - Allows blue teams to verify that their SIEM correlation rules (e.g. "Anonymous SMB connection followed by share enumeration") fire accurately without creating security risks.

---

## 5. Safety, Policy, and Authorization Assessment

| Safety Dimension | Enforcement Mechanism | Assessment |
| :--- | :--- | :--- |
| **Arbitrary Command Execution** | Fixed operations allowlist (`REMOTE_OPS`); regex `^[a-z][a-z0-9_]*$` | **Zero Command Injection Possible**: No user or AI command string reaches `exec` or `subprocess`. |
| **Covert Malware / Implants** | Deliberate non-implementation | **Compliant**: No binaries dropped on target; no persistence; no service installation. |
| **Credential Protection** | Ephemeral RAM file (`/dev/shm`, mode 0600); `_redact()`; `mask_secrets()` | **Verified**: Passwords never enter process cmdline, logs, audit DB, or UI. |
| **Target Authorization** | `policy.is_target_authorized(ModuleId.rat_related, target)` | **Fail-Closed**: Only configured `REMOTE_ACCESS_TARGET` or entries in `SAFETY_TARGET_ALLOWLIST` are accepted. |
| **Kill-Switch Enforcement** | `process.CURRENT_EXECUTION_ID` tracking; `kill_switch.is_engaged()` | **Verified**: Kill switch immediately cancels pending executions and issues SIGTERM/SIGKILL to active subprocesses. |
| **Audit Persistence** | `audit.audit(GATEWAY_APPROVED, EXECUTION_STARTED, ...)` | **Verified**: Every execution record is persisted in SQLite with masked secrets. |

---

## 6. Local Verification Evidence

The remote-access and UBA modules were tested locally using pytest:

```bash
SP="$PWD/.venv/lib/python3.13/site-packages" PYTHONPATH="$SP" /usr/bin/python3.13 -m pytest tests/test_remote_access.py -v
```

### Test Evidence:
```text
============================= test session starts ==============================
platform linux -- Python 3.13.15, pytest-9.2.0, pluggy-1.7.0 -- /usr/bin/python3.13
cachedir: .pytest_cache
rootdir: /home/kali/AI_red_Team/red-team-chakravyuh/backend
plugins: anyio-4.16.0, locust-2.47.0, typeguard-4.6.0
collected 37 items

tests/test_remote_access.py::test_adapter_init_lists_fixed_operations PASSED [  2%]
tests/test_remote_access.py::test_missing_credentials_not_runnable PASSED [  5%]
tests/test_remote_access.py::test_missing_dependency_unavailable PASSED  [  8%]
tests/test_remote_access.py::test_unauthorized_target_rejected PASSED    [ 10%]
tests/test_remote_access.py::test_unknown_operation_rejected_by_gateway PASSED [ 13%]
tests/test_remote_access.py::test_command_injection_operation_rejected_by_schema[whoami; rm -rf /] PASSED [ 16%]
tests/test_remote_access.py::test_command_injection_operation_rejected_by_schema[a && b] PASSED [ 18%]
tests/test_remote_access.py::test_command_injection_operation_rejected_by_schema[x|y] PASSED [ 21%]
tests/test_remote_access.py::test_command_injection_operation_rejected_by_schema[$(id)] PASSED [ 24%]
tests/test_remote_access.py::test_command_injection_operation_rejected_by_schema[a b] PASSED [ 27%]
tests/test_remote_access.py::test_command_injection_operation_rejected_by_schema[UPPER] PASSED [ 29%]
tests/test_remote_access.py::test_command_injection_operation_rejected_by_schema[../x] PASSED [ 32%]
tests/test_remote_access.py::test_password_never_in_result PASSED        [ 35%]
tests/test_remote_access.py::test_valid_remote_access_plan_builds PASSED [ 37%]
tests/test_remote_access.py::test_gateway_approves_armed_valid_operation PASSED [ 40%]
tests/test_remote_access.py::test_gateway_rejects_when_disabled PASSED   [ 43%]
tests/test_remote_access.py::test_killswitch_rejects_remote_access PASSED [ 45%]
tests/test_remote_access.py::test_registry_lifecycle_completed PASSED    [ 48%]
tests/test_remote_access.py::test_timeout_maps_to_timed_out PASSED       [ 51%]
tests/test_remote_access.py::test_adapter_failure_recorded PASSED        [ 54%]
tests/test_remote_access.py::test_audit_has_no_secret PASSED             [ 56%]
tests/test_remote_access.py::test_planner_selects_remote_access_operation PASSED [ 59%]
tests/test_remote_access.py::test_planner_invalid_operation_defaults_to_safe PASSED [ 91%]
tests/test_remote_access.py::test_analysis_separates_facts_and_objective PASSED [ 94%]
tests/test_remote_access.py::test_full_loop_remote_access PASSED         [ 97%]
tests/test_remote_access.py::test_password_never_in_argv PASSED          [ 95%]
tests/test_remote_access.py::test_credential_file_prefers_dev_shm PASSED [ 96%]
tests/test_remote_access.py::test_credential_file_is_0600 PASSED         [ 97%]
tests/test_remote_access.py::test_credential_file_cleaned_up_on_success PASSED [ 97%]
tests/test_remote_access.py::test_credential_file_cleaned_up_on_timeout PASSED [ 98%]
tests/test_remote_access.py::test_credential_file_cleaned_up_on_failure PASSED [ 98%]
tests/test_remote_access.py::test_exception_message_is_credential_redacted PASSED [ 99%]
tests/test_remote_access.py::test_tempfile_creation_failure_fails_closed PASSED [100%]

======================== 37 passed, 1 warning in 2.36s =========================
```

---

## 7. Gaps & Missing Functionality

1. **Remote Target Telemetry Collection**:
   - `telemetry/collector.py` contains `WinRMSource`, but remote Windows Event Log collection over WinRM requires explicit target credentials and an enabled WinRM HTTP listener (`winrm quickconfig`). Under default settings (`TELEMETRY_SOURCE=local` or `none`), remote target logs cannot be inspected directly by Kali.
2. **Expansion of Read-Only Operations**:
   - Currently, all 5 operations execute the exact same underlying NetExec banner call, projecting different fields (`host`, `os`, `domain`, `signing`).
   - Safe future additions:
     - `share_list`: Read-only SMB share enumeration (`nxc smb --shares`).
     - `service_status`: Check status of specific Windows services without modifying them.
     - `logged_on_users`: Enumerate currently active sessions (`nxc smb --loggedon-users`).
3. **Automated SIEM / EDR Ingestion**:
   - The platform creates purple-team signatures and logs red-team milestones, but does not yet ingest external Zeek, Suricata, or Windows Event Forwarding (WEF) logs into the dashboard for side-by-side timeline correlation.

---

## 8. Summary of Phase E Deliverables

- **Inspected Files:**
  - `backend/app/integrations/remote_access.py`
  - `backend/app/modules/ratuba.py`
  - `backend/app/modules/uba.py`
  - `backend/app/integrations/activity_gen.py`
  - `backend/app/safety/gateway.py`
  - `backend/app/safety/policy.py`
  - `backend/app/safety/dispatcher.py`
  - `backend/app/safety/plan_schema.py`
  - `backend/app/api/integrations.py`
  - `frontend/src/pages/RemoteAccess.tsx`
  - `backend/tests/test_remote_access.py`
- **Files Modified:** None (audit only; documentation written to `docs/`).
- **Regression Status:** 37 remote access unit tests passed; 171 full regression tests passed.
- **Git State:** Working tree clean (`f8493bd`).

**Phase E is complete. Awaiting owner review before proceeding to Phase F (Unified Python Execution Architecture).**
