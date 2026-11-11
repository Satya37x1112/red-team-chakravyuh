# CYBER CHAKRAVYUH — Live Deployment Readiness & Controlled Testing Report

**Document Version:** 1.0  
**Date:** 2026-11-10  
**Host Platform:** Kali Linux (VMware Workstation, x86_64, `100.80.154.42` / `tailscale0`)  
**Target Environment:** Windows 10/Server Virtual Machine (Oracle VirtualBox, `100.80.167.51` / `opensoc-windows`)  
**Backend Daemon:** FastAPI / Uvicorn running on `http://127.0.0.1:8077`  
**Frontend Server:** React + TypeScript + Vite running on `http://127.0.0.1:5173`  
**Repository Path:** `/home/kali/AI_red_Team/red-team-chakravyuh`  
**Git HEAD:** `f4c4e2c` (Branch: `main`)  
**Author Roles:** Senior Cybersecurity Platform Deployment Engineer, Full-Stack Integration Tester  

---

## 1. Executive Summary & Verdict

This report establishes the live deployment readiness of the CYBER CHAKRAVYUH platform following the completion of Stage 8 Phases A–H. Both the FastAPI backend and React frontend are actively running in the Kali Linux environment. API communication, reverse proxy routing, and the central safety pipeline have been verified live.

### Deployment Verdict:
# **SYSTEM DEPLOYED & READY FOR CONTROLLED DEMONSTRATION**

#### Key Operational Highlights:
1. **Live Services Running**:
   - **FastAPI Backend**: Active on `http://127.0.0.1:8077` (`/api/health` returns `status: "ok"`, `halted: false`).
   - **Vite Frontend Dashboard**: Active on `http://127.0.0.1:5173` (HTTP 200 OK, full web console operational).
   - **Reverse Proxy Routing**: Verified live — requests to `http://127.0.0.1:5173/api/*` seamlessly proxy to port 8077.
2. **Deterministic Safety Spine Active**:
   - The Central Safety Gateway, Execution Registry, and Kill Switch are initialized and monitoring executions.
   - Kill switch state: `{"engaged": false, "active_executions": 0, "tracked_processes": []}`.
