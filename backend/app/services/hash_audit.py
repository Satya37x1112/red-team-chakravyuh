"""Offline password hash auditing against authorized hashes using RockYou wordlist.

Supports format identification, dictionary comparisons for NTLM, MD5, SHA-1,
SHA-256, and SHA-512 with strict execution bounds, cancellation, and secret-masking
audit integration.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Callable

from ..safety import audit
from .wordlist import wordlist_service

log = logging.getLogger(__name__)

# Hex patterns for standard cryptographic hash lengths
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
_BCRYPT_RE = re.compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")

ALGORITHM_SIGNATURES: dict[str, int] = {
    "NTLM": 32,      # 16 bytes = 32 hex chars
    "MD5": 32,       # 16 bytes = 32 hex chars
    "SHA-1": 40,     # 20 bytes = 40 hex chars
    "SHA-256": 64,   # 32 bytes = 64 hex chars
    "SHA-512": 128,  # 64 bytes = 128 hex chars
}


def mask_hash(raw_hash: str) -> str:
    """Mask a hash for safe display and logging (e.g. '2b57••••••••••••••••••••••••••••fe')."""
    h = (raw_hash or "").strip()
    if len(h) <= 8:
        return "••••"
    return f"{h[:4]}{'•' * (len(h) - 6)}{h[-2:]}"


def mask_plaintext(plaintext: str) -> str:
    """Mask a recovered password for safe telemetry."""
    if not plaintext:
        return ""
    return "•" * min(len(plaintext), 24)


def identify_hash_formats(raw_hash: str) -> list[str]:
    """Identify possible cryptographic hash types from format and length."""
    cleaned = raw_hash.strip()
    if _BCRYPT_RE.match(cleaned):
        return ["bcrypt"]

    if not _HEX_RE.match(cleaned):
        return []

    length = len(cleaned)
    candidates: list[str] = []
    
    if length == 32:
        # 32 hex characters is both NTLM (Windows) and MD5
        candidates.extend(["NTLM", "MD5"])
    elif length == 40:
        candidates.append("SHA-1")
    elif length == 64:
        candidates.append("SHA-256")
    elif length == 128:
        candidates.append("SHA-512")

    return candidates


def compute_hash(plaintext: str, algorithm: str) -> str:
    """Compute the hexadecimal digest for a given algorithm and plaintext."""
    algo_upper = algorithm.upper()
    if algo_upper == "NTLM":
        # Windows NT Hash: MD4(UTF-16LE(password))
        return hashlib.new("md4", plaintext.encode("utf-16le")).hexdigest()
    elif algo_upper == "MD5":
        return hashlib.md5(plaintext.encode("utf-8", "replace")).hexdigest()
    elif algo_upper == "SHA-1" or algo_upper == "SHA1":
        return hashlib.sha1(plaintext.encode("utf-8", "replace")).hexdigest()
    elif algo_upper == "SHA-256" or algo_upper == "SHA256":
        return hashlib.sha256(plaintext.encode("utf-8", "replace")).hexdigest()
    elif algo_upper == "SHA-512" or algo_upper == "SHA512":
        return hashlib.sha512(plaintext.encode("utf-8", "replace")).hexdigest()
    else:
        raise ValueError(f"Unsupported hashing algorithm: {algorithm}")


class HashAuditor:
    """Bounded, cancellable offline hash auditor."""

    def audit(
        self,
        target_hash: str,
        algorithm: str | None = None,
        max_candidates: int = 100_000,
        timeout_seconds: float = 30.0,
        cancel_check: Callable[[], bool] | None = None,
    ) -> dict:
        """Audit an authorized password hash against the RockYou dictionary."""
        cleaned_hash = target_hash.strip().lower()
        if not cleaned_hash:
            raise ValueError("Target hash cannot be empty.")

        detected = identify_hash_formats(cleaned_hash)
        if not detected:
            raise ValueError(f"Unrecognized hash format (length {len(cleaned_hash)}). Supported: NTLM, MD5, SHA-1, SHA-256, SHA-512.")

        # Determine target algorithm
        chosen_algo = algorithm.upper() if algorithm else detected[0]
        if chosen_algo not in ("NTLM", "MD5", "SHA-1", "SHA-256", "SHA-512"):
            raise ValueError(f"Algorithm '{chosen_algo}' not supported for offline dictionary auditing.")

        # Clamp bounds
        max_c = max(1, min(max_candidates, 500_000))
        max_t = max(1.0, min(timeout_seconds, 120.0))

        wordlist_meta = wordlist_service.get_metadata()
        if not wordlist_meta.get("available"):
            return {
                "matched": False,
                "algorithm": chosen_algo,
                "detected_formats": detected,
                "target_hash_masked": mask_hash(cleaned_hash),
                "candidates_tested": 0,
                "duration_seconds": 0.0,
                "stop_reason": "WORDLIST_UNAVAILABLE",
                "message": wordlist_meta.get("status_message", "RockYou wordlist unavailable."),
                "wordlist_source": None,
                "recovered_plaintext": None,
                "recovered_masked": None,
            }

        start_time = time.monotonic()
        tested = 0
        matched = False
        recovered: str | None = None
        stop_reason = "EXHAUSTED"

        try:
            for candidate in wordlist_service.stream_passwords(max_count=max_c, timeout_seconds=max_t):
                if cancel_check and cancel_check():
                    stop_reason = "CANCELLED"
                    break

                tested += 1
                cand_digest = compute_hash(candidate, chosen_algo).lower()
                if cand_digest == cleaned_hash:
                    matched = True
                    recovered = candidate
                    stop_reason = "MATCH_CONFIRMED"
                    break

            if not matched and stop_reason == "EXHAUSTED":
                elapsed = time.monotonic() - start_time
                if elapsed >= max_t:
                    stop_reason = "TIMED_OUT"
                elif tested >= max_c:
                    stop_reason = "CANDIDATE_LIMIT_REACHED"

        except Exception as exc:
            log.error("Offline hash audit error: %s", exc)
            stop_reason = f"ERROR: {exc}"

        duration = round(time.monotonic() - start_time, 3)

        # Audit event emission (secret-free: raw recovered password is NEVER audited)
        audit.audit(
            event_type="OFFLINE_HASH_AUDIT",
            module="bruteforce",
            target="offline_authorized_hash",
            decision="matched" if matched else "unmatched",
            reason=f"Offline hash audit ({chosen_algo}) - {stop_reason}",
            payload={
                "algorithm": chosen_algo,
                "hash_masked": mask_hash(cleaned_hash),
                "candidates_tested": tested,
                "duration_seconds": duration,
                "matched": matched,
                "stop_reason": stop_reason,
                "wordlist_file": wordlist_meta.get("filename"),
            },
        )

        return {
            "matched": matched,
            "algorithm": chosen_algo,
            "detected_formats": detected,
            "target_hash_masked": mask_hash(cleaned_hash),
            "candidates_tested": tested,
            "duration_seconds": duration,
            "stop_reason": stop_reason,
            "message": (
                f"Password successfully confirmed matching candidate in RockYou after {tested} tests."
                if matched
                else f"No matching password found in {tested} candidate words tested ({stop_reason})."
            ),
            "wordlist_source": wordlist_meta.get("filename"),
            "recovered_plaintext": recovered,  # Returned only to the direct authenticated operator
            "recovered_masked": mask_plaintext(recovered) if recovered else None,
        }


# Singleton instance
hash_auditor = HashAuditor()
