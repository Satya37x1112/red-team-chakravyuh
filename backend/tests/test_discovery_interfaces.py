"""Interface enumeration returns loopback and is structured."""
from app.services.discovery import enumerate_interfaces
def test_interfaces_include_loopback():
    ifaces = enumerate_interfaces()
    assert isinstance(ifaces, list) and ifaces
    assert any(i.get("ip") == "127.0.0.1" or i.get("interface") == "lo" for i in ifaces)
