# AI RED TEAM — API Endpoint Reference

## Health & LLM
- `GET  /api/health` — status + telemetry source + kill-switch state
- `GET  /api/llm/config` · `POST /api/llm/test` — provider config / live inference test

## Network discovery & targets
- `GET  /api/network/interfaces` · `/subnets` · `/tailnet`
- `POST /api/network/discovery/start` · `GET /api/network/discovery/{id}[/hosts]` · `POST /api/network/discovery/{id}/cancel`
- `GET  /api/network/targets` · `POST /api/network/targets/select`

## Telemetry & recon
- `GET  /api/telemetry/latest` · `GET /api/telemetry/history` · `POST /api/telemetry/probe`
- `POST /api/attacks/soc-activity`

## Gated execution (ExecutionPlan → Gateway → Registry → Dispatcher)
- `POST /api/integrations/{hydra/run,locust/run,locust/simulate,remote_access/run}`
- `POST /api/execution/submit` · `POST /api/operations[/plan]`

## Auth testing & transfer
- `POST /api/auth/{offline-audit,live-validate,identify-hash}` · `GET /api/auth/rockyou/status`
- `POST /api/transfer/send` · `POST /api/transfer/receiver/check` · `GET /api/transfer/files`

## Safety
- `POST /api/killswitch` · `POST /api/killswitch/reset` (admin token) · `POST /api/assessment/run`
