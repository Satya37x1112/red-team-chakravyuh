"""Hash and recovered-plaintext values are masked, never shown in full."""
from app.services.hash_audit import mask_hash, mask_plaintext
def test_mask_hash_hides_middle():
    h = "a"*32; m = mask_hash(h)
    assert m != h and "•" in m or "*" in m or "…" in m
def test_mask_plaintext_hides_value():
    assert mask_plaintext("Secret123") not in ("Secret123",)
