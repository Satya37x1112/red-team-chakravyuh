#!/usr/bin/env bash
# Restart both dev servers (used after a .env or source change).
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$DIR/stop.sh"; sleep 2; "$DIR/start.sh"
