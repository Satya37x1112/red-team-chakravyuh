"""Operations Center — one aggregated view of everything the range produces.

Pulls live telemetry, session rollups, integration status, and the central
integration-artifact store into a single payload so the dashboard's Operations
Center page can render the whole picture from one call.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..integrations import all_status
from ..models import AttackSession, IntegrationArtifact
from ..telemetry.service import service

router = APIRouter(prefix="/api/central")


@router.get("/summary")
def central_summary(db: Session = Depends(get_db)) -> dict:
    snap = service.latest
    telemetry = (
        {
            "available": snap.available,
            "source": snap.source,
            "hostname": snap.hostname,
            "os_name": snap.os_name,
            "logged_in_user": snap.logged_in_user,
            "cpu_percent": snap.cpu_percent,
            "memory_percent": snap.memory_percent,
            "disk_percent": snap.disk_percent,
            "process_count": snap.process_count,
            "collected_at": snap.collected_at.isoformat() if snap.collected_at else None,
        }
        if snap
        else None
    )

    total_sessions = db.scalar(select(func.count()).select_from(AttackSession)) or 0
    state_rows = db.execute(select(AttackSession.state, func.count()).group_by(AttackSession.state)).all()
    by_state = {(s.value if hasattr(s, "value") else str(s)): c for s, c in state_rows}

    acount_rows = db.execute(
        select(IntegrationArtifact.integration, func.count()).group_by(IntegrationArtifact.integration)
    ).all()
    artifact_counts = {i: c for i, c in acount_rows}
    total_artifacts = db.scalar(select(func.count()).select_from(IntegrationArtifact)) or 0

    recent = db.scalars(
        select(IntegrationArtifact).order_by(IntegrationArtifact.created_at.desc()).limit(12)
    ).all()
    artifacts = [
        {
            "id": a.id,
            "created_at": a.created_at.isoformat(),
            "integration": a.integration,
            "kind": a.kind,
            "title": a.title,
            "summary": a.summary,
        }
        for a in recent
    ]

    integrations = all_status()
    return {
        "telemetry": telemetry,
        "sessions": {"total": total_sessions, "by_state": by_state},
        "integrations": {
            "total": len(integrations),
            "available": sum(1 for i in integrations if i["available"]),
            "items": integrations,
        },
        "artifacts": {"total": total_artifacts, "by_integration": artifact_counts, "recent": artifacts},
    }
