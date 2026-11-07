# CHAKRAVYUH — Master Project Progress (Cumulative)

**Permanent cumulative development record. Updated at the end of every section. Previous history is never erased.**

Last updated: 2026-11-07 (end of Section 3)
Repository: `/home/kali/AI_red_Team/red-team-chakravyuh/`
Test status at this update: **79/79 backend tests pass**; frontend `npm run typecheck` clean.

Status vocabulary (exact): `COMPLETED AND TESTED` · `IMPLEMENTED BUT NOT TESTED` · `PARTIALLY COMPLETED` · `BLOCKED` · `NOT STARTED`.
Honesty rules followed: no invented percentages; untested integrations are not marked verified; simulation ≠ real execution; documentation ≠ implementation; no API claimed working without a test.

---

## A. Overall Project Progress

**Objective:** an AI-driven Red-Team platform where a user gives an objective, ONE centralized AI brain plans, a deterministic Safety Gateway authorizes, bounded modules execute, and the AI analyses real evidence and recommends continue/modify/stop — authorized lab only, Kali-native, nothing installed on the Windows target.

**Completed sections:** 1 (audit), 2 (unified safety + execution control), 3 (centralized AI planner + feedback loop).

**Current architecture (as built):**
`Objective → Context Manager → Centralized AI Planner → Pydantic schema → Safety Gateway (deterministic) → Execution Registry → Dispatcher → Hydra/Locust (mock in tests) → Observation/Analysis → Feedback (CONTINUE/MODIFY/STOP) → bounded next iteration`, all behind `/api/operations/*`, persisted to `operations`/`operation_iterations`, with a unified kill switch over real + simulation work. The legacy simulation path (`/api/attacks/start`) and per-module integer `decide()` remain intact as legacy.

**Completed features:** structured plan schema, deterministic safety gateway, target allowlist, policy/cap enforcement, unified kill switch (real process-group termination), execution registry, audit logging with secret masking, centralized AI planner (mock-tested), post-execution analysis, feedback loop, operations API, AI Planner dashboard page.

**Partially completed:** Hydra/Locust (gateway-routed + mock-tested, not run live), telemetry (none/winrm/local implemented; winrm live unverified), centralized planner (logic tested with mock LLM; live LLM unverified), Kali deployment (runs; node not persistent).

**Not implemented:** RAT-related real capability (reserved; rejected at gateway), live end-to-end verification with a real LLM key + armed lab + target.

**Known limitations:** no `OPENROUTER_API_KEY` set → live AI path returns honest fallback; no real tool/target runs performed; operations are synchronous; kill-switch reset is token-gated and the frontend rearm button is not yet updated (awaiting owner decision).

---

## B. Mandatory Task Checklist

- [x] Repository inspection and audit — **COMPLETED AND TESTED**
- [x] Backend foundation — **COMPLETED AND TESTED**
- [~] Frontend foundation — **IMPLEMENTED BUT NOT TESTED**
- [~] Centralized AI planner — **PARTIALLY COMPLETED** (logic mock-tested; live LLM unverified)
- [x] Structured execution-plan schema — **COMPLETED AND TESTED**
- [x] Deterministic Safety Gateway — **COMPLETED AND TESTED**
- [x] Target allowlist — **COMPLETED AND TESTED**
- [x] Execution policy enforcement — **COMPLETED AND TESTED**
- [x] Unified kill switch — **COMPLETED AND TESTED**
- [x] Execution registry — **COMPLETED AND TESTED**
- [~] Hydra integration — **PARTIALLY COMPLETED** (fail-closed, gateway-routed, mock-tested; not run live)
- [~] Locust integration — **PARTIALLY COMPLETED** (fail-closed, gateway-routed, mock-tested; not run live)
- [ ] RAT-related capability — **NOT STARTED** (reserved; `rat_related` rejected at the gateway)
- [~] Telemetry collection — **PARTIALLY COMPLETED** (none/local/winrm implemented; winrm live unverified)
- [~] Observation engine — **PARTIALLY COMPLETED** (analysis component mock-tested; live telemetry-diff unverified)
- [x] AI feedback loop — **COMPLETED AND TESTED** (deterministic guardrails + mock LLM)
- [x] Audit logging — **COMPLETED AND TESTED**
- [~] Dashboard integration — **IMPLEMENTED BUT NOT TESTED** (typechecks + runs; no automated UI tests)
- [~] Automated testing — **PARTIALLY COMPLETED** (79 backend tests; no frontend test suite)
- [~] Kali deployment — **PARTIALLY COMPLETED** (backend venv runs; node installed locally, not persistent)
- [ ] Final end-to-end verification — **NOT STARTED** (needs real LLM key + armed lab + authorized target)

---

## C. Evidence-Based Status per Task

