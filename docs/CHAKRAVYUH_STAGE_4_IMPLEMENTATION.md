# CHAKRAVYUH — Stage 4 Implementation Notes

Stage 4 was a **verification/integration-confirmation** stage. The existing frontend was already
wired to the real backend APIs through earlier stages, with honest state handling, so no source
changes were needed (per the "verify, don't rewrite" rule).

## Hybrid data flow (confirmed end-to-end)
Operator → AIPlanner UI → `POST /api/operations` → Context → **centralized planner** (`agent/planner.py`,
one LLM client) → Pydantic `ExecutionPlan` → **Safety Gateway** (`evaluate`) → Execution Registry →
Dispatcher → adapter → telemetry → AI analysis/feedback → dashboard. When AI is unavailable the planner
falls back deterministically and the UI labels the plan `FALLBACK (NOT AI)` — no fabrication.

## WebSocket events
`/ws` streams telemetry + agent events; `useLive.ts` reconnects with backoff; `connected` drives the
"Telemetry live/Disconnected" indicator.

## AI-unavailable behaviour
OpenRouter auth is failing (model `anthropic/claude-sonnet-4.5`). The Python scripting layer is
unaffected: validation, gateway, execution, telemetry, and audit all function; the UI shows the AI as
unavailable. Restoring inference needs a valid key in `backend/.env` (owner action — not changed here).

## Verification
See the Stage 4 report in-session for exact commands and results (full backend suite, frontend
typecheck + production build).