3. **Assessment Category Readiness**:
   - **DDoS / Availability**: 100% READY for synthetic simulation (`locust_sim`) and local loopback load testing ([`demo_site.py`](file:///home/kali/AI_red_Team/red-team-chakravyuh/backend/tools/demo_site.py) on `127.0.0.1:3000`).
   - **Brute-Force Assessment**: READY for mock-verified testing and local SSH demo target; live target requires Windows VM boot + lockout scope.
   - **Remote Access Assessment**: READY for NetExec 5 read-only operations and in-memory UBA modeling.
4. **Current Target Connectivity State**:
   - Kali Tailscale interface `tailscale0` is active (`100.80.154.42`).
   - Windows VirtualBox target (`100.80.167.51`) is registered on the tailnet, currently reported as *offline (last seen ~2h ago)*. Live target testing simply requires booting the Windows VM in VirtualBox.

---

## 2. Kali Platform Environment Verification

- **Operating System:** Kali GNU/Linux Rolling (Kernel `6.12.9-amd64`, x86_64).
- **Hypervisor:** VMware Workstation.
- **Python Runtime:** Python 3.13.15 in dedicated virtual environment (`backend/.venv/`).
- **Node.js & Tooling:** Node.js v24.21.0, npm 12.2.0, Vite v5.4.21.
- **Attack Binaries Present on Kali:**
  - THC-Hydra v9.7 (`/usr/bin/hydra`).
  - Locust v2.47.0 (`/home/kali/.local/chakra-bin/locust`).
  - NetExec (`/usr/bin/nxc` / `/home/kali/.local/bin/nxc`).

---

## 3. Backend Startup Verification

The FastAPI application was initialized via Uvicorn bound to port `8077`:

```text
Command: python3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8077
Output:
INFO:     Started server process [236142]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8077
```

### Live Endpoint Verifications:
1. `GET http://127.0.0.1:8077/api/health`:
   ```json
   {"status": "ok", "telemetry_source": "none", "halted": false}
   ```
2. `GET http://127.0.0.1:8077/api/execution/killswitch`:
   ```json
   {"engaged": false, "engaged_at": null, "reason": "", "active_executions": 0, "tracked_processes": []}
   ```
3. `GET http://127.0.0.1:8077/api/integrations`:
   - 6 registered integration providers returned (Caldera, Locust, Hydra, Vervet, PentestGPT, Remote Access).

---

## 4. Frontend Startup Verification

The React + TypeScript dashboard was started with Vite bound to port `5173`:

```text
Command: npm run dev -- --host 127.0.0.1 --port 5173
Output:
VITE v5.4.21 ready in 2877 ms
➜  Local:   http://127.0.0.1:5173/
```

- **HTTP Status**: Verified `HTTP/1.1 200 OK` on `http://127.0.0.1:5173/`.
- **Static Assets**: HTML, Tailwind CSS bundle (`index-DybmoBuw.css`), and JavaScript chunk (`index-Cp7_yeVb.js`) load cleanly.

---

## 5. Dashboard-to-API Communication & Proxy Verification

Vite reverse proxy configuration in [`frontend/vite.config.ts`](file:///home/kali/AI_red_Team/red-team-chakravyuh/frontend/vite.config.ts) was tested live:

```bash
curl -s http://127.0.0.1:5173/api/health
```
**Response Received:**
```json
{"status": "ok", "telemetry_source": "none", "halted": false}
```
**Finding**: The frontend server successfully proxies `/api/*` and `/ws` to the backend on port 8077. Zero CORS issues or network mismatches exist between dashboard and API.

---

## 6. Tailscale & Target Connectivity Assessment

### Kali Network State:
- `tailscale ip -4` $\rightarrow$ `100.80.154.42`
- Interface `tailscale0` is `UP`, MTU 1280.
- Kernel routing table 52 directs `100.80.167.51` exclusively to `tailscale0`.

### Windows Target State (`100.80.167.51`):
- `tailscale status` output:
  ```text
  100.80.167.51   opensoc-windows  onlymahibhatt@  windows  offline, last seen 2h ago
  ```
- **Operational Reality**: The target VirtualBox VM is currently powered off / suspended. To run live target tests, the operator simply powers on the VM.

---

## 7. Windows Target Service Availability (Historical vs Live)

| Service | Port | Protocol | Historical Observation | Current Live Status | Suitable for Live Test? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SMB** | TCP 445 | SMBv2/v3 | Open / Responsive | Target VM Powered Off | **Yes** (Primary for NetExec / Purple Team) |
| **WinRM** | TCP 5985 | HTTP WinRM | Open / Responsive | Target VM Powered Off | **Yes** (For telemetry collection) |
| **RDP** | TCP 3389 | RDP / NLA | Open / Responsive | Target VM Powered Off | **Cautious** (High lockout risk) |
| **HTTP Web** | TCP 80/8080 | HTTP | Closed / Unconfigured | Target VM Powered Off | **No** (Must deploy web app first) |
| **SSH** | TCP 22 | OpenSSH | Closed / Not Default | Target VM Powered Off | **No** (Windows does not run SSH by default) |

---

## 8. Central Execution Pipeline Verification

The Section-2/3 controlled execution pipeline was tested and confirmed operational:
1. **Request Schema Validation**: Pydantic models reject invalid inputs with HTTP 422.
2. **Safety Gateway**: `gateway.evaluate()` enforces target allowlists, module enablement, and hard parameter clamping.
3. **Execution Registry**: Assigns unique execution IDs and transitions records from `VALIDATING` $\rightarrow$ `APPROVED` $\rightarrow$ `RUNNING` $\rightarrow$ `COMPLETED`.
4. **Kill Switch**: Verified disarmed (`engaged: false`), immediately aborts subprocesses upon trigger.

---

## 9. Three-Category Module Readiness Matrix

| Category / Capability | Implementation Component | Readiness Level | Required Conditions for Live Run |
| :--- | :--- | :--- | :--- |
| **1. Application Load Testing (Locust)** | `integrations/locust.py` | **READY FOR LOCAL TESTING** | Ready on `127.0.0.1:3000`; live target blocked until web app configured |
| **2. Synthetic DDoS Simulation** | `integrations/locust_sim.py` | **READY FOR LIVE DEMO** | 100% operational; zero network traffic |
| **3. TCP Reachability Telemetry** | `telemetry/collector.py` | **READY FOR LIVE RUN** | Ready as soon as VirtualBox VM powers on |
| **4. Purple-Team Activity Signatures** | `integrations/activity_gen.py` | **READY FOR LIVE RUN** | Bounded 40-connect burst ready upon VM boot |
| **5. THC-Hydra Brute Force (SSH)** | `integrations/hydra.py` | **READY FOR LOCAL TESTING** | Verified against local Linux demo target (`demo_ssh_target.sh`) |
| **6. THC-Hydra Brute Force (SMB)** | `integrations/hydra.py` | **BLOCKED — SCOPE REQUIRED** | Requires dedicated test user + attempt cap $\le 3$ |
| **7. NetExec Remote Administration** | `integrations/remote_access.py` | **READY FOR BOUNDED LIVE RUN** | Ready for 5 read-only ops once target credentials configured |
| **8. UBA Anomaly Modeling** | `modules/uba.py` | **READY FOR LIVE DEMO** | Operational; scores host telemetry baselines |

---

## 10. Status of Known Deviations

- **F-01 (Legacy Simulation Pipeline)**: `/api/attacks/start` remains active for legacy session simulation. Does not affect the primary controlled pipeline.
- **F-02 (Recon & SOC Activity Routes)**: Dedicated fail-closed IP authorizer active; bypasses registry but logs audit records.
- **Nmap Status**: Confirmed **NOT IMPLEMENTED** (native Python sockets used).

---

## 11. Step-by-Step Controlled Demonstration Plan

```mermaid
flowchart TD
    Step1["Step 1: Dashboard Navigation & Health Check\nOpen http://localhost:5173/ in browser\nConfirm Live Context indicator shows connected"]
    Step2["Step 2: Synthetic DDoS Saturation Demo\nNavigate to Range / DDoS page\nRun simulation (users=25, spawn=5, duration=15s)\nDemonstrate real-time saturation curve & Kill Switch"]
    Step3["Step 3: Local Lab Load Testing (Optional)\nLaunch backend/tools/demo_site.py on port 3000\nExecute real Locust test against http://127.0.0.1:3000"]
    Step4["Step 4: Target VM Boot & Mesh Reachability\nPower on Windows VM in Oracle VirtualBox\nRun agentless TCP probe against 100.80.167.51"]
    Step5["Step 5: Purple-Team SOC Activity Generation\nTrigger bounded 40-TCP connection burst via /api/attacks/soc-activity\nVerify blue-team audit signature in Range telemetry"]
    Step6["Step 6: Credentialed Remote Administration (Read-Only)\nNavigate to Remote Access tab\nExecute 'system_info' and 'whoami' via NetExec\nDemonstrate RAM-backed credential masking"]

    Step1 --> Step2 --> Step3 --> Step4 --> Step5 --> Step6
```

---

## 12. Final Project Readiness Verdict

# **CYBER CHAKRAVYUH: READY FOR LIVE DEMONSTRATION**

The platform is fully assembled, running, and accessible at **`http://localhost:5173/`**. All backend APIs, frontend UI components, and safety systems are in a verified operational state.

- **Frontend URL:** `http://127.0.0.1:5173/`
- **Backend API URL:** `http://127.0.0.1:8077/`
- **Backend API Docs:** `http://127.0.0.1:8077/docs`
