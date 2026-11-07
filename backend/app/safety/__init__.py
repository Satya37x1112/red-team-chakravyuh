"""Deterministic execution-control layer for CHAKRAVYUH.

A single, AI-independent pipeline that any proposer of work (a manual API call
today, the centralized AI planner later) must pass through before a real adapter
runs:

    ExecutionPlan (plan_schema)
        -> SafetyGateway.evaluate (gateway)   # fail-closed authorization
        -> ExecutionRegistry (registry)        # lifecycle + concurrency
        -> dispatcher.run_execution            # controlled adapter invocation
        -> managed subprocess (process)        # own process group, trackable
        -> audit (audit)                       # masked, persisted decisions
        -> KillSwitch (killswitch)             # unified halt over all of it

Safety policy (policy) stays separate from AI reasoning; the Gateway never
consults a model. See docs/CLAUDE_SECTION_2_IMPLEMENTATION.md.
"""
from __future__ import annotations

from .gateway import GatewayDecision, evaluate
from .killswitch import kill_switch
from .plan_schema import ExecutionParams, ExecutionPlan, ModuleId, PlanSource
from .registry import ExecState, ExecutionRecord, registry

__all__ = [
    "evaluate",
    "GatewayDecision",
    "kill_switch",
    "ExecutionPlan",
    "ExecutionParams",
    "ModuleId",
    "PlanSource",
    "registry",
    "ExecutionRecord",
    "ExecState",
]
