# CHAKRAVYUH — Final Feature & Verification Matrix

**Date:** 2026-11-07 · Source of truth: actual code + the existing stage reports.
Classifications: `IMPLEMENTED AND MOCK VERIFIED` · `IMPLEMENTED BUT LIVE UNVERIFIED` · `PARTIALLY IMPLEMENTED` · `BLOCKED` · `NOT IMPLEMENTED`.
Honesty rule: a mock-verified feature is **not** live-verified. No percentages invented.

Test baseline (offline/mock): **140 passed, 1 deselected (live OpenRouter), 1 warning**; full collection = **141 tests**. Frontend: `npm run typecheck` ✓, `npm run build` ✓.

---

| Feature | Status | Files | API | Tests / Evidence | Mock-verified | Live-verified | Limitations |
|---|---|---|---|---|---|---|---|
| **Centralized AI Planner** | IMPLEMENTED AND MOCK VERIFIED | `agent/planner.py`, `agent/context.py`, `agent/llm.py` | `POST /api/operations`, `/api/operations/plan` | `test_planner.py` (10), `test_operation_loop.py` (11) | ✅ (mock LLM) | ❌ (paid model BLOCKED; free model works) | Single-step-per-iteration; synchronous |
| **AI honest fallback/unavailable** | IMPLEMENTED AND MOCK VERIFIED | `agent/planner.py`, `agent/llm.py`, `integrations/_llm.py` | — | `test_planner.py::test_llm_unavailable_labeled_fallback`, `test_live_llm.py` (offline) | ✅ | n/a | — |
| **Module 1 — Hydra** | IMPLEMENTED BUT LIVE UNVERIFIED | `integrations/hydra.py` | `POST /api/integrations/hydra/run` | `test_execution_flow.py`, `test_operation_loop.py` | ✅ (mock adapter) | ❌ (no target run) | Disabled by default; needs wordlists+target |
| **Module 2 — Locust** | IMPLEMENTED BUT LIVE UNVERIFIED | `integrations/locust.py` | `POST /api/integrations/locust/run` | `test_execution_flow.py::test_locust_endpoint_uses_gateway`, `test_operation_loop.py::test_approved_locust_reaches_mock_adapter` | ✅ | ❌ | Disabled by default; bounded (caps), not flooding |
| **Module 3 — Remote Access (RAT alt)** | IMPLEMENTED BUT LIVE UNVERIFIED | `integrations/remote_access.py` | `POST /api/integrations/remote_access/run` | `test_remote_access.py` (37) | ✅ (mock subprocess) | ❌ (no NetExec run) | 5 read-only ops only; not a conventional RAT; disabled by default |
| **Structured ExecutionPlan schema** | IMPLEMENTED AND MOCK VERIFIED | `safety/plan_schema.py` | — | `test_plan_schema.py` (12) | ✅ | n/a | — |
| **Safety Gateway** | IMPLEMENTED AND MOCK VERIFIED | `safety/gateway.py`, `safety/policy.py` | gates all run routes | `test_gateway.py` (10), `test_ai_safety_integration.py` (6) | ✅ | n/a | — |
| **Target allowlists** | IMPLEMENTED AND MOCK VERIFIED | `safety/policy.py` (+ `collector.py` for blackbox) | — | `test_gateway.py`, `test_ai_safety_integration.py`, `test_blackbox_telemetry.py` | ✅ | ❌ (no real target) | Attack allowlist (`SAFETY_TARGET_ALLOWLIST`) + separate `BLACKBOX_ALLOWLIST` |
| **Operation allowlist (D2)** | IMPLEMENTED AND MOCK VERIFIED | `safety/gateway.py`, `safety/policy.py`, `integrations/remote_access.py` | — | `test_remote_access.py::test_unknown_operation_rejected_by_gateway` | ✅ | n/a | — |
| **Execution Registry** | IMPLEMENTED AND MOCK VERIFIED | `safety/registry.py` | `GET /api/execution[/{id}]` | `test_execution_flow.py`, `test_concurrency.py` | ✅ | n/a | In-memory (resets on restart) |
| **Unified Kill Switch** | IMPLEMENTED AND MOCK VERIFIED | `safety/killswitch.py`, `safety/process.py` | `POST /api/killswitch[/reset]` | `test_killswitch.py` (6) | ✅ (real managed subprocess killed) | ❌ (not vs a live attack) | No guaranteed remote-command cancellation (documented) |
| **Audit logging** | IMPLEMENTED AND MOCK VERIFIED | `safety/audit.py`, `models.py` | — | `test_execution_flow.py::test_secrets_never_leak`, `test_remote_access.py::test_audit_has_no_secret` | ✅ | n/a | SQLite; no rotation |
| **Telemetry — none/local** | IMPLEMENTED AND MOCK VERIFIED | `telemetry/collector.py` | `GET /api/telemetry/latest` | smoke + schema | ✅ | local=Kali host only | `local` must never be labelled target telemetry |
| **Telemetry — WinRM** | IMPLEMENTED BUT LIVE UNVERIFIED | `telemetry/collector.py::WinRMSource` | `GET /api/telemetry/latest` | code only | ❌ | ❌ (no target) | Needs an already-enabled WinRM + creds |
| **Telemetry — Blackbox** | IMPLEMENTED AND MOCK VERIFIED | `telemetry/collector.py::BlackboxSource` | `GET /api/telemetry/latest` | `test_blackbox_telemetry.py` (23, mocked sockets) | ✅ | ❌ (no real probe) | IPv4+RFC1918+allowlist; time-budget; disabled by default |
| **Feedback loop (CONTINUE/MODIFY/STOP)** | IMPLEMENTED AND MOCK VERIFIED | `agent/feedback.py`, `agent/operation.py` | via `/api/operations` | `test_feedback.py` (8), `test_operation_loop.py` | ✅ | n/a | AI advisory; deterministic guardrails final |
| **Dashboard (frontend)** | PARTIALLY IMPLEMENTED (VERIFIED BY CODE) | `frontend/src/pages/*`, `src/api.ts` | relative `/api` | typecheck + build; no click-through | code-only | ❌ | No dedicated Hydra/Locust pages; rearm token wiring pending |
| **Database** | IMPLEMENTED AND MOCK VERIFIED | `db.py`, `models.py` | — | auto-init on startup; persistence tests | ✅ | n/a | SQLite; no Alembic; DB-outage recovery untested |
| **Deployment (Kali-native)** | PARTIALLY IMPLEMENTED | `RUN_SERVERS.md`, `KALI.md` | — | Stage 5.3 readiness | ✅ (manual start) | n/a | No start script; Node PATH not persistent; no dup-guard |
| **Testing** | IMPLEMENTED AND MOCK VERIFIED | `backend/tests/*` | — | 141 tests (140 offline + 1 live deselected) | ✅ | n/a | 1 network-dependent (live OpenRouter) |
| **Legacy simulation path** | IMPLEMENTED (retained) | `agent/decision.py`, `modules/*`, `api/routes.py` | `POST /api/attacks/start` | pre-existing | n/a | n/a | Separate from the real pipeline; kept for continuity |

---

## Not implemented (by design)
- A **conventional covert RAT** (implant/persistence/stealth/cred-dumping) — deliberately **NOT IMPLEMENTED**; Module 3 is credentialed remote administration with a fixed read-only operation allowlist.
- Live attack execution, real target contact, paid-model AI runs — not performed in any stage (constraints).

## Blocked
- **Paid-model AI planning** (`anthropic/claude-sonnet-4.5`) — BLOCKED on OpenRouter credits; the free fallback model works.
