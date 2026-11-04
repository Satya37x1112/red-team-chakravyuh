#!/usr/bin/env bash
# Fail if any Rust source file exceeds the per-file line budget.
# Modularity is a measurement here, not a vibe: a file over budget is doing
# two jobs and wants splitting.
set -euo pipefail

budget="${1:-200}"
bad=0

while IFS= read -r f; do
  n=$(wc -l <"$f")
  if [ "$n" -gt "$budget" ]; then
    printf '%4d  %s\n' "$n" "$f"
    bad=1
  fi
done < <(find crates -name '*.rs' -type f)

if [ "$bad" -ne 0 ]; then
  echo "error: files above the ${budget}-line budget (split them)" >&2
  exit 1
fi
echo "ok: all source files within the ${budget}-line budget"
