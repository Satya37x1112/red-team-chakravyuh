# CHAKRAVYUH — DDoS Research Lab (Architecture & Safety Design)

**Date:** 2026-11-09 · Status: **DESIGN / READY WITH LIMITATIONS** (owner creates the VM).
A dedicated, disposable Linux HTTP target for **bounded, authorized** availability/resilience
research — reusing the existing CHAKRAVYUH Locust integration, Safety Gateway, and Kill Switch
unchanged. Separate from the Windows target `100.80.167.51`.

---

## 1. Topology
```
 Kali attacker VM (100.80.154.42)                 Research target VM (own 100.x)
 ├─ CHAKRAVYUH frontend  :5173                     ├─ research_target_app.py  :8080
 ├─ FastAPI backend      :8077                     │   /health /test /metrics (read-only)
 └─ Locust (venv)  ──HTTP load──► tailscale0 ──────┘  (firewall: only kali:→8080)

 Windows target opensoc-windows (100.80.167.51)  — SEPARATE, untouched, no load sent
```
Only the research service port is reachable; no unrestricted tailnet discovery; no public exposure.

## 2. Execution flow (existing architecture, unchanged)
```
Dashboard → FastAPI → Central AI Planner → Pydantic ExecutionPlan → Safety Gateway
 → Execution Registry → Locust Dispatcher → Research Target → Telemetry → AI Analysis
 → Audit Logging → Dashboard
```
- The research target is wired by **config only** (no new engine), exactly like any Locust target.
- AI analyzes **measured** telemetry; it can never bypass the Safety Gateway.

## 3. Locust integration (preserved; config only)
Point the existing adapter at the authorized research target (in `backend/.env`):
```
LOCUST_ENABLED=true
LOCUST_TARGET_URL=http://<research-target-tailscale-ip>:8080
LOCUST_FILE_PATH=/home/kali/AI_red_Team/red-team-chakravyuh/backend/tools/locustfile_demo.py
SAFETY_TARGET_ALLOWLIST=http://<research-target-tailscale-ip>:8080
```
Hard caps stay as-is (the Gateway clamps every request DOWN to these; a request can only lower them):
- **≤ 50 virtual users · ≤ 10 spawn/s · ≤ 120 s.** No distributed workers.
- Explicit target allowlisting + explicit per-run approval + Kill-Switch enforcement.

**Explicitly out of scope / not implemented:** SYN/UDP floods, connection exhaustion, amplification,
reflection, distributed flooding, or any service-disruption primitive. This is a bounded HTTP
load generator (`self.client.get("/")`) against an authorized app — a resilience test, not an attack.

## 4. Telemetry — measured vs simulated
- **Measured (real Locust run):** total/successful/failed requests, response-time percentiles,
  throughput (req/s), HTTP status distribution — from Locust's own stats.
- **Target-side:** `/metrics` reports request counters, p50/p95/p99, CPU% and mem% (from `/proc`),
  availability, and recovery (latency returns to baseline after load stops).
- **Simulated (separate mode):** the DDoS **Simulation Mode** (`locust_sim` adapter) produces clearly
  labelled synthetic telemetry with NO traffic — never mixed with, or presented as, measured values.
- No metric is ever fabricated; missing measurements are reported as missing.

## 5. Safety boundaries
- Kill Switch terminates the managed Locust subprocess group mid-run; new requests are rejected while engaged.
- Research target is separate from the Windows target; no load is ever sent to `100.80.167.51`.
- AI (OpenRouter / OmniRoute 3.8.53) analysis is read-only over telemetry; credentials/provider config unchanged.
- The target hosts no admin surface, no destructive endpoint, and no intentional vulnerability.

## 6. Owner actions required before a live run
1. Create the Alpine VM per `CHAKRAVYUH_DDOS_TARGET_SETUP.md` (confirm host RAM headroom first).
2. Join it to the tailnet (`tailscale up`) and note its `100.x` IP.
3. Copy + run `research_target_app.py`; restrict :8080 to kali via the target firewall.
4. Set the four `.env` lines above (target IP) and restart the backend.
5. Run a bounded load from the dashboard (start small, ramp within caps).

## 7. Known limitations
- Design only — no VM is created/booted here (per scope).
- Host is RAM-constrained; keep the target at 512 MB. Physical-host totals need owner confirmation.
- Real load requires the owner to stand up the VM + service first; until then only Simulation Mode runs.
