"""Capture-avoiding substitution: every constructor, shadowing and renaming."""
import copy

import pytest

from examples import SUBST_AST_CASES, SUBST_CASES, SUBST_NO_EVAL_CASES
from lambda1_visitors import (
    D0E000, D0Eint, D0Evar, FreshNames, SubstitutionVisitor,
    d0exp_fvset, d0exp_pretty, d0exp_substitute,
)
import lambda1_vp  # importable once lambda1_visitors has set up sys.path

ARGS = ("dexp", "target", "replacement", "expected")
TARGET_FREE = [case for case in SUBST_CASES if case[2] in d0exp_fvset(case[1])]
TARGET_NOT_FREE = [case for case in SUBST_CASES
                   if case[2] not in d0exp_fvset(case[1])]


def params(cases):
    return [pytest.param(*case[1:], id=case[0]) for case in cases]


@pytest.fixture
def no_evaluator(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("expression was evaluated")
    monkeypatch.setattr(lambda1_vp.EvaluateVisitor, "__init__", refuse)


@pytest.mark.parametrize(ARGS, params(SUBST_CASES))
def test_exact_output(dexp, target, replacement, expected):
    assert d0exp_pretty(d0exp_substitute(dexp, target, replacement)) == expected


@pytest.mark.parametrize(ARGS, params(SUBST_AST_CASES))
def test_exact_structure(dexp, target, replacement, expected):
    assert d0exp_substitute(dexp, target, replacement) == expected


def test_cases_cover_every_constructor():
    covered = {type(case[1]) for case in SUBST_CASES}
    assert covered == set(D0E000.__subclasses__())


def test_visitor_dispatches_through_accept():
    visitor = SubstitutionVisitor("x", D0Eint(3), FreshNames({"x"}))
    assert D0Evar("x").accept(visitor) == D0Eint(3)


@pytest.mark.parametrize(ARGS, params(TARGET_FREE))
def test_free_variables_when_target_is_free(dexp, target, replacement, expected):
    result = d0exp_substitute(dexp, target, replacement)
    assert d0exp_fvset(result) == ((d0exp_fvset(dexp) - {target})
                                   | d0exp_fvset(replacement))


@pytest.mark.parametrize(ARGS, params(TARGET_NOT_FREE))
def test_unchanged_when_target_is_not_free(dexp, target, replacement, expected):
    result = d0exp_substitute(dexp, target, replacement)
    assert result == dexp
    assert d0exp_fvset(result) == d0exp_fvset(dexp)


@pytest.mark.parametrize(ARGS, params(SUBST_CASES))
def test_inputs_unchanged(dexp, target, replacement, expected):
    before = copy.deepcopy((dexp, replacement))
    d0exp_substitute(dexp, target, replacement)
    assert (dexp, replacement) == before


@pytest.mark.parametrize(ARGS, params(SUBST_CASES))
def test_repeated_calls_agree(dexp, target, replacement, expected):
    assert (d0exp_substitute(dexp, target, replacement)
            == d0exp_substitute(dexp, target, replacement))


@pytest.mark.parametrize(ARGS, params(SUBST_NO_EVAL_CASES))
def test_no_eval_results_fail_when_evaluated(dexp, target, replacement, expected):
    result = d0exp_substitute(dexp, target, replacement)
    with pytest.raises((TypeError, ZeroDivisionError, RecursionError)):
        lambda1_vp.d0exp_evaluate(result)


def test_evaluation_is_blocked(no_evaluator):
    with pytest.raises(AssertionError):
        lambda1_vp.d0exp_evaluate(D0Eint(1))


@pytest.mark.usefixtures("no_evaluator")
@pytest.mark.parametrize(ARGS, params(SUBST_CASES + SUBST_NO_EVAL_CASES))
def test_substitutes_without_evaluating(dexp, target, replacement, expected):
    assert d0exp_pretty(d0exp_substitute(dexp, target, replacement)) == expected
