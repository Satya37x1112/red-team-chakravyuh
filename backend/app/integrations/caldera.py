"""MITRE CALDERA report analyzer.

Ports the caldera-ai-project pipeline (parser.py + dataset_builder.py +
ai_analyzer.py) into an in-process, path-independent adapter:

  Caldera operation JSON  ->  structured steps  ->  ATT&CK technique/tactic
  rollup + pass/fail stats  ->  (optional) OpenRouter SOC-analyst narrative.

Everything here is READ-ONLY analysis of a report the operator provides. It
opens no socket and contacts no host; the AI step reuses the project's existing
OpenRouter key (never Groq), and if that key is absent the structured analysis
still returns — only the narrative is marked unavailable.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from ..config import settings
from . import _llm
from .base import Integration, IntegrationStatus

# Vendored sample reports shipped with the caldera-ai-project repo, used as
# demo input when the operator hasn't pointed caldera_report_dir elsewhere.
_VENDORED_SAMPLES = (
    Path(__file__).resolve().parents[3]
    / "caldera-ai-project-main"
    / "caldera-ai-project-main"
    / "data"
)

_SOC_SYSTEM = (
    "You are a senior SOC analyst reviewing a MITRE Caldera adversary-emulation "
    "exercise run in a controlled, authorized laboratory. This is a simulation, "
    "not a confirmed real-world breach — never describe it as one. Produce a "
    "professional, well-structured security assessment in Markdown."
)

_SOC_SECTIONS = """Structure the report with these sections:
1. Executive Summary — purpose, environment, overall observations.
2. Simulation Overview — adversary profile, host/agent info, execution results.
3. MITRE ATT&CK Technique Analysis — per technique: ID, name, tactic, what was
   tested, security impact.
4. Detection Engineering Opportunities — Windows event logs, PowerShell logging,
   endpoint detection ideas, candidate SIEM alerts.
5. Risk Assessment — classify findings Critical/High/Medium/Low with reasoning.
6. Defensive Recommendations — prevention, detection, monitoring, hardening.
Keep it grounded strictly in the data provided; do not invent techniques."""


def _step_status(status: Any) -> str:
    # Caldera convention: status 0 == success, anything else == failed/other.
    return "Success" if status == 0 else "Failed"


def _command_of(step: dict) -> str | None:
    return step.get("plaintext_command") or step.get("command")


def parse_report(data: dict) -> dict[str, Any]:
    """Extract operation metadata + a flat list of executed steps from one report."""
    steps_by_agent = data.get("steps", {}) or {}
    rows: list[dict[str, Any]] = []
    for agent_id, agent_data in steps_by_agent.items():
        for step in agent_data.get("steps", []) or []:
            attack = step.get("attack", {}) or {}
            rows.append(
                {
                    "operation": data.get("name"),
                    "agent": agent_id,
                    "ability": step.get("name"),
                    "technique_id": attack.get("technique_id"),
                    "technique_name": attack.get("technique_name"),
                    "tactic": attack.get("tactic"),
                    "status": _step_status(step.get("status")),
                    "executor": step.get("executor"),
                    "platform": step.get("platform"),
                    "command": _command_of(step),
                }
            )
    return {
        "operation": data.get("name"),
        "planner": data.get("planner"),
        "adversary": (data.get("adversary") or {}).get("name")
        if isinstance(data.get("adversary"), dict)
        else data.get("adversary"),
        "start": data.get("start"),
        "finish": data.get("finish"),
        "host_group": data.get("host_group"),
        "steps": rows,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Pass/fail counts and ATT&CK technique/tactic rollups over parsed steps."""
    total = len(rows)
    success = sum(1 for r in rows if r["status"] == "Success")
    failed = total - success
    techniques = Counter(
        f"{r['technique_id']} · {r['technique_name']}"
        for r in rows
        if r.get("technique_id")
    )
    tactics = Counter(r["tactic"] for r in rows if r.get("tactic"))
    return {
        "total_steps": total,
        "success": success,
        "failed": failed,
        "success_rate": round(100 * success / total, 1) if total else 0.0,
        "distinct_techniques": len(techniques),
        "distinct_tactics": len(tactics),
        "techniques": [{"name": k, "count": v} for k, v in techniques.most_common()],
        "tactics": [{"name": k, "count": v} for k, v in tactics.most_common()],
    }


