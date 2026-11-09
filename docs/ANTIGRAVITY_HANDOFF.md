# CYBER CHAKRAVYUH — Handoff Brief for Antigravity

**Written for:** the next agent (Antigravity) + the project owner.
**Date:** 2026-11-09 · Repo: `/home/kali/AI_red_Team/red-team-chakravyuh/` · Host: Kali (VMware guest).
**Purpose:** everything that exists, the current running state, the safety rails, and exactly what to do next.

> CHAKRAVYUH is an **authorized** AI red-vs-blue lab platform. All work happens **on Kali only**. The
> "target" is the owner's SOC lab (`opensoc-windows`, Tailscale). Nothing here attacks third parties.

---

## 1. What CHAKRAVYUH is (one paragraph)
FastAPI backend + React/Vite dashboard. An operator (or the AI planner) proposes bounded work; a
deterministic **Safety Gateway** authorizes it (kill-switch → module-enabled → target-allowlist →
caps); an **Execution Registry** + **Dispatcher** run it through an **adapter**; results go to
**AI analysis** (OpenRouter / OmniRoute) and **audit**, then back to the dashboard. One of each:
planner, LLM client, plan schema, gateway, registry, dispatcher, kill switch, audit.

## 2. What was done in this session (chronological)
1. **OmniRoute gateway** installed (v3.8.53) user-level on a dedicated **Node 24** (`~/.local/node24`),
   loopback-only + auth, wired to CHAKRAVYUH by config. OpenRouter is the live default. Docs:
   `CHAKRAVYUH_OMNIROUTE_SETUP.md`, `_INTEGRATION.md`, `_RUNBOOK.md`. **LIVE-VERIFIED.**
2. **One-Click Attack** panel on the dashboard (`frontend/src/components/QuickAttack.tsx`).
3. **DDoS Simulation Mode** — separate `locust_sim` adapter + `simulate` plan flag + gateway sim-branch +
   `POST /api/integrations/locust/simulate` + Integrations UI banner "SIMULATION — NO NETWORK TRAFFIC".
4. **DDoS research-lab design** (no VM created): `CHAKRAVYUH_DDOS_RESEARCH_LAB.md`,
   `CHAKRAVYUH_DDOS_TARGET_SETUP.md`, zero-dep `backend/tools/research_target_app.py`.
5. **On-demand recon probe** — Target Recon page: enter an IP → bounded TCP-connect probe →
   open ports + a SOC proof-note. `POST /api/telemetry/probe`, `collector.authorize_recon_target`.
6. **SOC detection-signature generator** (the latest ask) — One-Click Attack panel now takes a **target
   IP**; RUN ATTACK generates a bounded, non-destructive SOC signature for the chosen TTP:
   `POST /api/attacks/soc-activity` → `backend/app/integrations/activity_gen.py`.
7. **Stage-1 baseline audit**: `CHAKRAVYUH_FINAL_BASELINE_AUDIT.md`.

## 3. The SOC-signature generator — how it behaves (IMPORTANT)
`activity_gen.generate_signature(kind, target)` — authorized targets only (RFC1918 or current tailnet
peer; **public IPs refused**). Bounded + non-destructive by design:
| Kind | What it actually does | SOC detects | NOT |
|---|---|---|---|
| `ddos` | ≤40 TCP connects over ≤8 s (~5/s) | NIDS: elevated connection rate / sweep | a real flood / DoS |
| `bruteforce` | ≤5 SMB auths with **bogus random usernames** | Windows 4625 failed-logon burst | real creds / account lockout |
| `rat_related` | read-only SMB enumeration (null session) | anonymous logon / SMB tree connect | implant / persistence / commands |
Every response is labelled `simulated_attack: true` with a `note` + `detectable_as`. Verified: a local
listener confirmed the ddos burst makes real (bounded) connections; public IP → HTTP 423.

