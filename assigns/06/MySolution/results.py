"""Expected kinds, outcome types and errors shared across the pipeline.

Outcomes a caller must handle (a run that finished, a budget that ran out, an
observation that decoded, ran out or met an unexpected shape) are returned as
small frozen dataclasses, so the caller has to look at which case it received.
Inputs outside a function's contract (an unsupported source form, an open
target term given to execution, a negative budget) raise exceptions instead.

This module imports nothing from the rest of the package, so every other
module can depend on it without creating a cycle.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

V = TypeVar("V")


########################################################################
# Expected kinds. Church zero and FALSE are the same lambda term, so a
# caller must say which kind of data it expects before anything is decoded.

@dataclass(frozen=True)
class NatKind:
    def __str__(self) -> str:
        return "natural"


@dataclass(frozen=True)
class BoolKind:
    def __str__(self) -> str:
        return "boolean"


@dataclass(frozen=True)
class PairKind:
    first: Kind
    second: Kind

    def __str__(self) -> str:
        return f"({self.first}, {self.second})"


type Kind = NatKind | BoolKind | PairKind

NAT = NatKind()
BOOL = BoolKind()

# Decoded data in Python: int for a natural, bool for a boolean, and a
# 2-tuple for a pair.
type Data = int | bool | tuple[Data, Data]


def has_kind(kind: Kind, data: object) -> bool:
    """Whether data is Python data of the given kind; a bool is never a natural."""
    match kind:
        case NatKind():
            return type(data) is int and data >= 0
        case BoolKind():
            return type(data) is bool
        case PairKind(first, second):
            return (type(data) is tuple and len(data) == 2
                    and has_kind(first, data[0]) and has_kind(second, data[1]))
    raise TypeError(f"unsupported expected kind: {kind!r}")


def same_data(left: object, right: object) -> bool:
    """Equality that keeps naturals and booleans apart, unlike 1 == True."""
    if type(left) is not type(right):
        return False
    if type(left) is tuple:
        return (len(left) == len(right)
                and all(same_data(a, b) for a, b in zip(left, right)))
    return left == right


def format_data(data: Data) -> str:
    """Print decoded data the way the source language writes it."""
    if type(data) is bool:
        return "true" if data else "false"
    if type(data) is tuple:
        return f"({format_data(data[0])}, {format_data(data[1])})"
    return str(data)


########################################################################
# Evaluation outcomes. `steps` counts contractions of an application of a
# function value; for target terms these are exactly the beta-value steps.

@dataclass(frozen=True)
class Completed(Generic[V]):
    """Evaluation reached a value; `budget` is None for an unbounded run."""
    value: V
    steps: int
    budget: int | None


@dataclass(frozen=True)
class Exhausted:
    """Another step was needed after `budget` steps had been used.

    This is not a proof that the program diverges.
    """
    steps: int
    budget: int


########################################################################
# Observation outcomes. Their step counts and budgets cover observation
# only; the execution that produced the observed value is reported apart.
# `path` names the part of the result being observed, such as "result" or
# "result.first.second".

@dataclass(frozen=True)
class Decoded:
    data: Data
    steps: int
    budget: int


@dataclass(frozen=True)
class ObservationExhausted:
    steps: int
    budget: int
    path: str


@dataclass(frozen=True)
class Malformed:
    reason: str
    steps: int
    budget: int
    path: str


type Observation = Decoded | ObservationExhausted | Malformed


########################################################################
# Errors.

class UnsupportedSourceError(ValueError):
    """The source AST uses a literal or operator outside the language.

    `detail` names the offending literal or operator, and `path` lists the
    constructors from the root down to it.
    """

    def __init__(self, detail: str, path: tuple[str, ...] = ()) -> None:
        self.detail = detail
        self.path = path
        where = " > ".join(path) if path else "the root"
        super().__init__(f"{detail} (at {where})")


class OpenTermError(ValueError):
    """Target execution was asked to run a term with free variables."""

    def __init__(self, names: frozenset[str]) -> None:
        self.names = names
        super().__init__(
            "target execution needs a closed term; free variables: "
            + ", ".join(sorted(names)))


class SourceEvaluationError(RuntimeError):
    """Source evaluation met an ill-typed operation or an unbound variable."""
