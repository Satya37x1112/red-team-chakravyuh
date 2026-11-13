# AI RED TEAM — Frontend (React + TypeScript + Vite)

Operator dashboard for the AI RED TEAM platform. Talks to the FastAPI backend on
`:8077` via the Vite dev proxy (`/api`, `/ws`).

```bash
PATH="$HOME/.local/node/bin:$PATH" npm run dev   # http://127.0.0.1:5173
npm run typecheck && npm run build
```
Pages: Dashboard, Network Discovery, Target Recon, AI Planner, Integrations, Settings.
