# CYBER CHAKRAVYUH — Live Demo Runbook (~8–12 min)

**Pre-demo checklist:** backend `/api/health` 200 · frontend `127.0.0.1:5173` 200 · kill switch disengaged (`halted:false`) · (optional) `tailscale ping 100.80.167.51` pong · (optional) OpenRouter key valid. Re-arm token kept privately by the operator.

### Part 1 — Introduction (1 min)
- **Action:** open dashboard. **Say:** "AI proposes, deterministic Python authorizes and executes — the AI never runs tools." **UI:** modules + live telemetry status. **Recovery:** if UI down, restart `npm run dev`.

### Part 2 — Network Discovery (2 min)
- **Action:** Network Discovery → Run tailnet discovery. **Backend:** `POST /api/network/discovery/start {mode:tailnet}` → scan_id + execution_id. **UI:** peers listed, all **pending**. **Audit:** `DISCOVERY_STARTED/COMPLETED`. **Say:** "Discovered ≠ authorized." **Recovery:** if a peer is offline, note it honestly.

### Part 3 — Harmless reconnaissance (2 min)
- **Action:** select an **authorized** target → run Target Recon probe. **Backend:** `select` → `authorize_recon_target`; `POST /api/telemetry/probe`. **UI:** measured open ports / "unreachable" if offline. **Audit:** `RECON_PROBE (completed)`. **Say:** "Backend validated authorization before any packet; results are measured, not fabricated." **Recovery:** target offline → show the honest "reachable:false" result.

### Part 4 — Safety controls (2–3 min)
- **Action:** try to select a public IP (`8.8.8.8`) → **400 rejected**; try the hotspot subnet → **400 rejected (dynamic)**. Engage **kill switch** → attempt any op → **423 blocked** → re-arm with admin token → normal. **Audit:** `KILLSWITCH_ENGAGED/RESET`, `GATEWAY_REJECTED`. **Say:** "Fail-closed authorization + a global kill switch with an admin-token reset."

### Part 5 — Blue Team / telemetry (1–2 min)
- **Action:** show telemetry panel + audit history + UBA. **Say:** "Measured vs simulated vs unavailable are labeled. Blue-Team detection runs on the target's own SOC/Wazuh — external to this app; we do not forward events." **Only** show Wazuh alerts if the target+agent are live and evidence exists.

### Part 6 — AI (1 min)
- **Action:** AI Planner → submit an objective. **If OpenRouter authed:** show AI plan (`AI PLAN`). **Else:** show **FALLBACK (NOT AI)** label. **Say:** "If AI is down, deterministic planning continues — nothing is faked."

### Part 7 — Closing (1 min)
- **Say:** "Live: discovery, authorization, recon, kill-switch, audit. Blocked: live Windows ops + AI inference — both external dependencies. 249 tests pass."

> Do not change configuration to force success. Keep the primary demo harmless/read-only.
