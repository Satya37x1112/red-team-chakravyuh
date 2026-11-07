# CHAKRAVYUH — Section 2: Unified Safety Architecture & Execution Control

**Author:** Implementation engineer (Claude Code, on Kali)
**Date:** 2026-11-07
**Status:** Implemented and tested. 39/39 automated tests pass. No real attack tool was executed and no target was contacted.

> Scope honoured: worked only in `/home/kali/AI_red_Team/red-team-chakravyuh/`; no Docker; Kali-native; nothing installed on any Windows target; no new attack capability; no dependency installed (used `pytest`, already present). Existing functionality preserved except the one deliberate, documented security change to kill-switch reset (§13).

---

## 1. New Architecture

Section 1 found two disconnected execution paths and no deterministic control spine. Section 2 builds that spine as a new package, `app/safety/`, and routes the existing real integrations through it. Nothing executes a real adapter except through this pipeline:

```
          proposer of work
   (manual API today · AI planner later)
                  │
                  ▼
        ExecutionPlan  ........................ plan_schema.py  (strict Pydantic, extra=forbid)
                  │   structural + sanity validation
                  ▼
        SafetyGateway.evaluate  ................ gateway.py     (deterministic, AI-independent)
         A kill-switch/operational state
         B module supported + enabled
         C adapter available (honest)
         D target in authorized allowlist
         E concurrency policy (atomic)
         F clamp params DOWN to caps
                  │  approve → create record        reject → 423, NO record, adapter never reached
                  ▼
        ExecutionRegistry  ..................... registry.py    (lifecycle state machine, thread-safe)
          REQUESTED→VALIDATING→APPROVED→RUNNING→OBSERVING→COMPLETED
          (+ REJECTED/CANCEL_REQUESTED/CANCELLED/FAILED/TIMED_OUT)
                  │
                  ▼
        dispatcher.run_execution  .............. dispatcher.py  (the only path to an adapter)
          sets execution context ──► adapter(validated_params)
                  │                        │
                  │                        ▼
                  │                 Integration._run ──► process.run_managed  ... process.py
                  │                   (own process GROUP, tracked by PID+execution_id)
                  ▼
        audit (masked, persisted)  ............. audit.py  →  models.AuditRecord (existing DB)
                  ▲
                  │ consulted by every stage; terminates all of the above
        KillSwitch  ............................ killswitch.py  (unified halt + process-group kill)
          engage: signal active records → killpg(SIGTERM→grace→SIGKILL) → mark CANCELLED
          reset:  requires SAFETY_ADMIN_TOKEN (no unauthenticated reset)

        policy.py = the authoritative caps / allowlist / enabled flags (from config, never from a plan)
```

Key property: **the AI never authorizes anything.** It can only *propose* an `ExecutionPlan`; the Gateway (pure Python, no model) decides, and caps live in `policy.py`/`config.py`, which no plan can touch.

---

## 2. New Files

| File | Responsibility |
|---|---|
| `backend/app/safety/__init__.py` | Package surface (`evaluate`, `kill_switch`, `registry`, schema types). |
| `backend/app/safety/plan_schema.py` | `ExecutionPlan` / `ExecutionParams` / `ModuleId` / `PlanSource`. Strict validation; no self-authorization or cap fields. |
| `backend/app/safety/policy.py` | Authoritative caps, target allowlist, module-enabled, adapter-availability, parameter clamping. |
| `backend/app/safety/registry.py` | `ExecutionRegistry` + `ExecutionRecord` + `ExecState`; validated transitions; concurrency-safe. |
| `backend/app/safety/process.py` | `run_managed` (own process group + tracking), `terminate_execution`, `terminate_all`. |
| `backend/app/safety/killswitch.py` | `KillSwitch` singleton: unified engage/reset, process-group termination, token-gated reset. |
| `backend/app/safety/audit.py` | Secret masking + `audit()` writer to `audit_records`. |
| `backend/app/safety/gateway.py` | `SafetyGateway.evaluate` → `GatewayDecision`; fail-closed. |
| `backend/app/safety/dispatcher.py` | Controlled adapter invocation + per-execution cancellation. Mock-injectable. |
| `backend/app/api/execution.py` | `/api/execution/*` router (submit, status, list, cancel, kill-switch state). |
| `backend/tests/__init__.py`, `conftest.py` | Test package + fixtures (state isolation, armed-module fixtures). |
| `backend/tests/test_plan_schema.py` | 12 schema-validation tests. |
| `backend/tests/test_gateway.py` | 10 Gateway tests. |
| `backend/tests/test_killswitch.py` | 6 kill-switch tests (incl. real managed-subprocess termination). |
| `backend/tests/test_execution_flow.py` | 8 end-to-end flow tests (mock adapters, endpoint routing, secret masking). |
| `backend/tests/test_concurrency.py` | 3 concurrency tests. |
| `docs/CLAUDE_SECTION_2_IMPLEMENTATION.md` | This document. |

