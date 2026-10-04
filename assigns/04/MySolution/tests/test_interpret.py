"""Interpret: real evaluation with d0exp_evaluate."""
import pytest

from lambda_web.backend.contract import Operation, Outcome
from lambda_web.backend.lambda_backend import LambdaBackend
from tests.programs import ADD_42, DIV_ZERO, fact, fib

B = LambdaBackend()


@pytest.mark.parametrize("source, value", [
    (ADD_42, "D0Vint(arg1=42)"),
    ('D0Eop2("-", D0Eint(2), D0Eint(5))', "D0Vint(arg1=-3)"),
    ('D0Eop2("*", D0Eint(6), D0Eint(7))', "D0Vint(arg1=42)"),
    ('D0Eop2("/", D0Eint(7), D0Eint(2))', "D0Vint(arg1=3)"),
    ('D0Eop2("<", D0Eint(1), D0Eint(2))', "D0Vbtf(arg1=True)"),
    ('D0Elet("x", D0Eint(5), D0Eop2("*", D0Evar("x"), D0Evar("x")))',
     "D0Vint(arg1=25)"),
    ('D0Epfst(D0Epair(D0Eint(1), D0Eint(2)))', "D0Vint(arg1=1)"),
    (fact(0), "D0Vint(arg1=1)"),
    (fact(1), "D0Vint(arg1=1)"),
    (fact(5), "D0Vint(arg1=120)"),
    (fact(10), "D0Vint(arg1=3628800)"),
    (fib(0), "D0Vint(arg1=0)"),
    (fib(1), "D0Vint(arg1=1)"),
    (fib(2), "D0Vint(arg1=1)"),
    (fib(10), "D0Vint(arg1=55)"),
])
def test_interpret_values(source, value):
    r = B.interpret(source, 3)
    assert (r.operation, r.revision, r.outcome) == \
        (Operation.INTERPRET, 3, Outcome.OK)
    assert r.output == value


@pytest.mark.parametrize("source", [
    'D0Eint(',
    'D0Eint("x")',
    '__import__("os").system("echo hacked")',
])
def test_malformed_input_is_input_error(source):
    r = B.interpret(source, 1)
    assert r.outcome is Outcome.INPUT_ERROR
    assert r.message == "Invalid input"


@pytest.mark.parametrize("source, detail", [
    (DIV_ZERO, "ZeroDivisionError"),
    ('D0Eop2("%", D0Eint(1), D0Eint(2))', "TypeError"),
    ('D0Eapp(D0Eint(1), D0Eint(2))', "TypeError"),
    ('D0Eif0(D0Eint(1), D0Eint(2), D0Eint(3))', "TypeError"),
    ('D0Evar("x")', "D0V000()"),
    ('D0Epair(D0Eint(1), D0Evar("y"))', "D0V000()"),
], ids=["div-zero", "unknown-op", "apply-non-function", "non-bool-if",
        "unbound-var", "error-inside-pair"])
def test_runtime_failure_is_language_error(source, detail):
    r = B.interpret(source, 1)
    assert r.outcome is Outcome.LANGUAGE_ERROR
    assert r.message.startswith("Runtime error")
    assert detail in r.output


def test_deep_recursion_is_backend_failure():
    r = B.interpret(fact(100000), 1)
    assert r.outcome is Outcome.BACKEND_FAILURE
    assert "recursion" in r.message


def test_lint_passes_but_interpret_fails():
    assert B.lint(DIV_ZERO, 1).ok
    assert B.interpret(DIV_ZERO, 1).outcome is Outcome.LANGUAGE_ERROR
