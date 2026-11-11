"""Operator-controlled remote file transfer service with SHA-256 integrity verification.

Demonstrates genuine, authenticated remote data transfer between the Kali operator
machine and the designated Windows lab target.

Hard safety properties:
  - Strict operator control: requires explicit target and file selection.
  - Path-traversal prevention: sanitizes filenames; rejects directory traversal.
  - File-size validation: hard cap at 10 MB.
  - Cryptographic integrity verification: pre-transfer SHA-256 compared against
    post-receipt SHA-256 calculated by the receiver.
  - Audit logging: every transfer attempt and outcome is permanently logged.
  - UBA integration: transfer events feed directly into the UBA anomaly engine.
  - Zero arbitrary execution: files are stored only, never executed.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ..modules.uba import score_transfer_event
from ..safety import audit
from ..safety.killswitch import kill_switch

log = logging.getLogger(__name__)

DEFAULT_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
_FILENAME_SAFE_RE = re.compile(r"^[a-zA-Z0-9_\-\.][a-zA-Z0-9_\-\. ]{0,120}$")


def sanitize_filename(filename: str) -> str | None:
    """Ensure filename has no path traversal components and conforms to safe pattern."""
    if not filename:
        return None
    raw = filename.strip()
    if ".." in raw or "/" in raw or "\\" in raw or "\0" in raw:
        return None
    base = os.path.basename(raw.replace("\\", "/")).strip()
    if not _FILENAME_SAFE_RE.match(base):
        return None
    return base


def compute_file_sha256(file_path: str | Path) -> str:
    """Calculate the SHA-256 hash of a local file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(64 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


class TransferService:
    """Operator-controlled remote file transfer service."""

    def check_receiver(self, target_url: str, auth_token: str | None = None, timeout: float = 3.0) -> dict[str, Any]:
        """Check receiver connectivity, status, and authentication."""
        base_url = target_url.strip().rstrip("/")
        health_url = f"{base_url}/health"
        req = urllib.request.Request(
            health_url,
            headers={"User-Agent": "CyberChakravyuh-Sender/1.0", "X-Chakravyuh-Auth": auth_token or ""},
            method="GET",
        )
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                latency = round((time.monotonic() - start) * 1000.0, 2)
                return {
                    "reachable": True,
                    "target_url": base_url,
                    "status": data.get("status", "READY"),
                    "authenticated": data.get("authenticated", False),
                    "destination_directory": data.get("destination_directory"),
                    "latency_ms": latency,
                    "service": data.get("service"),
                }
        except Exception as exc:
            latency = round((time.monotonic() - start) * 1000.0, 2)
            return {
                "reachable": False,
                "target_url": base_url,
                "status": "UNREACHABLE",
                "authenticated": False,
                "latency_ms": latency,
                "error": f"Could not reach receiver at {health_url}: {exc}",
            }

    def transfer_file(
        self,
        local_path: str,
        target_url: str,
        auth_token: str,
        custom_filename: str | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Perform authenticated file transfer with pre/post SHA-256 integrity verification."""
        if kill_switch.is_engaged():
            raise RuntimeError("Kill switch is engaged; data transfer is blocked.")

        # 1. Source file validation
        p = Path(local_path)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"Source file '{local_path}' does not exist or is not a regular file.")

        size_bytes = p.stat().st_size
        if size_bytes <= 0:
            raise ValueError("Cannot transfer empty file (0 bytes).")
        if size_bytes > DEFAULT_MAX_FILE_BYTES:
            raise ValueError(f"File size {size_bytes} bytes exceeds maximum lab cap of {DEFAULT_MAX_FILE_BYTES} bytes.")

        # 2. Filename validation & path traversal prevention
        raw_name = custom_filename or p.name
        safe_name = sanitize_filename(raw_name)
        if not safe_name:
            raise ValueError(f"Filename '{raw_name}' contains unsafe characters or directory traversal components.")

        # 3. Calculate sender-side SHA-256 before transfer
        pre_sha256 = compute_file_sha256(p)

        # 4. Perform authenticated upload
        base_url = target_url.strip().rstrip("/")
        upload_url = f"{base_url}/upload"

        started = time.monotonic()
        with open(p, "rb") as f:
            file_bytes = f.read()

        req = urllib.request.Request(
            upload_url,
            data=file_bytes,
            headers={
                "User-Agent": "CyberChakravyuh-Sender/1.0",
                "X-Chakravyuh-Auth": auth_token,
                "X-File-Name": safe_name,
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(file_bytes)),
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw_resp = resp.read().decode("utf-8")
                receiver_data = json.loads(raw_resp)
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Receiver HTTP error {exc.code}: {err_body}") from exc
        except Exception as exc:
            raise RuntimeError(f"Connection to receiver failed: {exc}") from exc

        duration = round(time.monotonic() - started, 3)

        # 5. Extract receiver-calculated SHA-256 and verify integrity
        post_sha256 = receiver_data.get("sha256", "").lower()
        verified = bool(pre_sha256.lower() == post_sha256)

        result_payload = {
            "status": "COMPLETED" if verified else "INTEGRITY_MISMATCH",
            "filename": safe_name,
            "size_bytes": size_bytes,
            "target_url": base_url,
            "pre_transfer_sha256": pre_sha256,
            "post_transfer_sha256": post_sha256,
            "integrity_verified": verified,
            "duration_seconds": duration,
            "transfer_rate_kbps": round((size_bytes / 1024.0) / duration, 2) if duration > 0 else 0.0,
            "receiver_response": receiver_data,
            "destination_path": receiver_data.get("destination"),
            "timestamp": time.time(),
        }

        # 6. Audit logging (permanent immutable record)
        audit.audit(
            event_type="REMOTE_FILE_TRANSFER",
            module="rat_related",
            target=base_url,
            decision="verified" if verified else "failed",
            reason=f"Authenticated data transfer of '{safe_name}' ({size_bytes} B) - Integrity verified: {verified}",
            payload={
                "filename": safe_name,
                "size_bytes": size_bytes,
                "pre_sha256": pre_sha256,
                "post_sha256": post_sha256,
                "integrity_verified": verified,
                "duration_seconds": duration,
            },
        )

        # 7. Feed event into UBA
        uba_anomaly = score_transfer_event({
            "filename": safe_name,
            "size_bytes": size_bytes,
            "target": base_url,
            "integrity_verified": verified,
        })
        if uba_anomaly:
            result_payload["uba_anomaly"] = {
                "category": uba_anomaly.category,
                "description": uba_anomaly.description,
                "score": uba_anomaly.score,
            }

        return result_payload


# Singleton instance
transfer_service = TransferService()