---

## 3. Modified Files

| File | Change | Compatibility |
|---|---|---|
| `backend/app/config.py` | Added `safety_target_allowlist`, `safety_max_concurrent_executions`, `killswitch_grace_seconds`, `safety_admin_token`. | Additive; all default to safe values. |
| `backend/app/models.py` | Added `AuditRecord` table. | Additive; `init_db()` creates it. |
| `backend/app/main.py` | Included the new `execution_router`. | Additive. |
| `backend/app/integrations/base.py` | `_run()` now delegates to `process.run_managed` (own process group, trackable). | Drop-in: same `CompletedProcess` return, same `TimeoutExpired`. Hydra/Locust unchanged. |
| `backend/app/api/integrations.py` | `hydra_run` / `locust_run` now go Request → Gateway → Registry → dispatcher → adapter. Added `execution_id`/`execution_state` to responses. | Status codes preserved (423 on block); response is a superset of the old shape. |
| `backend/app/api/routes.py` | `/killswitch` now uses the unified `KillSwitch` (also stops real executions); `/killswitch/reset` now requires an admin token. | **Breaking for reset only** — see §13/§15. |
| `backend/app/agent/orchestrator.py` | `halted` is now a property delegating to the unified kill switch; registers its simulation-session terminator. | `orchestrator.halted` still readable everywhere; one engage halts both paths. |
| `backend/.env.example` | Documented the four new `SAFETY_*` / `KILLSWITCH_*` variables. | Additive. |

No files were deleted. No existing adapter, model, or endpoint was removed or duplicated.

---

## 4. Structured Plan Schema (`plan_schema.py`)

`ExecutionPlan` (Pydantic v2, `extra="forbid"`): `plan_id`, `scenario_id`, `execution_id` (system-assigned; ignored if a proposer sets it), `module` (`bruteforce`|`ddos`|`rat_related`), `source` (`ai`|`manual`|`system`), `requested_target`, `params` (`ExecutionParams`), `requested_duration_seconds`, `created_at`, `reasoning`, `metadata`.

Enforced invariants:
- **No cap/authorization fields exist** — a plan carries only *requested* values, so no caller (AI included) can raise a limit or self-approve. (`test_plan_has_no_self_authorization_fields`.)
- Unknown fields → rejected (`extra="forbid"`). Missing mandatory fields → rejected. Out-of-sanity ranges (e.g. `users>10_000`) → rejected. Secret-looking `metadata` keys → rejected. Whitespace/injection in `requested_target` → rejected.
- Reusable verbatim by the future AI planner (it builds `ExecutionPlan(source=ai, …)`).

---

## 5. Safety Gateway Design (`gateway.py`)

`evaluate(plan) -> GatewayDecision`. Deterministic, no model call. Checks in order; any failure → reject; any internal exception → reject (fail-closed). On approval it creates the `APPROVED` registry record and returns `{approved, reason, policy_id, execution_id, validated_parameters, timestamp, module, target, adapter}`. A rejected plan creates **no** record, so it can never reach an adapter (`test_unauthorized_target_rejected`, `test_submit_rejected_never_runs_adapter`).

`GatewayDecision` is the structured contract the dashboard and audit consume.

---

## 6. Policy Enforcement (`policy.py`)

Pure functions over `settings`:
- `module_enabled` — `HYDRA_ENABLED` / `LOCUST_ENABLED`.
- `integration_available` — asks the real adapter's `status()` honestly.
- `authorized_targets` / `is_target_authorized` — the module's configured target **plus** `SAFETY_TARGET_ALLOWLIST`; nothing else.
- `clamp_params` — returns values clamped **down** to the configured caps; a request can only lower them. This is why **the AI cannot exceed a limit** (`test_ai_cannot_exceed_fixed_limits`: 5000 users → clamped to 50). Defence in depth — the adapters also clamp independently.

