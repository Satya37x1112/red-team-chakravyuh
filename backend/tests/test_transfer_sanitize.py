"""Transfer filename sanitization blocks path traversal; SHA-256 is correct."""
import hashlib, tempfile, os
from app.services.transfer import sanitize_filename, compute_file_sha256

def test_sanitize_rejects_traversal():
    for bad in ["../etc/passwd", "a/b.txt", "..\\win.ini", "/abs", ""]:
        assert sanitize_filename(bad) in (None, os.path.basename(bad)) or "/" not in (sanitize_filename(bad) or "")

def test_sanitize_allows_plain_name():
    assert sanitize_filename("report.txt") == "report.txt"

def test_sha256_matches_hashlib():
    f = tempfile.NamedTemporaryFile(delete=False); f.write(b"airedteam"); f.close()
    try:
        assert compute_file_sha256(f.name) == hashlib.sha256(b"airedteam").hexdigest()
    finally:
        os.unlink(f.name)
