"""LAMBDA backend: real Lint and Interpret built on the supplied lambda1.py.

Implements the LanguageBackend contract. Every method returns a Result;
errors from reading or evaluating the source are reported, not raised.
Type-check, Compile and Execute are placeholders that report they are not
implemented; they never claim success or produce an artifact.
"""
import multiprocessing

from lambda_web.backend import lambda1 as L
from lambda_web.backend.contract import Artifact, Operation, Outcome, Result
from lambda_web.backend.reader import ReadError, read_d0exp

INTERPRET_TIMEOUT_S = 5.0


class LambdaBackend:

    def __init__(self, timeout: float = INTERPRET_TIMEOUT_S):
        self.timeout = timeout

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
        """Evaluate in a child process, killed after `self.timeout` seconds.

        A separate process is used because a running thread cannot be
        stopped; killing the process guarantees a nonterminating or very
        slow program cannot leave the application busy.
        """
        return _run_bounded(_interpret, source, revision, self.timeout)

    def typecheck(self, source: str, revision: int) -> Result:
        return Result(Operation.TYPECHECK, revision, Outcome.NOT_IMPLEMENTED,
                      "Type checking is not yet implemented.")

    def compile(self, source: str,
                revision: int) -> tuple[Result, Artifact | None]:
        return (Result(Operation.COMPILE, revision, Outcome.NOT_IMPLEMENTED,
                       "Compilation is not yet implemented.",
                       "No generated code was produced, so Execute is "
                       "unavailable."),
                None)

    def execute(self, artifact: Artifact) -> Result:
        return Result(Operation.EXECUTE, artifact.revision,
                      Outcome.NOT_IMPLEMENTED,
                      "Executing generated code is not yet implemented.")


def _interpret(source: str, revision: int) -> Result:
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


def _run_bounded(fn, source: str, revision: int, timeout: float) -> Result:
    """Run fn(source, revision) in a child process with a time limit."""
    ctx = multiprocessing.get_context("spawn")
    recv_end, send_end = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child, args=(send_end, fn, source, revision),
                       daemon=True)
    proc.start()
    send_end.close()
    try:
        if recv_end.poll(timeout):
            return recv_end.recv()
        return Result(Operation.INTERPRET, revision, Outcome.BACKEND_FAILURE,
                      f"Timed out after {timeout:g} s",
                      "The program did not finish within the time limit.")
    except EOFError:
        return Result(Operation.INTERPRET, revision, Outcome.BACKEND_FAILURE,
                      "Interpreter process exited unexpectedly")
    finally:
        if proc.is_alive():
            proc.kill()
        proc.join()
        recv_end.close()


def _child(conn, fn, source: str, revision: int) -> None:
    try:
        conn.send(fn(source, revision))
    finally:
        conn.close()
