# CHAKRAVYUH — Section 3: Centralized AI Planner & Intelligent Feedback Loop

**Author:** Implementation engineer (Claude Code, on Kali)
**Date:** 2026-11-07
**Status:** Implemented and tested. 79/79 automated tests pass (40 new this section). No real attack tool was executed, no target was contacted, no dependency was installed, nothing was pushed.

> Scope honoured: worked only in `/home/kali/AI_red_Team/red-team-chakravyuh/`; no Docker; Kali-native; nothing on the Windows target; no real attack; mock LLM + mock adapters in every test; the RAT-related module remains explicitly unavailable; existing working code preserved.

---

## 1. Centralized AI Architecture

Section 3 turns the Section-2 safety spine into a closed AI loop. ONE planner reasons over the whole scenario and proposes bounded work; deterministic components (gateway, policy, kill switch) retain all authority.

```
USER OBJECTIVE
     │
     ▼
Scenario Context Manager ........ agent/context.py   (telemetry labelled by scope; modules/targets/history)
     │
     ▼
Centralized AI Planner .......... agent/planner.py   (ONE brain → structured ExecutionPlan, source=ai)
     │   (LLM via agent/llm.py → OpenRouter; honest fallback=system; unavailable=no plan)
     ▼
ExecutionPlan (Pydantic) ........ safety/plan_schema.py   (Section 2 — reused, not duplicated)
     │
     ▼
Deterministic Safety Gateway .... safety/gateway.py   (authorizes; AI can't; fail-closed)
     │
  ┌──┴───────────────┐
REJECTED           APPROVED
  │                   │
  ▼                   ▼
audit/iteration   Execution Dispatcher ... safety/dispatcher.py → Hydra / Locust (mock in tests)
                      │
                      ▼
                Execution result (registry record, masked)
                      │
                      ▼
          Post-execution Analysis ......... agent/analysis.py   (measured FACTS vs interpretation)
                      │
                      ▼
               Feedback Engine ............ agent/feedback.py   (CONTINUE / MODIFY / STOP)
                      │        (deterministic guardrails win: max-iter, repeated-failure, kill-switch, met)
                      ▼
               Next bounded iteration (re-enters the planner; re-authorized by the Gateway)
```

Orchestrated by `agent/operation.py` (`run_operation`), persisted to `operations` + `operation_iterations`, exposed at `/api/operations/*`.

Invariant: **the AI proposes; deterministic Python authorizes.** The planner never picks a target, never sets a cap, never approves a plan, and never forces continuation.

---

## 2. The integer-based mechanism — replaced vs migrated

- **Before:** `agent/decision.py::decide(kind, telemetry)` returned ONE bounded integer per module, wired only into the simulation path (`modules/base.py::plan`).
- **Now:** the centralized planner (`agent/planner.py`) is the authoritative AI for the real controlled pipeline. It emits a complete `ExecutionPlan` (module + bounded params + reasoning + provenance), not a lone integer, and feeds the Section-2 Gateway.
- **Migration decision (honest):** `decision.py` is **retained, unchanged, as legacy** for the existing simulation modules so prior work keeps running. It is no longer the brain of the real path. Both share the same OpenRouter plumbing and the same honest-degradation discipline, so there is no duplicated LLM client. The legacy `/api/decision/{kind}` endpoint and simulation `/api/attacks/start` are untouched.

---

## 3. Context Manager (`agent/context.py`)

`build_context(objective, scenario_id, module_hint, history)` → `ScenarioContext` with: objective, scenario id, per-module capability/enabled/adapter-availability/authorized-targets/caps, telemetry, prior-iteration history, and safety state. Honesty rules enforced:
- Telemetry is labelled by **scope**: `windows_target` (remote WinRM), `kali_host` (local psutil — the attacker box, never the target), or `unavailable`. Missing telemetry is reported unavailable, never as zero metrics (`_telemetry_view`).
- `authorized_target_for(module)` binds the plan's target to the configured allowlist — the AI cannot choose a target.
- `runnable_modules()` = enabled + adapter-available + has-authorized-target.
- Safety state (caps, allowlist, kill switch) is read-only to the AI.

---

## 4. Structured Plan Generation (`agent/planner.py`)

