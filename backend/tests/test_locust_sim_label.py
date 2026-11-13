"""DDoS simulation is clearly labelled and generates no network traffic."""
from app.integrations.locust_sim import run_simulation, BANNER
def test_simulation_is_labelled():
    r = run_simulation(users=10, spawn_rate=5, run_seconds=1)
    assert r.get("simulated") is True
    assert "NO NETWORK TRAFFIC" in r.get("banner", BANNER)
    assert "totals" in r
