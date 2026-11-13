"""LocalSource reports real host metrics for the machine the platform runs on."""
import pytest
from app.telemetry.collector import LocalSource

psutil = pytest.importorskip("psutil")


def test_local_source_returns_host_metrics():
    t = LocalSource().collect()
    assert t.source == "local" and t.available is True
    assert t.cpu_percent is not None and 0 <= t.cpu_percent <= 100
    assert t.memory_percent is not None and 0 <= t.memory_percent <= 100
    assert (t.process_count or 0) > 0
