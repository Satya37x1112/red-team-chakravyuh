"""An ExecutionPlan cannot carry a cap-raising field (extra=forbid)."""
import pytest
from pydantic import ValidationError
from app.safety.plan_schema import ExecutionPlan, ModuleId
def test_plan_rejects_unknown_cap_field():
    with pytest.raises(ValidationError):
        ExecutionPlan(scenario_id="x", module=ModuleId.ddos, requested_target="10.0.0.1",
                      max_users=9999)  # not an allowed field
def test_valid_plan_builds():
    p = ExecutionPlan(scenario_id="x", module=ModuleId.ddos, requested_target="10.0.0.1")
    assert p.module is ModuleId.ddos
