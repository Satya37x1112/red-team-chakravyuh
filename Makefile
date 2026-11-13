# AI RED TEAM — common dev tasks
PY := /usr/bin/python3.13
SP := backend/.venv/lib/python3.13/site-packages

.PHONY: start stop restart health test typecheck build
start:   ; ./scripts/start.sh
stop:    ; ./scripts/stop.sh
restart: ; ./scripts/restart.sh
health:  ; ./scripts/health.sh
test:    ; cd backend && PYTHONPATH="$(PWD)/.venv/lib/python3.13/site-packages:$$PYTHONPATH" $(PY) -m pytest -q
typecheck: ; cd frontend && PATH="$$HOME/.local/node/bin:$$PATH" npm run typecheck
build:   ; cd frontend && PATH="$$HOME/.local/node/bin:$$PATH" npm run build
