"""Structured execution-plan schema validation."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.safety.plan_schema import ExecutionParams, ExecutionPlan, ModuleId, PlanSource


def _valid_kwargs(**over):
    base = dict(
        scenario_id="s1",
        module=ModuleId.bruteforce,
        requested_target="10.0.0.5",
        params=ExecutionParams(tasks=2, run_seconds=10),
    )
    base.update(over)
    return base


def test_valid_plan_accepted():
    plan = ExecutionPlan(**_valid_kwargs())
    assert plan.module is ModuleId.bruteforce
    assert plan.source is PlanSource.manual  # default
    assert plan.plan_id  # auto-assigned


def test_invalid_module_rejected():
    with pytest.raises(ValidationError):
        ExecutionPlan(**_valid_kwargs(module="banana"))


def test_missing_mandatory_field_rejected():
    kwargs = _valid_kwargs()
    kwargs.pop("scenario_id")
    with pytest.raises(ValidationError):
        ExecutionPlan(**kwargs)


def test_missing_target_rejected():
    kwargs = _valid_kwargs()
    kwargs.pop("requested_target")
    with pytest.raises(ValidationError):
        ExecutionPlan(**kwargs)


def test_malformed_param_rejected():
    # tasks must be >= 1
    with pytest.raises(ValidationError):
        ExecutionPlan(**_valid_kwargs(params=ExecutionParams(tasks=0)))


def test_out_of_range_param_rejected():
    # users sanity bound is 10_000
    with pytest.raises(ValidationError):
        ExecutionPlan(
            scenario_id="s1", module=ModuleId.ddos, requested_target="http://h:8080",
            params=ExecutionParams(users=20_000),
        )


def test_unexpected_field_rejected():
    with pytest.raises(ValidationError):
        ExecutionPlan(**_valid_kwargs(surprise="x"))


def test_unexpected_param_field_rejected():
    with pytest.raises(ValidationError):
        ExecutionParams(max_users=999)  # no such field; extra=forbid


def test_plan_has_no_self_authorization_fields():
    # The plan must not be able to approve itself or carry caps/policy ids.
    fields = set(ExecutionPlan.model_fields)
    for forbidden in ("approved", "policy_id", "max_users", "max_tasks", "caps", "authorized"):
        assert forbidden not in fields


def test_metadata_secret_key_rejected():
    with pytest.raises(ValidationError):
        ExecutionPlan(**_valid_kwargs(metadata={"password": "hunter2"}))


def test_target_with_whitespace_rejected():
    with pytest.raises(ValidationError):
        ExecutionPlan(**_valid_kwargs(requested_target="10.0.0.5 ; rm -rf"))


def test_ai_source_is_representable():
    plan = ExecutionPlan(**_valid_kwargs(source=PlanSource.ai))
    assert plan.source is PlanSource.ai
