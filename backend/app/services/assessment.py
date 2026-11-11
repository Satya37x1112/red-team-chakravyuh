"""One-Click Orchestrated Assessment Service.

Executes a bounded, authorized sequence of existing cyber-range modules:
  1. Target validation (RFC1918 or current tailnet peer only; public IPs refused).
  2. Reachability probe (TCP connect / tailscale ping; if offline, stop early).
  3. Non-destructive recon probe (discovers open ports and service latencies).
  4. Bounded purple-team SOC signatures (DDoS, Brute Force, RAT; skips 445-dependent
     signatures if port 445 is closed).
  5. Offline hash audit (audits supplied password hash against RockYou dictionary locally).
  6. Live tools notice (explicitly marks real Locust & file transfer as requiring setup;
     never fakes live execution).
  7. Result aggregation and central audit trail persistence.

Every step respects the Unified Kill Switch and reports genuine execution state.
"""
from __future__ import annotations

import logging
import socket
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Callable

from ..agent.orchestrator import orchestrator
from ..integrations import activity_gen
from ..safety import audit
from ..safety.killswitch import kill_switch
from ..safety.registry import ExecState, ExecutionRecord, registry
from ..telemetry import collector
from .hash_audit import hash_auditor

log = logging.getLogger(__name__)

# Canonical Step Statuses:
# READY | RUNNING | DONE | SKIPPED | BLOCKED | STOPPED | UNAVAILABLE

_WELL_KNOWN_SERVICES: dict[int, str] = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    135: "MSRPC",
    139: "NetBIOS",
    143: "IMAP",
    389: "LDAP",
    443: "HTTPS",
    445: "SMB",
    1433: "MSSQL",
    1521: "Oracle",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    5985: "WinRM-HTTP",
    5986: "WinRM-HTTPS",
    8000: "HTTP-Alt",
    8080: "HTTP-Proxy",
    8443: "HTTPS-Alt",
}


def check_target_reachability(target: str, timeout: float = 1.0) -> bool:
    """Non-destructive reachability probe via TCP connect to common ports or tailscale ping.
    
    Returns True if the target responds with an open port, an explicit TCP reset/refused
    (which proves the host OS is online), or an ICMP/tailnet ping pong.
    """
    cleaned = target.strip()
    
    # 1. Quick TCP connect across common ports
    for port in [445, 80, 22, 3389, 8080, 135]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((cleaned, port))
            s.close()
            return True
        except ConnectionRefusedError:
            # An active RST packet proves the target host IP is reachable on the network!
            s.close()
            return True
        except Exception:
            s.close()

    # 2. Tailscale ping if in the Tailscale CGNAT range
    if cleaned.startswith("100."):
        try:
            res = subprocess.run(
                ["tailscale", "ping", f"--timeout={max(1, int(timeout))}s", "--c=1", cleaned],
                capture_output=True,
                text=True,
                timeout=timeout + 1.0,
            )
            if res.returncode == 0 and "pong" in res.stdout.lower():
                return True
        except Exception:
            pass

    # 3. Standard ICMP ping probe (1 packet, short timeout)
    try:
        res = subprocess.run(
            ["ping", "-c", "1", "-W", f"{max(1, int(timeout))}", cleaned],
            capture_output=True,
            timeout=timeout + 1.0,
        )
        if res.returncode == 0:
            return True
    except Exception:
        pass

    return False


