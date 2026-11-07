# CHAKRAVYUH — Stage 5.1: Final Architecture Integration Audit

**Author:** Implementation engineer (Claude Code, on Kali) — acting as auditor
**Date:** 2026-11-07
**Nature:** READ-ONLY audit of completed Sections 1–4. No source modified, no commits, no target contact, no attack tool executed, running dev servers preserved.

Status vocabulary (per component): `VERIFIED BY CODE + TESTS` · `VERIFIED BY CODE ONLY` · `PARTIALLY VERIFIED` · `NOT VERIFIED` · `FAILED` · `BLOCKED`.

---

## 1. Executive Summary

The CHAKRAVYUH pipeline is **genuinely integrated**, not a set of isolated tool wrappers. One centralized AI planner feeds a deterministic Safety Gateway that authorizes every execution; all three modules (Hydra, Locust, NetExec remote-access) share the same schema, gateway, registry, dispatcher, kill switch and audit. **No Gateway bypass route was found** — every path that reaches an adapter calls `evaluate()` first, and `dispatcher.run_execution` refuses any record that is not `APPROVED`. The kill switch covers all three managed integrations (they all run through the managed, process-grouped subprocess runner). The AI layer cannot invoke tools, shells, or the dispatcher directly, and cannot alter caps or allowlists.

**Backend: 125 passed, 1 warning.** Frontend: typecheck clean, production build succeeds (71 modules).

Everything is **MOCK/CODE-verified**. No live attack, authentication, or remote command has ever been run against a real target, and the live LLM path runs only on the free fallback model (paid model out of credits). Those remain the project's unverified frontier.

> Note: the working tree also contains **uncommitted Stage-5 work** (blackbox/IP-only telemetry + a Target Recon page, 7 passing tests). It is outside the Sections 1–4 audit scope and is called out in §10/§11, not assessed as part of 1–4.

---

## 2. Verified Architecture Diagram (as traced in code)

```
User objective
  │  frontend: pages/AIPlanner.tsx, RemoteAccess.tsx, Integrations.tsx → src/api.ts (relative /api)
  ▼
FastAPI routes ........ api/operations.py, api/execution.py, api/integrations.py, api/routes.py (main.py mounts all)
  ▼
Context Manager ....... agent/context.py::build_context  (telemetry scope-labelled; modules advertise caps+ops)
  ▼
Centralized AI Planner  agent/planner.py::generate_plan  (ONE planner; llm via agent/llm.py; honest fallback/unavailable)
  ▼
ExecutionPlan ......... safety/plan_schema.py  (Pydantic, extra=forbid; operation = safe token only)
  ▼
Safety Gateway ........ safety/gateway.py::evaluate  (A kill-switch · B module enabled · C adapter available ·
  │                      D target allowlist · D2 operation allowlist · E concurrency · F clamp-to-caps; fail-closed)
  ├── rejected → audit (safety/audit.py), no registry record, 423  ─────────────► adapter NEVER reached
  ▼ approved
Execution Registry .... safety/registry.py  (REQUESTED→VALIDATING→APPROVED→RUNNING→…→COMPLETED/FAILED/…)
  ▼
Dispatcher ............ safety/dispatcher.py::run_execution (requires APPROVED; sets exec context)
  ▼
Integration Adapter ... integrations/{hydra,locust,remote_access}.py  (own hard caps; self._run → managed process group)
  ▼
Observation / Analysis  agent/analysis.py  (measured FACTS vs AI interpretation; evidence-based objective_met)
  ▼
AI Feedback ........... agent/feedback.py  (CONTINUE/MODIFY/STOP; deterministic guardrails always win)
  ▼
Audit / DB ............ models.py (AuditRecord, Operation, OperationIteration, …) — secret-masked
  ▼
Dashboard ............. live WS (ws.py) + REST polling
         ▲
Unified Kill Switch ... safety/killswitch.py — consulted by the Gateway; terminates managed process groups of ALL adapters
```

---

## 3. Module-by-Module Assessment

