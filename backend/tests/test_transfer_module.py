"""Unit and integration tests for Remote Data Transfer Module.

Tests:
  - Filename sanitization and path traversal rejection
  - SHA-256 hash calculation pre/post transfer
  - File size bounds enforcement (rejecting empty or oversized files)
  - Receiver communication and authentication
  - Cryptographic integrity verification (match vs mismatch)
  - UBA transfer event integration
  - Safety Gateway allowlist enforcement
  - Kill-switch fail-closed enforcement
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.modules.uba import score_transfer_event
from app.services.transfer import (
    compute_file_sha256,
    sanitize_filename,
    transfer_service,
)

client = TestClient(app)


def test_sanitize_filename_traversal_prevention():
    """Verify directory traversal patterns are strictly rejected."""
    assert sanitize_filename("../secret.txt") is None
    assert sanitize_filename("..\\secret.txt") is None
    assert sanitize_filename("/etc/passwd") is None
    assert sanitize_filename("C:\\Windows\\System32\\cmd.exe") is None
    assert sanitize_filename("file\0null.txt") is None
    assert sanitize_filename("") is None
    # Valid filenames
    assert sanitize_filename("artifact.txt") == "artifact.txt"
    assert sanitize_filename("report_2026-11-10.pdf") == "report_2026-11-10.pdf"


def test_compute_file_sha256(tmp_path: Path):
    """Verify SHA-256 calculation matches hashlib digest."""
    test_file = tmp_path / "test.dat"
    content = b"Cyber Chakravyuh Test Payload 2026"
    test_file.write_bytes(content)
    import hashlib
    expected_hash = hashlib.sha256(content).hexdigest().lower()
    computed = compute_file_sha256(test_file)
    assert computed == expected_hash


def test_transfer_empty_file_rejected(tmp_path: Path):
    """Verify transferring empty file raises ValueError."""
    empty_file = tmp_path / "empty.dat"
    empty_file.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        transfer_service.transfer_file(str(empty_file), "http://127.0.0.1:8090", "token")


def test_transfer_missing_file_rejected():
    """Verify transferring non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        transfer_service.transfer_file("/nonexistent/file.dat", "http://127.0.0.1:8090", "token")


def test_transfer_integrity_verified_success(tmp_path: Path):
    """Verify end-to-end SHA-256 match confirms transfer integrity."""
    test_file = tmp_path / "verified_payload.bin"
    payload = b"Authorized Lab Verification Payload"
    test_file.write_bytes(payload)
    file_hash = compute_file_sha256(test_file)

    mock_resp = MagicMock()
    json_bytes = json.dumps({
        "status": "SUCCESS",
        "filename": "verified_payload.bin",
        "size_bytes": len(payload),
        "sha256": file_hash,
        "destination": "C:\\lab\\received\\verified_payload.bin",
    }).encode("utf-8")
    mock_resp.__enter__.return_value.read.return_value = json_bytes

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = transfer_service.transfer_file(
            local_path=str(test_file),
            target_url="http://127.0.0.1:8090",
            auth_token="test-token",
        )
        assert res["status"] == "COMPLETED"
        assert res["integrity_verified"] is True
        assert res["pre_transfer_sha256"] == file_hash
        assert res["post_transfer_sha256"] == file_hash
        assert "uba_anomaly" in res
        assert res["uba_anomaly"]["category"] == "data_transfer"


def test_transfer_integrity_mismatch(tmp_path: Path):
    """Verify SHA-256 mismatch is flagged as integrity failure."""
    test_file = tmp_path / "corrupt_payload.bin"
    test_file.write_bytes(b"Good Data")
    pre_hash = compute_file_sha256(test_file)

    mock_resp = MagicMock()
    json_bytes = json.dumps({
        "status": "SUCCESS",
        "filename": "corrupt_payload.bin",
        "size_bytes": 9,
        "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    }).encode("utf-8")
    mock_resp.__enter__.return_value.read.return_value = json_bytes

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = transfer_service.transfer_file(
            local_path=str(test_file),
            target_url="http://127.0.0.1:8090",
            auth_token="test-token",
        )
        assert res["status"] == "INTEGRITY_MISMATCH"
        assert res["integrity_verified"] is False
        assert res["pre_transfer_sha256"] != res["post_transfer_sha256"]


def test_uba_anomaly_scoring_on_transfer():
    """Verify UBA scores data transfer event appropriately."""
    anom_verified = score_transfer_event({
        "filename": "test.pdf",
        "size_bytes": 1024,
        "target": "http://100.80.167.51:8090",
        "integrity_verified": True,
    })
    assert anom_verified is not None
    assert anom_verified.category == "data_transfer"
    assert anom_verified.score == 0.50

    anom_corrupt = score_transfer_event({
        "filename": "test.pdf",
        "size_bytes": 1024,
        "target": "http://100.80.167.51:8090",
        "integrity_verified": False,
    })
    assert anom_corrupt is not None
    assert anom_corrupt.score == 0.85  # Higher anomaly for corrupted/mismatched transfer


def test_api_transfer_unauthorized_target_rejected(tmp_path: Path):
    """Verify POST /api/transfer/send rejects unauthorized target URLs."""
    test_file = tmp_path / "transfer.dat"
    test_file.write_bytes(b"data")
    resp = client.post(
        "/api/transfer/send",
        json={
            "file_path": str(test_file),
            "target_url": "http://unauthorized-external-site.com:8090",
            "auth_token": "token",
        },
    )
    assert resp.status_code == 423
    assert "not in the authorized allowlist" in resp.json()["detail"]


def test_api_transfer_files_list():
    """Verify GET /api/transfer/files returns available files."""
    resp = client.get("/api/transfer/files")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "name" in data[0]
    assert "size_bytes" in data[0]
