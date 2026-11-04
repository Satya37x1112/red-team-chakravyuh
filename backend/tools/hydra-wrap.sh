#!/usr/bin/env bash
# Forwarder: the native Windows backend invokes this via hydra.cmd. It translates
# any Windows-style path arguments (e.g. the -L/-P wordlists) to WSL paths, then
# execs the real hydra installed in WSL. Authorized lab use only.
set -uo pipefail
args=()
for a in "$@"; do
  if [[ "$a" =~ ^[A-Za-z]:[\\/] ]]; then
    args+=("$(wslpath -u "$a")")
  else
    args+=("$a")
  fi
done
exec hydra "${args[@]}"
