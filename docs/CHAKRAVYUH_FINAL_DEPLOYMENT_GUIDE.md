# CYBER CHAKRAVYUH — Final Kali Deployment & Operations Guide

**Document Version:** 2.0 (Verified Kali-Native Deployment)  
**Date:** 2026-11-10  
**Target Platform:** Kali Linux Only (Bare-metal or VMware Guest)  
**Repository Directory:** `/home/kali/AI_red_Team/red-team-chakravyuh`  

---

## 1. Environment Prerequisites

Before initiating services on Kali Linux, ensure the following native binaries and libraries are present:

1. **Python Runtime**: Python 3.13 (`/usr/bin/python3.13`) with installed backend dependencies located in `backend/.venv/lib/python3.13/site-packages`.
2. **Node.js Runtime**: Node.js v22.11+ located at `~/.local/node/bin/node` and `npm`.
3. **Dedicated Tool Shims**: Shim directory `~/.local/chakra-bin` containing the Python 3.13 Locust execution wrapper.
4. **Network & VPN Daemon**: `tailscaled` active with authenticated connection to the operational tailnet.
5. **System Tools**: Standard Linux networking utilities (`iproute2`, `iptables`, `procps`).

---

## 2. Environment Variables Configuration

Runtime settings are managed exclusively via `backend/.env` (permissions `0600`, gitignored and untracked). 

> **SECURITY MANDATE:** Never print, commit, or log sensitive secrets. Below is the sanitized configuration schema:

```ini
# --- Generic LLM Configuration (Centralized Planner) ---
LLM_PROVIDER=openrouter
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-sonnet-4.5
LLM_TIMEOUT=60
# Set your active API key here (held in memory, never echoed by API)
LLM_API_KEY=<YOUR_OPENROUTER_OR_COMPATIBLE_KEY>
OPENROUTER_API_KEY=<FALLBACK_KEY_VARIABLE>

# --- Security & Safety Gateway Controls ---
SAFETY_ADMIN_TOKEN=<STRONG_SECRET_TOKEN_FOR_KILLSWITCH_REARM>
SAFETY_MAX_CONCURRENT_EXECUTIONS=2
SAFETY_TARGET_ALLOWLIST=100.80.167.51,192.168.176.50

# --- Telemetry Configuration ---
# Options: none | local | winrm | blackbox
TELEMETRY_SOURCE=blackbox
BLACKBOX_TARGET=100.80.167.51
BLACKBOX_ALLOWLIST=100.80.167.51,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16

# --- Attack Module Caps & Enablement ---
# Hydra (Authentication Testing)
HYDRA_ENABLED=false
HYDRA_TARGET=100.80.167.51
HYDRA_SERVICE=ssh
HYDRA_MAX_TASKS=4
HYDRA_MAX_RUN_SECONDS=30

# Locust (Load Generation)
LOCUST_ENABLED=false
LOCUST_TARGET_URL=http://100.80.167.51:8080
LOCUST_FILE_PATH=tools/locustfile.py
LOCUST_MAX_USERS=50
LOCUST_MAX_SPAWN_RATE=10
LOCUST_MAX_RUN_SECONDS=60

# NetExec (Remote Administration)
REMOTE_ACCESS_ENABLED=false
REMOTE_ACCESS_TARGET=100.80.167.51
REMOTE_ACCESS_PROTOCOL=smb
REMOTE_ACCESS_USERNAME=labadmin
REMOTE_ACCESS_PASSWORD=<LAB_CREDENTIAL>
REMOTE_ACCESS_MAX_RUN_SECONDS=30

# --- Network Discovery & Target Selection ---
DISCOVERY_ENABLED=true
DISCOVERY_DEFAULT_SOURCE=tailnet
DISCOVERY_LAB_SUBNET_ENABLED=false
DISCOVERY_AUTHORIZED_SUBNETS=192.168.100.0/24
DISCOVERY_MAX_HOSTS=64
DISCOVERY_CONNECT_TIMEOUT=0.5
DISCOVERY_PORTS=22,80,443,445,3389,8080
```

---

## 3. Server Startup Procedures (Kali Native)

The platform comprises two primary servers operating in concert:

| Service | Architecture | Binding Address | Description |
|---|---|---|---|
| **FastAPI Backend** | Python 3.13 / Uvicorn | `http://127.0.0.1:8077` | REST API, Safety Gateway, Dispatcher, WebSocket Hub |
| **React Dashboard** | Vite Dev / Static Build | `http://localhost:5173` | Operator UI, Telemetry Charts, One-Click Controls |

