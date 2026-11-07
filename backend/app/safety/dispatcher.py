"""Scenario dispatcher — the ONLY controlled path from an approved decision to
a real adapter.

Given an APPROVED execution (by id), it:

  * sets the current-execution context so any subprocess the adapter spawns is
    attributed to this execution and reachable by the kill switch;
  * advances the registry RUNNING -> COMPLETED / FAILED / TIMED_OUT / CANCELLED;
  * records audit milestones with secrets masked.

Adapters are injectable (``adapters=`` / ``cancel`` hooks) so tests exercise the
whole flow with mock adapters and simulated processes — no real attack tool is
run here. A rejected plan has no APPROVED record, so it can never reach this
code.
"""
from __future__ import annotations

import subprocess
from typing import Callable

from . import audit, process
from .registry import ExecState, registry

# An adapter callable takes the validated parameters and returns a result dict;
# it may raise subprocess.TimeoutExpired, RuntimeError (blocked), or Exception.
Adapter = Callable[[dict], dict]


def _hydra_adapter(params: dict) -> dict:
    from ..integrations.hydra import HydraIntegration

    return HydraIntegration().run(tasks=params.get("tasks"), run_seconds=params.get("run_seconds"))


def _locust_adapter(params: dict) -> dict:
    from ..integrations.locust import LocustIntegration

    return LocustIntegration().run(
        users=params.get("users"),
        spawn_rate=params.get("spawn_rate"),
        run_seconds=params.get("run_seconds"),
    )


def _remote_access_adapter(params: dict) -> dict:
    from ..integrations.remote_access import RemoteAccessIntegration

    return RemoteAccessIntegration().run(
        operation=params.get("operation"),
        run_seconds=params.get("run_seconds"),
    )


def default_adapters() -> dict[str, Adapter]:
    return {"hydra": _hydra_adapter, "locust": _locust_adapter, "remote_access": _remote_access_adapter}


def run_execution(execution_id: str, *, adapters: dict[str, Adapter] | None = None) -> dict:
    """Run one APPROVED execution to a terminal state. Returns a masked result."""
    adapters = adapters or default_adapters()
    rec = registry.get(execution_id)
    if rec is None:
        raise KeyError(execution_id)
    if rec.state != ExecState.APPROVED:
        raise RuntimeError(f"execution {execution_id} is not APPROVED (state={rec.state.value})")

    # Honour a cancel that arrived between approval and start.
    if rec.cancel_requested:
        registry.transition(execution_id, ExecState.CANCELLED)
        audit.audit(audit.CANCEL_CONFIRMED, execution_id=execution_id, module=rec.module,
                    reason="cancelled before start")
        return {"execution_id": execution_id, "state": ExecState.CANCELLED.value}

    adapter = adapters.get(rec.adapter)
    if adapter is None:
        registry.transition(execution_id, ExecState.FAILED, error=f"no adapter '{rec.adapter}'")
        audit.audit(audit.EXECUTION_FAILED, execution_id=execution_id, module=rec.module,
                    reason=f"no adapter '{rec.adapter}'")
        return {"execution_id": execution_id, "state": ExecState.FAILED.value}

    registry.transition(execution_id, ExecState.RUNNING)
    audit.audit(audit.EXECUTION_STARTED, execution_id=execution_id, scenario_id=rec.scenario_id,
                module=rec.module, target=rec.target,
                payload={"validated_parameters": rec.validated_parameters})

    token = process.CURRENT_EXECUTION_ID.set(execution_id)
    try:
        result = adapter(dict(rec.validated_parameters))
    except subprocess.TimeoutExpired as exc:
        registry.transition(execution_id, ExecState.TIMED_OUT, error="run-time cap exceeded")
        audit.audit(audit.EXECUTION_TIMED_OUT, execution_id=execution_id, module=rec.module,
                    reason=str(exc)[:300])
        return {"execution_id": execution_id, "state": ExecState.TIMED_OUT.value}
    except RuntimeError as exc:
        # Adapter fail-closed precondition (e.g. disabled / unconfigured).
        registry.transition(execution_id, ExecState.FAILED, error=str(exc)[:500])
        audit.audit(audit.EXECUTION_FAILED, execution_id=execution_id, module=rec.module,
                    reason=str(exc)[:500])
        return {"execution_id": execution_id, "state": ExecState.FAILED.value}
    except Exception as exc:  # noqa: BLE001
        registry.transition(execution_id, ExecState.FAILED, error=f"{type(exc).__name__}: {exc}"[:500])
        audit.audit(audit.EXECUTION_FAILED, execution_id=execution_id, module=rec.module,
                    reason=f"{type(exc).__name__}: {exc}"[:500])
        return {"execution_id": execution_id, "state": ExecState.FAILED.value}
    finally:
        process.CURRENT_EXECUTION_ID.reset(token)

    masked = audit.mask_secrets(result)
    exit_code = result.get("exit_code") if isinstance(result, dict) else None

    _TERMINAL = (
        ExecState.CANCELLED, ExecState.COMPLETED, ExecState.FAILED, ExecState.TIMED_OUT,
    )
    # The kill switch may have already driven this record to a terminal state
    # (CANCELLED/FAILED) while the adapter was mid-run. If so, respect it — never
    # force COMPLETED over a cancellation.
    current = registry.get(execution_id)
    if current and current.state in _TERMINAL:
        return {"execution_id": execution_id, "state": current.state.value, "result": masked}

    # If a cancel was requested but the state is not yet terminal, honour it.
    if current and current.cancel_requested:
        registry.transition(execution_id, ExecState.CANCELLED, exit_code=exit_code)
        audit.audit(audit.CANCEL_CONFIRMED, execution_id=execution_id, module=rec.module)
        return {"execution_id": execution_id, "state": ExecState.CANCELLED.value, "result": masked}

    registry.transition(execution_id, ExecState.COMPLETED, exit_code=exit_code)
    audit.audit(audit.EXECUTION_COMPLETED, execution_id=execution_id, scenario_id=rec.scenario_id,
                module=rec.module, target=rec.target, payload={"result": masked})
    return {"execution_id": execution_id, "state": ExecState.COMPLETED.value, "result": masked}


def cancel_execution(execution_id: str, *, grace_seconds: float = 5.0) -> dict:
    """Request cancellation of one execution and terminate its managed processes."""
    rec = registry.request_cancel(execution_id)
    if rec is None:
        raise KeyError(execution_id)
    audit.audit(audit.CANCEL_REQUESTED, execution_id=execution_id, module=rec.module)
    outcomes = process.terminate_execution(execution_id, grace_seconds=grace_seconds)
    all_stopped = all(o.stopped for o in outcomes) if outcomes else True
    # If there was a live process, reflect the confirmed stop; otherwise leave the
    # running adapter to notice cancel_requested and finish (dispatcher handles it).
    if outcomes:
        if all_stopped:
            try:
                registry.transition(execution_id, ExecState.CANCELLED)
            except Exception:
                pass
            audit.audit(audit.CANCEL_CONFIRMED, execution_id=execution_id, module=rec.module)
        else:
            try:
                registry.transition(execution_id, ExecState.FAILED,
                                    error="cancellation could not confirm process termination")
            except Exception:
                pass
            audit.audit(audit.CANCEL_FAILED, execution_id=execution_id, module=rec.module)
    return {
        "execution_id": execution_id,
        "cancel_requested": True,
        "processes": [o.__dict__ for o in outcomes],
        "all_stopped": all_stopped,
    }
