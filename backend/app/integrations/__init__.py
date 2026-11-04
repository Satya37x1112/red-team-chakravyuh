"""External-tool integrations, registered behind a uniform, optional interface.

Each adapter degrades honestly when its tool/key/config is missing (see base.py).
Import this package to get the registry:

    from .integrations import REGISTRY, get_integration, all_status
"""
from __future__ import annotations

from .base import Integration, IntegrationStatus
from .caldera import CalderaIntegration
from .locust import LocustIntegration
from .pentestgpt import PentestGPTIntegration
from .vervet import VervetIntegration

REGISTRY: dict[str, Integration] = {
    cls.name: cls()
    for cls in (CalderaIntegration, LocustIntegration, VervetIntegration, PentestGPTIntegration)
}


def get_integration(name: str) -> Integration | None:
    return REGISTRY.get(name)


def all_status() -> list[dict]:
    """Status of every integration, each guarded so one failure can't hide the rest."""
    out = []
    for name, integ in REGISTRY.items():
        try:
            out.append(integ.status().as_dict())
        except Exception as exc:  # noqa: BLE001
            out.append(
                IntegrationStatus(
                    name=name,
                    title=getattr(integ, "title", name),
                    category=getattr(integ, "category", "analysis"),
                    repo=getattr(integ, "repo", ""),
                    available=False,
                    reason=f"status check failed: {exc}",
                ).as_dict()
            )
    return out


__all__ = ["REGISTRY", "get_integration", "all_status", "Integration", "IntegrationStatus"]