**Repository inspection and audit — COMPLETED AND TESTED.** `docs/CLAUDE_SECTION_1_AUDIT.md`. Evidence: git/source read, grep for fabricated data (none), env presence checks. No code.

**Backend foundation — COMPLETED AND TESTED.** FastAPI app (`app/main.py`) boots; `/api/health` → ok (verified live). Files: pre-existing + Section-2/3 additions.

**Frontend foundation — IMPLEMENTED BUT NOT TESTED.** React/Vite app runs (verified session 1); `npm run typecheck` clean. No automated UI tests.

**Centralized AI planner — PARTIALLY COMPLETED.** Files: `app/agent/planner.py`, `context.py`, `llm.py`. APIs: `/api/operations/plan`, `/api/operations`. Tests: `test_planner.py` (10) + `test_operation_loop.py` (11) with mock LLM. Result: all pass. Limitation: live OpenRouter path unverified (no key); currently returns honest fallback.

**Structured plan schema — COMPLETED AND TESTED.** `app/safety/plan_schema.py`. Tests: `test_plan_schema.py` (12). Pass.

**Deterministic Safety Gateway — COMPLETED AND TESTED.** `app/safety/gateway.py` (+ `dry_run`). Tests: `test_gateway.py` (10), `test_ai_safety_integration.py` (6). Pass.

