"""Credentialed Remote Access / Post-Exploitation Demonstration (RAT Alternative).

This is NOT a conventional RAT. There is no implant, no persistence, no stealth,
no credential harvesting/dumping, no reverse shell, no arbitrary command
execution, and nothing that survives the authorized session. It demonstrates
controlled, credentialed remote ADMINISTRATION against an authorized Windows lab
host using an approved remote-management interface (NetExec / `nxc`), limited to
a fixed, hardcoded allowlist of benign READ-ONLY operations.

Hard safety properties:
  * Runs only on Kali; connects only to the configured authorized target.
  * Requires explicit, valid lab credentials (fail-closed without them).
  * NEVER guesses/sprays credentials and NEVER takes an arbitrary target.
  * The caller/AI selects an OPERATION IDENTIFIER only; this adapter maps each id
    to its OWN fixed argv. No command string from the AI/API/user is ever run.
    Unknown identifiers are rejected. No shell (shell=False), no `-x`, no
    arbitrary PowerShell.
  * The password never appears in results, audit, logs, or exceptions — it is
    redacted from captured output before anything is stored or returned.

Known limitation: the password is passed on the local `nxc` argv, so it is
briefly visible in Kali's own process list during the call (same class of
limitation as other Kali CLI tools). It is never sent to the target beyond the
authenticated protocol, never to the LLM, and never surfaced by the app.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
import time
from typing import Any

from ..config import settings
from .base import Integration, IntegrationStatus

log = logging.getLogger(__name__)

# The ONLY operations this module can perform. Each id maps to a fixed projection
# of a single safe, read-only NetExec authentication+banner call. Benign + bounded.
REMOTE_OPS: dict[str, str] = {
    "connectivity_check": "Verify authenticated remote-management connectivity (auth success/fail).",
    "whoami": "Report the authenticated account identity confirmed by the remote service.",
    "hostname": "Retrieve the remote hostname (computer name) from the protocol banner.",
    "os_info": "Retrieve the remote operating-system string from the protocol banner.",
    "system_info": "Retrieve basic system info (hostname, OS, domain, signing) from the banner.",
}

# NetExec/CrackMapExec banner parsing (host line + the auth result line).
_NAME = re.compile(r"\(name:([^)]*)\)")
_DOMAIN = re.compile(r"\(domain:([^)]*)\)")
_SIGNING = re.compile(r"\(signing:([^)]*)\)")
# The host line: PROTO  <ip>  <port>  <HOST>  [*] <OS string> (name:..) (domain:..) ...
_HOSTLINE = re.compile(r"^\s*\w+\s+\S+\s+\d+\s+(?P<host>\S+)\s+\[\*\]\s+(?P<os>.*?)(?:\s+\(name:|$)")
_AUTH_OK = re.compile(r"\[\+\]")
_AUTH_FAIL = re.compile(r"\[\-\]")


def _redact(text: str, *secrets: str) -> str:
    """Remove secret literals (e.g. the password) from captured output."""
    out = text or ""
    for s in secrets:
        if s:
            out = out.replace(s, "«redacted»")
    return out


def _secure_tmpdir() -> str | None:
    """Prefer /dev/shm (RAM-backed, not persisted to disk) for the credential file."""
    for d in ("/dev/shm", tempfile.gettempdir()):
        try:
            if d and os.path.isdir(d) and os.access(d, os.W_OK):
                return d
        except OSError:
            continue
    return None


def _write_secret_file(secret: str) -> str:
    """Write `secret` to a fresh 0600 file and return its path. Fail-closed: raises
    if no secure location is writable (the caller must NOT fall back to argv)."""
    d = _secure_tmpdir()
    if d is None:
        raise RuntimeError("no writable secure temp directory for the credential file")
    fd, path = tempfile.mkstemp(prefix="rac_", dir=d)  # mkstemp creates the file mode 0600
    try:
        os.write(fd, (secret + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    try:
        os.chmod(path, 0o600)  # belt-and-suspenders in case of a lax umask/override
    except OSError:
        pass
    return path


def _safe_unlink(path: str | None) -> None:
    """Best-effort delete of the credential file. Never raises; never logs the secret."""
    if not path:
        return
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        log.warning("remote_access: could not remove credential file: %s", exc.__class__.__name__)


class RemoteAccessIntegration(Integration):
    name = "remote_access"
    title = "Credentialed Remote Access / Post-Exploitation Demonstration (RAT Alternative)"
    category = "remote-access"
    repo = "netexec"

    # ---- status / preconditions (fail-closed) ------------------------------

    def status(self) -> IntegrationStatus:
        bin_path = self._which(settings.remote_access_bin)
        detail: dict[str, Any] = {
            "enabled": settings.remote_access_enabled,
            "protocol": settings.remote_access_protocol,
            "target": settings.remote_access_target or None,
            "user_configured": bool(settings.remote_access_user),
            "credentials_configured": bool(settings.remote_access_user and settings.remote_access_password),
            "operations": list(REMOTE_OPS.keys()),
            "operation_descriptions": REMOTE_OPS,
            "caps": {"max_run_seconds": settings.remote_access_max_run_seconds},
        }
        if bin_path is None:
            return self._unavailable(
                f"NetExec ('{settings.remote_access_bin}') not found on PATH. The remote-access "
                "module stays unavailable until it is installed.", **detail)
        detail["binary"] = bin_path
        if not settings.remote_access_enabled:
            return self._ok("NetExec present but the remote-access runner is disabled. Set "
                            "REMOTE_ACCESS_ENABLED=true (plus target + credentials) to arm it.",
                            runnable=False, **detail)
        if not settings.remote_access_target:
            return self._ok("Remote access enabled but REMOTE_ACCESS_TARGET is not set.", runnable=False, **detail)
        if not (settings.remote_access_user and settings.remote_access_password):
            return self._ok("Remote access enabled but lab credentials are not fully configured.",
                            runnable=False, **detail)
        return self._ok(f"Armed — {settings.remote_access_protocol}://{settings.remote_access_target}, "
                        f"{len(REMOTE_OPS)} read-only operations available.", runnable=True, **detail)

    def preconditions(self) -> str | None:
        st = self.status()
        if not st.available:
            return st.reason
        if not st.detail.get("runnable"):
            return st.reason
        return None

    # ---- run (fixed argv per operation id; never an arbitrary command) ------

    def run(self, *, operation: str | None = None, run_seconds: int | None = None) -> dict[str, Any]:
        """Perform ONE allowlisted read-only operation against the configured target."""
        blocked = self.preconditions()
        if blocked:
            raise RuntimeError(blocked)
        if operation not in REMOTE_OPS:
            # Defence in depth — the gateway already rejects unknown ops.
            raise RuntimeError(f"operation '{operation}' is not in the approved allowlist")

        secs = max(1, min(run_seconds or settings.remote_access_max_run_seconds,
                          settings.remote_access_max_run_seconds))
        user = settings.remote_access_user
        pw = settings.remote_access_password

        # MEDIUM-1 remediation: write the password to a short-lived 0600 file
        # (preferring RAM-backed /dev/shm) and pass it as `-p <file>`. NetExec reads
        # a file as a one-password list, so the plaintext NEVER appears on the argv
        # (hence not in /proc/<pid>/cmdline, ps, or the process registry). Fail-closed:
        # if the file can't be created we abort — never fall back to argv.
        pw_file: str | None = None
        try:
            try:
                pw_file = _write_secret_file(pw)
            except Exception as exc:  # noqa: BLE001 - redact; never leak the secret
                raise RuntimeError(f"could not prepare secure credential file: {_redact(str(exc), pw)}")

            # FIXED argv — a read-only authenticated banner query. No -x, no command
            # string, no shell. argv carries only the credential-file PATH, not the secret.
            cmd = [self._which(settings.remote_access_bin) or settings.remote_access_bin,
                   settings.remote_access_protocol, settings.remote_access_target,
                   "-u", user, "-p", pw_file]
            if settings.remote_access_domain:
                cmd += ["-d", settings.remote_access_domain]

            started = time.monotonic()
            timed_out = False
            stdout = stderr = ""
            returncode: int | None = None
            try:
                proc = self._run(cmd, timeout=secs)
                stdout, stderr, returncode = proc.stdout, proc.stderr, proc.returncode
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            except Exception as exc:  # LOW-1: redact the password from any exception text
                raise RuntimeError(_redact(f"{type(exc).__name__}: {exc}", pw)) from None
            duration = round(time.monotonic() - started, 2)

            # NetExec still echoes the password in its success line, so redact the
            # captured output before parsing/returning, as before.
            combined = _redact(stdout + "\n" + stderr, pw)
            return self._project(operation, combined, timed_out, returncode, duration)
        finally:
            # Cleanup on EVERY path: success, failure, timeout, or cancellation.
            _safe_unlink(pw_file)

    def _project(self, operation: str, text: str, timed_out: bool, rc: int | None, duration: float) -> dict[str, Any]:
        auth_ok = bool(_AUTH_OK.search(text))
        auth_fail = bool(_AUTH_FAIL.search(text)) and not auth_ok
        host = os_str = domain = signing = None
        for line in text.splitlines():
            m = _HOSTLINE.match(line)
            if m:
                host = host or m.group("host")
                os_str = os_str or m.group("os").strip()
            if (nm := _NAME.search(line)):
                host = nm.group(1) or host
            if (dm := _DOMAIN.search(line)):
                domain = dm.group(1) or domain
            if (sg := _SIGNING.search(line)):
                signing = sg.group(1) or signing

        if timed_out:
            status = "timed_out"
        elif auth_ok:
            status = "success"
        elif auth_fail:
            status = "auth_failed"
        elif host or os_str:
            status = "reachable_no_auth"
        else:
            status = "unreachable"

        measured: dict[str, Any] = {}
        if operation == "connectivity_check":
            measured = {"reachable": bool(host or os_str or auth_ok or auth_fail), "authenticated": auth_ok}
        elif operation == "whoami":
            # Identity = the configured principal, CONFIRMED by successful auth.
            principal = (f"{domain}\\{settings.remote_access_user}" if domain else settings.remote_access_user)
            measured = {"authenticated_as": principal if auth_ok else None, "authenticated": auth_ok}
        elif operation == "hostname":
            measured = {"hostname": host}
        elif operation == "os_info":
            measured = {"os": os_str}
        elif operation == "system_info":
            measured = {"hostname": host, "os": os_str, "domain": domain, "signing": signing}

        if auth_ok:
            message = f"{operation}: authenticated OK to {settings.remote_access_target}."
        elif auth_fail:
            message = f"{operation}: authentication failed."
        elif status == "reachable_no_auth":
            message = f"{operation}: host reachable; authentication not confirmed."
        elif timed_out:
            message = f"{operation}: timed out after the run-time cap."
        else:
            message = f"{operation}: target not reachable / no response."

        return {
            "operation": operation,
            "target": settings.remote_access_target,
            "protocol": settings.remote_access_protocol,
            "status": status,
            "measured": measured,
            "message": message,
            "exit_code": rc,
            "timed_out": timed_out,
            "duration_seconds": duration,
            # NOTE: password is never included; output was redacted before projection.
        }