Design note (honest): values *within sanity but above a cap* are **clamped down**, not rejected (matches the repo's "requests can lower, never raise" philosophy); values *beyond sanity* are **rejected by the schema**. Both routes guarantee limits can't be exceeded.

---

## 7. Execution Registry (`registry.py`)

In-memory, `threading.RLock`-guarded. `ExecutionRecord` holds ids, module/adapter/target, state, timestamps, PID, cancel flag, exit code, error, gateway decision, and clamped parameters — **never a secret**. `transition()` enforces the allowed state graph and rejects illegal moves (e.g. `CANCELLED → COMPLETED`). `active_count()` backs the concurrency policy.

Lifecycle: `REQUESTED → VALIDATING → APPROVED → RUNNING → OBSERVING → COMPLETED`, with `REJECTED / CANCEL_REQUESTED / CANCELLED / FAILED / TIMED_OUT` as off-path/terminal states.

---

## 8. Kill-Switch Design (`killswitch.py` + `process.py`)

The Section-1 gap was that the kill switch only flipped a flag and stopped simulations — real Hydra/Locust subprocesses kept running. Now:

1. Every adapter subprocess is launched by `process.run_managed` in its **own process group** (`start_new_session=True`) and registered by PID + execution id.
2. `KillSwitch.engage()` marks the range halted, requests cancel on all active records, then `killpg(SIGTERM)` → grace period → `killpg(SIGKILL)` on every tracked group, records each outcome, and marks executions `CANCELLED` (or `FAILED` if a process could not be confirmed dead).
3. It is **idempotent** (repeat engage is safe), **confirms** termination before claiming it, and **never touches a process the app didn't launch** (`test_unrelated_process_not_terminated`).
4. `reset(token)` requires `SAFETY_ADMIN_TOKEN`; with none configured, reset is refused — there is no unauthenticated reset.

The orchestrator's simulation-session terminator is registered with the switch, so **one engage halts both the real and the simulation paths**. `orchestrator.halted` now reads the unified state.

Verified live: a managed `sleep` subprocess is killed by the switch, its PID confirmed dead, and the record moved to `CANCELLED` (`test_active_execution_cancelled_and_process_terminated`).

---

## 9. Hydra & Locust Integration Changes

- The adapters themselves were **not rewritten**; they keep their own independent fail-closed caps and secret masking.
- `POST /api/integrations/hydra/run` and `/locust/run` now build an `ExecutionPlan`, call `evaluate`, and — only if approved — run through `dispatcher.run_execution`. A rejection returns **423** and never invokes the adapter.
- Because adapter subprocesses now run via `run_managed`, the kill switch can terminate an in-flight Hydra/Locust run.
- Responses are a **superset** of the old shape (same keys + `execution_id`, `execution_state`), so existing dashboard code keeps working.
- There is no remaining code path that calls the adapters directly from the API (verified: the old direct `HydraIntegration()/LocustIntegration()` calls were removed from the router).

---

## 10. API Changes

New `/api/execution` router:
- `POST /api/execution/submit` — submit an `ExecutionPlan`; 423 on Gateway rejection, 502 on adapter failure, else the masked outcome.
- `GET /api/execution` (`?active_only=`) — list executions.
- `GET /api/execution/{id}` — one execution's status.
- `POST /api/execution/{id}/cancel` — request cancellation + terminate its managed processes.
- `GET /api/execution/killswitch` — kill-switch state + tracked processes.

Changed in `/api`:
- `POST /api/killswitch` — unified engage (now also stops real executions); returns the full kill report.
- `POST /api/killswitch/reset` — now requires `{"admin_token": "..."}` and returns 403 without it.

All responses are secret-masked. No endpoint invokes an adapter outside the controlled path.

---

## 11. Audit Logging (`audit.py` + `models.AuditRecord`)

Every milestone is persisted to `audit_records` (reusing the existing DB): `EXECUTION_REQUESTED`, `GATEWAY_APPROVED/REJECTED`, `EXECUTION_STARTED/COMPLETED/FAILED/TIMED_OUT`, `KILLSWITCH_ENGAGED/RESET`, `CANCEL_REQUESTED/CONFIRMED/FAILED`. Each record carries `execution_id`, `scenario_id`, `module`, `target`, `decision`, `reason`, `policy_id`, and a **secret-masked** `payload`. `mask_secrets()` redacts password/API-key/token/credential-list keys recursively; verified a planted secret reaches neither the API response nor the audit log (`test_secrets_never_leak_to_result_or_audit`).

---

## 12. Test Results (actually executed)

Command:
```
cd backend && source .venv/bin/activate && python -m pytest tests/ -p no:cacheprovider -q
```
Result: **39 passed, 1 warning in ~2.7s** (the warning is an upstream Starlette deprecation, not ours).

| File | Tests | Covers |
|---|---|---|
| `test_plan_schema.py` | 12 | valid plan; invalid/missing/malformed/out-of-range/unexpected fields; no self-authorization; secret metadata; target injection. |
| `test_gateway.py` | 10 | authorized vs unauthorized target; disabled/unsupported/unavailable module; AI cannot exceed caps; schema rejects absurd values; fail-closed on internal error; kill-switch blocks; concurrency limit. |
| `test_killswitch.py` | 6 | new execs rejected after engage; **real managed subprocess terminated + record CANCELLED**; repeated engage safe; reset requires auth; cancellation-failure recorded; **unrelated process untouched**. |
| `test_execution_flow.py` | 8 | approved reaches correct mock adapter with clamped params; adapter error recorded; **secrets never leak**; Hydra & Locust endpoints go through the Gateway; disabled → 423; rejected submit never runs an adapter; status/listing. |
| `test_concurrency.py` | 3 | concurrency cap not bypassed under a 12-thread race; engage + concurrent requests never raise and all later requests rejected; registry consistent under parallel transitions. |

Runtime smoke test (app booted on :8078, read-only, no attack): `/api/health` ok; `/api/execution` `[]`; submit/hydra-run with modules disabled → **423**; integrations list intact; engage → `halted:true`; reset without a configured token → **403**.

---

## 13. Remaining Limitations (honest)

1. **Kill-switch reset is now a breaking change for the current frontend.** `frontend/src/api.ts::rearm()` posts to `/api/killswitch/reset` with no body; it will now get 422/403 until (a) the operator sets `SAFETY_ADMIN_TOKEN` and (b) the UI sends it. **This needs your decision** (see §15). Engage is unchanged and still works.
2. **Execution is synchronous** (blocks the request thread), exactly as the old endpoints were. A long real run holds the HTTP connection; an async job/queue model is future work.
3. **Registry is in-memory.** Execution records don't survive a backend restart (the audit trail in the DB does). Fine for the lab; a persistent registry is future work.
4. **Locust overrun edge case:** the Locust adapter doesn't catch its own `TimeoutExpired`, so an overrun past its own `-t + 30s` maps to `TIMED_OUT` with an empty result. Harmless; documented.
5. **POSIX-only process groups** (correct for Kali). The Windows fallback terminates the single process, not a tree — not needed here since all tooling runs on Kali.
6. **No audit retention/rotation** yet.
7. **The two execution paths are not merged.** Section 2 unified the *kill switch* and built the control spine, but `/api/attacks/start` (simulation) and the real path still coexist; wiring the AI planner to drive the real path through this spine is Section 3+.
8. **The AI planner is not implemented** (correctly out of scope). The Gateway currently serves manual plans; the schema is ready for AI plans.

---

## 14. Instructions for Future AI Planner Integration (Section 3 hand-off)

The spine is intentionally planner-agnostic. To wire the centralized AI planner:

1. Have the planner emit `ExecutionPlan` objects with `source=PlanSource.ai`, `scenario_id`, `module`, `requested_target`, and requested `params`/`reasoning`. **It must not set caps or `execution_id`** (the schema has no cap fields; the Gateway assigns the id).
2. Pass each plan to `app.safety.evaluate(plan)`. If `decision.approved`, call `app.safety.dispatcher.run_execution(decision.execution_id)`; otherwise surface `decision.reason` (the AI does not retry by widening scope — caps are not negotiable).
3. For the feedback loop, read the terminal `ExecutionRecord` (via `registry.get`) and the masked result, feed them back to the planner, and let it emit the next `ExecutionPlan`. The Gateway re-authorizes every step.
4. The planner must remain **outside** `app/safety/`: safety policy stays deterministic and independent of the model. Never let the planner import or mutate `policy.py`/`config.py` caps.
5. Target authorization for AI-proposed targets flows through `SAFETY_TARGET_ALLOWLIST` / the configured module target — the AI cannot introduce a new target that isn't already authorized.

---

## 15. Requires Your Approval / Decision

- **Kill-switch reset auth (breaking):** confirm you want token-gated reset (recommended, and required by the Section-2 brief: "no unauthenticated public reset"). If yes, I will (in a later section, with your go-ahead) update the frontend rearm button to send the token. Interim: set `SAFETY_ADMIN_TOKEN` in `.env` and reset via `curl -X POST /api/killswitch/reset -d '{"admin_token":"..."}'`.
- **Nothing else requires approval.** No dependencies were installed; `pytest` was already present.

---

### Section-2 completion checklist (self-audit)
- [x] Structured execution-plan schema — `plan_schema.py`
- [x] Strict plan validation — 12 passing tests
- [x] Deterministic Safety Gateway — `gateway.py`, fail-closed
- [x] Target authorization / allowlist — `policy.py`
- [x] Policy & execution-limit enforcement (clamp-down) — `policy.py`
- [x] Unified kill switch over real + simulation work — `killswitch.py` + `process.py`
- [x] Execution lifecycle registry — `registry.py`
- [x] Hydra & Locust routed through the Gateway — `api/integrations.py`
- [x] Audit logging with secret masking — `audit.py` + `models.AuditRecord`
- [x] Automated tests for critical security behaviour — 39 passing
- [x] Existing functionality preserved (except documented reset change)
- [x] Documentation (this file)

**Stopping here. Section 3 (centralized AI planner) NOT started. Awaiting your review and explicit instruction.**
