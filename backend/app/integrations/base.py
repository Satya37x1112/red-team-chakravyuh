"""Shared contract for external-tool integrations.

Every integration is OPTIONAL and degrades honestly. If a tool's binary, Python
package, API key, or configuration is missing, `status()` reports
`available=False` with a human-readable `reason` instead of raising — exactly the
way the telemetry collector returns "unavailable" rather than fabricating data.

Integrations never widen the project's safety boundary on their own. The
analysis-oriented ones (caldera, vervet describe/report, pentestgpt planning)
only read and reason. The one real action path — Locust load generation — stays
gated behind explicit operator configuration (see locust.py).
"""
from __future__ import annotations

import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class IntegrationStatus:
    name: str
    title: str
    category: str            # "analysis" | "load-test" | "emulation" | "agent"
    repo: str
    available: bool
    reason: str              # why available / why not
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "category": self.category,
            "repo": self.repo,
            "available": self.available,
            "reason": self.reason,
            "detail": self.detail,
        }


class Integration(ABC):
    """Base for all external-tool adapters."""

    name: str = "base"
    title: str = "Integration"
    category: str = "analysis"
    repo: str = ""

    @abstractmethod
    def status(self) -> IntegrationStatus:
        """Report availability without side effects (no network, no runs)."""
        raise NotImplementedError

    # ---- helpers ------------------------------------------------------------

    def _ok(self, reason: str, **detail: Any) -> IntegrationStatus:
        return IntegrationStatus(self.name, self.title, self.category, self.repo, True, reason, detail)

    def _unavailable(self, reason: str, **detail: Any) -> IntegrationStatus:
        return IntegrationStatus(self.name, self.title, self.category, self.repo, False, reason, detail)

    @staticmethod
    def _which(binary: str) -> str | None:
        """Absolute path of an executable, or None. Accepts a full path.

        Searches PATH first, then the directory of the running interpreter
        (the venv's Scripts/bin). The native backend often runs via the venv's
        python.exe without the venv on PATH, so console scripts installed into
        the venv (locust, pentestgpt-agent) would otherwise look 'not found'.
        """
        found = shutil.which(binary)
        if found:
            return found
        import os
        import sys

        bindir = os.path.dirname(sys.executable)
        for cand in (binary, f"{binary}.exe", f"{binary}.cmd", f"{binary}.bat"):
            candidate = os.path.join(bindir, cand)
            if os.path.isfile(candidate):
                return candidate
        return None

    @staticmethod
    def _run(cmd: list[str], timeout: float = 30, cwd: str | None = None) -> subprocess.CompletedProcess:
        """Run a command with no shell, captured output, and a hard timeout.

        Delegates to the Section-2 managed-process runner so every child starts
        in its own process group and is tracked for the lifetime of the call —
        this is what lets the unified kill switch terminate an in-flight Hydra or
        Locust run, not just the Python handler waiting on it. Behaviourally a
        drop-in for subprocess.run: same CompletedProcess return, same
        TimeoutExpired on timeout. Callers translate failures into a clean
        'unavailable' or an HTTP error rather than crashing the server.
        """
        from ..safety.process import run_managed

        return run_managed(cmd, timeout=timeout, cwd=cwd)