class AssessmentService:
    """Orchestrates bounded, authorized multi-module assessments."""

    def __init__(self) -> None:
        self._latest_assessment: dict[str, Any] | None = None

    @property
    def latest(self) -> dict[str, Any] | None:
        return self._latest_assessment

    def run(
        self,
        target: str,
        password_hash: str | None = None,
        reachability_fn: Callable[[str, float], bool] | None = None,
    ) -> dict[str, Any]:
        """Execute the full orchestrated assessment sequence."""
        target = (target or "").strip()
        started_at = datetime.now(timezone.utc).isoformat()
        t_start = time.monotonic()
        is_reachable_fn = reachability_fn or check_target_reachability

        # 1. Register in ExecutionRegistry
        rec = ExecutionRecord(
            scenario_id="orchestrated_assessment",
            module="assessment",
            adapter="orchestrator",
            target=target,
            source="manual",
        )
        registry.create(rec)
        try:
            registry.transition(rec.execution_id, ExecState.VALIDATING)
        except Exception:
            pass

        def is_halted() -> bool:
            return kill_switch.is_engaged() or orchestrator.halted or rec.cancel_requested

        # Step templates
        steps: list[dict[str, Any]] = [
            {
                "id": "target_validation",
                "name": "Target Authorization Validation",
                "status": "READY",
                "details": "Verifying target belongs to RFC1918 private lab space or active Tailnet peers.",
            },
            {
                "id": "reachability",
                "name": "Target Reachability Probe",
                "status": "READY",
                "details": "Probing target host connectivity (TCP connect / Tailscale ping).",
            },
            {
                "id": "recon_probe",
                "name": "Non-Destructive Recon Probe",
                "status": "READY",
                "details": "Scanning authorized port array to discover open services and baseline latency.",
            },
            {
                "id": "soc_ddos",
                "name": "DDoS SOC Detection Signature",
                "status": "READY",
                "details": "Generating bounded purple-team TCP connection burst (40 connects max).",
            },
            {
                "id": "soc_bruteforce",
                "name": "Brute Force SOC Detection Signature",
                "status": "READY",
                "details": "Emitting bounded failed logon signature (5 bogus usernames, no lockout). Requires port 445.",
            },
            {
                "id": "soc_rat",
                "name": "RAT / Remote Enumeration SOC Signature",
                "status": "READY",
                "details": "Performing read-only SMB enumeration signature (no implant/commands). Requires port 445.",
            },
            {
                "id": "offline_hash_audit",
                "name": "Offline Password Hash Audit",
                "status": "READY",
                "details": "Auditing operator-supplied hash against local RockYou wordlist.",
            },
            {
                "id": "locust_load_test",
                "name": "Live HTTP Load Testing",
                "status": "UNAVAILABLE",
                "details": "Requires setup: authorized HTTP service & locustfile. Available in Integrations tab.",
            },
            {
                "id": "remote_file_transfer",
                "name": "Authenticated Remote Data Transfer",
                "status": "UNAVAILABLE",
                "details": "Requires setup: Windows receiver running on port 8090. Available in Remote Access tab.",
            },
        ]

        def step_by_id(sid: str) -> dict[str, Any]:
            for s in steps:
                if s["id"] == sid:
                    return s
            raise KeyError(sid)

        open_ports: list[int] = []
        open_port_details: list[dict[str, Any]] = []

        # -------------------------------------------------------------
        # STEP 0: Check kill switch before starting
        # -------------------------------------------------------------
        if is_halted():
            try:
                registry.transition(rec.execution_id, ExecState.CANCELLED, error="Kill switch engaged")
            except Exception:
                pass
            for s in steps:
                s["status"] = "STOPPED"
                s["details"] = "Kill switch engaged — assessment halted."
            result = {
                "assessment_id": rec.execution_id,
                "target": target,
                "status": "STOPPED",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "open_ports": [],
                "open_port_details": [],
                "steps": steps,
                "summary": {"status": "STOPPED", "reason": "Kill switch engaged"},
            }
            self._latest_assessment = result
            return result

        # -------------------------------------------------------------
        # STEP 1: Target Validation (Fail-Closed)
        # -------------------------------------------------------------
        t0 = time.monotonic()
        s_val = step_by_id("target_validation")
        s_val["status"] = "RUNNING"
        ok, reason = collector.authorize_recon_target(target)
        s_val["duration_seconds"] = round(time.monotonic() - t0, 4)

        if not ok:
            s_val["status"] = "BLOCKED"
            s_val["details"] = f"Target refused (fail-closed): {reason}"
            for s in steps[1:]:
                s["status"] = "SKIPPED"
                s["details"] = "Skipped: Target authorization check failed."
            
            try:
                registry.transition(rec.execution_id, ExecState.REJECTED, error=reason)
            except Exception:
                pass

            audit.audit(
                audit.GATEWAY_REJECTED,
                module="assessment",
                target=target,
                decision="rejected",
                reason=reason,
            )

            result = {
                "assessment_id": rec.execution_id,
                "target": target,
                "status": "BLOCKED",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "open_ports": [],
                "open_port_details": [],
                "steps": steps,
                "summary": {"status": "BLOCKED", "reason": reason},
            }
            self._latest_assessment = result
            return result

        s_val["status"] = "DONE"
        s_val["details"] = "Target authorized: RFC1918 private lab space or verified Tailnet peer."
        try:
            registry.transition(rec.execution_id, ExecState.APPROVED)
            registry.transition(rec.execution_id, ExecState.RUNNING)
        except Exception:
            pass

        # -------------------------------------------------------------
        # STEP 2: Reachability Probe
        # -------------------------------------------------------------
        if is_halted():
            return self._handle_halt(rec, steps, target, started_at, open_ports, open_port_details)

        t0 = time.monotonic()
        s_reach = step_by_id("reachability")
        s_reach["status"] = "RUNNING"
        target_online = is_reachable_fn(target, 1.2)
        s_reach["duration_seconds"] = round(time.monotonic() - t0, 3)

        if not target_online:
            s_reach["status"] = "UNAVAILABLE"
            s_reach["details"] = (
                "TARGET OFFLINE — Target did not respond to TCP connect or ping. "
                "Halting target-side assessment to prevent fabricating results."
            )
            # Steps 3, 4, 5, 6 are skipped
            for sid in ["recon_probe", "soc_ddos", "soc_bruteforce", "soc_rat"]:
                s = step_by_id(sid)
                s["status"] = "SKIPPED"
                s["details"] = "Skipped: Target host is offline."

            # Offline hash audit can still run locally if a hash was provided!
            self._run_offline_hash_audit(step_by_id("offline_hash_audit"), password_hash, is_halted)

            return self._finalize(
                rec, steps, target, started_at, t_start, open_ports, open_port_details, "COMPLETED", target_online=False
            )

        s_reach["status"] = "DONE"
        s_reach["details"] = "Target is online and responding to network probes."

        # -------------------------------------------------------------
        # STEP 3: Recon Probe (Open Ports)
        # -------------------------------------------------------------
        if is_halted():
            return self._handle_halt(rec, steps, target, started_at, open_ports, open_port_details)

        t0 = time.monotonic()
        s_recon = step_by_id("recon_probe")
        s_recon["status"] = "RUNNING"
        probe_res = collector.run_probe(target)
        s_recon["duration_seconds"] = round(time.monotonic() - t0, 3)

        net_probe = probe_res.network
        if net_probe:
            open_ports = sorted(list(net_probe.open_ports))
            for p in net_probe.ports:
                if p.open:
                    service_name = _WELL_KNOWN_SERVICES.get(p.port, p.service or "unknown")
                    open_port_details.append({
                        "port": p.port,
                        "service": service_name,
                        "latency_ms": p.latency_ms,
                    })

        s_recon["status"] = "DONE"
        s_recon["details"] = f"Recon complete — {len(open_ports)} port(s) open: {open_ports}."
        s_recon["data"] = {
            "open_ports": open_ports,
            "ports_probed": net_probe.ports_probed if net_probe else 0,
            "latency_ms": net_probe.latency_ms if net_probe else None,
            "http_status": net_probe.http_status if net_probe else None,
        }

        # -------------------------------------------------------------
        # STEP 4: SOC Signatures (DDoS, Brute Force, RAT)
        # -------------------------------------------------------------
        # 4a. DDoS Signature
        if is_halted():
            return self._handle_halt(rec, steps, target, started_at, open_ports, open_port_details)

        t0 = time.monotonic()
        s_ddos = step_by_id("soc_ddos")
        s_ddos["status"] = "RUNNING"
        sig_ddos = activity_gen.generate_signature("ddos", target)
        s_ddos["duration_seconds"] = round(time.monotonic() - t0, 3)
        s_ddos["status"] = "DONE"
        s_ddos["details"] = (
            f"Generated bounded connection burst signature ({sig_ddos.get('connects_attempted', 40)} connects). "
            f"Detectable in Zeek/Suricata."
        )
        s_ddos["data"] = {
            "connects_attempted": sig_ddos.get("connects_attempted"),
            "established": sig_ddos.get("established"),
            "refused": sig_ddos.get("refused"),
            "detectable_as": sig_ddos.get("detectable_as"),
        }

        # 4b. Brute Force Signature (requires port 445)
        if is_halted():
            return self._handle_halt(rec, steps, target, started_at, open_ports, open_port_details)

        t0 = time.monotonic()
        s_bf = step_by_id("soc_bruteforce")
        if 445 in open_ports:
            s_bf["status"] = "RUNNING"
            sig_bf = activity_gen.generate_signature("bruteforce", target)
            s_bf["duration_seconds"] = round(time.monotonic() - t0, 3)
            s_bf["status"] = "DONE"
            s_bf["details"] = (
                f"Generated bounded failed logon signature ({sig_bf.get('failed_auth_attempts', 5)} bogus usernames, "
                f"no lockout). Detectable as Windows Security Event 4625."
            )
            s_bf["data"] = {
                "failed_auth_attempts": sig_bf.get("failed_auth_attempts"),
                "method": sig_bf.get("method"),
                "detectable_as": sig_bf.get("detectable_as"),
            }
        else:
            s_bf["status"] = "SKIPPED"
            s_bf["details"] = "Skipped — Port 445 (SMB) is not open on target host."

        # 4c. RAT / Remote Access Signature (requires port 445)
        if is_halted():
            return self._handle_halt(rec, steps, target, started_at, open_ports, open_port_details)

        t0 = time.monotonic()
        s_rat = step_by_id("soc_rat")
        if 445 in open_ports:
            s_rat["status"] = "RUNNING"
            sig_rat = activity_gen.generate_signature("rat_related", target)
            s_rat["duration_seconds"] = round(time.monotonic() - t0, 3)
            s_rat["status"] = "DONE"
            s_rat["details"] = (
                "Generated read-only SMB enumeration signature (no commands, no implant). "
                "Detectable as anonymous SMB logon (Event 4624 / tree connect)."
            )
            s_rat["data"] = {
                "enumerated": sig_rat.get("enumerated"),
                "detectable_as": sig_rat.get("detectable_as"),
            }
        else:
            s_rat["status"] = "SKIPPED"
            s_rat["details"] = "Skipped — Port 445 (SMB) is not open on target host."

        # -------------------------------------------------------------
        # STEP 5: Offline Password Hash Audit (local RockYou comparison)
        # -------------------------------------------------------------
        if is_halted():
            return self._handle_halt(rec, steps, target, started_at, open_ports, open_port_details)

        self._run_offline_hash_audit(step_by_id("offline_hash_audit"), password_hash, is_halted)

        return self._finalize(
            rec, steps, target, started_at, t_start, open_ports, open_port_details, "COMPLETED", target_online=True
        )

    def _run_offline_hash_audit(
        self,
        step: dict[str, Any],
        password_hash: str | None,
        is_halted: Callable[[], bool],
    ) -> None:
        """Run offline dictionary comparison if hash was supplied."""
        if not password_hash or not password_hash.strip():
            step["status"] = "SKIPPED"
            step["details"] = "Skipped — No authorized password hash provided by operator."
            return

        h = password_hash.strip()
        t0 = time.monotonic()
        step["status"] = "RUNNING"
        try:
            res = hash_auditor.audit(
                target_hash=h,
                max_candidates=50_000,
                timeout_seconds=15.0,
                cancel_check=is_halted,
            )
            step["duration_seconds"] = round(time.monotonic() - t0, 3)
            step["status"] = "DONE"
            if res.get("matched"):
                step["details"] = (
                    f"Confirmed password match in RockYou: '{res.get('recovered_plaintext')}' "
                    f"after {res.get('candidates_tested')} tests ({res.get('algorithm')})."
                )
            else:
                step["details"] = (
                    f"No match in {res.get('candidates_tested')} RockYou candidate words "
                    f"({res.get('stop_reason')}, {res.get('algorithm')})."
                )
            step["data"] = {
                "matched": res.get("matched"),
                "algorithm": res.get("algorithm"),
                "candidates_tested": res.get("candidates_tested"),
                "stop_reason": res.get("stop_reason"),
                "target_hash_masked": res.get("target_hash_masked"),
                "recovered_masked": res.get("recovered_masked"),
                "recovered_plaintext": res.get("recovered_plaintext"),
            }
        except Exception as exc:
            step["duration_seconds"] = round(time.monotonic() - t0, 3)
            step["status"] = "FAILED"
            step["details"] = f"Offline hash audit error: {exc}"

    def _handle_halt(
        self,
        rec: ExecutionRecord,
        steps: list[dict[str, Any]],
        target: str,
        started_at: str,
        open_ports: list[int],
        open_port_details: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Handle kill-switch emergency halt mid-sequence."""
        for s in steps:
            if s["status"] in ("READY", "RUNNING"):
                s["status"] = "STOPPED"
                s["details"] = "Halted by Kill Switch."

        try:
            registry.transition(rec.execution_id, ExecState.CANCELLED, error="Kill switch engaged")
        except Exception:
            pass

        audit.audit(
            "ASSESSMENT_HALT",
            module="assessment",
            target=target,
            decision="cancelled",
            reason="Kill switch engaged during orchestrated assessment",
            payload={"execution_id": rec.execution_id},
        )

        result = {
            "assessment_id": rec.execution_id,
            "target": target,
            "status": "STOPPED",
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "open_ports": open_ports,
            "open_port_details": open_port_details,
            "steps": steps,
            "summary": {"status": "STOPPED", "reason": "Kill switch engaged during sequence"},
        }
        self._latest_assessment = result
        return result

    def _finalize(
        self,
        rec: ExecutionRecord,
        steps: list[dict[str, Any]],
        target: str,
        started_at: str,
        t_start: float,
        open_ports: list[int],
        open_port_details: list[dict[str, Any]],
        status: str,
        target_online: bool,
    ) -> dict[str, Any]:
        """Finalize assessment execution, log central audit, and record outcome."""
        completed_at = datetime.now(timezone.utc).isoformat()
        duration = round(time.monotonic() - t_start, 3)

        done_count = sum(1 for s in steps if s["status"] == "DONE")
        skip_count = sum(1 for s in steps if s["status"] == "SKIPPED")
        unavail_count = sum(1 for s in steps if s["status"] == "UNAVAILABLE")

        summary = {
            "status": status,
            "target_online": target_online,
            "open_ports_count": len(open_ports),
            "total_steps": len(steps),
            "completed_steps": done_count,
            "skipped_steps": skip_count,
            "unavailable_steps": unavail_count,
            "duration_seconds": duration,
            "execution_id": rec.execution_id,
        }

        try:
            registry.transition(rec.execution_id, ExecState.COMPLETED)
        except Exception:
            pass

        audit_id = audit.audit(
            "ASSESSMENT_RUN",
            module="assessment",
            target=target,
            decision="completed",
            reason=f"One-click assessment completed in {duration}s ({len(open_ports)} open ports)",
            payload={
                "target_online": target_online,
                "open_ports": open_ports,
                "completed_steps": done_count,
                "execution_id": rec.execution_id,
            },
        )
        summary["audit_id"] = audit_id

        result = {
            "assessment_id": rec.execution_id,
            "target": target,
            "status": status,
            "started_at": started_at,
            "completed_at": completed_at,
            "open_ports": open_ports,
            "open_port_details": open_port_details,
            "steps": steps,
            "summary": summary,
        }
        self._latest_assessment = result
        return result


assessment_service = AssessmentService()
