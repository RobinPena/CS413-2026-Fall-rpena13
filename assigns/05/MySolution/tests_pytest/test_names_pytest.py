"""Name collection and the fresh-name policy used by substitution."""
import pytest

from examples import NAMES_CASES, PRETTY_CASES, PRETTY_NO_EVAL_CASES
from lambda1_visitors import (
    D0E000, AllNamesVisitor, D0Evar, FreshNames, d0exp_allnames, d0exp_fvset,
)


def params(cases):
    return [pytest.param(dexp, expected, id=name) for name, dexp, expected in cases]


@pytest.mark.parametrize(("dexp", "expected"), params(NAMES_CASES))
def test_exact_names(dexp, expected):
    assert d0exp_allnames(dexp) == expected


def test_cases_cover_every_constructor():
    covered = {type(dexp) for _, dexp, _ in NAMES_CASES}
    assert covered == set(D0E000.__subclasses__())


@pytest.mark.parametrize(("dexp", "expected"),
                         params(PRETTY_CASES + PRETTY_NO_EVAL_CASES))
def test_includes_every_free_variable(dexp, expected):
    assert d0exp_fvset(dexp) <= d0exp_allnames(dexp)


def test_visitor_dispatches_through_accept():
    assert D0Evar("x").accept(AllNamesVisitor()) == {"x"}


def test_first_suffix_when_unused():
    assert FreshNames(set()).fresh("y") == "y_1"


def test_skips_names_already_used():
    assert FreshNames({"y", "y_1", "y_2"}).fresh("y") == "y_3"


def test_never_repeats_a_generated_name():
    supply = FreshNames({"y"})
    assert [supply.fresh("y") for _ in range(3)] == ["y_1", "y_2", "y_3"]


def test_bases_are_independent():
    supply = FreshNames(set())
    assert (supply.fresh("y"), supply.fresh("f")) == ("y_1", "f_1")


def test_suffix_is_appended_not_replaced():
    assert FreshNames({"y_1"}).fresh("y_1") == "y_1_1"


def test_same_used_set_gives_same_sequence():
    used = {"x", "y", "y_1"}
    first, second = FreshNames(used), FreshNames(used)
    assert ([first.fresh("y"), first.fresh("x")]
            == [second.fresh("y"), second.fresh("x")])


def test_does_not_modify_the_given_set():
    used = {"y"}
    FreshNames(used).fresh("y")
    assert used == {"y"}