## 4. Current running state
- **Backend** `uvicorn app.main:app` on **127.0.0.1:8077** — RUNNING (see §6 for how it's started).
- **Frontend** Vite on **http://localhost:5173** — RUNNING (proxies `/api` → 8077).
- **Tailscale**: Kali = `100.80.154.42`. Target `opensoc-windows` `100.80.167.51` was **OFFLINE** (last
  seen ~2 h ago) — so live auth/enumeration signatures fall back honestly until it is powered on.
- **Git**: working tree has **uncommitted** changes from items 5–7 above (nothing committed/pushed by this
  session beyond what the owner committed). HEAD ≈ `27d083b`.

## 5. Environment quirks the next agent MUST know
- **Python venv is half-broken**: the system Python was upgraded 3.13→3.14 externally; `backend/.venv`
  interpreter now points at 3.14 but the packages are under `python3.13/`. **Run the backend + tests with
  Python 3.13 + the venv packages**, e.g.:
  ```sh
  cd backend; SP="$PWD/.venv/lib/python3.13/site-packages"
  PYTHONPATH="$SP" /usr/bin/python3.13 -m pytest -q
  PATH="$HOME/.local/chakra-bin:$PATH" PYTHONPATH="$SP" /usr/bin/python3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8077
  ```
  (`~/.local/chakra-bin/locust` is a shim so the Locust adapter finds a 3.13 locust.) A clean rebuild of
  the venv for 3.14 is a pending owner decision.
- **Frontend** uses the older Node at `~/.local/node` (v22.11); OmniRoute uses `~/.local/node24` (v24).
- **Secrets**: `backend/.env` (gitignored, `600`) holds OpenRouter + DeepSeek keys. **These were pasted in
  chat earlier → the owner should ROTATE them.** Never print/commit keys.

## 6. How to run everything (Kali only)
```sh
# Backend (3.13 invocation — see §5)
cd /home/kali/AI_red_Team/red-team-chakravyuh/backend
SP="$PWD/.venv/lib/python3.13/site-packages"
PATH="$HOME/.local/chakra-bin:$PATH" PYTHONPATH="$SP" /usr/bin/python3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8077 &

# Frontend
cd ../frontend && PATH="$HOME/.local/node/bin:$PATH" npm run dev   # http://localhost:5173

# OmniRoute (optional AI gateway) — see docs/CHAKRAVYUH_OMNIROUTE_RUNBOOK.md
~/.local/bin/chakravyuh-omniroute
```
Dashboard → **Operations overview → One-Click Attack**: pick DDoS/Brute Force/RAT, enter the target IP,
RUN ATTACK → the SOC-signature note appears. **Target Recon** page: enter an IP → recon probe.

## 7. What Antigravity should do next (task list)
1. **Bring the target online**: the owner powers on `opensoc-windows`; confirm `tailscale ping 100.80.167.51`
   returns pong. Only then do the live SMB 4625 / enumeration signatures actually land in the SOC.
2. **Validate detections end-to-end** with the Blue Team: run each kind from the dashboard against the
   online target, then confirm the SOC (Wazuh/Splunk/Sentinel) shows: connection-rate alert (ddos),
   4625 burst (bruteforce), anonymous-logon/enum (rat). Capture screenshots as proof.
3. **Decide the venv**: either keep the 3.13 invocation (works) or rebuild `backend/.venv` for Python 3.14
   (`python3.14 -m venv`, reinstall `backend/requirements.txt`) — owner's call.
4. **Rotate the OpenRouter + DeepSeek keys** (pasted in chat), update `backend/.env`.
5. **Optional**: stand up the disposable Alpine **research target VM** per `CHAKRAVYUH_DDOS_RESEARCH_LAB.md`
   for real (bounded) Locust load tests against an HTTP app — separate from the Windows box.
6. **Commit** when the owner approves (nothing has been pushed).

## 8. Hard safety rails (do NOT cross)
- Only RFC1918 / tailnet-peer targets; **public IPs are refused** — keep it that way.
- **No real DoS/flood, no real credential cracking, no account-lockout testing, no implant/persistence,
  no arbitrary remote command execution.** The generators are bounded detection signatures, not attacks.
- Tailscale membership ≠ authorization. Don't attack any box without the owner's explicit go-ahead.
- Kali only. No changes to the Windows host, no new VMs without approval, no commits/pushes without approval.

## 9. Key files (map)
- Safety spine: `backend/app/safety/{gateway,policy,registry,dispatcher,killswitch,audit,plan_schema}.py`
- Adapters: `backend/app/integrations/{hydra,locust,locust_sim,remote_access,activity_gen}.py`
- Recon: `backend/app/telemetry/collector.py` (`run_probe`, `authorize_recon_target`, `probe_on_demand`)
- API: `backend/app/api/{routes,integrations,llm,operations,execution,central}.py`
- Dashboard: `frontend/src/pages/{Dashboard,TargetRecon,Integrations,Operation}.tsx`,
  `frontend/src/components/QuickAttack.tsx`, `frontend/src/api.ts`
- Docs: everything under `docs/CHAKRAVYUH_*.md`
