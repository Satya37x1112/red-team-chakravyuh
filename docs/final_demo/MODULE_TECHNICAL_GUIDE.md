# CYBER CHAKRAVYUH — Module Technical Guide

Status labels: **LIVE VERIFIED · MOCK VERIFIED · SIMULATION VERIFIED · IMPLEMENTED—NOT LIVE VERIFIED · BLOCKED**.

## Network Discovery
- **Purpose:** enumerate lab assets (Tailnet peers / optional lab subnet) and let the operator explicitly authorize a target.
- **Tech/files:** `app/services/discovery.py`, `app/api/network.py`, `frontend/src/pages/NetworkDiscovery.tsx`.
- **Routes:** `GET /api/network/{interfaces,subnets,tailnet}`, `POST /api/network/discovery/start`, `GET /api/network/discovery/{id}[/hosts]`, `POST /api/network/targets/select`.
- **Flow:** `tailscale status --json` → peers (state **pending**) → `select()` → `authorize_recon_target()` → **authorized + selected**. Lab-subnet sweeps are off by default and allowlist-gated.
- **Safety:** dynamic hotspot/default-route subnet rejected; public/loopback rejected; empty allowlist denies sweeps; atomic scan-concurrency limit; kill-switch honored per-peer/per-port; cancelled-before-start cannot become RUNNING.
- **Status:** **LIVE VERIFIED** (enumeration, selection, rejections). **Limitation:** tailnet asset-listing by default; online flag depends on `tailscale` JSON.

## Hydra (authentication security testing)
- **Purpose:** bounded credential-resilience testing against an authorized service.
- **Tech/files:** Hydra v9.7, `app/integrations/hydra.py`; gated via `app/api/integrations.py` `/hydra/run` → `evaluate()` → Registry → Dispatcher.
- **Safety:** target allowlist, **attempt cap** (`hydra_max_attempts`), lockout-aware design, secret redaction, timeout/cancel, audit. `live-validate` adds a ≤3-attempt single-account profile + non-admin-account rejection.
- **Status:** **MOCK VERIFIED** (tests + mocked processes). **No live authentication attempts performed.** Live needs an authorized online target + documented creds.

## Locust (availability / resilience)
- **Purpose:** bounded HTTP load testing — *not* a DDoS engine.
- **Tech/files:** Locust 2.47, `app/integrations/locust.py` (real), `app/integrations/locust_sim.py` (simulation).
- **Safety limits:** ≤50 users, ≤120 s, Gateway-clamped; cancel + kill-switch. **Simulation mode** generates synthetic metrics with **"SIMULATION — NO NETWORK TRAFFIC GENERATED"** and never mixes with measured data.
- **Status:** **MOCK VERIFIED** (real adapter) + **SIMULATION VERIFIED**. Real load needs an authorized HTTP target.

## NetExec (remote administration — read-only)
- **Purpose:** authenticated **read-only** remote info, no shell.
- **Tech/files:** `nxc`, `app/integrations/remote_access.py`; gated via `/remote_access/run`.
- **Operations (fixed):** `connectivity_check`, `whoami`, `hostname`, `os_info`, `system_info`. Credentials via protected config/stdin (never argv/logs). **No arbitrary command execution** (fixed operation identifiers, not command strings).
- **Status:** **IMPLEMENTED — NOT LIVE VERIFIED** (Windows offline).

## Telemetry & UBA
- **Sources:** agentless blackbox TCP-connect probe (`app/telemetry/collector.py`), live WebSocket events, SQLite audit. UBA scoring `app/modules/uba.py`.
- **Measured vs not:** probe reachability/open-ports/latency = **measured**; Windows CPU/RAM/event-log = **unavailable** (external probe can't see inside — reported unavailable, never fabricated); DDoS-sim metrics = **simulated/labeled**.
- **Status:** **MOCK VERIFIED**.

## File Transfer
- **Purpose:** operator-controlled authenticated file transfer with integrity.
- **Tech/files:** `app/services/transfer.py`, `app/api/transfer.py`, `backend/tools/windows_receiver.py`.
- **Controls:** auth token to receiver, **filename/path-traversal sanitization**, **10 MB** size limit, **SHA-256 before+after** with match check, audit, kill-switch; **received files are not executed**.
- **Status:** **IMPLEMENTED — NOT VERIFIED (BLOCKED)** — requires the operator to start the visible receiver on Windows.

## AI Planning
- **Config:** OpenRouter, model `anthropic/claude-sonnet-4.5`, centralized client `app/integrations/_llm.py`, planner `app/agent/planner.py`.
- **Flow:** objective → structured plan → **Pydantic validation** → Gateway. Honest fallback: on provider failure the planner returns a deterministic plan labeled **FALLBACK (NOT AI)**; no fabricated AI output.
- **Status:** **BLOCKED — PROVIDER AUTHENTICATION** (OpenRouter auth failing). Deterministic layer fully functional.