**Target allowlist — COMPLETED AND TESTED.** `app/safety/policy.py::authorized_targets`. Tested via gateway tests (unauthorized rejected; AI can't widen).

**Execution policy enforcement — COMPLETED AND TESTED.** `policy.clamp_params` (clamp-down). Tested (AI 9999 → cap 4).

**Unified kill switch — COMPLETED AND TESTED.** `app/safety/killswitch.py` + `process.py`. Tests: `test_killswitch.py` (6) incl. real managed-subprocess termination and unrelated-process safety. Pass.

**Execution registry — COMPLETED AND TESTED.** `app/safety/registry.py`. Tested via flow + concurrency (`test_execution_flow.py`, `test_concurrency.py`).

**Hydra integration — PARTIALLY COMPLETED.** `app/integrations/hydra.py` (unchanged) routed via `app/api/integrations.py` → gateway/dispatcher. Tested with mock adapter (`test_execution_flow.py`, `test_operation_loop.py`). **Not run against a target** — live execution unverified.

**Locust integration — PARTIALLY COMPLETED.** `app/integrations/locust.py` routed via gateway/dispatcher; mock-tested. **Not run live.**

**RAT-related capability — NOT STARTED.** Reserved. `rat_related` is rejected at the gateway (`test_ai_safety_integration.py::test_rat_related_plan_is_rejected`, `test_operation_loop.py::test_rat_related_never_runs`).

**Telemetry collection — PARTIALLY COMPLETED.** `app/telemetry/*` (none/local/winrm). `none`/`local` work; **winrm remote collection unverified** (no target). Context manager labels scope honestly.

**Observation engine — PARTIALLY COMPLETED.** `app/agent/analysis.py` (measured facts vs interpretation) + Section-2 before/after telemetry in the simulation orchestrator. Mock-tested; live telemetry-diff on real execution unverified.

**AI feedback loop — COMPLETED AND TESTED.** `app/agent/feedback.py` + loop in `app/agent/operation.py`. Tests: `test_feedback.py` (8) + loop tests. Deterministic guardrails (max-iter, repeated-failure, kill-switch, objective-met) fully tested; AI advisory word mock-tested.

**Audit logging — COMPLETED AND TESTED.** `app/safety/audit.py` + `models.AuditRecord`/`OperationIteration`. Secret-masking tested (`test_execution_flow.py::test_secrets_never_leak...`).

**Dashboard integration — IMPLEMENTED BUT NOT TESTED.** `frontend/src/pages/AIPlanner.tsx` + api/types/route/nav. Typechecks; honest AI/fallback/unavailable states. No automated UI test; live operation UI unverified end-to-end.

**Automated testing — PARTIALLY COMPLETED.** 79 backend tests (pytest). Frontend: typecheck only.

**Kali deployment — PARTIALLY COMPLETED.** Backend venv + uvicorn run verified; native tools present (hydra/nmap/nxc/evil-winrm/impacket); Node installed to `~/.local/node` (not persistent on PATH); no service unit.

**Final end-to-end verification — NOT STARTED.** Requires a real LLM key, an armed module, and an authorized target — none exercised (by section rules).

---

## D. Section-wise Development History (permanent)

### Section 1 — Repository Audit
- **Objective:** evidence-based audit of the existing VAJRAPRAHAAR/CHAKRAVYUH repo.
- **Work:** full backend/frontend read; status classifications; identified two disconnected execution paths, a per-module integer AI recommender, fail-closed Hydra/Locust, simulation-only RAT, kill switch not covering real tools.
- **Files created:** `docs/CLAUDE_SECTION_1_AUDIT.md`. **Modified:** none.
- **Tests executed:** read-only checks (git, grep, env presence). **Issues found:** kill-switch gap; no centralized planner; no safety gateway; no tests. **Decisions:** keep existing work; recommend Section 2 = deterministic spine. **Remaining:** everything in Sections 2–3+.

### Section 2 — Unified Safety Architecture & Execution Control
- **Objective:** deterministic execution-control spine; unify the kill switch; route Hydra/Locust through a Safety Gateway.
- **Work:** plan schema, gateway, policy, registry, managed processes, unified kill switch, audit, dispatcher; routed real integrations; new `/api/execution/*`; 39 tests.
- **Files created:** `app/safety/{__init__,plan_schema,policy,registry,process,killswitch,audit,gateway,dispatcher}.py`, `app/api/execution.py`, `tests/{conftest,test_plan_schema,test_gateway,test_killswitch,test_execution_flow,test_concurrency}.py`, `docs/CLAUDE_SECTION_2_IMPLEMENTATION.md`.
- **Files modified:** `app/config.py`, `app/models.py` (AuditRecord), `app/main.py`, `app/integrations/base.py`, `app/api/integrations.py`, `app/api/routes.py`, `app/agent/orchestrator.py`, `backend/.env.example`.
- **Tests executed:** 39 pytest → pass; runtime smoke (423 on disabled, engage halts, token-gated reset 403). **Issues found/fixed:** variable-name collision in hydra_run; TestClient lifespan event-loop fragility (worked around). **Decisions:** token-gated kill-switch reset (breaking for the frontend rearm button). **Remaining:** centralized AI planner (Section 3).

### Section 3 — Centralized AI Planner & Feedback Loop
- **Objective:** replace the integer recommender with ONE centralized AI planner feeding the Section-2 gateway; add analysis + feedback loop.
- **Work:** context manager, planner, LLM helper, analysis, feedback engine, operation runner; `/api/operations/*`; `operations`/`operation_iterations` tables; gateway `dry_run`; AI Planner dashboard page; 40 new tests.
- **Files created:** `app/agent/{llm,context,planner,analysis,feedback,operation}.py`, `app/api/operations.py`, `tests/{test_planner,test_ai_safety_integration,test_operation_loop,test_feedback,test_operations_api}.py`, `frontend/src/pages/AIPlanner.tsx`, `docs/CLAUDE_SECTION_3_IMPLEMENTATION.md`, `docs/CHAKRAVYUH_MASTER_PROGRESS.md`.
- **Files modified:** `app/config.py` (ai_* settings), `app/models.py` (Operation, OperationIteration), `app/main.py` (operations router), `app/safety/gateway.py` (dry_run), `tests/conftest.py` (ai_* watched), `frontend/src/{api.ts,types.ts,App.tsx,components/Layout.tsx}`.
- **Tests executed:** 79 pytest → pass; runtime smoke of `/api/operations/*`; frontend typecheck clean. **Issues found/fixed:** one test wrongly expected a gateway rejection for the no-runnable-module case (it is an honest "no plan" — corrected). **Decisions:** keep legacy `decision.py` for the simulation path; bind AI target to the authorized allowlist; deterministic guardrails override AI feedback. **Remaining:** live-LLM verification, real-tool verification, Section 4 (RAT-related).

---

## E. Remaining Work

- **Pending tasks:** live-LLM planning verification; real Hydra/Locust execution verification (armed lab); RAT-related capability (Section 4); async operation execution; WebSocket live iteration streaming; frontend rearm token wiring; frontend automated tests; Kali service/persistent Node.
- **Technical blockers:** none blocking development. Live verification is gated on an `OPENROUTER_API_KEY` and an authorized target+armed module (owner-provided).
- **Security issues:** kill-switch reset is token-gated by design; the frontend rearm button needs updating (owner decision). No other open security issue.
- **Unverified integrations:** Hydra, Locust (live), WinRM telemetry, live OpenRouter LLM.
- **Dependencies requiring installation (with approval):** none currently; a real engagement would add nothing new on Kali (tools already present). Node persistence is an environment setup, not a Python dependency.
- **Features requiring owner approval:** kill-switch reset UX change; whether/when to arm a module for a live verification run; Section 4 authorization.

---

## F. Completion-Accuracy Statement

This report avoids invented percentages, does not mark untested integrations as verified (Hydra/Locust/WinRM/live-LLM are explicitly PARTIAL/unverified), never equates simulation with real execution, and treats documentation as documentation — not implementation. Every "COMPLETED AND TESTED" item names the test file(s) that were actually executed and passed. Updated only after implementation and testing.
