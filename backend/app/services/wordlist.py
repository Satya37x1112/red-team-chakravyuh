"""Wordlist management and RockYou integration for CYBER CHAKRAVYUH.

Handles discovery, validation, metadata extraction, and safe streaming of
password wordlists (supporting both compressed .gz and plain .txt formats)
without exposing raw credentials in logs or telemetry.
"""
from __future__ import annotations

import gzip
import logging
import os
import time
from pathlib import Path
from typing import Generator, Iterator

log = logging.getLogger(__name__)

STANDARD_ROCKYOU_LOCATIONS = [
    Path("/usr/share/wordlists/rockyou.txt.gz"),
    Path("/usr/share/wordlists/rockyou.txt"),
    Path("/usr/share/seclists/Passwords/Leaked-Databases/rockyou.txt"),
    Path("/usr/share/seclists/Passwords/Leaked-Databases/rockyou.txt.gz"),
]

# Standard RockYou line count is widely established (14,344,392 entries)
ROCKYOU_CANONICAL_LINES = 14_344_392


def format_size(bytes_n: int) -> str:
    """Format bytes into human-readable string."""
    if bytes_n < 1024:
        return f"{bytes_n} B"
    elif bytes_n < 1024 * 1024:
        return f"{bytes_n / 1024:.1f} KB"
    elif bytes_n < 1024 * 1024 * 1024:
        return f"{bytes_n / (1024 * 1024):.1f} MB"
    return f"{bytes_n / (1024 * 1024 * 1024):.2f} GB"


class WordlistService:
    """Service to discover and stream wordlists safely."""

    def __init__(self, override_path: str | None = None) -> None:
        self.override_path = Path(override_path) if override_path else None
        self._cached_metadata: dict | None = None

    def locate_rockyou(self) -> Path | None:
        """Find the RockYou wordlist file on the local host."""
        if self.override_path and self.override_path.exists():
            return self.override_path

        for candidate in STANDARD_ROCKYOU_LOCATIONS:
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def get_metadata(self, force_refresh: bool = False) -> dict:
        """Retrieve wordlist metadata without reading entire file into memory."""
        if self._cached_metadata and not force_refresh:
            return self._cached_metadata

        target_file = self.locate_rockyou()
        if not target_file:
            meta = {
                "available": False,
                "path": None,
                "filename": None,
                "format": "none",
                "size_bytes": 0,
                "size_formatted": "0 B",
                "estimated_lines": 0,
                "readable": False,
                "status": "NOT_FOUND",
                "status_message": (
                    "RockYou wordlist not found. Ensure rockyou.txt or rockyou.txt.gz "
                    "is present at /usr/share/wordlists/."
                ),
            }
            self._cached_metadata = meta
            return meta

        try:
            size_b = os.path.getsize(target_file)
            is_gz = target_file.name.endswith(".gz")
            
            # Verify readability by reading the first line
            readable = False
            first_entry_len = 0
            if is_gz:
                with gzip.open(target_file, "rt", encoding="latin-1", errors="replace") as gz:
                    first_line = next(gz, "").strip()
                    first_entry_len = len(first_line)
                    readable = True
            else:
                with open(target_file, "r", encoding="latin-1", errors="replace") as f:
                    first_line = next(f, "").strip()
                    first_entry_len = len(first_line)
                    readable = True

            meta = {
                "available": True,
                "path": str(target_file),
                "filename": target_file.name,
                "format": "gzip" if is_gz else "plain",
                "size_bytes": size_b,
                "size_formatted": format_size(size_b),
                "estimated_lines": ROCKYOU_CANONICAL_LINES if "rockyou" in target_file.name.lower() else None,
                "readable": readable,
                "status": "AVAILABLE",
                "status_message": f"RockYou active ({'compressed gzip' if is_gz else 'plain text'}, {format_size(size_b)})",
                "sample_entry_length": first_entry_len,
            }
        except Exception as exc:
            log.warning("Failed to inspect wordlist %s: %s", target_file, exc)
            meta = {
                "available": False,
                "path": str(target_file),
                "filename": target_file.name,
                "format": "unknown",
                "size_bytes": 0,
                "size_formatted": "0 B",
                "estimated_lines": 0,
                "readable": False,
                "status": "PERMISSION_OR_READ_ERROR",
                "status_message": f"Wordlist found at {target_file} but unreadable: {exc}",
            }

        self._cached_metadata = meta
        return meta

    def stream_passwords(
        self,
        max_count: int | None = None,
        timeout_seconds: float | None = None,
    ) -> Iterator[str]:
        """Stream passwords sequentially with bounded count and timeout limits."""
        path = self.locate_rockyou()
        if not path or not path.exists():
            raise FileNotFoundError("RockYou wordlist is not available on this system.")

        start_time = time.monotonic()
        count = 0
        is_gz = path.name.endswith(".gz")

        opener = gzip.open(path, "rt", encoding="latin-1", errors="replace") if is_gz else open(
            path, "r", encoding="latin-1", errors="replace"
        )

        with opener as f:
            for line in f:
                if max_count is not None and count >= max_count:
                    break
                if timeout_seconds is not None and (time.monotonic() - start_time) > timeout_seconds:
                    log.info("Wordlist streaming hit timeout limit of %.1fs", timeout_seconds)
                    break

                pwd = line.rstrip("\r\n")
                if pwd:  # skip completely blank lines
                    count += 1
                    yield pwd


# Singleton instance
wordlist_service = WordlistService()
