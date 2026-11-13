"""Subnet enumeration marks loopback/public as not authorized for discovery."""
from app.services.discovery import enumerate_subnets
def test_loopback_not_authorized():
    subs = enumerate_subnets()
    assert isinstance(subs, list)
    lo = [s for s in subs if "127.0.0.0" in (s.get("subnet") or "")]
    if lo:
        assert lo[0].get("authorized_for_discovery") is False
