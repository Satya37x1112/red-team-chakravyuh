#!/usr/bin/env bash
# Stop the AI RED TEAM backend and frontend dev servers.
pkill -f 'uvicorn app.main:app' 2>/dev/null && echo "backend stopped" || echo "backend not running"
pkill -f 'vite' 2>/dev/null && echo "frontend stopped" || echo "frontend not running"
