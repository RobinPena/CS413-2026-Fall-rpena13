"""Capture-avoiding substitution: every constructor, shadowing and renaming."""
import pytest

from examples import SUBST_AST_CASES, SUBST_CASES
from lambda1_visitors import (
    D0E000, D0Eint, D0Evar, FreshNames, SubstitutionVisitor,
    d0exp_pretty, d0exp_substitute,
)

ARGS = ("dexp", "target", "replacement", "expected")


def params(cases):
    return [pytest.param(*case[1:], id=case[0]) for case in cases]


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
