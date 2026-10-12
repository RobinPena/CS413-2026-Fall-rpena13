"""Pretty printing: exact output for every constructor, without evaluation."""
import pytest

from examples import PRETTY_CASES, PRETTY_NO_EVAL_CASES
from lambda1_visitors import D0E000, D0Eint, PrettyPrintVisitor, d0exp_pretty
import lambda1_vp  # importable once lambda1_visitors has set up sys.path


def params(cases):
    return [pytest.param(dexp, expected, id=name) for name, dexp, expected in cases]


@pytest.fixture
def no_evaluator(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("expression was evaluated")
    monkeypatch.setattr(lambda1_vp.EvaluateVisitor, "__init__", refuse)


@pytest.mark.parametrize(("dexp", "expected"), params(PRETTY_CASES))
def test_exact_output(dexp, expected):
    assert d0exp_pretty(dexp) == expected


def test_cases_cover_every_constructor():
    covered = {type(dexp) for _, dexp, _ in PRETTY_CASES}
    assert covered == set(D0E000.__subclasses__())


def test_visitor_dispatches_through_accept():
    assert D0Eint(5).accept(PrettyPrintVisitor()) == "5"


@pytest.mark.parametrize(("dexp", "expected"), params(PRETTY_NO_EVAL_CASES))
def test_no_eval_cases_fail_when_evaluated(dexp, expected):
    with pytest.raises((TypeError, ZeroDivisionError, RecursionError)):
        lambda1_vp.d0exp_evaluate(dexp)


@pytest.mark.usefixtures("no_evaluator")
@pytest.mark.parametrize(("dexp", "expected"), params(PRETTY_NO_EVAL_CASES))
def test_prints_without_evaluating(dexp, expected):
    assert d0exp_pretty(dexp) == expected
