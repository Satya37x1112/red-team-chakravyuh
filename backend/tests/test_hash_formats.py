"""Hash-format identification recognizes common algorithms by length."""
import hashlib
from app.services.hash_audit import identify_hash_formats

def test_md5_and_ntlm_detected():
    fmts = identify_hash_formats(hashlib.md5(b"x").hexdigest())
    assert "MD5" in fmts or "NTLM" in fmts
def test_sha256_detected():
    assert "SHA-256" in identify_hash_formats(hashlib.sha256(b"x").hexdigest())
def test_garbage_not_identified():
    assert identify_hash_formats("zzz") == [] or "MD5" not in identify_hash_formats("zzz")
