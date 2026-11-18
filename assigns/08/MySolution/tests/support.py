"""Helpers shared by the solver, laziness and adapter tests.

Everything here runs the real solver.lam on the supplied LAMBDA3 interpreter.
The validator and the reference enumerator are independent Python checks,
used only to judge the solver's output, never to produce it.
"""
from __future__ import annotations

import itertools
from collections import Counter
from contextlib import contextmanager
from functools import lru_cache

from MySolution import lambda_adapter as adapter
from MySolution.lambda_adapter import L
from basics0 import fnlist_cons  # importable once lambda_adapter has set sys.path

# The solver's event type and stream type, for test continuations in LAMBDA3.
E = "(sint, sint, sint, List[sint])"
STRM_E = f"Strm[{E}]"


def evaluate(source: str):
    """Type-check and evaluate a LAMBDA3 expression in the scope of solver.lam."""
    expression = L.D0Elets(adapter.DECLARATIONS, L.d0exp_parse(source))
    L.d0exp_typecheck(expression)
    return L.d0exp_evaluate(expression)


def to_python(value):
    """Convert LAMBDA3 integers, Booleans, lists and tuples to Python values."""
    if isinstance(value, (L.D0Vint, L.D0Vbtf)):
        return value.arg1
    if isinstance(value, L.D0Vtupl):
        return tuple(to_python(item) for item in value.arg1)
    if isinstance(value, L.D0Vlist):
        result, items = [], value.arg1
        while isinstance(items, fnlist_cons):
            result.append(to_python(items.arg1))
            items = items.arg2
        return result
    raise TypeError(f"cannot convert {type(value).__name__}")


def board_source(board: list[int]) -> str:
    """LAMBDA3 source for a row-order board, in the solver's newest-first order."""
    source = "list_nil()"
    for column in board:
        source = f"list_cons({column}, {source})"
    return source


def raw_events(stream, limit: int = 1000) -> list[tuple]:
    """Force a stream without the adapter's decoding.

    Returns (tag, column, row, row-order board) tuples, so test continuations
    may emit marker tags the adapter would reject.
    """
    result = []
    for _ in range(limit):
        cell = adapter.force(stream)
        if not cell.is_cons:
            break
        tag, column, row, board = to_python(cell.head)
        result.append((tag, column, row, board[::-1]))
        stream = cell.tail
    return result


# The longest trace the tests read (8x8 has 33,589 events). A broken search
# that never reaches done fails here instead of running for minutes.
TRACE_LIMIT = 40_000


def fresh_trace(size: int) -> list[dict]:
    """Every event of a newly opened stream, decoded by the adapter."""
    taken = adapter.take(adapter.open_stream(size), TRACE_LIMIT)
    if not taken.done:
        raise AssertionError(f"size {size}: no done event within {TRACE_LIMIT} events")
    return taken.events


@lru_cache(maxsize=None)
def trace(size: int) -> tuple[dict, ...]:
    """fresh_trace, computed once per size (the 8x8 trace takes seconds)."""
    return tuple(fresh_trace(size))


def solutions(events) -> list[list[int]]:
    return [event["board"] for event in events if event["event"] == "solution"]


def attacker(board: list[int], column: int, row: int) -> int | None:
    """The nearest earlier row whose queen attacks (row, column), or None."""
    for earlier in range(row - 1, -1, -1):
        if board[earlier] == column or abs(board[earlier] - column) == row - earlier:
            return earlier
    return None


def is_valid_partial(board: list[int], size: int) -> bool:
    """Columns in range, and no two queens share a column or a diagonal."""
    return (all(0 <= column < size for column in board)
            and all(attacker(board, board[row], row) is None for row in range(len(board))))


def reference_solutions(size: int) -> list[list[int]]:
    """Every solution in lexicographic order, by brute force over permutations."""
    return [list(p) for p in itertools.permutations(range(size)) if is_valid_partial(list(p), size)]


@contextmanager
def count_applications():
    """Count the function applications the interpreter performs, by fix name.

    lambda3 sends every application, including lazy_eval running a thunk,
    through the module function _d0val_apply, so wrapping it observes the
    work the solver really does. Applications of lam closures are counted
    under "<lam>".
    """
    counts = Counter()
    original = L._d0val_apply

    def counting(function, argument):
        counts[function.arg2.arg1 if isinstance(function, L.D0Vfix) else "<lam>"] += 1
        return original(function, argument)

    L._d0val_apply = counting
    try:
        yield counts
    finally:
        L._d0val_apply = original
