"""Test double for the LanguageBackend contract."""
from lambda_web.backend.contract import Artifact, Operation, Outcome, Result


class FakeBackend:
    """Records every call and returns a fixed result per operation."""

    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def _ok(self, op: Operation, revision: int) -> Result:
        self.calls.append((op.name.lower(), revision))
        return Result(op, revision, Outcome.OK, f"fake {op.value}")

    def lint(self, source, revision):
        return self._ok(Operation.LINT, revision)

    def interpret(self, source, revision):
        return self._ok(Operation.INTERPRET, revision)

    def typecheck(self, source, revision):
        return self._ok(Operation.TYPECHECK, revision)

    def compile(self, source, revision) -> tuple[Result, Artifact | None]:
        return self._ok(Operation.COMPILE, revision), None

    def execute(self, artifact):
        return self._ok(Operation.EXECUTE, artifact.revision)
