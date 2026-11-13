#!/usr/bin/env bash
# Quick health check of the AI RED TEAM stack.
b=$(curl -s -m4 -o /dev/null -w '%{http_code}' http://127.0.0.1:8077/api/health)
f=$(curl -s -m4 -o /dev/null -w '%{http_code}' http://127.0.0.1:5173/)
echo "backend  :8077 → $b"
echo "frontend :5173 → $f"
[ "$b" = "200" ] && curl -s -m4 http://127.0.0.1:8077/api/health
