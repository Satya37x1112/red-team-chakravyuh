"""Kill-switch reset is refused without the configured admin token."""
from app.safety.killswitch import kill_switch
from app.config import settings
def test_reset_refused_without_token(monkeypatch):
    monkeypatch.setattr(settings, "safety_admin_token", "the-token")
    kill_switch.engage("test")
    ok, _ = kill_switch.reset("wrong"); assert ok is False
    ok2, _ = kill_switch.reset("the-token"); assert ok2 is True
