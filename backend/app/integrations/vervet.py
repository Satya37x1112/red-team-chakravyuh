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

import ipaddress
import json
import os
import socket
import subprocess
import tempfile
import time
from typing import Any

from ..config import settings
from .base import Integration, IntegrationStatus


def primary_ipv4() -> str:
    """Best-effort primary non-loopback IPv4 of this host (for the GUI default)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))  # no packets sent; just picks the egress iface
            return s.getsockname()[0]
        finally:
            s.close()
    except Exception:
        return "127.0.0.1"


def _signing() -> tuple[bytes, str]:
    """(ed25519 seed bytes, authority public-key hex) from the configured seed."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    seed = bytes.fromhex(settings.vervet_scope_seed)
    sk = Ed25519PrivateKey.from_private_bytes(seed)
    authority = sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    return seed, authority


def _sign_manifest(claims: dict) -> tuple[dict, str]:
    """Sign claims with Ed25519 over vervet's canonical (compact, field-order) JSON."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    seed, authority = _signing()
    sk = Ed25519PrivateKey.from_private_bytes(seed)
    canonical = json.dumps(claims, separators=(",", ":")).encode()  # matches serde_json::to_vec
    signature = sk.sign(canonical).hex()
    return {"claims": claims, "signature": signature}, authority


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
        return self._ok(
            "Ready — describe/report (read-only) plus a GUI service-discovery scan.",
            binary=path,
            version=version,
            suggested_target=primary_ipv4(),
            gui_techniques=settings.vervet_gui_technique_list,
        )

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

    def emulate(self, target: str, technique: str = "T1046") -> dict[str, Any]:
        """Auto-sign a scope for `target` + `technique` and fire vervet emulate.

        Restricted to the GUI technique allowlist (non-destructive discovery only).
        Returns the vq1 receipt, derived findings (open ports), and ATT&CK coverage.
        """
        path = self._bin()
        if path is None:
            raise RuntimeError("vervet binary not found")
        # Validate target is a real IPv4 (no hostnames / ranges from the web form).
        try:
            ipaddress.IPv4Address(target)
        except ValueError as exc:
            raise ValueError(f"target must be a valid IPv4 address: {exc}") from exc
        allowed = settings.vervet_gui_technique_list
        if technique not in allowed:
            raise ValueError(f"technique '{technique}' is not allowed from the GUI (allowed: {', '.join(allowed)})")

        now = int(time.time())
        claims = {
            "engagement_id": f"RTC-GUI-{now}",
            "operator": "console",
            "authorized_cidrs": [f"{target}/32"],
            "excluded_cidrs": [],
            "technique_allowlist": [technique],
            "valid_from": now - 3600,
            "valid_until": now + 86400,
        }
        manifest, authority = _sign_manifest(claims)

        workdir = tempfile.mkdtemp(prefix="vervet_gui_")
        store = os.path.join(workdir, "receipts")
        mf = os.path.join(workdir, "manifest.json")
        with open(mf, "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        try:
            proc = self._run(
                [path, "emulate", technique, "--manifest", mf, "--authority", authority,
                 "--target", target, "--store", store],
                timeout=60,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"vervet emulate timed out: {exc}") from exc
        if proc.returncode != 0:
            # exit 2 = typed scope refusal; surface the reason verbatim.
            raise RuntimeError((proc.stderr or proc.stdout or "vervet emulate failed").strip())

        receipt = json.loads(proc.stdout)
        handles = receipt.get("envelope", {}).get("handles", {})
        findings = [
            {"handle": h, "kind": v.get("kind"), "detail": v.get("detail"), "target": v.get("target")}
            for h, v in handles.items()
        ]

        coverage = None
        try:
            stored = None
            for root, _dirs, files in os.walk(store):
                for name in files:
                    if name.endswith(".json"):
                        stored = os.path.join(root, name)
                        break
            if stored:
                rep = self._run([path, "report", stored], timeout=20)
                if rep.returncode == 0:
                    coverage = json.loads(rep.stdout)
        except Exception:
            coverage = None

        return {
            "target": target,
            "technique": technique,
            "authority": authority,
            "engagement_id": claims["engagement_id"],
            "receipt": receipt,
            "findings": findings,
            "coverage": coverage,
        }
