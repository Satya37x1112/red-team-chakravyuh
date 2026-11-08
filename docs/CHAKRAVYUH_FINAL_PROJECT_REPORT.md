# CHAKRAVYUH — Final Project Report

**Date:** 2026-11-07 · Academic Red-Team cyber-range platform · Kali-native · authorized isolated lab only.

---

## 1. Executive summary
CHAKRAVYUH is an AI-assisted Red-Team console in which one **centralized AI planner** proposes bounded offensive work across three modules, a **deterministic Safety Gateway** authorizes every action, execution is tracked, bounded, and audited, and the AI analyses **real evidence** to recommend continue/modify/stop. It is **fully mock/code-verified end-to-end** (141 tests; 140 pass offline, 1 live-LLM test deselected) with a clean frontend typecheck + build. It is **ready for demonstration preparation** and **not yet live-verified** against a real target. It is an academic isolated-lab tool, **not production-secure**.

## 2. Problem statement
Can an AI meaningfully assist offensive testing while remaining provably bounded, authorized, and auditable? Naively giving an LLM the ability to run tools is unacceptable. The project answers this with **"AI proposes, deterministic code decides."**

## 3. Objectives
One integrated console; one AI brain coordinating three modules; a deterministic gateway; bounded, audited execution; honest evidence; authorized lab only; nothing installed on the Windows target; Kali-native; no Docker.

## 4. Architecture
`Objective → Dashboard → FastAPI → Context Manager → Centralized AI Planner → ExecutionPlan (Pydantic) → Safety Gateway → Execution Registry → Dispatcher → Integration Adapter → Observation/Analysis → AI Feedback → Database/Audit → Dashboard`, with a unified kill switch over all managed executions. Full detail: `CHAKRAVYUH_FINAL_ARCHITECTURE.md`.

## 5. Implementation details
- **Backend** (`app/`): `main.py` (FastAPI + lifespan), `api/*` (operations, execution, integrations, routes, central), `agent/*` (context, planner, llm, analysis, feedback, operation; legacy decision), `safety/*` (plan_schema, policy, gateway, registry, dispatcher, process, killswitch, audit), `integrations/*` (hydra, locust, remote_access, caldera, vervet, pentestgpt), `telemetry/*` (collector, service, schema), `models.py`, `db.py`, `ws.py`.
- **Frontend** (`frontend/src/`): pages (AIPlanner, RemoteAccess, TargetRecon, Operations/OperationsCenter, Integrations, Dashboard, History, Reports), `api.ts`, `types.ts`, components.
- **AI boundary:** the AI layer imports no subprocess/dispatcher/adapter; it only produces a structured plan.

## 6. Module descriptions
1. **Hydra — Authentication Testing:** bounded credential testing; caps; cracked password never surfaced.
2. **Locust — Bounded Service-Load Testing:** operator locustfile vs one authorized URL; user/spawn/duration caps; not flooding.
3. **NetExec — Credentialed Remote Access (RAT alternative):** five fixed read-only operations; no implant/persistence/shell/arbitrary-command; 0600 `/dev/shm` credential file.
4. **Blackbox Telemetry:** agentless IP-only external probe; IPv4+RFC1918+allowlist; time-budgeted; honest (no faked internals).
5. **WinRM Telemetry:** remote read-only PowerShell; implemented, live-unverified.

## 7. Technology stack
Python 3.13, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy/SQLite, WebSocket, OpenRouter (OpenAI-compatible); React 18 + TypeScript + Vite + Tailwind; THC-Hydra / Locust / NetExec on Kali. No Docker.

## 8. Safety & security design
Deterministic gateway independent of the AI; target + operation allowlists; clamp-to-caps (AI can only lower); unified kill switch with real process-group termination; token-gated reset; secret masking across results/audit/logs/exceptions; credential file (0600, `/dev/shm`, cleaned every path, fail-closed); `.env` gitignored + untracked; backend bound to loopback; CORS restricted. **No API auth (by design, isolated single-operator lab) — not production-secure.**

## 9. Testing methodology
All verification uses **mocks and isolated fixtures** (mock LLM, mock adapters, mocked sockets) — no real tool runs, no target contact. The single live-LLM test is isolated/deselected in offline mode. This cleanly separates logic verification (done) from live verification (pending).

## 10. Exact test evidence (reconciled)
- **Full collection: 141 tests.**
- **Offline/mock run: `140 passed, 0 failed, 0 skipped, 1 deselected, 1 warning`.** The **1 deselected** is `test_live_llm.py::test_live_structured_plan_validates_and_is_bound` — the only network-dependent test (a real OpenRouter call); it is deselected transparently (not modified) to honor "no live API calls."
- With a credited OpenRouter key present, the full run = **141 passed** (the live test then runs). The **1 warning** is an upstream Starlette `BlockingPortal` deprecation, not project code.
- **Frontend:** `npm run typecheck` ✓ · `npm run build` ✓ (71 modules).
- Command: `python -m pytest tests/ -q --deselect "tests/test_live_llm.py::test_live_structured_plan_validates_and_is_bound"`.

Per-file: plan_schema 12 · gateway 10 · killswitch 6 · execution_flow 8 · concurrency 3 · planner 10 · ai_safety_integration 6 · operation_loop 11 · feedback 8 · operations_api 5 · live_llm 2 (1 offline + 1 live) · remote_access 37 · blackbox_telemetry 23.

## 11. Deployment status
Kali-native, manual startup verified (Stage 5.3). Backend/Gateway/Kill-switch/Audit/Configuration = **READY**; Startup/Shutdown/Frontend/Database/AI/Hydra/Locust/Remote-Access/Telemetry/Security/Recovery = **READY WITH LIMITATIONS**. See `CHAKRAVYUH_FINAL_FEATURE_MATRIX.md` and `CLAUDE_STAGE_5_3_DEPLOYMENT_READINESS.md`.

## 12. Limitations
Mock/code-verified only; real Hydra/Locust/NetExec/WinRM/blackbox vs a target UNVERIFIED; paid-model AI BLOCKED (credits); browser click-through and DB-outage recovery UNVERIFIED; no guaranteed remote-command cancellation; no start script; Node PATH not persistent; execution registry in-memory; not production-secure.

## 13. Future scope
Supervised live verification on the authorized lab target; credited AI keys; async execution + live WS streaming; dedicated Hydra/Locust pages + rearm token wiring; frontend tests; persistent registry; start/stop script; Alembic; WMI telemetry.

## 14. Conclusion
CHAKRAVYUH delivers the intended vision as a **genuinely integrated, safety-first, AI-assisted Red-Team platform**: one centralized AI brain, deterministic safety outside the AI, three bounded modules, honest telemetry, full auditing, and a comprehensive mock-verified test suite. The single remaining milestone is a **supervised live run** against the authorized lab target — the platform is otherwise complete and verified at the code/mock level.

> Honest framing: every result shown by the platform today is synthetic/mock or a safety behaviour. No real attack outcome has been produced.
