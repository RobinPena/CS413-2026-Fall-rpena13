"""Placeholder operations and the bounded Interpret."""
import time

from lambda_web.backend.contract import Artifact, Operation, Outcome
from lambda_web.backend.lambda_backend import LambdaBackend
from tests.programs import ADD_42, fib

B = LambdaBackend()


def test_typecheck_is_not_implemented():
    r = B.typecheck(ADD_42, 2)
    assert (r.operation, r.revision, r.outcome) == \
        (Operation.TYPECHECK, 2, Outcome.NOT_IMPLEMENTED)
    assert not r.ok
    assert "not yet implemented" in r.message


def test_compile_is_not_implemented_and_yields_no_artifact():
    r, artifact = B.compile(ADD_42, 2)
    assert (r.operation, r.outcome) == \
        (Operation.COMPILE, Outcome.NOT_IMPLEMENTED)
    assert not r.ok
    assert artifact is None
    assert "Execute" in r.output


def test_execute_is_not_implemented():
    r = B.execute(Artifact(revision=2, format="python", code=""))
    assert (r.operation, r.outcome) == \
        (Operation.EXECUTE, Outcome.NOT_IMPLEMENTED)
    assert not r.ok


def test_slow_program_times_out_then_retry_succeeds():
    fast = LambdaBackend(timeout=0.5)
    start = time.monotonic()
    r = fast.interpret(fib(30), 4)
    assert time.monotonic() - start < 3
    assert r.outcome is Outcome.BACKEND_FAILURE
    assert r.message.startswith("Timed out")

    retry = fast.interpret(ADD_42, 5)
    assert retry.ok and retry.output == "D0Vint(arg1=42)"
