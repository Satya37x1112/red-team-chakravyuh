# CHAKRAVYUH — Stage 1 Baseline Audit

**Date:** 2026-11-09 · Read-only inspection + baseline tests. No source modified.
Scope: establish the verified current state before the staged completion work.

---

## 1. Repository / environment
- Repo: `/home/kali/AI_red_Team/red-team-chakravyuh/` · HEAD `27d083b` · working tree **clean**.
- Dev host: **Kali** guest under VMware — 4 vCPU, 3.8 GB RAM, 45 GB free disk, Python 3.13.15 + Node 22.11.
- `.env`: git-ignored ✓, untracked ✓, perms `600` ✓. Keys never printed.
- Note: `backend/.venv` interpreter was externally repointed to Python 3.14; tests run via
  `PYTHONPATH=.venv/lib/python3.13/site-packages /usr/bin/python3.13 -m pytest` (3.13 + venv packages).

## 2. Architecture — one of each (verified present)
Single centralized: Planner (`agent/planner.py`), LLM client (`integrations/_llm.py` + `agent/llm.py`),
Execution-plan schema (`safety/plan_schema.py`), Safety Gateway (`safety/gateway.py`),
Execution Registry (`safety/registry.py`), Dispatcher (`safety/dispatcher.py`),
Kill Switch (`safety/killswitch.py`), Audit (`safety/audit.py`), Policy (`safety/policy.py`).
Adapters: `hydra.py`, `locust.py`, `locust_sim.py`, `remote_access.py` (NetExec), plus
`caldera/pentestgpt/vervet`. Flow matches: Plan → Gateway → Registry → Dispatcher → Adapter → Audit.

## 3. Baseline tests (actual)
| Suite | Command | Result |
|---|---|---|
| Backend | `python3.13 -m pytest -q` (14 test files) | **166 passed**, 1 warning |
| Frontend typecheck | `npm run typecheck` | **pass (0)** |
| Frontend build | `npm run build` | **pass (0)** |

## 4. Module status (Stage-1 assessment)
| Module | Status |
|---|---|
| AI Planner (OpenRouter) | IMPLEMENTED · MOCK-VERIFIED · **LIVE-VERIFIED** (live inference confirmed today) |
| OmniRoute 3.8.53 gateway | IMPLEMENTED · **LIVE-VERIFIED** (loopback+auth, inference through it confirmed today) |
| Safety Gateway | IMPLEMENTED · MOCK-VERIFIED (`test_gateway.py`) |
| Execution Registry | IMPLEMENTED · MOCK-VERIFIED |
| Kill Switch | IMPLEMENTED · MOCK-VERIFIED (process-level `test_killswitch.py`) |
| Audit | IMPLEMENTED · MOCK-VERIFIED |
| Hydra (auth testing) | IMPLEMENTED · MOCK-VERIFIED · live = **BLOCKED — AUTHORIZATION REQUIRED** |
| Locust (load) | IMPLEMENTED · MOCK-VERIFIED · live needs an authorized HTTP target (research VM not created) |
| DDoS Simulation | IMPLEMENTED · **verified locally** (synthetic, no traffic, through full lifecycle) |
| NetExec (5 ops incl. `system_info`) | IMPLEMENTED · MOCK-VERIFIED · live = **BLOCKED — AUTHORIZATION REQUIRED** |
| Network Recon — Blackbox TCP | IMPLEMENTED · MOCK-VERIFIED |
| Network Recon — **Nmap** | **NOT IMPLEMENTED** — no genuine adapter in `backend/app` (only Blackbox TCP-connect) |
| Telemetry / Dashboard | IMPLEMENTED · build-verified |

## 5. Tailscale (revalidated)
- Kali: `100.80.154.42` (matches historical). Tailnet reachable.
- `opensoc-windows` `100.80.167.51`: **offline (last seen ~2h ago)**, owned by a **different** Tailscale
  account (`onlymahibhatt@`) than Kali (`manoharisatyasarthak@`). Membership ≠ authorization.

## 6. Gaps / defects identified (for the staged work)
1. **Nmap** is not a real adapter — recon claims must stay limited to Blackbox TCP-connect.
2. **venv interpreter** mismatch (3.14 vs 3.13 packages) — tests need the 3.13 invocation; a clean rebuild
   for 3.14 is pending owner decision.
3. **Live attack paths (Hydra/NetExec/Locust-real)** are BLOCKED pending explicit owner authorization of a
   target + service + limits (and the Windows target is currently offline).
4. OpenRouter/DeepSeek keys were pasted into chat earlier today → **owner should rotate them**.

## 7. Conclusion
Core architecture is present, single-instance, and passes its full automated suite (166). AI (OpenRouter +
OmniRoute) is live-verified. Live external attack modules are implementation-complete but authorization- and
(for the research target) environment-blocked. No source was modified in this stage.

**Stage-1 verdict: DEVELOPMENT SUBSTANTIAL — VERIFICATION PARTIAL (awaiting owner review before Stage 2).**
