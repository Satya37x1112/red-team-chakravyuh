#!/usr/bin/env bash
# Start the AI RED TEAM backend (FastAPI/uvicorn) and frontend (Vite).
# Encapsulates the Python 3.13 invocation (venv interpreter is 3.14 but packages
# are under 3.13) and the user-level Node path.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT/backend"
SP="$PWD/.venv/lib/python3.13/site-packages"
PATH="$HOME/.local/chakra-bin:$PATH" PYTHONPATH="$SP" \
  /usr/bin/python3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8077 \
  > "$ROOT/scripts/backend.log" 2>&1 &
echo "backend  → http://127.0.0.1:8077 (pid $!)"

cd "$ROOT/frontend"
PATH="$HOME/.local/node/bin:$PATH" npm run dev > "$ROOT/scripts/frontend.log" 2>&1 &
echo "frontend → http://127.0.0.1:5173 (pid $!)"
echo "logs: scripts/backend.log, scripts/frontend.log"
