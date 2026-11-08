# CHAKRAVYUH — Academic Demonstration Guide (Mock / Synthetic)

**Date:** 2026-11-07 · **Written for:** presenting CHAKRAVYUH in an academic review using **mock/synthetic** execution — **no live attacks, no target contact**.

> ⚠️ **Honesty rule for the whole demo:** everything shown here is **mock/synthetic** or **safety behaviour**. Never present a synthetic result as a real attack outcome. When a panel shows an outcome, say "this is a mock/synthetic result" out loud.

Prerequisites: backend on `http://127.0.0.1:8077`, frontend on `http://localhost:5173` (see `CHAKRAVYUH_KALI_SETUP.md`). All attack modules **disabled** (default). Optionally set an OpenRouter key for live AI narration (free model works).

---

## Part A — Project introduction (2–3 min)
- **What it is:** an AI-assisted Red-Team console for an **authorized, isolated lab**. A user gives an objective; one **centralized AI brain** plans; **deterministic Python** authorizes and executes bounded work; the AI then analyses real evidence and recommends continue/modify/stop.
- **Red-Team objective:** safely demonstrate three capabilities — authentication testing (Hydra), bounded service-load testing (Locust), and credentialed remote administration (NetExec) — against an authorized lab Windows VM, with everything running on Kali.
- **Centralized AI planning:** ONE planner understands the whole scenario and coordinates the three modules (not three separate agents).
- **The key distinction:** **AI proposes, deterministic code decides.** The AI never picks a target, never raises a limit, never approves its own plan, never runs a command.

## Part B — Architecture (3 min)
- Show the diagram in `CHAKRAVYUH_FINAL_ARCHITECTURE.md`.
- Walk the common pipeline: **Objective → Context → Planner → Schema → Safety Gateway → Registry → Dispatcher → Adapter → Analysis → Feedback → Audit → Dashboard.**
- Emphasise: all three modules share the **same** planner, schema, gateway, registry, kill switch — one spine, not three silos.

## Part C — Dashboard tour (4 min)
Open `http://localhost:5173` and show (sidebar):
- **AI Planner** (Agent → AI Planner): objective box; "Preview plan" (dry-run) shows the AI/fallback plan + Safety-Gateway verdict; "Run operation" shows the bounded loop.
- **Integrations**: the Hydra/Locust/Caldera/vervet panels and their armed/not-armed status.
- **Remote Access** (Operations → Remote Access): the five approved operation identifiers; **no command box, no shell**.
- **Target Recon** (Lab → Target Recon): the IP → open-ports → telemetry layout (unavailable until blackbox is configured).
- **Operations**: recent AI operations with their iteration trail.
- **Kill switch**: the engage control (Win+Alt+K shortcut) and halted state.

## Part D — Module demonstrations (MOCKS only, ~6 min)

The cleanest mock demo is the **AI Planner "Preview plan"** flow (dry-run, never executes) plus the test-suite evidence. For a live-moving demo without a target, run the mocked E2E tests and narrate them:

```
cd backend && source .venv/bin/activate
python -m pytest tests/test_operation_loop.py tests/test_remote_access.py -q
```
- **Hydra workflow:** `test_operation_loop.py::test_loop_completes_when_objective_met` — plan → gateway approve → mock adapter returns a synthetic "credential found" → analysis → feedback STOP. *(Synthetic — no real authentication.)*
- **Locust workflow:** `test_approved_locust_reaches_mock_adapter` — bounded load plan (caps clamped) → mock adapter returns synthetic request/failure totals → analysis. *(Synthetic — no traffic.)*
- **Remote Access workflow:** `test_full_loop_remote_access` — approved operation id `connectivity_check` → gateway → mock adapter returns a synthetic "authenticated" result → analysis. *(Synthetic — no NetExec run.)*
- **Blackbox telemetry:** `test_blackbox_telemetry.py` — authorized private IP, mocked sockets, open-port/latency parsing, honest partial results. *(Mocked sockets — no real probe.)*

## Part E — Safety demonstrations (the strongest part, ~5 min)
Run the safety tests live and narrate each:
```
python -m pytest tests/test_gateway.py tests/test_ai_safety_integration.py tests/test_killswitch.py -q
```
- **Unauthorized target rejected:** `test_unauthorized_target_rejected` — a plan for an off-allowlist target is refused; no record created.
- **Unsafe operation rejected:** `test_remote_access.py::test_unknown_operation_rejected_by_gateway` and the 7 **command-injection** cases rejected by the schema.
- **Policy cap enforcement:** `test_ai_cannot_exceed_fixed_limits` — the AI asks for 5000 users; the gateway clamps to the configured cap.
- **Kill-switch activation:** `test_new_executions_rejected_after_activation` + `test_killswitch` terminates a real managed subprocess and leaves unrelated processes untouched.
- **Secret masking:** `test_password_never_in_result` / `test_audit_has_no_secret` / `test_password_never_in_argv` — the credential never appears in results, audit, or argv.
- **Honest AI-unavailable:** `test_llm_unavailable_labeled_fallback` — no key ⇒ clearly-labelled fallback, never mislabelled as AI.

## Part F — Results (~3 min)
Using an operation's detail (or the mocked loop output), show:
- **Execution lifecycle:** REQUESTED→VALIDATING→APPROVED→RUNNING→COMPLETED (or REJECTED/FAILED/TIMED_OUT/CANCELLED).
- **Synthetic observations:** the mock adapter's structured result (labelled synthetic).
- **AI analysis:** measured **facts** (from the result) shown separately from AI **interpretation**.
- **Feedback:** CONTINUE / MODIFY / STOP, with the deterministic guardrail that produced it.
- **Audit history:** the `OperationIteration` / `AuditRecord` rows (secret-masked).

## Part G — Limitations (disclose clearly, ~2 min)
State plainly:
- **Real Hydra/Locust/NetExec target execution is UNVERIFIED** — demonstrated with mocks only.
- **WinRM and Blackbox live telemetry are UNVERIFIED** — no target contacted.
- **Paid-model AI is BLOCKED** when OpenRouter credits are unavailable (the free fallback model works).
- **Browser click-through testing is incomplete** (typecheck + build verified, not interactive UI).
- **Database-outage recovery is unverified**; the execution registry is in-memory (resets on restart).
- **Process termination** cannot guarantee cancelling a remote command already accepted by the target (mitigated by short, read-only, bounded remote ops).

---

### One-line closing
"CHAKRAVYUH is a working, integrated, safety-first AI Red-Team console — fully mock-verified end to end; the only thing left is a supervised live run against our authorized lab target."
