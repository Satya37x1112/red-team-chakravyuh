"""Bounded, authorized SOC DETECTION-SIGNATURE generator (purple-team).

Given (kind, target) it performs a SMALL, bounded, NON-destructive amount of real
network activity so the target's SOC / Blue Team logs the telltale detection
events for that TTP. It is explicitly NOT a real attack:
  * DDoS  -> a bounded TCP connection burst (NOT a sustained flood; no DoS).
  * Brute force -> a few FAILED auth attempts with BOGUS random usernames
                   (no real credentials; bogus accounts can't lock real ones).
  * RAT   -> read-only SMB enumeration (no implant, no persistence, no commands).
Fail-closed: public/global IPs are refused; only RFC1918 or current tailnet peers
are allowed (reuses the recon authorizer). All counts are hard-capped here.
"""
from __future__ import annotations

import random
import socket
import string
import subprocess
import time

from ..telemetry import collector

# Hard caps — a request can never raise these.
MAX_DDOS_CONNECTS = 40      # bounded burst; ~5/s over <=8s — a signature, not a flood
DDOS_WINDOW_S = 8.0
DDOS_PORTS = [80, 445, 3389, 8080]
MAX_BRUTE_ATTEMPTS = 5      # a few 4625s; bogus users -> no real-account lockout
BRUTE_PORT = 445
RAT_PORTS = [445, 5985]


def _source_ip() -> str | None:
    try:
        r = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=5)
        return (r.stdout.strip().splitlines() or [None])[0]
    except Exception:
        return None


def _rand_user() -> str:
    return "svc_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))


def _tcp_reachable(target: str, port: int, timeout: float = 1.5) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((target, port)); return True
    except Exception:
        return False
    finally:
        s.close()


def _ddos_signature(target: str) -> dict:
    established = refused = 0
    t0 = time.monotonic()
    for i in range(MAX_DDOS_CONNECTS):
        if time.monotonic() - t0 > DDOS_WINDOW_S:
            break
        port = DDOS_PORTS[i % len(DDOS_PORTS)]
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        try:
            s.connect((target, port)); established += 1
        except ConnectionRefusedError:
            refused += 1
        except Exception:
            pass
        finally:
            s.close()
    return {
        "connects_attempted": MAX_DDOS_CONNECTS,
        "established": established,
        "refused": refused,
        "detectable_as": "elevated connection rate / port sweep (Zeek conn.log, Suricata scan/DoS rules)",
    }


def _bruteforce_signature(target: str) -> dict:
    users: list[str] = []
    reachable = _tcp_reachable(target, BRUTE_PORT)
    if reachable and _nxc_present():
        for _ in range(MAX_BRUTE_ATTEMPTS):
            u = _rand_user()
            try:
                # ONE bogus SMB auth attempt -> Windows 4625 failed logon. No lockout:
                # the username does not exist, so no real account is affected.
                subprocess.run(["nxc", "smb", target, "-u", u, "-p", "Wrong-" + _rand_user()],
                               capture_output=True, text=True, timeout=20)
            except Exception:
                pass
            users.append(u)
        method = "SMB auth (bogus usernames) via NetExec"
    else:
        # Fallback when the auth service is unreachable or nxc is absent: a few
        # connection attempts to the auth ports still register as a login-probe.
        for _ in range(MAX_BRUTE_ATTEMPTS):
            _tcp_reachable(target, BRUTE_PORT, 1.0)
        method = "SMB connection attempts (service unreachable — no auth sent)"
    return {
        "failed_auth_attempts": len(users),
        "bogus_users": users,
        "method": method,
        "detectable_as": "Windows Security 4625 failed-logon burst / brute-force (SIEM correlation)",
    }


def _rat_signature(target: str) -> dict:
    enumerated = False
    out = ""
    if _tcp_reachable(target, 445) and _nxc_present():
        try:
            r = subprocess.run(["nxc", "smb", target], capture_output=True, text=True, timeout=25)
            out = (r.stdout or "")[:200]
            enumerated = True
        except Exception:
            pass
    else:
        for p in RAT_PORTS:
            _tcp_reachable(target, p, 1.0)
    return {
        "enumerated": enumerated,
        "banner_excerpt": out or None,
        "detectable_as": "anonymous SMB session / remote enumeration (4624 anonymous logon, SMB tree connect)",
    }


def _nxc_present() -> bool:
    import shutil
    return shutil.which("nxc") is not None


_LABELS = {
    "ddos": "DDoS (bounded connection burst — NOT a real flood, no service disruption)",
    "bruteforce": "Brute force (bogus credentials — NOT real cracking, no account lockout)",
    "rat_related": "RAT / remote access (read-only enumeration — NO implant, NO persistence)",
}
_ALIAS = {"ratuba": "rat_related", "rat": "rat_related"}


def generate_signature(kind: str, target: str) -> dict:
    kind = _ALIAS.get(kind, kind)
    ok, reason = collector.authorize_recon_target(target)
    if not ok:
        return {"authorized": False, "reason": reason, "kind": kind, "target": target}
    src = _source_ip()
    if kind == "ddos":
        sig = _ddos_signature(target)
    elif kind == "bruteforce":
        sig = _bruteforce_signature(target)
    elif kind == "rat_related":
        sig = _rat_signature(target)
    else:
        return {"authorized": True, "error": f"unknown kind '{kind}'", "target": target}
    label = _LABELS[kind]
    sig.update({
        "authorized": True,
        "kind": kind,
        "label": label,
        "target": target,
        "source_ip": src,
        "simulated_attack": True,
        "note": (f"Generated a bounded {label} signature against {target} from "
                 f"{src or 'this Kali host'}. Check the SOC for the events listed in 'detectable_as' "
                 f"— proof of red-team activity. No service was disrupted, no real credential was used, "
                 f"and nothing was installed on the target."),
    })
    return sig