### Module 1 — Hydra (authentication testing) — **VERIFIED BY CODE + TESTS**
- Adapter `integrations/hydra.py`: fail-closed `status()`/`preconditions()`; one list-pair against one configured target/service; caps on tasks/attempts/run-time; `-f` stop-on-first; **cracked password never returned** (masked to dots). Runs via `self._run` (managed process group) → kill-switch reachable.
- Gateway-routed at `api/integrations.py::hydra_run` (evaluate → 423 on reject → dispatcher). Target bound to allowlist; AI/API can only lower caps.
- Credentials: wordlists are operator files; no secret on argv (`-L`/`-P` are file paths).
- Tests: `test_execution_flow.py`, `test_operation_loop.py`, `test_gateway.py`.

### Module 2 — Locust (bounded service-load testing) — **VERIFIED BY CODE + TESTS**
- Adapter `integrations/locust.py`: fail-closed; drives an operator locustfile against one authorized target URL; **hard caps on users / spawn-rate / duration**, clamp-down only; headless; managed process group. This is **bounded lab load testing**, not unrestricted flooding — it cannot target an arbitrary host (target comes from config/allowlist, never the request/AI).
- Gateway-routed at `api/integrations.py::locust_run`.
- Tests: `test_execution_flow.py`, `test_operation_loop.py`.

### Module 3 — Remote Access (NetExec, RAT alternative) — **VERIFIED BY CODE + TESTS**
- Adapter `integrations/remote_access.py`: **five fixed operation identifiers** (`connectivity_check`, `whoami`, `hostname`, `os_info`, `system_info`), each mapping to ONE fixed argv (a read-only NetExec auth+banner query) — **no `-x`, no shell, no arbitrary command, no implant/persistence**.
- **Credential file:** password written via `tempfile.mkstemp` (**0600**), preferring **`/dev/shm`**, passed as `-p <file>` (no argv exposure — verified vs NetExec 1.5.1 `connection.py:416`); **cleanup on every path** (`finally` + `_safe_unlink`); **fail-closed** on file-creation error; **exception text credential-redacted**; output redaction for NetExec's echoed password.
- Gateway **D2 operation-allowlist** check rejects unknown ops; 30-second cap enforced in **both** policy (gateway clamp) and the adapter.
- Confirmed: no arbitrary shell, no covert implant, no persistence.
- Tests: `test_remote_access.py` (37, incl. 8 credential-security tests).

---

## 4. Centralized AI Integration Assessment — **VERIFIED BY CODE + TESTS**

- **One planner:** a single `generate_plan` (`agent/planner.py:162`), used by `api/operations.py` and `agent/operation.py`. No per-module AI agents. (The legacy per-module integer `decision.py` remains only for the *simulation* path and is not in the real pipeline.)
- **Shared context:** all three modules advertise `enabled`/`adapter_available`/`authorized_targets`/`approved_operations`/`caps` to the same `build_context` (`agent/context.py`).
- **AI cannot act:** `planner/context/analysis/feedback` import no `subprocess`, dispatcher, or adapter (grep-verified). AI selects a module + bounded params + (for remote access) an operation **identifier**, never a command; the **target is bound to the allowlist**, never chosen by the AI.
- **Validation + gateway:** every plan (AI or fallback) is a Pydantic `ExecutionPlan` and passes `evaluate()`; the AI cannot change caps, allowlists, policy, or kill-switch state.
- **Honest degradation:** no key / malformed / timeout → clearly-labelled `fallback` (source=system) or `unavailable`, never mislabelled as AI (`test_planner.py`).
- **Feedback:** CONTINUE/MODIFY/STOP with deterministic guardrails (max-iter, repeated-failure, kill-switch, objective-met) that override the AI (`test_feedback.py`).
- **Facts vs interpretation:** `agent/analysis.py` separates measured facts (from the real result) from AI interpretation; `objective_met` is evidence-based.

---

## 5. Safety Gateway Assessment — **VERIFIED BY CODE + TESTS**

