"""vervet adapter — the signed adversary-emulation CLI (Rust).

vervet is CLI-first and self-describing: `vervet describe` emits its protocol,
verb surface, and every registered ATT&CK technique as JSON — no external docs
needed. This adapter surfaces the read-only `describe` (and `report`, folding
vq1 receipts into ATT&CK coverage) into the console.

It never runs `emulate` on its own. `emulate` is the state-changing verb and
vervet itself refuses it without an Ed25519-signed scope manifest; this adapter
does not attempt to sign scopes or fire techniques — that stays an explicit,
out-of-band operator action.
"""
from __future__ import annotations

import json
import subprocess
from typing import Any

from ..config import settings
from .base import Integration, IntegrationStatus


class VervetIntegration(Integration):
    name = "vervet"
    title = "vervet Adversary Emulation"
    category = "emulation"
    repo = "vervet"

    def _bin(self) -> str | None:
        return self._which(settings.vervet_bin)

    def status(self) -> IntegrationStatus:
        path = self._bin()
        if path is None:
            return self._unavailable(
                "vervet binary not found. Build it from the vervet-main crate "
                "(`cargo build --release -p vervet-cli`) and set VERVET_BIN to the "
                "binary, or put it on PATH.",
                looked_for=settings.vervet_bin,
            )
        version = None
        try:
            proc = self._run([path, "--version"], timeout=10)
            version = (proc.stdout or proc.stderr or "").strip() or None
        except Exception:
            pass
        return self._ok("Ready — `describe` and `report` are available (read-only).", binary=path, version=version)

    def describe(self) -> dict[str, Any]:
        """Run `vervet describe` and return its parsed self-description."""
        path = self._bin()
        if path is None:
            raise RuntimeError("vervet binary not found")
        try:
            proc = self._run([path, "describe"], timeout=20)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"vervet describe timed out: {exc}") from exc
        if proc.returncode != 0:
            raise RuntimeError(f"vervet describe failed (exit {proc.returncode}): {proc.stderr[:300]}")
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"could not parse vervet describe output: {exc}") from exc
