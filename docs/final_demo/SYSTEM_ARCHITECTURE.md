# CYBER CHAKRAVYUH — System Architecture (evidence-based)

## Component flow (verified against code)
| Stage | File / symbol | Receives | Produces |
|---|---|---|---|
| Dashboard | `frontend/src/pages/*`, `api.ts` | operator actions | HTTP requests |
| FastAPI | `app/api/*.py` routers | HTTP request | validated request (Pydantic) |
| Context / Planner | `app/agent/context.py`, `agent/planner.py` | objective + telemetry | structured plan (AI or fallback) |
| ExecutionPlan | `app/safety/plan_schema.py` | planner output | validated `ExecutionPlan` (no caps field) |
| **Safety Gateway** | `app/safety/gateway.py:evaluate()` | plan | `GatewayDecision` (approve/reject) **+ authorization** |
| Policy | `app/safety/policy.py` | module+target+params | allowlist/caps verdict |
| **Execution Registry** | `app/safety/registry.py` | approved plan | `ExecutionRecord` + **unique execution_id** + lifecycle |
| Dispatcher | `app/safety/dispatcher.py:run_execution()` | execution_id | invokes adapter; transitions state |
| Adapter | `app/integrations/{hydra,locust,remote_access}.py` | clamped params | real tool result |
| Telemetry/Analysis | `app/telemetry/*`, `agent/analysis.py` | result | measured metrics / AI interpretation |
| Audit | `app/safety/audit.py` | every decision/result | SQLite `AuditRecord` (secrets masked) |
| Dashboard results | WebSocket `/ws` (`useLive.ts`) + REST | events/telemetry | live UI |

- **Authorization** happens in `gateway.evaluate()` (and `authorize_recon_target()` for recon paths) — never in the frontend.
- **Kill switch** (`app/safety/killswitch.py`) is checked at the top of `evaluate()` and in each network-touching route; reset requires `SAFETY_ADMIN_TOKEN` (no unauthenticated reset).
- **Execution registration + audit**: in the Gateway (record) and Dispatcher (lifecycle + audit).
- **AI vs deterministic:** the planner only *proposes*; the Gateway/policy/registry/dispatcher are AI-independent and authoritative.

## ⚠️ Legacy routes NOT fully unified (documented honestly)
These enforce **central authorization + kill-switch + audit** but do **NOT** go through the unified `ExecutionPlan → Gateway → Registry → Dispatcher` pipeline:
`POST /api/telemetry/probe`, `POST /api/attacks/soc-activity`, `POST /api/assessment/run` (One-Click), `POST /api/auth/live-validate`, `POST /api/transfer/send`.
Fully-unified paths: `hydra/run`, `locust/run`, `locust/simulate`, `remote_access/run`, `execution/submit`, `operations`.

## Mermaid — architecture
```mermaid
flowchart TD
  UI[React Dashboard] -->|HTTP /api| API[FastAPI routers]
  API --> PL[AI Planner (agent/planner.py)]
  PL --> EP[ExecutionPlan (Pydantic)]
  EP --> GW[Safety Gateway evaluate()]
  GW -->|reject fail-closed| UI
  GW --> POL[Policy: allowlist + caps]
  POL --> REG[Execution Registry (execution_id)]
  REG --> DIS[Dispatcher]
  DIS --> AD[Adapter: Hydra / Locust / NetExec]
  AD --> TEL[Telemetry + Analysis]
  TEL --> AUD[(SQLite Audit)]
  AUD --> UI
  KS{{Kill Switch}} -.blocks.-> GW
  KS -.blocks.-> API
```

## Mermaid — sequence (harmless recon probe)
```mermaid
sequenceDiagram
  actor Op as Operator
  participant UI as Dashboard
  participant API as FastAPI /api/telemetry/probe
  participant AZ as authorize_recon_target()
  participant PR as run_probe (TCP connect)
  participant AU as Audit (SQLite)
  Op->>UI: enter authorized target IP
  UI->>API: POST {target}
  API->>API: kill-switch check (423 if engaged)
  API->>AZ: authorize (RFC1918 or tailnet peer; reject public/hotspot)
  AZ-->>API: ok / refused
  API->>PR: bounded TCP connect (approved ports)
  PR-->>API: reachable? open_ports[] (or unreachable)
  API->>AU: RECON_PROBE (decision=completed)
  API-->>UI: measured result + soc_note
```
