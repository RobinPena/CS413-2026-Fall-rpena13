"""Free-variable analysis (d0exp_fvset) and the Lint operation."""
import pytest

from lambda_web.backend import lambda1 as L
from lambda_web.backend.contract import Operation, Outcome
from lambda_web.backend.lambda_backend import LambdaBackend
from tests.programs import ADD_42, DIV_ZERO, fact, fib

V, I = L.D0Evar, L.D0Eint
Op2, Lam, Fix, App, Let = L.D0Eop2, L.D0Elam, L.D0Efix, L.D0Eapp, L.D0Elet


# --- d0exp_fvset ------------------------------------------------------

@pytest.mark.parametrize("dexp, expected", [
    (I(1), set()),
    (L.D0Ebtf(True), set()),
    (V("x"), {"x"}),
    (L.D0Eop1("-1", V("x")), {"x"}),
    (Op2("+", V("x"), V("y")), {"x", "y"}),
    (Lam("x", Op2("+", V("x"), V("y"))), {"y"}),
    (Fix("f", "x", App(V("f"), Op2("+", V("x"), V("z")))), {"z"}),
    (App(V("f"), V("a")), {"f", "a"}),
    (L.D0Eif0(V("c"), V("t"), V("e")), {"c", "t", "e"}),
    (Let("x", V("y"), V("x")), {"y"}),
    (L.D0Epair(V("a"), V("b")), {"a", "b"}),
    (L.D0Epfst(V("p")), {"p"}),
    (L.D0Epsnd(V("p")), {"p"}),
], ids=["int", "btf", "var", "op1", "op2", "lam", "fix", "app", "if0",
        "let", "pair", "pfst", "psnd"])
def test_fvset_each_constructor(dexp, expected):
    result = L.d0exp_fvset(dexp)
    assert type(result) is frozenset
    assert result == expected


def test_fvset_duplicate_occurrences_counted_once():
    assert L.d0exp_fvset(Op2("+", V("x"), Op2("*", V("x"), V("x")))) == {"x"}


@pytest.mark.parametrize("dexp, expected", [
    (Lam("x", Lam("y", Op2("+", V("x"), V("y")))), set()),
    (Lam("x", Lam("x", V("x"))), set()),
    (Op2("+", Lam("x", V("x")), V("x")), {"x"}),
], ids=["nested", "shadowed", "binding-does-not-leak"])
def test_fvset_nested_bindings(dexp, expected):
    assert L.d0exp_fvset(dexp) == expected


def test_fvset_fix_binds_name_and_parameter_only_in_body():
    assert L.d0exp_fvset(Fix("f", "x", App(V("f"), V("x")))) == set()
    assert L.d0exp_fvset(App(Fix("f", "x", V("x")), V("f"))) == {"f"}


def test_fvset_let_initializer_is_outside_scope():
    assert L.d0exp_fvset(Let("x", V("x"), I(1))) == {"x"}
    assert L.d0exp_fvset(Let("x", I(1), V("x"))) == set()
    assert L.d0exp_fvset(Let("f", Lam("n", App(V("f"), V("n"))),
                             V("f"))) == {"f"}


# --- Lint operation ---------------------------------------------------

B = LambdaBackend()


@pytest.mark.parametrize("source", [ADD_42, fact(5), fib(10),
                                    'D0Elam("unused", D0Eint(1))'])
def test_lint_passes_closed_program(source):
    r = B.lint(source, 7)
    assert (r.operation, r.revision, r.outcome) == \
        (Operation.LINT, 7, Outcome.OK)
    assert r.message == "No free variables found."


def test_lint_lists_undeclared_names_sorted():
    r = B.lint('D0Eop2("+", D0Evar("zeta"), '
               'D0Eop2("*", D0Evar("alpha"), D0Evar("zeta")))', 1)
    assert r.outcome is Outcome.LANGUAGE_ERROR
    assert r.message == "Undeclared variable(s): alpha, zeta"


def test_lint_does_not_evaluate(monkeypatch):
    assert B.lint(DIV_ZERO, 1).outcome is Outcome.OK

    def boom(*args, **kwargs):
        raise AssertionError("Lint must not evaluate")
    monkeypatch.setattr(L, "d0exp_evaluate", boom)
    assert B.lint(fact(5), 1).ok


def test_lint_reports_malformed_input():
    r = B.lint('D0Eint(', 1)
    assert r.outcome is Outcome.INPUT_ERROR
