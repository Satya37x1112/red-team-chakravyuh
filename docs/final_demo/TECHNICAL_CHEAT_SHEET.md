# CYBER CHAKRAVYUH — Technical Cheat Sheet (one page)

- **Repo:** `/home/kali/AI_red_Team/red-team-chakravyuh/` · branch `main` · baseline HEAD `39c5233`
- **Backend:** `http://127.0.0.1:8077` (FastAPI/uvicorn) · **Frontend:** `http://127.0.0.1:5173` (React+TS+Vite)
- **Tests:** **249 passing** (run via Python 3.13: `PYTHONPATH="$PWD:$PWD/.venv/lib/python3.13/site-packages" /usr/bin/python3.13 -m pytest -q`)

### Startup
```bash
cd backend && PATH="$HOME/.local/chakra-bin:$PATH" \
  PYTHONPATH="$PWD/.venv/lib/python3.13/site-packages" \
  /usr/bin/python3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8077 &
cd ../frontend && PATH="$HOME/.local/node/bin:$PATH" npm run dev &
```

### Key API routes
- Discovery: `GET /api/network/{interfaces,subnets,tailnet}`, `POST /api/network/discovery/start`, `GET /api/network/discovery/{id}[/hosts]`, `POST /api/network/targets/select`, `GET /api/network/targets`
- Recon: `POST /api/telemetry/probe` · Activity: `POST /api/attacks/soc-activity` · Assessment: `POST /api/assessment/run`
- Gated adapters: `POST /api/integrations/{hydra/run,locust/run,locust/simulate,remote_access/run}`, `POST /api/execution/submit`, `POST /api/operations[/plan]`
- Auth testing: `POST /api/auth/{offline-audit,live-validate,identify-hash}`, `GET /api/auth/rockyou/status` · Transfer: `POST /api/transfer/send`
- Safety/AI: `POST /api/killswitch[/reset]`, `GET /api/llm/config`, `POST /api/llm/test`, `GET /api/health`

### Core modules (files)
Gateway `app/safety/gateway.py` · Registry `app/safety/registry.py` · Dispatcher `app/safety/dispatcher.py` · Kill switch `app/safety/killswitch.py` · Audit `app/safety/audit.py` · Plan `app/safety/plan_schema.py` · Policy `app/safety/policy.py` · Planner `app/agent/planner.py` · LLM `app/integrations/_llm.py` · Discovery `app/services/discovery.py` · Central authz `app/telemetry/collector.py:authorize_recon_target`

### Technologies
Kali Linux · FastAPI · Pydantic · React/TypeScript/Vite · Tailscale · Hydra v9.7 · Locust 2.47 · NetExec (nxc) · SQLite audit · OpenRouter (`anthropic/claude-sonnet-4.5`) + optional OmniRoute

### Current blockers
Windows `100.80.167.51` **offline** · OpenRouter **auth failing** · file-transfer needs operator-started receiver · recon/assessment/auth-validate/transfer routes not in unified Registry pipeline · venv interpreter 3.14 vs 3.13 packages (use 3.13 invocation).

### Safe demo sequence
Discover tailnet → select+authorize target → bounded recon probe → show audit `RECON_PROBE` → reject public/hotspot → kill switch (block 423) → re-arm → (optional) AI or FALLBACK label.
