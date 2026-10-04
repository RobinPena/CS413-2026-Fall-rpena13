"""LAMBDA backend: real Lint and Interpret built on the supplied lambda1.py.

Implements the LanguageBackend contract. Every method returns a Result;
errors from reading or evaluating the source are reported, not raised.
"""
from lambda_web.backend import lambda1 as L
from lambda_web.backend.contract import Operation, Outcome, Result
from lambda_web.backend.reader import ReadError, read_d0exp


class LambdaBackend:

    def lint(self, source: str, revision: int) -> Result:
        """Report undeclared (free) variables without evaluating."""
        op = Operation.LINT
        try:
            dexp = read_d0exp(source)
        except ReadError as e:
            return Result(op, revision, Outcome.INPUT_ERROR,
                          "Invalid input", str(e))
        free = L.d0exp_fvset(dexp)
        if free:
            names = ", ".join(sorted(free))
            return Result(op, revision, Outcome.LANGUAGE_ERROR,
                          f"Undeclared variable(s): {names}")
        return Result(op, revision, Outcome.OK, "No free variables found.")

    def interpret(self, source: str, revision: int) -> Result:
        """Evaluate with d0exp_evaluate in the empty environment."""
        op = Operation.INTERPRET
        try:
            dexp = read_d0exp(source)
        except ReadError as e:
            return Result(op, revision, Outcome.INPUT_ERROR,
                          "Invalid input", str(e))
        try:
            dval = L.d0exp_evaluate(dexp, L.ENVnil())
        except RecursionError:
            return Result(op, revision, Outcome.BACKEND_FAILURE,
                          "Interpreter recursion limit exceeded")
        except Exception as e:
            return Result(op, revision, Outcome.LANGUAGE_ERROR,
                          "Runtime error", f"{type(e).__name__}: {e}")
        if _has_error_value(dval):
            return Result(op, revision, Outcome.LANGUAGE_ERROR,
                          "Runtime error: evaluation produced an error value",
                          repr(dval))
        return Result(op, revision, Outcome.OK, "Value", repr(dval))


def _has_error_value(dval: L.D0V000) -> bool:
    """True if dval is the D0V000() error sentinel or a pair containing it."""
    if type(dval) is L.D0V000:
        return True
    if isinstance(dval, L.D0Vpair):
        return _has_error_value(dval.arg1) or _has_error_value(dval.arg2)
    return False
