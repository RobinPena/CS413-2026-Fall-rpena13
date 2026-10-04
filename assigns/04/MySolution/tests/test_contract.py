"""Backend contract types."""
import dataclasses

import pytest

from lambda_web.backend.contract import Artifact, Operation, Outcome, Result


def test_operations_in_required_button_order():
    assert [op.value for op in Operation] == \
        ["Lint", "Interpret", "Type-check", "Compile", "Execute"]


@pytest.mark.parametrize("outcome", list(Outcome))
def test_only_ok_outcome_is_success(outcome):
    r = Result(Operation.LINT, 1, outcome, "m")
    assert r.ok == (outcome is Outcome.OK)


def test_result_is_immutable():
    r = Result(Operation.LINT, 1, Outcome.OK, "m")
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.outcome = Outcome.INPUT_ERROR


def test_artifact_belongs_to_a_revision():
    assert Artifact(revision=4, format="python", code="").revision == 4