`generate_plan(context, llm)` → `PlanningResult{status, plan, reasoning, model, prompt_version, ai_raw, errors}`:
- No runnable module → `status="unavailable"`, `plan=None` (honest; the AI has nothing safe to plan).
- LLM proposes `{module, params, reasoning, expected_observations, confidence}` as strict JSON. The planner: validates the module is runnable; **binds the target from the authorized scope (never the AI)**; clamps params to schema bounds; builds an `ExecutionPlan(source=ai)`.
- Any failure (no key, timeout, malformed JSON, invalid module, schema reject) → a clearly-labelled **deterministic fallback** plan (`source=system`), never mislabelled as AI. If the fallback can't build a valid plan → `unavailable`.

---

## 5. LLM Integration (`agent/llm.py`)

One injectable interface `LLMComplete(system, user) -> (text|None, model|None, errors)`. `default_llm` routes through the existing `integrations/_llm.complete` (OpenRouter, OpenAI-compatible). `text is None` ⇒ unavailable ⇒ honest fallback. `extract_json` robustly pulls JSON out of fenced/prose replies. Tests inject mocks → no network, deterministic.

---

## 6. Schema Validation (`safety/plan_schema.py`, reused)

Every plan — AI or fallback — is a Pydantic `ExecutionPlan` (`extra="forbid"`, no cap/authorization fields). Construction *is* validation: malformed/out-of-range/unknown fields raise before the Gateway. The planner additionally clamps AI params to schema sanity so a hostile/garbled value can't crash planning; the Gateway then clamps to the real caps.

---

## 7. Safety Gateway Integration (`safety/gateway.py`)

Unchanged authority from Section 2, now the mandatory gate for AI plans. Added a `dry_run=True` mode for the preview endpoint (runs every check, creates **no** registry record). `test_ai_safety_integration.py` proves: valid AI plan → approved; off-allowlist target → rejected; AI params 9999 → clamped to the cap (4); the AI cannot widen the allowlist; internal error → fail-closed; `rat_related` → rejected ("not executable").

---

## 8. Execution Dispatcher Integration (`safety/dispatcher.py`, reused)

Approved plans run through the existing dispatcher (own process group, registry lifecycle, kill-switch reachable, secrets masked). `run_operation` passes **mock adapters in tests**; in production it uses the real adapters, which stay fail-closed/disabled by default, so a disabled module is rejected by the Gateway and nothing runs. The RAT adapter does not exist and `rat_related` is rejected at the Gateway — a plan schema that can *name* it does not make it runnable.

---

## 9. Post-Execution Analysis (`agent/analysis.py`)

`analyze(record, result, context, llm)` → `AnalysisResult{measured_facts, interpretation, source, objective_met, evidence}`:
- **Measured facts** are extracted ONLY from the real execution record/result (state, exit code, Hydra `found_count`/attempts/message, Locust totals). Nothing is invented.
- `objective_met` is **evidence-based** (Hydra found a pair; Locust observed failures) — no evidence ⇒ not met.
- **Interpretation** is one labelled sentence (AI when available, else deterministic) and is kept separate from the facts. A failed/empty/timed-out execution is analysed honestly; success is never claimed without evidence.

---

## 10. Feedback Loop (`agent/feedback.py`)

`decide(...)` → `CONTINUE | MODIFY | STOP` with reasoning + evidence + source. **Deterministic guardrails are evaluated first and always win**: kill-switch engaged, objective met, `iteration+1 >= max`, or `consecutive_failures >= AI_CONSECUTIVE_FAILURE_STOP` ⇒ STOP. Only when it is already safe to proceed is the AI asked (one word); an invalid/unavailable answer falls back to a deterministic default (MODIFY after a non-clean run, else CONTINUE). The AI can never force continuation, never raise the iteration cap, and every proposed next plan re-passes schema + Gateway (`test_feedback_cannot_bypass_gateway`).

---

## 11. API Changes (`app/api/operations.py`, new router)

- `POST /api/operations/plan` — context → AI plan → **Gateway dry-run** preview. No execution.
- `POST /api/operations` — run the bounded loop; fail-closed (disabled module ⇒ Gateway rejects ⇒ nothing runs).
- `GET /api/operations` — list; `GET /api/operations/{id}` — full iteration trail.

Pydantic request/response models; secrets masked; no endpoint bypasses the Gateway. Existing endpoints untouched. `main.py` includes the new router.

---

## 12. Database & Audit Changes (`app/models.py`)

Two new tables (existing SQLite DB, no new DB layer):
- `operations` — objective, scenario id, module hint, target, status, final recommendation, iteration count, timestamps.
- `operation_iterations` — per cycle: plan source (ai/system/none), model, prompt version, **masked** `ai_output`, validation result, **masked** `gateway_decision`, execution id/state, **masked** `result_summary`, `analysis`, feedback action + reasoning.

