"""Bounded observation of target values as naturals, booleans and pairs.

    observe(value, kind, budget) -> Decoded | ObservationExhausted | Malformed

A finished execution yields a lambda whose body may still contain redexes,
so its data cannot be read off its syntax, and reducing under its binders
is not allowed. Instead each observer applies the value to a small pure
context and runs that with the shared evaluator under a step budget. Call
by value then leaves a result of fixed shape that Python can inspect.

Natural: run  n STEP BASE  where

    STEP = lam tail. lam c. lam z. c tail
    BASE = lam c. lam z. z

  Every tail is a value before STEP receives it, so a numeral n leaves a
  finished spine of n nodes over a base:

    node = lam c. lam z. c tail       where tail is another closed spine
    base = lam c. lam z. z

  Python counts the nodes, matching the shapes up to renaming of c and z.
  Anything else is Malformed rather than silently read as some number.

Boolean: run  b YES NO  where

    YES = lam a. lam b. lam c. a
    NO  = lam a. lam b. lam c. c

  TRUE selects YES and FALSE selects NO; the result is compared with each
  marker up to alpha-equivalence. With three parameters the markers differ
  from each other and from TRUE, FALSE and every numeral, so a numeral
  greater than zero, for example, leaves neither marker and is Malformed.

Pair: run  FST v  and decode the result with the first component's kind,
  then do the same with  SND v  and the second kind, recursively.

The caller must say which kind to expect: NUM(0) and FALSE are the same
term, decoded as 0 or false according to that kind.

One observation budget covers the whole observation. Projections and all
nested component observations draw on the same remaining budget, and the
reported step count is their total. Steps of the execution that produced
the value are never included. A pair is reported Decoded only when every
component decoded; otherwise the outcome names the path of the component
where observation stopped, such as "result.first".

Not every invalid term is detected: an untyped term may happen to produce
a valid spine or marker, such as I, which observes as the natural 1.
"""
from __future__ import annotations

from .encodings import FST, SND
from .evaluator import evaluate
from .results import (
    BoolKind, Decoded, Exhausted, Kind, Malformed, NatKind, Observation,
    ObservationExhausted, PairKind,
)
from .target import App, Lam, Term, Var, alpha_equivalent, app, lam, show

STEP = lam("tail", "c", "z", App(Var("c"), Var("tail")))
BASE = lam("c", "z", Var("z"))
YES = lam("a", "b", "c", Var("a"))
NO = lam("a", "b", "c", Var("c"))


def observe(value: Term, kind: Kind, budget: int) -> Observation:
    """Decode a finished target value as data of the expected kind."""
    if type(budget) is not int or budget < 0:
        raise ValueError(f"budget must be a nonnegative integer, not {budget!r}")
    _check_kind(kind)
    if not isinstance(value, Lam):
        raise ValueError("observe needs a value (a lambda); run the program first")
    session = _Session(budget)
    try:
        data = session.decode(value, kind, "result")
    except _OutOfBudget as stop:
        return ObservationExhausted(session.used, budget, stop.path)
    except _BadShape as bad:
        return Malformed(bad.reason, session.used, budget, bad.path)
    return Decoded(data, session.used, budget)


def _check_kind(kind: Kind) -> None:
    match kind:
        case NatKind() | BoolKind():
            return
        case PairKind(first, second):
            _check_kind(first)
            _check_kind(second)
            return
    raise TypeError(f"unsupported expected kind: {kind!r}")


class _OutOfBudget(Exception):
    def __init__(self, path: str) -> None:
        self.path = path


class _BadShape(Exception):
    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason


class _Session:
    """One observation: the shared budget and the steps used so far."""

    def __init__(self, budget: int) -> None:
        self.budget = budget
        self.used = 0

    def run(self, term: Term, path: str) -> Term:
        result = evaluate(term, self.budget - self.used)
        self.used += result.steps
        if isinstance(result, Exhausted):
            raise _OutOfBudget(path)
        return result.value

    def decode(self, value: Term, kind: Kind, path: str):
        match kind:
            case NatKind():
                return _count_spine(self.run(app(value, STEP, BASE), path), path)
            case BoolKind():
                return _selected_marker(self.run(app(value, YES, NO), path), path)
            case PairKind(first_kind, second_kind):
                first_path, second_path = path + ".first", path + ".second"
                first = self.run(App(FST, value), first_path)
                first_data = self.decode(first, first_kind, first_path)
                second = self.run(App(SND, value), second_path)
                return (first_data, self.decode(second, second_kind, second_path))


def _count_spine(term: Term, path: str) -> int:
    # The only variables in a spine are each level's own c and z, matched by
    # name against that level's binders, so a tail that refers to an outer
    # binder fails to match at its own level. An accepted spine is closed.
    count, node = 0, term
    while True:
        match node:
            case Lam(_, Lam(z, Var(name))) if name == z:
                return count
            case Lam(c, Lam(z, App(Var(name), tail))) if name == c != z:
                count += 1
                node = tail
            case _:
                raise _BadShape(path, (
                    f"natural observation ended in {show(node, 60)}, which is "
                    "neither a spine node (lam c. lam z. c tail) nor the base "
                    "(lam c. lam z. z)"))


def _selected_marker(term: Term, path: str) -> bool:
    if alpha_equivalent(term, YES):
        return True
    if alpha_equivalent(term, NO):
        return False
    raise _BadShape(path, (
        f"boolean observation ended in {show(term, 60)}, which is neither "
        f"marker {show(YES)} nor {show(NO)}"))