def _dataset_text(parsed_reports: list[dict], rows: list[dict]) -> str:
    """Compact, model-friendly rendering of the parsed data for the LLM."""
    ops = ", ".join(sorted({p.get("operation") or "?" for p in parsed_reports}))
    lines = [f"Operations: {ops}", ""]
    for r in rows:
        lines.append(
            f"- [{r['status']}] {r.get('tactic')}/{r.get('technique_id')} "
            f"{r.get('technique_name')} :: {r.get('ability')} "
            f"({r.get('executor')}) cmd={r.get('command')!r}"
        )
    return "\n".join(lines)


def analyze(reports: list[dict], *, ai: bool = True) -> dict[str, Any]:
    """Full analysis of one or more raw Caldera report dicts.

    Returns parsed steps, a stats rollup, and — when `ai` and an OpenRouter key
    are available — a Markdown SOC narrative. The narrative failing never fails
    the structured analysis.
    """
    parsed = [parse_report(r) for r in reports]
    rows = [row for p in parsed for row in p["steps"]]
    stats = summarize(rows)
    result: dict[str, Any] = {
        "reports": [{k: v for k, v in p.items() if k != "steps"} for p in parsed],
        "steps": rows,
        "stats": stats,
        "ai": {"status": "skipped", "model": None, "report_markdown": None, "errors": []},
    }
    if not ai or not rows:
        if not rows:
            result["ai"]["status"] = "skipped"
            result["ai"]["errors"] = ["No executed steps in the report(s)."]
        return result

    user_prompt = _SOC_SECTIONS + "\n\nCaldera simulation data:\n\n" + _dataset_text(parsed, rows)
    text, model, errors = _llm.complete(_SOC_SYSTEM, user_prompt, max_tokens=2200, temperature=0.3)
    if text is None:
        result["ai"] = {"status": "unavailable", "model": None, "report_markdown": None, "errors": errors}
    else:
        result["ai"] = {"status": "ok", "model": model, "report_markdown": text, "errors": errors}
    return result


def _sample_dir() -> Path:
    if settings.caldera_report_dir:
        return Path(settings.caldera_report_dir)
    return _VENDORED_SAMPLES


def list_samples() -> list[dict[str, Any]]:
    """Caldera report JSON files available as demo input."""
    d = _sample_dir()
    if not d.exists():
        return []
    out = []
    for f in sorted(d.glob("*report*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            name = data.get("name")
        except Exception:
            name = None
        out.append({"file": f.name, "operation": name})
    return out


def load_sample(file_name: str) -> dict:
    """Load one sample report by basename (no path traversal)."""
    safe = Path(file_name).name
    path = _sample_dir() / safe
    if not path.exists():
        raise FileNotFoundError(f"sample report not found: {safe}")
    return json.loads(path.read_text(encoding="utf-8"))


class CalderaIntegration(Integration):
    name = "caldera"
    title = "MITRE CALDERA Analyzer"
    category = "analysis"
    repo = "caldera-ai-project"

    def status(self) -> IntegrationStatus:
        samples = list_samples()
        ai_ready = bool(settings.openrouter_api_key)
        reason = (
            "Ready — parses Caldera operation reports into ATT&CK coverage."
            if ai_ready
            else "Ready for structured analysis; set OPENROUTER_API_KEY for the AI SOC narrative."
        )
        return self._ok(
            reason,
            ai_narrative=ai_ready,
            sample_count=len(samples),
            sample_dir=str(_sample_dir()),
        )
