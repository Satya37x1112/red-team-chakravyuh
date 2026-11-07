# CHAKRAVYUH — Section 3.1: Live AI Planner & Safety Verification

**Author:** Implementation engineer (Claude Code, on Kali)
**Date:** 2026-11-07
**Nature:** Verification & correction section (no new capability). No Docker, Kali-native, nothing on the Windows target, no target contact, no attack tool run, no recon, no dependency installed, no push/commit.

**Headline result:** backend **80 passed, 1 skipped** (the skip is the live-LLM test — `OPENROUTER_API_KEY` is not configured); frontend **typecheck clean + production build succeeds**. The deterministic safety architecture and the mock/offline AI path are **MOCK/OFFLINE VERIFIED**. The **live OpenRouter path is BLOCKED** (no key) and therefore **unverified** — not fabricated.

---

## 1. Verification Scope

Verify, without real execution: OpenRouter integration + key status; the centralized planner (valid/invalid/unavailable/isolation); the Section-2 Safety Gateway (independent of the LLM); the unified kill switch (controlled mock subprocesses only); the frontend AI Planner (connectivity, honest states, no secret exposure); the full mocked workflow; and backend regression. Correct only in-scope issues.

Verification legend used throughout:
- **LIVE VERIFIED** — exercised against the real provider/tool.
- **MOCK VERIFIED** — exercised with mock LLM / mock adapters / controlled mock subprocess.
- **IMPLEMENTED BUT UNVERIFIED** — code exists; not exercised end-to-end live.
- **BLOCKED** — cannot verify now (missing prerequisite).

---

## 2. Repository State Before Verification

- Branch `main`, working tree clean; Sections 1–3 committed (`b494e47` Section 3, `a38b396` Section 2, `5c0b5f4` Section 1, on top of `b7e7621`). The Section-2 feature branch was fast-forwarded into `main` and deleted at the owner's request.
- No uncommitted changes existed at the start of 3.1. (3.1 adds one test file + this doc + the progress update, intentionally left uncommitted per the 3.1 stop condition.)

---

## 3. OpenRouter Configuration Status

Inspected `app/config.py`, `app/integrations/_llm.py`, `app/agent/llm.py`, `app/agent/decision.py`.
- Config present and correct: `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`, `OPENROUTER_MODEL=anthropic/claude-sonnet-4.5`, `OPENROUTER_FALLBACK_MODELS=openrouter/free`. Client is OpenAI-compatible, `timeout=60`, `max_retries=0`, `response`/JSON parsing guarded.
- `OPENROUTER_API_KEY`: **EMPTY / not configured** (verified by presence check; the value was never printed).
- Secret handling: the key is read only from env into `settings`; it is never logged, never returned by any endpoint, and never sent to the frontend. `app/safety/audit.mask_secrets` redacts key/token/credential fields before persistence.
- **Consequence:** live LLM verification is **BLOCKED**. Per the brief, no successful AI response is fabricated; all offline/mock verification proceeds.

---

## 4. Live LLM Test Result

**BLOCKED — not performed.** `OPENROUTER_API_KEY` is not set, so `tests/test_live_llm.py::test_live_structured_plan_validates_and_is_bound` is **skipped** (pytest: `SKIPPED [1] … OPENROUTER_API_KEY not configured; live LLM verification blocked`).

The test is in place and will run automatically if a key is later configured. It is an **AI-planning-only** test: it builds a clearly-SIMULATED context, asks the real model for a structured plan, validates it against the Pydantic schema, asserts the target is bound to the authorized allowlist (the AI cannot invent one) and that the gateway clamps params to caps — and it **never invokes the dispatcher or contacts a target**.

What *was* verified live/offline about the LLM path:
- `test_default_llm_without_key_is_offline_and_honest` — **OFFLINE VERIFIED**: with no key, `default_llm` returns `(None, None, [errors])` and makes **no network call** (it never constructs a client). The planner then yields an honest fallback/unavailable — never a fabricated AI answer.

