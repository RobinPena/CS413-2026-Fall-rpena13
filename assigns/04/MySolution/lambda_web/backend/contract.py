"""Backend contract: the operations a language backend offers and the
results it returns.

The controller and tests depend only on this module, never on how a
particular backend runs the language tools, so a backend can be replaced
(e.g. by a real type checker/compiler, or a test double) without changing
the controller or view.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class Operation(Enum):
    LINT = "Lint"
    INTERPRET = "Interpret"
    TYPECHECK = "Type-check"
    COMPILE = "Compile"
    EXECUTE = "Execute"


class Outcome(Enum):
    OK = "ok"                            # operation succeeded
    INPUT_ERROR = "input error"          # source is not a valid d0exp
    LANGUAGE_ERROR = "language error"    # valid input the language rejects:
                                         # undeclared variables, runtime failure
    BACKEND_FAILURE = "backend failure"  # tool crashed or hit its time limit
    NOT_IMPLEMENTED = "not implemented"  # operation has no implementation yet


@dataclass(frozen=True)
class Result:
    """Outcome of one operation on one source revision.

    `message` is a one-line summary; `output` holds longer text such as an
    evaluated value or diagnostic. Both are plain text, never markup.
    """
    operation: Operation
    revision: int
    outcome: Outcome
    message: str
    output: str = ""

    @property
    def ok(self) -> bool:
        return self.outcome is Outcome.OK


@dataclass(frozen=True)
class Artifact:
    """Generated code produced by Compile and consumed by Execute.

    An artifact belongs to exactly one source revision; any change to the
    source invalidates it. Execute must run the artifact as given and never
    recompile or fall back to interpretation.
    """
    revision: int
    format: str      # e.g. "python", "js", "wasm"
    code: str


class LanguageBackend(Protocol):
    """Language tools the controller calls. Every method returns a Result
    tagged with the given operation and revision, and reports failures as
    a Result rather than raising."""

    def lint(self, source: str, revision: int) -> Result: ...
    def interpret(self, source: str, revision: int) -> Result: ...
    def typecheck(self, source: str, revision: int) -> Result: ...
    def compile(self, source: str,
                revision: int) -> tuple[Result, Artifact | None]: ...
    def execute(self, artifact: Artifact) -> Result: ...
