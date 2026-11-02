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
    cpu_mean: float = 0.0
    cpu_std: float = 0.0
    mem_mean: float = 0.0
    mem_std: float = 0.0
    proc_mean: float = 0.0
    proc_std: float = 0.0
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

    cpu = [t.cpu_percent for t in usable if t.cpu_percent is not None]
    memv = [t.memory_percent for t in usable if t.memory_percent is not None]
    procs = [t.process_count for t in usable if t.process_count is not None]
    if cpu:
        b.cpu_mean, b.cpu_std = mean(cpu), (pstdev(cpu) if len(cpu) > 1 else 0.0)
    if memv:
        b.mem_mean, b.mem_std = mean(memv), (pstdev(memv) if len(memv) > 1 else 0.0)
    if procs:
        b.proc_mean, b.proc_std = mean(procs), (pstdev(procs) if len(procs) > 1 else 0.0)
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
        if z >= 1.5:
            anomalies.append(
                Anomaly("network", f"{conns} connections vs baseline ~{baseline.conn_mean:.0f} (z={z:.1f})", round(min(1.0, z / 4), 2))
            )

    # Behavioural drift: how far CPU, memory and process count sit from the
    # baseline's normal range. A live host always varies a little, so this is a
    # real, low-level signal rather than a fixed zero.
    def _z(val, m, sd):
        return abs(val - m) / sd if (sd and val is not None) else None
    zs = [z for z in (
        _z(snap.cpu_percent, baseline.cpu_mean, baseline.cpu_std),
        _z(snap.memory_percent, baseline.mem_mean, baseline.mem_std),
        _z(snap.process_count, baseline.proc_mean, baseline.proc_std),
    ) if z is not None]
    if zs:
        drift = min(1.0, (sum(min(z, 4) for z in zs) / len(zs)) / 4)
        score = round(min(0.6, 0.08 + 0.5 * drift), 2)
        if score >= 0.08:
            anomalies.append(
                Anomaly("behaviour", f"activity drift from baseline (cpu/memory/process variance, z≈{max(zs):.1f})", score)
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