`safety/gateway.py::evaluate` runs, in order and fail-closed: kill-switch → module supported+enabled → adapter available → target allowlist → **operation allowlist (D2)** → concurrency (atomic lock) → clamp-to-caps. A rejected plan creates **no registry record**. **No bypass found:** the four dispatch sites (`execution.py:31`, `integrations.py:228/274/321`) are each immediately preceded by `evaluate()` + a reject→423 guard, and `run_execution` refuses any non-`APPROVED` record (`dispatcher.py:64`). Concurrency enforced under a race (`test_concurrency.py`). Secrets masked in audit (`safety/audit.py`).

---

## 6. Kill-Switch Assessment — **VERIFIED BY CODE + TESTS**

`safety/killswitch.py` is the single authority; the Gateway consults it (new work rejected while engaged). All **three** adapters shell out through `base._run → safety/process.run_managed`, which launches each child in its **own process group**, so `engage()` terminates in-flight Hydra/Locust/NetExec runs (SIGTERM→grace→SIGKILL), records outcomes, marks executions CANCELLED, and never touches unrelated processes (`test_killswitch.py`, incl. a real managed-subprocess kill + unrelated-process-safety test). Reset is token-gated (`SAFETY_ADMIN_TOKEN`). **Documented limit:** a remote command already accepted by the target can't be guaranteed-cancelled — mitigated by short, read-only, bounded remote ops.

---

## 7. Frontend Assessment — **VERIFIED BY CODE ONLY** (typecheck + build; not click-tested)

- `src/api.ts` uses relative `/api/*` (Vite proxy → real backend). Pages: `Dashboard`, `AIPlanner` (AI vs fallback vs unavailable, gateway decision, facts vs interpretation), `RemoteAccess` (approved ops, no command input, no shell, kill-switch aware), `Integrations` (Hydra/Locust/vervet/caldera panels), `OperationsCenter`, `History`, `Reports`, `Report`, plus the simulation `Operation` pages.
- **Honest finding:** there is **no dedicated "Hydra page" / "Locust page"** — Hydra and Locust are surfaced through the **Integrations** panels and the **AI Planner** operations flow, while **Remote Access has its own page**. This is a UI-consistency gap, not a safety gap.
- **Known issue (carried from Section 2):** `api.rearm()` still POSTs `/api/killswitch/reset` without the admin token, so the rearm button returns 403/422 until wired (degrades gracefully with an error toast). **PARTIALLY VERIFIED.**
- Checks: `npm run typecheck` clean; `npm run build` ✓ (71 modules; only a pre-existing chunk-size advisory).

---

## 8. Automated Test Results

```
cd backend && source .venv/bin/activate && python -m pytest tests/ -q
→ 125 passed, 1 warning in ~16s
```
| File | Tests |
|---|---|
| test_plan_schema.py | 12 |
| test_gateway.py | 10 |
| test_killswitch.py | 6 |
| test_execution_flow.py | 8 |
| test_concurrency.py | 3 |
| test_planner.py | 10 |
| test_ai_safety_integration.py | 6 |
| test_operation_loop.py | 11 |
| test_feedback.py | 8 |
| test_operations_api.py | 5 |
| test_live_llm.py | 2 |
| test_remote_access.py | 37 |
| test_blackbox_telemetry.py | 7 (uncommitted Stage-5 work) |

- **Failed:** 0. **Skipped:** 0. **Warnings:** 1 (upstream Starlette `BlockingPortal` deprecation — not ours).
- **Network access:** `test_live_llm.py::test_live_structured_plan_validates_and_is_bound` makes a **real OpenRouter call** (keys present) — AI-planning only, no target. `test_blackbox_telemetry.py` opens **loopback (127.0.0.1)** sockets only — no external/target network. All other tests are fully offline/mocked.
- Frontend: `npm run typecheck` clean; `npm run build` success.

---

## 9. Security Findings

