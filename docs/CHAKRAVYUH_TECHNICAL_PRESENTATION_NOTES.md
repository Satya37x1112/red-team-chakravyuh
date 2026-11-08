# CHAKRAVYUH — Technical Presentation Notes (Academic Meeting)

**Date:** 2026-11-07 · For presenting to faculty/reviewers. All claims are grounded in the actual code and tests; nothing experimental is invented.

---

## 1. Problem statement
Red-team tooling is powerful but dangerous and fragmented: operators wire many separate tools by hand, with weak, inconsistent safety. Adding "AI" naively is worse — an LLM that can run commands is an unbounded risk. The problem: **can an AI meaningfully assist offensive testing while deterministic controls keep it provably bounded and auditable?**

## 2. Project objectives
A single integrated console where a user gives an objective, **one centralized AI brain** plans across three red-team modules, a **deterministic Safety Gateway** authorizes every action, execution is bounded and audited, and the AI analyses **real evidence** — authorized lab only, Kali-native, nothing installed on the target.

## 3. Existing system limitations (the baseline we started from)
The earlier codebase (VAJRAPRAHAAR) had **two disconnected paths**: a simulation path with a per-module integer "AI", and a separate manual tool path with no AI, no central gateway, and a kill switch that did not stop real tools. There was no centralized planner, no structured plan schema, no deterministic gateway, and no tests (see `docs/CLAUDE_SECTION_1_AUDIT.md`).

## 4. Proposed architecture
`Objective → Context → Centralized Planner → ExecutionPlan (Pydantic) → Safety Gateway → Registry → Dispatcher → Adapter → Analysis → Feedback → Audit → Dashboard`, with a unified kill switch over all managed executions. One planner, one schema, one gateway, one registry, one kill switch. (Diagram: `CHAKRAVYUH_FINAL_ARCHITECTURE.md`.)

## 5. Centralized AI design
A single `generate_plan` (`app/agent/planner.py`) reads a shared context and proposes **one** module + bounded params (+ an operation identifier for remote access). It routes through the existing OpenRouter integration with an **honest fallback**: no key / malformed / timeout ⇒ a clearly-labelled deterministic fallback or `unavailable`, never mislabelled as AI. The AI **proposes**; it cannot act.

## 6. Three integrated modules
1. **Hydra** — bounded authentication testing (caps; cracked password never shown).
2. **Locust** — bounded service-load testing (user/spawn/duration caps; not flooding).
3. **NetExec** — credentialed remote administration, **five fixed read-only operations** (not a conventional RAT).
Plus **Blackbox telemetry** (agentless, IP-only, authorized + bounded) and **WinRM telemetry** (implemented, live-unverified).

## 7. Safety Gateway
Deterministic, AI-independent (`app/safety/gateway.py`): kill-switch state → module enabled → adapter available → target allowlist → operation allowlist (D2) → concurrency → clamp-to-caps. Fail-closed on any error. A rejected plan creates **no** registry record, so it can never reach an adapter.

## 8. Execution registry & kill switch
The registry (`app/safety/registry.py`) tracks a lifecycle state machine concurrency-safely. The kill switch (`app/safety/killswitch.py` + `process.py`) runs every adapter subprocess in its own **process group**, so one engage terminates in-flight Hydra/Locust/NetExec work (SIGTERM→grace→SIGKILL); reset is token-gated.

## 9. Telemetry & reconnaissance
Honest, scope-labelled telemetry: `none` / `local` (Kali host) / `winrm` (remote read-only) / `blackbox` (agentless external probe). Blackbox is IPv4+RFC1918+allowlist-gated, authorized before any socket, and time-budgeted; it never fabricates host internals (CPU/RAM stay unavailable).

## 10. Technology stack
Python 3.13 · FastAPI · Uvicorn · Pydantic v2 · SQLAlchemy/SQLite · WebSocket · OpenRouter · React 18 + TypeScript + Vite + Tailwind · THC-Hydra/Locust/NetExec on Kali. No Docker.

## 11. Testing methodology
**Everything is verified with mocks and isolated fixtures** — mock LLM responses, mock adapters, mocked sockets — so no real target is contacted and no real tool runs during testing. The one live-LLM test is deselected in offline mode. This isolates *logic* verification from *live* verification and keeps the suite deterministic and safe.

## 12. Results & evidence
Backend **140 passed, 0 failed, 0 skipped, 1 deselected (live OpenRouter), 1 warning**; full collection = **141 tests**. Frontend `npm run typecheck` ✓ and `npm run build` ✓. Cross-module audits confirm one planner/gateway/registry/kill-switch and **no gateway bypass** (Stages 5.1–5.3).

## 13. Limitations
Mock/code-verified, **not live-verified**: real Hydra/Locust/NetExec/WinRM/blackbox against a target are unverified; paid-model AI is blocked (credits); browser click-through and DB-outage recovery are unverified; remote-command cancellation is not guaranteed; no automated start script; Node PATH not persistent. **Not production-secure** (academic isolated lab; no API auth by design).

## 14. Future improvements
Supervised live verification on the authorized lab target; credited OpenRouter keys for the paid model; async execution + WebSocket live iteration streaming; dedicated Hydra/Locust UI pages + rearm token wiring; frontend tests; a persistent registry; a startup/shutdown script; Alembic migrations; WMI telemetry (credentialed inside-metrics).

---

## Likely questions & accurate answers

**Q: Why a centralized planner instead of three per-module agents?**
A: One brain sees the whole scenario and shares one context, one schema, and one safety gateway — so coordination, auditing, and safety are consistent. Three independent agents would duplicate logic and create three places safety could diverge. Grep confirms a single `generate_plan`.

**Q: Why can't the AI directly execute commands?**
A: By construction. The AI layer (`planner/context/analysis/feedback`) imports no `subprocess`, no dispatcher, and no adapter (verified). The AI only emits a structured plan; a deterministic gateway authorizes it and a deterministic dispatcher runs the adapter. This is the core safety property — the AI proposes, Python decides.

**Q: How does target authorization work?**
A: The AI never picks a target; `requested_target` is bound to a configured **allowlist**. The gateway rejects anything not on it, and a rejected plan creates no execution record, so it can't reach an adapter. Telemetry uses a **separate** blackbox allowlist (IPv4 + RFC1918) to avoid coupling.

**Q: Why use mocks? Isn't that "fake"?**
A: Mocks verify the *logic and safety* of the pipeline deterministically and safely, without attacking anything. They are clearly labelled synthetic and are never presented as real attack results. Live verification is a separate, supervised step on the authorized target — intentionally not done yet.

**Q: Why is the third module not a conventional RAT?**
A: It has no implant, no persistence, no stealth, no credential theft, no arbitrary command execution, and nothing that survives the session. It performs **credentialed remote administration** limited to five fixed, read-only operation identifiers over an approved interface (NetExec). The AI/API picks an *identifier*, never a command string.

**Q: How is credential security maintained?**
A: Credentials live only in the local gitignored `.env`; they are never in a plan, never sent to the LLM, never in API responses/audit/logs/exceptions. For remote access the password is written to a 0600 `/dev/shm` file passed as `-p <file>` (so it never appears on argv / `/proc`/`ps`), cleaned up on every path, fail-closed if the file can't be created, with exception text redacted.

**Q: What remains unverified?**
A: Any *live* behaviour — real Hydra/Locust/NetExec/WinRM/blackbox against a real target, paid-model AI, and interactive browser testing. The platform is fully mock/code-verified; the live run is the next supervised step.
