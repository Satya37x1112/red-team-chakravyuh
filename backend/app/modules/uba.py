"""A small, real UBA engine.

It builds a baseline from a series of real telemetry snapshots (the set of
processes normally seen, typical connection counts, usual logon event volume)
and scores how far a later snapshot deviates. No ML black box — explainable
rules over observed values, so the dashboard can show *why* something scored.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, pstdev

from ..telemetry.schema import Telemetry


@dataclass
class Baseline:
    known_processes: set[str] = field(default_factory=set)
    conn_mean: float = 0.0
    conn_std: float = 0.0
    logon_event_mean: float = 0.0
    samples: int = 0

    @property
    def ready(self) -> bool:
        return self.samples >= 3


@dataclass
class Anomaly:
    category: str  # process | network | logon
    description: str
    score: float  # 0..1


def build_baseline(history: list[Telemetry]) -> Baseline:
    usable = [t for t in history if t.available]
    b = Baseline(samples=len(usable))
    if not usable:
        return b
    for t in usable:
        b.known_processes.update(p.name.lower() for p in t.processes)
    conns = [len(t.connections) for t in usable]
    logons = [sum(1 for e in t.windows_events if e.event_id in (4624, 4625)) for t in usable]
    b.conn_mean = mean(conns) if conns else 0.0
    b.conn_std = pstdev(conns) if len(conns) > 1 else 0.0
    b.logon_event_mean = mean(logons) if logons else 0.0
    return b


def score_snapshot(baseline: Baseline, snap: Telemetry) -> list[Anomaly]:
    """Return explainable anomalies for one real snapshot against the baseline."""
    anomalies: list[Anomaly] = []
    if not baseline.ready or not snap.available:
        return anomalies

    # New processes never seen during baselining.
    seen = {p.name.lower() for p in snap.processes}
    new = sorted(seen - baseline.known_processes)
    if new:
        score = min(1.0, 0.2 + 0.15 * len(new))
        anomalies.append(
            Anomaly("process", f"{len(new)} new process(es): {', '.join(new[:5])}", round(score, 2))
        )

    # Connection count well above the baseline (z-score style).
    conns = len(snap.connections)
    if baseline.conn_std > 0:
        z = (conns - baseline.conn_mean) / baseline.conn_std
        if z >= 2:
            anomalies.append(
                Anomaly("network", f"{conns} connections vs baseline ~{baseline.conn_mean:.0f} (z={z:.1f})", round(min(1.0, z / 4), 2))
            )

    # Spike in logon events (possible brute-force footprint in the lab).
    logons = sum(1 for e in snap.windows_events if e.event_id in (4624, 4625))
    if baseline.logon_event_mean >= 0 and logons > baseline.logon_event_mean * 3 and logons >= 5:
        anomalies.append(
            Anomaly("logon", f"{logons} logon events vs baseline ~{baseline.logon_event_mean:.0f}", 0.7)
        )
    return anomalies


def risk_score(anomalies: list[Anomaly]) -> float:
    """Combine anomaly scores into a 0..1 session risk, saturating with count."""
    if not anomalies:
        return 0.0
    top = max(a.score for a in anomalies)
    breadth = min(0.3, 0.1 * len(anomalies))
    return round(min(1.0, top + breadth), 2)
