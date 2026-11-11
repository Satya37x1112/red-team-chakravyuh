"""Unit and integration tests for the Authentication Testing Module.

Tests:
  - RockYou wordlist discovery and gzip streaming
  - Hash format identification (NTLM, MD5, SHA-1, SHA-256, SHA-512)
  - Offline hash auditing against dictionary with match confirmation and limits
  - Secret redaction in audit logs and output
  - Live authentication validation parameters, attempt capping (≤ 3), and safety gateway
"""
from __future__ import annotations

import gzip
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.auth import _FORBIDDEN_LIVE_ACCOUNTS
from app.main import app
from app.services.hash_audit import (
    compute_hash,
    hash_auditor,
    identify_hash_formats,
    mask_hash,
    mask_plaintext,
)
from app.services.wordlist import WordlistService, wordlist_service

client = TestClient(app)


def test_rockyou_metadata_detection():
    """Verify RockYou metadata reports accurately on Kali."""
    meta = wordlist_service.get_metadata(force_refresh=True)
    assert isinstance(meta, dict)
    assert "available" in meta
    if meta["available"]:
        assert meta["format"] in ("gzip", "plain")
        assert meta["size_bytes"] > 0
        assert meta["readable"] is True
        assert meta["status"] == "AVAILABLE"


def test_custom_wordlist_service(tmp_path: Path):
    """Test WordlistService with custom compressed and plain wordlists."""
    # Plain text file
    plain = tmp_path / "custom.txt"
    plain.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    svc_plain = WordlistService(str(plain))
    meta_p = svc_plain.get_metadata()
    assert meta_p["available"] is True
    assert meta_p["format"] == "plain"
    items = list(svc_plain.stream_passwords())
    assert items == ["alpha", "beta", "gamma"]

    # Gzipped file
    gz_file = tmp_path / "custom.txt.gz"
    with gzip.open(gz_file, "wt", encoding="utf-8") as f:
        f.write("secret1\nsecret2\nsecret3\n")
    svc_gz = WordlistService(str(gz_file))
    meta_gz = svc_gz.get_metadata()
    assert meta_gz["available"] is True
    assert meta_gz["format"] == "gzip"
    items_gz = list(svc_gz.stream_passwords())
    assert items_gz == ["secret1", "secret2", "secret3"]


def test_hash_format_identification():
    """Verify cryptographic hash length and format identification."""
    # NTLM / MD5 (32 hex characters)
    assert set(identify_hash_formats("2b576acbe6bcfda7294d6bd18041b8fe")) == {"NTLM", "MD5"}
    # SHA-1 (40 hex characters)
    assert identify_hash_formats("2fd4e1c67a2d28fced849ee1bb76e7391b93eb12") == ["SHA-1"]
    # SHA-256 (64 hex characters)
    assert identify_hash_formats("5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8") == ["SHA-256"]
    # SHA-512 (128 hex characters)
    assert identify_hash_formats("a" * 128) == ["SHA-512"]
    # Invalid characters
    assert identify_hash_formats("not_a_valid_hex_hash!!") == []


def test_hash_masking():
    """Verify secrets are masked properly in hash output."""
    raw = "8846f7eaee8fb117ad06bdd830b7586c"
    masked = mask_hash(raw)
    assert masked.startswith("8846")
    assert masked.endswith("6c")
    assert "•" in masked
    assert raw not in masked

    p_masked = mask_plaintext("MySuperSecretPassword")
    assert "•" in p_masked
    assert "SuperSecret" not in p_masked


def test_offline_ntlm_hash_audit_success():
    """Test genuine NTLM offline hash match confirmation."""
    pw = "password"
    ntlm_h = compute_hash(pw, "NTLM")
    result = hash_auditor.audit(ntlm_h, algorithm="NTLM", max_candidates=1000)
    assert result["matched"] is True
    assert result["recovered_plaintext"] == pw
    assert result["stop_reason"] == "MATCH_CONFIRMED"
    assert result["algorithm"] == "NTLM"


def test_offline_sha256_hash_audit_success():
    """Test genuine SHA-256 offline hash match confirmation."""
    pw = "123456"
    sha_h = compute_hash(pw, "SHA-256")
    result = hash_auditor.audit(sha_h, algorithm="SHA-256", max_candidates=1000)
    assert result["matched"] is True
    assert result["recovered_plaintext"] == pw
    assert result["stop_reason"] == "MATCH_CONFIRMED"


def test_offline_hash_audit_unmatched():
    """Test bounded search when hash does not exist in tested dictionary range."""
    fake_hash = "0" * 64  # SHA-256 of nothing realistic in top 50
    result = hash_auditor.audit(fake_hash, algorithm="SHA-256", max_candidates=50)
    assert result["matched"] is False
    assert result["recovered_plaintext"] is None
    assert result["stop_reason"] in ("CANDIDATE_LIMIT_REACHED", "EXHAUSTED")


def test_offline_audit_api_endpoint():
    """Verify POST /api/auth/offline-audit endpoint."""
    pw = "123456"
    h = compute_hash(pw, "MD5")
    resp = client.post("/api/auth/offline-audit", json={"hash": h, "algorithm": "MD5", "max_candidates": 100})
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched"] is True
    assert data["recovered_plaintext"] == pw
    assert data["algorithm"] == "MD5"


def test_identify_hash_api_endpoint():
    """Verify POST /api/auth/identify-hash endpoint."""
    resp = client.post("/api/auth/identify-hash", json={"hash": "e" * 64})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_supported"] is True
    assert "SHA-256" in data["detected_algorithms"]


def test_live_auth_administrative_account_rejected():
    """Verify live validation rejects administrator/root accounts."""
    for adm in _FORBIDDEN_LIVE_ACCOUNTS:
        resp = client.post(
            "/api/auth/live-validate",
            json={"target": "100.80.167.51", "service": "smb", "account": adm},
        )
        assert resp.status_code == 400
        assert "administrative" in resp.json()["detail"].lower()


def test_live_auth_unauthorized_target_rejected():
    """Verify live validation rejects targets not in allowlist (fail-closed)."""
    resp = client.post(
        "/api/auth/live-validate",
        json={"target": "8.8.8.8", "service": "ssh", "account": "testuser"},
    )
    assert resp.status_code == 423
    assert "not in the authorized allowlist" in resp.json()["detail"]


@patch("app.integrations.hydra.HydraIntegration._run")
def test_live_auth_validation_attempt_cap(mock_run):
    """Verify live authentication validation enforces max 3 attempts and stops on success."""
    from app.config import settings
    # Allow local target for the mock test
    orig = settings.safety_target_allowlist
    try:
        settings.safety_target_allowlist = "127.0.0.1"
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "[22][ssh] host: 127.0.0.1 login: labuser password: Summer2026!\n[ATTEMPT] target 127.0.0.1 - login \"labuser\" - pass \"Summer2026!\" - 1 of 3\n"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        resp = client.post(
            "/api/auth/live-validate",
            json={
                "target": "127.0.0.1",
                "service": "ssh",
                "account": "labuser",
                "passwords": ["p1", "p2", "p3", "p4", "p5"],  # 5 passed, must clamp to 3
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is True
        assert data["outcome"] == "AUTHENTICATION_CONFIRMED"
        assert data["max_attempts_cap"] == 3
        assert data["account_masked"] == "la****r"
        assert "audit_reference" in data
    finally:
        settings.safety_target_allowlist = orig