---

## 5. Centralized Planner Verification — MOCK VERIFIED

`tests/test_planner.py` (10) + `tests/test_operation_loop.py` (11), all passing:
- **A. Planning:** valid scenario → structured plan; uses the context manager; considers module availability; **target comes from the authorized config, never invented** (`test_ai_never_sets_target`); reasoning/expected-observations recorded.
- **B. Invalid output:** malformed JSON → fallback; missing module → fallback; invalid module id → fallback; out-of-range params → clamped to schema then (gateway) to caps.
- **C. LLM unavailable:** no key / timeout / provider error → clearly-labelled **fallback (`source=system`)** or **unavailable**; fallback is **never** labelled AI-generated.
- **D. Execution isolation:** verified by import audit — `planner.py`/`context.py`/`analysis.py`/`feedback.py` import no `subprocess`, dispatcher, Hydra or Locust; **only `operation.py` calls the dispatcher**, and only after gateway approval. AI planning cannot invoke shell/tools, cannot modify gateway policy, cannot change the allowlist (`test_ai_cannot_change_allowlist`).

---

## 6. Safety Gateway Verification — MOCK VERIFIED (independent of the LLM)

`tests/test_gateway.py` (10) + `tests/test_ai_safety_integration.py` (6), all passing: authorized target accepted; unauthorized target rejected; unsupported module (`rat_related`) rejected; disabled module rejected; adapter-unavailable rejected; out-of-range params clamped (schema rejects absurd); AI attempt to exceed limits → clamped to caps; internal policy error → **fail-closed** rejection; kill-switch active → new plans rejected; concurrency cap enforced under a 12-thread race. Every rejected plan creates **no runnable record**, so it cannot reach the dispatcher (`test_submit_rejected_never_runs_adapter`). No safety control was weakened to pass a test.

---

## 7. Kill-Switch Verification — MOCK VERIFIED

`tests/test_killswitch.py` (6), all passing, using only a controlled `python -c "sleep"` mock subprocess: new executions rejected after activation; active mock execution cancelled and its **managed child process-group terminated** (PID confirmed dead); repeated activation safe (idempotent); cancellation outcomes recorded; failed termination reported honestly (`CANCEL_FAILED`); reset remains protected by `SAFETY_ADMIN_TOKEN`; **unrelated processes are never terminated** (`test_unrelated_process_not_terminated`). No real attack process was launched.

---

## 8. Frontend Verification

- **Connectivity:** `src/api.ts` calls relative `/api/...` (Vite proxies to the real backend on :8077); the new `operationPlan`/`startOperation`/`listOperations`/`getOperation` methods map to the real `/api/operations/*`. **Static-VERIFIED** (contract matches the backend smoke test in §10).
- **Honest states:** `src/pages/AIPlanner.tsx` renders `AI-GENERATED` vs `FALLBACK (NOT AI)` vs `UNAVAILABLE`, `GATEWAY APPROVED/REJECTED`, and **separates "Measured facts (evidence)" from "Interpretation"**; missing telemetry shows the scope label (`unavailable`); API errors are caught and shown. No fabricated results.
- **No secret exposure:** a frontend grep found no API key/secret value; the only `OPENROUTER_API_KEY` occurrence is a config *hint label* (variable name) in `DecisionPanel.tsx`, not a value. The key is backend-only.
- **Checks run:** `npm run typecheck` → clean; `npm run build` → **success** (69 modules; only a pre-existing chunk-size advisory). Node/npm were available via `~/.local/node/bin` on PATH; no package was installed.
- **Known issue (out of 3.1 scope, owner decision pending):** `api.rearm()` still POSTs `/api/killswitch/reset` with no body, while Section 2 made reset require `{admin_token}`. The button therefore fails with 403/422 — but it **degrades gracefully** (App.tsx catches the error and shows a "Re-arm failed" toast; no crash). Flagged, not changed.

---

