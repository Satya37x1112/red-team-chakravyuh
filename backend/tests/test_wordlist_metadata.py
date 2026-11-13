"""Wordlist service reports rockyou metadata without exposing entries."""
from app.services.wordlist import wordlist_service
def test_metadata_shape():
    meta = wordlist_service.get_metadata(force_refresh=True)
    assert isinstance(meta, dict)
    assert "available" in meta
    # never leak actual password entries in metadata
    assert "entries" not in meta and "passwords" not in meta