### 3.1 Terminal 1 — Start the FastAPI Backend
Due to the system-level Python 3.14 upgrade, the backend must be invoked using Python 3.13 with explicit virtual environment site-packages and the chakra-bin shim:

```bash
cd /home/kali/AI_red_Team/red-team-chakravyuh/backend

# Configure paths to the Python 3.13 virtual environment packages and tool shims
SP="$PWD/.venv/lib/python3.13/site-packages"
export PATH="$HOME/.local/chakra-bin:$PATH"
export PYTHONPATH="$SP"

# Start Uvicorn bound to localhost on port 8077
/usr/bin/python3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8077
```

**Expected Startup Output:**
```
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8077 (Press CTRL+C to quit)
```

### 3.2 Terminal 2 — Start the React Frontend Dashboard
Launch the frontend using the established Node.js runtime:

```bash
cd /home/kali/AI_red_Team/red-team-chakravyuh/frontend

# Ensure Node v22 is in the execution PATH
export PATH="$HOME/.local/node/bin:$PATH"

# Start the Vite development server
npm run dev
```

**Expected Startup Output:**
```
  VITE v5.4.21  ready in ... ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### 3.3 Network Proxying & WebSocket Connection
The Vite development server is pre-configured (`vite.config.ts`) to forward API and WebSocket requests transparently:
- Frontend API calls to `/api/*` are reverse-proxied to `http://127.0.0.1:8077/api/*`.
- WebSocket requests to `/ws` are forwarded to `ws://127.0.0.1:8077/ws`.
- No cross-origin resource sharing (CORS) re-configuration is necessary for standard local development.

---

## 4. Optional: Self-Hosted OmniRoute Gateway Startup

If routing LLM calls through the local, self-hosted OmniRoute gateway (Node 24) rather than directly to OpenRouter:

```bash
# In a dedicated terminal:
~/.local/bin/chakravyuh-omniroute
```
- Listens on `http://127.0.0.1:8000`.
- To route the platform through OmniRoute, navigate to the Dashboard **Settings** page and set:
  - **Provider**: `omniroute`
  - **Base URL**: `http://127.0.0.1:8000/v1`

---

## 5. Health Verification & Smoke Testing

Perform immediate verification of running services from Kali:

### 5.1 Backend Health Check
```bash
curl -s http://127.0.0.1:8077/api/health | jq .
```
Expected response:
```json
{
  "status": "ok",
  "halted": false,
  "service": "VAJRAPRAHAAR",
  "telemetry_source": "blackbox",
  "active_sessions": 0
}
```

### 5.2 LLM Configuration State Check
```bash
curl -s http://127.0.0.1:8077/api/llm/config | jq .
```
Expected response:
```json
{
  "provider": "openrouter",
  "base_url": "https://openrouter.ai/api/v1",
  "model": "anthropic/claude-sonnet-4.5",
  "timeout": 60,
  "api_key_configured": true,
  "config_valid": true,
  "reason": "OK"
}
```

### 5.3 WebSocket Stream Check
Verify that the WebSocket channel connects and delivers initial telemetry:
```bash
python3 -c "
import asyncio, websockets, json
async def check():
    async with websockets.connect('ws://127.0.0.1:8077/ws') as ws:
        msg = await asyncio.wait_for(ws.recv(), timeout=5)
        print('WS received:', json.loads(msg)['type'])
asyncio.run(check())
"
```
Expected output: `WS received: TELEMETRY_UPDATE`

---

## 6. Safe Operational Shutdown Procedures

To gracefully terminate CYBER CHAKRAVYUH processes:

1. **Stop Frontend**: In Terminal 2, press `Ctrl+C`.
2. **Stop Backend**: In Terminal 1, press `Ctrl+C`. The FastAPI lifespan will invoke `await service.stop()`, safely releasing SQLite database locks and terminating background telemetry pollers.
3. **Verify Process Cleanup**:
   ```bash
   pgrep -fa "uvicorn|vite"
   ```
   Ensure no orphan background processes linger.
4. **Emergency Stop**: If an active execution process fails to terminate, activate the platform kill switch:
   ```bash
   curl -s -X POST http://127.0.0.1:8077/api/killswitch | jq .
   ```
