# AI RED TEAM — Server Runbook

Helper scripts in `scripts/` encapsulate the correct startup (the venv interpreter
is Python 3.14 but the installed packages are under `python3.13`, so the backend
must run with `/usr/bin/python3.13` + the venv `site-packages` on `PYTHONPATH`;
the frontend uses the user-level Node at `~/.local/node`).

| Script | Purpose |
|---|---|
| `scripts/start.sh` | Start backend (`:8077`) + frontend (`:5173`); logs to `scripts/*.log` |
| `scripts/stop.sh` | Stop both dev servers |
| `scripts/restart.sh` | Restart both (use after a `.env` or source change) |
| `scripts/health.sh` | Check both endpoints + print backend health JSON |

```bash
./scripts/start.sh      # backend + frontend
./scripts/health.sh     # verify
./scripts/restart.sh    # after editing backend/.env
```

Frontend binds `127.0.0.1:5173` (IPv4). Backend reads config from the gitignored
`backend/.env` at startup, so a config change needs a restart.
