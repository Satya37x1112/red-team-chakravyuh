"""Operations Center — one aggregated view of everything the range produces.

Pulls live telemetry, session rollups, integration status, and the central
integration-artifact store into a single payload so the dashboard's Operations
Center page can render the whole picture from one call.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

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


def _merge_technique(acc: dict, tid: str, name: str | None, tactic: str | None, observations: int, source: str) -> None:
    if not tid:
        return
    cur = acc.setdefault(tid, {"id": tid, "name": name, "tactic": tactic, "observations": 0, "sources": []})
    if name and not cur.get("name"):
        cur["name"] = name
    if tactic and not cur.get("tactic"):
        cur["tactic"] = tactic
    cur["observations"] += observations
    if source not in cur["sources"]:
        cur["sources"].append(source)


@router.get("/report")
def pentest_report(db: Session = Depends(get_db)) -> dict:
    """Assemble every persisted test artifact into one structured pentest report."""
    arts = db.scalars(select(IntegrationArtifact).order_by(IntegrationArtifact.created_at)).all()
    snap = service.latest

    findings: list[dict] = []
    techniques: dict[str, dict] = {}
    timeline: list[dict] = []
    tools_used: dict[str, int] = {}
    targets: set[str] = set()

    for a in arts:
        tools_used[a.integration] = tools_used.get(a.integration, 0) + 1
        timeline.append(
            {
                "at": a.created_at.isoformat(),
                "integration": a.integration,
                "kind": a.kind,
                "title": a.title,
                "summary": a.summary,
            }
        )
        p = a.payload or {}

        if a.integration == "vervet" and a.kind == "emulate":
            tgt = p.get("target")
            if tgt:
                targets.add(tgt)
            open_ports = [f.get("detail") for f in p.get("findings", []) if f.get("detail")]
            if open_ports:
                findings.append(
                    {
                        "severity": "info",
                        "title": f"Network services exposed on {tgt}",
                        "target": tgt,
                        "detail": "Open service ports discovered: " + ", ".join(open_ports),
                        "technique": p.get("technique"),
                        "source": "vervet",
                        "at": a.created_at.isoformat(),
                    }
                )
            for t in (p.get("coverage") or {}).get("techniques", []):
                _merge_technique(
                    techniques, t.get("id"), t.get("name"), t.get("tactic"), t.get("observations", 0), "vervet"
                )

        elif a.integration == "caldera" and a.kind == "analysis":
            stats = p.get("stats", {})
            for rep in p.get("reports", []):
                if rep.get("operation"):
                    targets.add(f"caldera:{rep['operation']}")
            for t in stats.get("techniques", []):
                m = re.match(r"\s*(T[0-9.]+)\s*·?\s*(.*)", t.get("name", ""))
                if m:
                    _merge_technique(techniques, m.group(1), m.group(2) or None, None, t.get("count", 0), "caldera")
            findings.append(
                {
                    "severity": "medium" if stats.get("success", 0) else "info",
                    "title": "Adversary emulation executed (CALDERA)",
                    "target": ", ".join(r.get("operation", "?") for r in p.get("reports", [])) or "lab",
                    "detail": (
                        f"{stats.get('total_steps', 0)} steps across {stats.get('distinct_techniques', 0)} ATT&CK "
                        f"techniques / {stats.get('distinct_tactics', 0)} tactics; "
                        f"{stats.get('success', 0)} succeeded, {stats.get('failed', 0)} failed."
                    ),
                    "source": "caldera",
                    "at": a.created_at.isoformat(),
                }
            )

        elif a.integration == "locust" and a.kind == "load_test":
            params = p.get("params", {})
            tgt = params.get("target")
            if tgt:
                targets.add(tgt)
            agg = None
            for row in p.get("stats") or []:
                if isinstance(row, dict) and row.get("name") in ("Aggregated", "Total", "/"):
                    agg = row
                    break
            reqs = agg.get("num_requests") if agg else None
            fails = agg.get("num_failures") if agg else None
            findings.append(
                {
                    "severity": "low",
                    "title": f"Load / availability test against {tgt}",
                    "target": tgt,
                    "detail": (
                        f"{params.get('users')} users for {params.get('run_seconds')}s — "
                        f"{reqs} requests, {fails} failures."
                    ),
                    "technique": "T1498 (Network Denial of Service — controlled)",
                    "source": "locust",
                    "at": a.created_at.isoformat(),
                }
            )

    now = datetime.now(timezone.utc)
    sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    findings.sort(key=lambda f: sev_rank.get(f.get("severity", "info"), 5))

    return {
        "meta": {
            "title": "Red Team Chakravyuh — Penetration Test Report",
            "generated_at": now.isoformat(),
            "operator": snap.logged_in_user if snap else None,
            "console_host": snap.hostname if snap else None,
        },
        "scope": {
            "targets": sorted(targets),
            "telemetry_host": snap.hostname if snap else None,
            "os_name": snap.os_name if snap else None,
        },
        "summary": {
            "total_tests": len(arts),
            "tools_used": tools_used,
            "finding_count": len(findings),
            "technique_count": len(techniques),
            "severity_breakdown": {
                s: sum(1 for f in findings if f.get("severity") == s)
                for s in ("critical", "high", "medium", "low", "info")
            },
        },
        "methodology": [
            {"tool": i["title"], "status": "available" if i["available"] else "not run", "role": i["category"]}
            for i in all_status()
        ],
        "findings": findings,
        "attack_coverage": sorted(techniques.values(), key=lambda t: t["id"]),
        "timeline": timeline,
    }
