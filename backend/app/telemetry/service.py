"""Background poller: collect real telemetry on an interval, persist it, and
broadcast it. Also keeps a short in-memory ring of recent snapshots so the UBA
engine can baseline without re-querying the DB.
"""
from __future__ import annotations

import asyncio
from collections import deque

from ..config import settings
from ..db import SessionLocal
from ..models import TelemetrySnapshot, Target
from ..ws import hub
from .collector import TelemetrySource, build_source
from .schema import Telemetry

RING_SIZE = 60


class TelemetryService:
    def __init__(self, source: TelemetrySource | None = None) -> None:
        self.source = source or build_source()
        self.latest: Telemetry | None = None
        self.history: deque[Telemetry] = deque(maxlen=RING_SIZE)
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def collect_once(self) -> Telemetry:
        snap = self.source.collect()
        self.latest = snap
        self.history.append(snap)
        self._persist(snap)
        return snap

    def _persist(self, snap: Telemetry) -> None:
        db = SessionLocal()
        try:
            target = db.query(Target).first()
            if target is None:
                target = Target(
                    name=snap.hostname or "LAB-TARGET",
                    address=settings.winrm_endpoint or "local",
                    os_name=snap.os_name,
                    role_label="target",
                )
                db.add(target)
                db.flush()
            db.add(
                TelemetrySnapshot(
                    target_id=target.id,
                    source=snap.source,
                    available=snap.available,
                    hostname=snap.hostname,
                    cpu_percent=snap.cpu_percent,
                    memory_percent=snap.memory_percent,
                    disk_percent=snap.disk_percent,
                    process_count=snap.process_count,
                    data=snap.model_dump(mode="json"),
                )
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    async def _loop(self) -> None:
        while not self._stop.is_set():
            snap = await asyncio.to_thread(self.collect_once)
            await hub.broadcast("TELEMETRY_UPDATE", snap.model_dump(mode="json"))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=settings.poll_interval)
            except asyncio.TimeoutError:
                pass

    def start(self) -> None:
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
            self._task = None


service = TelemetryService()