| Sev | Finding | Status |
|---|---|---|
| CRITICAL | — none | — |
| HIGH | — none | — |
| MEDIUM | — none open. (The Section-4 argv credential exposure was **remediated**: 0600 `/dev/shm` credential file, no argv secret; verified by tests.) | Resolved |
| LOW | Credential file exists briefly on the Kali box during a remote op (0600, RAM-backed, deleted immediately) — readable only by root, which can read process memory anyway. Not a new exposure. | Accepted |
| LOW | Frontend rearm button not wired to the token-gated reset (403/422; graceful). | Open (owner decision) |
| INFORMATIONAL | `.env` is **gitignored and untracked**; no real OpenRouter key or password is tracked anywhere in the repo (grep-verified). `.env.example` holds placeholders only. | Good |
| INFORMATIONAL | No inline password on any adapter argv (Hydra `-P` file, NetExec `-p` 0600 file); no `-x`/arbitrary command; `shell=False` everywhere. | Good |
| INFORMATIONAL | Execution caps enforced server-side in policy **and** independently in each adapter; AI/API can only lower them. | Good |

No hardcoded secrets, no tracked `.env`, no unsafe command construction, no target-authorization bypass, no missing caps, no kill-switch gap found.

---

## 10. Integration Gaps

1. **Frontend UI consistency:** no dedicated Hydra/Locust pages (surfaced via Integrations + AI Planner). Non-safety.
2. **Rearm token wiring:** frontend rearm needs the admin token (owner decision pending).
3. **Simulation vs real paths coexist:** the legacy `/api/attacks/start` simulation path and `decision.py` remain alongside the real pipeline (intended; documented).
4. **Uncommitted Stage-5 work in tree:** blackbox/IP-only telemetry (`collector.py` `BlackboxSource`, `schema.py` `NetworkProbe`, `TargetRecon.tsx`) with 7 passing tests — complete and tested but **not committed** and **outside Sections 1–4**.

---

## 11. Live-Unverified Components

| Component | Status |
|---|---|
| Real Hydra auth against a target | **NOT VERIFIED** (mock only) |
| Real Locust load against a target | **NOT VERIFIED** (mock only) |
| Real NetExec auth/banner against a Windows target | **NOT VERIFIED** (mock only) |
| Real WinRM telemetry | **NOT VERIFIED** |
| Paid-model live AI planning | **BLOCKED** (OpenRouter credits exhausted; free fallback works) |
| Frontend live interaction (click-through) | **PARTIALLY VERIFIED** (typecheck + build only) |
| Blackbox telemetry vs a real target | **NOT VERIFIED** (loopback-tested only; uncommitted) |

---

## 12. Recommended Next Steps

1. **Decide on the rearm token UX** (wire `SAFETY_ADMIN_TOKEN` into the frontend, or confirm CLI-only reset).
2. **Credited OpenRouter keys** for paid-model live AI verification (reminder standing).
3. A **supervised live verification pass** on the authorized lab target (one module armed, one bounded run each) — the only way to move the three modules from NOT VERIFIED to live-verified.
4. Decide whether to **commit the Stage-5 blackbox telemetry** work (currently uncommitted).
5. (Optional) add dedicated Hydra/Locust UI pages for consistency with Remote Access.

---

### Auditor's direct answers
- **Do all three modules genuinely share the centralized architecture?** **Yes** — one context manager, one planner, one schema, one gateway, one registry, one dispatcher, one kill switch, one audit.
- **Any Gateway bypass?** **No** — every dispatch route calls `evaluate()` first and `run_execution` requires `APPROVED`.
- **Kill switch covers all managed integrations?** **Yes** — all three adapters run through the managed process-group runner.
- **Is the AI planner genuinely centralized?** **Yes** — a single `generate_plan`, tool-isolated.
- **Blockers before Stage 5.2:** none technical; live verification needs an authorized target + go-ahead, and paid-model AI needs credited keys.

See `docs/CHAKRAVYUH_MASTER_PROGRESS.md` for the cumulative record (Stage 5.1 entry added).