## 9. Backend Regression Test Results

```
cd backend && source .venv/bin/activate && python -m pytest tests/ -q
→ 80 passed, 1 skipped, 1 warning in ~3.7s
```
- Previous baseline (Section 3) was 79 passed. 3.1 adds `tests/test_live_llm.py` (+1 offline test passing, +1 live test skipped). **No regression.**
- The 1 warning is an upstream Starlette deprecation, not ours. The 1 skip is the live-LLM test (no key).

---

## 10. Mocked Workflow Results — MOCK VERIFIED

Full `Objective → Context → AI Planner → schema → Safety Gateway → mock Dispatcher → mock Execution → Observation → AI Analysis → Feedback` exercised by `tests/test_operation_loop.py` (11) + `tests/test_feedback.py` (8): successful mocked planning; unauthorized/rejected plans never execute; execution failures recorded then STOP after the configured repeated-failure cap; missing telemetry reported honestly; no fabricated metrics; CONTINUE, MODIFY, STOP all handled; kill-switch interruption yields REJECTED + no execution; max-iteration cap enforced and client-requested iteration counts clamped; the Gateway re-authorizes **every** iteration (`test_feedback_cannot_bypass_gateway`).

Runtime smoke (backend on :8079, nothing armed): `/api/operations/plan` → `planning_status=unavailable, plan=None, runnable=[], telemetry=unavailable`; `/api/operations` → `status=STOPPED, plan_source=none, execution_state=None, feedback=STOP`; list works. Honest fail-closed.

---

## 11. Issues Discovered

1. **Live LLM path unverifiable** — `OPENROUTER_API_KEY` absent. BLOCKED (expected; not a bug).
2. **Frontend rearm button vs token-gated reset** — pre-existing Section-2 consequence; degrades gracefully; owner decision pending. Not corrected (out of 3.1 scope and intentional).
3. No functional defects found in the planner, gateway, kill switch, analysis, feedback, or operations API during verification.

---

## 12. Corrections Made

- **Added** `backend/tests/test_live_llm.py`: a guarded live-LLM AI-planning test (auto-skips without a key) + an offline-honesty test proving the no-key path makes no network call and is labelled non-AI.
- No production code required correction — all existing behaviour verified as specified. No safety control was weakened.

---

## 13. Remaining Limitations

- **Live AI planning:** BLOCKED until `OPENROUTER_API_KEY` is configured; then `test_live_llm.py` verifies it automatically.
- **Real Hydra / Locust execution, real WinRM telemetry:** IMPLEMENTED BUT UNVERIFIED (no tool run, no target contacted — by rule).
- **Frontend live interaction:** verified by typecheck + build + contract, not by an automated browser test.
- **Kill-switch reset UX:** frontend rearm needs the admin token wired (owner decision).

---

## 14. Live vs Mocked — Explicit Distinction

| Capability | Status |
|---|---|
| Live LLM (OpenRouter) planning | **BLOCKED** (no key) — unverified, not fabricated |
| Offline no-key LLM honesty | **OFFLINE VERIFIED** |
| Mock-LLM planner logic | **MOCK VERIFIED** |
| Mock-adapter execution flow | **MOCK VERIFIED** |
| Deterministic Safety Gateway | **MOCK VERIFIED** (LLM-independent) |
| Unified kill switch (mock subprocess) | **MOCK VERIFIED** |
| Full mocked AI workflow | **MOCK VERIFIED** |
| Real Hydra execution | **IMPLEMENTED BUT UNVERIFIED** |
| Real Locust execution | **IMPLEMENTED BUT UNVERIFIED** |
| Real Windows (WinRM) telemetry | **IMPLEMENTED BUT UNVERIFIED** |
| Frontend (typecheck + build + contract) | **VERIFIED**; live UI interaction **UNVERIFIED** |

See `docs/CHAKRAVYUH_MASTER_PROGRESS.md` for the cumulative record (Section 3.1 entry added).
