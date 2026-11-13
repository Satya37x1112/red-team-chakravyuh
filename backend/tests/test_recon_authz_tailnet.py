"""Recon authorization: public rejected; RFC1918 allowed; loopback rejected."""
from app.telemetry.collector import authorize_recon_target
def test_public_rejected():
    ok, _ = authorize_recon_target("8.8.8.8"); assert ok is False
def test_rfc1918_allowed():
    ok, _ = authorize_recon_target("192.168.77.5"); assert ok is True
def test_loopback_rejected():
    ok, _ = authorize_recon_target("127.0.0.1"); assert ok is False
def test_invalid_rejected():
    ok, _ = authorize_recon_target("not-an-ip"); assert ok is False