Every JSON field is run through `safety/audit.mask_secrets` before persistence; the Section-2 `audit_records` trail still captures gateway/execution/kill-switch events. No plaintext credential, key, or token is stored.

---

## 13. Frontend Changes

A new, self-contained page `frontend/src/pages/AIPlanner.tsx` (route `/planner`, nav "AI Planner"), reusing existing `ui.tsx` components (Panel/Pill/Button/SectionLabel/Tag/Empty). It lets the user submit an objective and:
- **Preview plan** → shows planning status **honestly distinguished** (AI-GENERATED vs FALLBACK (NOT AI) vs UNAVAILABLE), telemetry scope, runnable modules, and the Gateway's dry-run verdict.
- **Run operation** → shows each iteration's plan source, Gateway decision, execution state, **measured facts vs AI interpretation** (visually separated), and the feedback recommendation.
- A "Recent operations" list loads prior runs. Unavailable data renders an honest empty/unavailable state — no fake visualizations.

Added `api.ts` methods (`operationPlan`, `startOperation`, `listOperations`, `getOperation`) and `types.ts` interfaces. `App.tsx` + `Layout.tsx` get one route + one nav entry. No other page was changed; the dashboard design is preserved. **`npm run typecheck` passes.**

---

## 14. Tests Performed

All with mock LLM + mock adapters; no target, no real tool. New files:
| File | Tests | Covers |
|---|---|---|
| `test_planner.py` | 10 | valid AI plan; AI never sets target; malformed/missing-module/invalid-module → fallback; params clamped; LLM-unavailable labelled fallback; timeout → fallback; no runnable → unavailable; model/prompt recorded. |
| `test_ai_safety_integration.py` | 6 | AI plan → Gateway approved; off-allowlist rejected; AI can't exceed caps; AI can't widen allowlist; fail-closed; rat_related rejected. |
| `test_operation_loop.py` | 11 | objective-met → COMPLETED; approved Hydra/Locust reach mock adapters with clamped params; error recorded + stop; kill switch prevents execution; rat_related never runs; missing telemetry honest; no fabricated metrics; CONTINUE→cap STOP; max-iter clamp; feedback can't bypass gateway. |
| `test_feedback.py` | 8 | objective-met/kill-switch/max-iter/repeated-failure force STOP; FAILED→MODIFY; completed-not-met→CONTINUE; AI word used when safe; AI can't override deterministic STOP. |
| `test_operations_api.py` | 5 | preview unavailable when nothing armed; preview fallback+approved when armed; run disabled → no execution; list/get; 404. |

Plus the Section-2 suite (39) re-run green.

---

## 15. Actual Test Results

```
cd backend && source .venv/bin/activate && python -m pytest tests/ -p no:cacheprovider -q
→ 79 passed, 1 warning in ~2.9s   (warning = upstream Starlette deprecation)
```
Runtime smoke (app on :8079, nothing armed): `/api/operations/plan` → `planning_status=unavailable, plan=None, runnable=[], telemetry=unavailable`; `/api/operations` → `status=STOPPED, plan_source=none, execution_state=None, feedback=STOP` (honest fail-closed); list works. Frontend `npm run typecheck` → clean.

---

## 16. Remaining Limitations (honest)

1. **AI planning was exercised only with mock LLMs.** No `OPENROUTER_API_KEY` is set, so the live path currently returns the honest **fallback** (not AI). Real-LLM planning is unverified end-to-end until a key is configured — the code path is tested with mocks, not a live model.
2. **No real execution was run** (per the brief). Hydra/Locust via the operation loop are verified only with mock adapters; live tool execution through the loop is unverified.
3. **Operation runs are synchronous** (block the request), like the Section-2 endpoints. A long loop holds the HTTP connection; async orchestration is future work.
4. **Feedback MODIFY does not yet re-shape parameters cleverly** — it re-plans from updated context; a smarter parameter-revision strategy is future work.
5. **Kill-switch reset still requires `SAFETY_ADMIN_TOKEN`** (Section-2 change); the frontend rearm button is still unmodified and will 403/422 until you decide on that (unchanged this section).
6. **RAT-related module remains unavailable** by design; `rat_related` is rejected at the Gateway.
7. **Frontend shows planning/analysis** but does not yet stream live iteration updates over WebSocket (it fetches the completed operation). Live streaming is future work.

---

See also `docs/CHAKRAVYUH_MASTER_PROGRESS.md` for the cumulative project record.
