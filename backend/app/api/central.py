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


# Offensive knowledge base: open service port -> (service, severity, attacker note, hardening).
_PORT_INTEL: dict[int, tuple[str, str, str, str]] = {
    21: ("FTP", "medium", "Often cleartext / anonymous login — sniff or guess creds, read/write files.",
         "Disable FTP or enforce FTPS; no anonymous access."),
    22: ("SSH", "medium", "Credential brute force and key reuse; a direct remote foothold if creds fall.",
         "Key-only auth, disable password login, fail2ban/rate-limit."),
    23: ("Telnet", "high", "Cleartext protocol — credentials are trivially sniffed.",
         "Disable Telnet entirely; use SSH."),
    80: ("HTTP", "medium", "Web attack surface — enumerate the app for injection, auth bypass, upload flaws.",
         "Put behind TLS/WAF; patch and review the app."),
    135: ("MSRPC", "high", "RPC/DCOM endpoint mapper — enumeration and coercion (PetitPotam-class) pivots.",
          "Block 135 at the host firewall from untrusted networks."),
    139: ("NetBIOS/SMB", "high", "Legacy SMB — null-session user/share enumeration.",
          "Disable NetBIOS over TCP/IP; restrict SMB to trusted subnets."),
    443: ("HTTPS", "medium", "Encrypted web surface — still enumerate the app and its auth.",
          "Patch the app; strong TLS; WAF."),
    445: ("SMB", "critical", "Lateral movement, SMB relay, share/user enumeration, and EternalBlue-class RCE on "
          "unpatched hosts — a top red-team pivot.",
          "Patch (MS17-010+), require SMB signing, firewall 445 off untrusted networks, disable SMBv1."),
    1433: ("MSSQL", "high", "Direct database exposure — xp_cmdshell RCE if creds/sa fall.",
           "Firewall the DB, strong auth, disable xp_cmdshell."),
    3306: ("MySQL", "high", "Direct database exposure — credential attacks and data theft.",
           "Bind to localhost / firewall; strong auth."),
    3389: ("RDP", "high", "Credential brute force and BlueKeep-class RCE — a prime interactive foothold.",
           "NLA on, MFA/RD Gateway, lock down source IPs, patch."),
    5432: ("PostgreSQL", "high", "Direct database exposure — credential attacks and data theft.",
           "Bind to localhost / firewall; strong auth."),
    8080: ("HTTP-alt", "medium", "App/proxy surface — enumerate for the same web flaws as port 80.",
           "TLS + auth in front; patch the app."),
}


def _port_of(detail: str | None) -> int | None:
    if not detail:
        return None
    m = re.search(r"(\d+)\s*$", detail)
    return int(m.group(1)) if m else None


@router.get("/analysis")
def smart_analysis(ai: bool = False, db: Session = Depends(get_db)) -> dict:
    """Turn the integrated emulation data into prioritized, red-team-framed issues.

    Fast by default (grounded heuristic headline). Pass ?ai=true to also try an
    LLM-written headline — slower and best-effort, since free models can lag.
    """
    arts = db.scalars(
        select(IntegrationArtifact)
        .where(IntegrationArtifact.integration.in_(["vervet", "caldera", "pentestgpt"]))
        .order_by(IntegrationArtifact.created_at.desc())
    ).all()

    issues: list[dict] = []
    host_ports: dict[str, set[int]] = {}
    caldera_techniques = 0
    caldera_ok = 0

    for a in arts:
        p = a.payload or {}
        if a.integration == "vervet" and a.kind == "emulate":
            tgt = p.get("target") or "target"
            for f in p.get("findings", []):
                port = _port_of(f.get("detail"))
                if port is not None:
                    host_ports.setdefault(tgt, set()).add(port)
        elif a.integration == "caldera" and a.kind == "analysis":
            stats = p.get("stats", {})
            caldera_techniques = max(caldera_techniques, stats.get("distinct_techniques", 0))
            caldera_ok = max(caldera_ok, stats.get("success", 0))

    # One issue per exposed, interesting service, de-duplicated across hosts.
    for host, ports in sorted(host_ports.items()):
        for port in sorted(ports):
            intel = _PORT_INTEL.get(port)
            if not intel:
                continue
            svc, sev, note, fix = intel
            issues.append(
                {
                    "severity": sev,
                    "title": f"{svc} exposed on {host} (tcp/{port})",
                    "evidence": f"vervet T1046 observed tcp/{port} open on {host}.",
                    "attacker_note": note,
                    "recommendation": fix,
                }
            )

    if caldera_techniques:
        issues.append(
            {
                "severity": "medium",
                "title": f"Adversary TTPs executed unimpeded ({caldera_techniques} techniques)",
                "evidence": f"CALDERA ran {caldera_techniques} ATT&CK techniques; {caldera_ok} steps succeeded.",
                "attacker_note": "Successful discovery/execution with no visible blocking means the kill-chain early "
                "stages are open — expect follow-on credential access and lateral movement.",
                "recommendation": "Deploy EDR + Sysmon, alert on the executed technique IDs, and tune detections "
                "until these steps fail or fire alarms.",
            }
        )

    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    issues.sort(key=lambda i: rank.get(i["severity"], 5))
    counts = {s: sum(1 for i in issues if i["severity"] == s) for s in ("critical", "high", "medium", "low", "info")}

    # Smart headline: a grounded heuristic by default; upgrade to an LLM sentence
    # only when it comes back clean (free models often dump chain-of-thought).
    headline = None
    model = None
    if issues:
        n_crit = counts["critical"] + counts["high"]
        headline = (
            f"{n_crit} high-impact exposure(s) across {len(host_ports)} host(s) — SMB/RPC/RDP surface offers the "
            f"fastest path to a foothold and lateral movement."
            if n_crit
            else f"{len(issues)} issue(s) identified; attack surface is limited but enumerable."
        )
        if ai:
            top = ", ".join(i["title"] for i in issues[:4])
            try:
                from ..integrations import _llm

                sys_p = (
                    "You are a red team lead. Reply with ONLY one plain sentence (max 35 words), no lists, no "
                    "markdown, no preamble: state the biggest risk and the most likely attack path from these "
                    "authorized-lab findings. Offensive framing."
                )
                text, m, _errs = _llm.complete(
                    sys_p, f"Findings: {top}. Counts: {counts}.", max_tokens=120, temperature=0.3
                )
                cand = (text or "").strip()
                first = cand.splitlines()[0].strip() if cand else ""
                bad = (
                    not cand
                    or len(cand.splitlines()) > 1
                    or len(first) > 260
                    or bool(re.match(r"^\d+[.)]", first))
                    or any(x in cand for x in ("**", "Role:", "Task:", "Analyze", "```", "Findings:"))
                )
                if not bad:
                    headline, model = first, m
            except Exception:
                pass

    return {
        "headline": headline,
        "model": model,
        "issue_count": len(issues),
        "severity_counts": counts,
        "hosts_scanned": sorted(host_ports.keys()),
        "issues": issues,
    }
