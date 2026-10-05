"""Test double for the LanguageBackend contract."""
import threading

from lambda_web.backend.contract import Artifact, Operation, Outcome, Result


class FakeBackend:
    """Records every call and returns an OK result per operation.

    Options let tests inject behavior without touching the controller or
    view: `crashes` makes the next N calls raise, `gate` makes calls wait
    until the test releases it, and `artifact` makes Compile produce
    generated code so Execute becomes available.
    """

    def __init__(self, *, crashes: int = 0,
                 gate: threading.Event | None = None,
                 artifact: bool = False):
        self.calls: list[tuple[str, int, str]] = []
        self.crashes = crashes
        self.gate = gate
        self.artifact = artifact
        self.started = threading.Event()

    def _call(self, op: Operation, revision: int, payload: str) -> Result:
        self.calls.append((op.name.lower(), revision, payload))
        self.started.set()
        if self.gate is not None:
            self.gate.wait(timeout=5)
        if self.crashes:
            self.crashes -= 1
            raise RuntimeError("injected backend crash")
        return Result(op, revision, Outcome.OK, f"fake {op.value}")

    def lint(self, source, revision):
        return self._call(Operation.LINT, revision, source)

    def interpret(self, source, revision):
        return self._call(Operation.INTERPRET, revision, source)

    def typecheck(self, source, revision):
        return self._call(Operation.TYPECHECK, revision, source)

    def compile(self, source, revision) -> tuple[Result, Artifact | None]:
        result = self._call(Operation.COMPILE, revision, source)
        return result, (Artifact(revision, "fake", "generated")
                        if self.artifact else None)

    def execute(self, artifact):
        return self._call(Operation.EXECUTE, artifact.revision, artifact.code)
