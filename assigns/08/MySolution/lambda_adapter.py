"""Bridge between Python and the LAMBDA3 solver in solver.lam (DESIGN.md section 5).

    open_stream(size) -> cursor          a fresh, unforced Strm[Event]
    take(cursor, limit) -> Taken         force at most `limit` cells, decode them
    event_to_json(value) -> dict         one LAMBDA3 event tuple as a JSON event

This module loads trusted code, applies and forces interpreter values, and
converts events to JSON. It does not search: every event comes from
solver.lam. Forcing goes through the interpreter's own lazy_eval, so
memoization works exactly as it does in LAMBDA3 source.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

SOLUTION_DIR = Path(__file__).resolve().parent
LAMBDA3_DIR = SOLUTION_DIR.parent / "LAMBDA3"
SOLVER_PATH = SOLUTION_DIR / "solver.lam"

if str(LAMBDA3_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA3_DIR))

import lambda3 as L  # noqa: E402  (needs LAMBDA3_DIR on sys.path)
from basics0 import fnlist_cons, fnlist_nil  # noqa: E402

# Refuse to run against another assignment's copy of the interpreter.
if Path(L.__file__).resolve().parent != LAMBDA3_DIR:
    raise ImportError(f"lambda3 must come from {LAMBDA3_DIR}, not {L.__file__}")

MIN_SIZE = 4
MAX_SIZE = 10

EVENT_NAMES = ("try", "place", "reject", "backtrack", "solution", "done")

EVENT_TYPE = L.TTuple((L.TSint(), L.TSint(), L.TSint(), L.TList(L.TSint())))
STREAM_TYPE = L.TLazy(L.TStcn(EVENT_TYPE))


class SolverError(RuntimeError):
    """The solver produced something its contract rules out."""


def load_declarations(path: Path = SOLVER_PATH):
    """Parse and type-check solver.lam; check the factory's type."""
    declarations = L.d0cls_parse(path.read_text(encoding="utf-8"))
    L.d0cls_typecheck(declarations)
    factory_type = L.d0exp_typecheck(L.D0Elets(declarations, L.D0Evar("queens_stream")))
    if factory_type != L.TFun(L.TSint(), STREAM_TYPE):
        raise SolverError(f"queens_stream has type {L.format_type(factory_type)}")
    return declarations


DECLARATIONS = load_declarations()
_FACTORY = L.d0exp_evaluate(L.D0Elets(DECLARATIONS, L.D0Evar("queens_stream")))

_OPEN = L.D0Eapp(L.D0Evar("queens_stream"), L.D0Evar("size"))
_FORCE = L.D0Eop1("lazy_eval", L.D0Evar("cursor"))


def open_stream(size: int) -> L.D0Vlazy:
    """Apply queens_stream to size. No search runs until the result is forced."""
    if isinstance(size, bool) or not isinstance(size, int) or not MIN_SIZE <= size <= MAX_SIZE:
        raise ValueError(f"board size must be an integer from {MIN_SIZE} to {MAX_SIZE}")
    env = L.ENVcns("size", L.D0Vint(size), L.ENVcns("queens_stream", _FACTORY, L.ENVnil()))
    cursor = L.d0exp_evaluate(_OPEN, env)
    if not isinstance(cursor, L.D0Vlazy):
        raise SolverError("queens_stream did not return a lazy stream")
    return cursor


def force(cursor: L.D0Vlazy) -> L.D0Vstcn:
    """Evaluate lazy_eval(cursor) in LAMBDA3, returning the stream cell."""
    cell = L.d0exp_evaluate(_FORCE, L.ENVcns("cursor", cursor, L.ENVnil()))
    if not isinstance(cell, L.D0Vstcn):
        raise SolverError("forcing a stream did not produce a stream cell")
    return cell


def _int(value) -> int:
    if not isinstance(value, L.D0Vint):
        raise SolverError("malformed event: integer expected")
    return value.arg1


def board_to_json(board) -> list[int]:
    """Solver boards list the newest row first; JSON boards are in row order.

    This is the only place a board is reversed.
    """
    if not isinstance(board, L.D0Vlist):
        raise SolverError("malformed event: board list expected")
    columns = []
    items = board.arg1
    while isinstance(items, fnlist_cons):
        columns.append(_int(items.arg1))
        items = items.arg2
    if not isinstance(items, fnlist_nil):
        raise SolverError("malformed event: improper board list")
    columns.reverse()
    return columns


def event_to_json(value) -> dict:
    """Convert (tag, column, row, board) to its documented JSON object."""
    if not isinstance(value, L.D0Vtupl) or len(value.arg1) != 4:
        raise SolverError("malformed event: 4-tuple expected")
    tag, column, row, board = value.arg1
    tag = _int(tag)
    if not 0 <= tag < len(EVENT_NAMES):
        raise SolverError(f"malformed event: unknown tag {tag}")
    name = EVENT_NAMES[tag]
    if name == "done":
        return {"event": "done"}
    if name == "solution":
        return {"event": "solution", "board": board_to_json(board)}
    return {"event": name, "column": _int(column), "row": _int(row),
            "board": board_to_json(board)}


@dataclass(frozen=True)
class Taken:
    """The result of take: decoded events, where to continue, and whether done was delivered."""

    events: list[dict]
    cursor: L.D0Vlazy | None  # the unforced tail to read next; None after done
    done: bool


def take(cursor: L.D0Vlazy, limit: int) -> Taken:
    """Force at most limit cells starting at cursor.

    The tail of the last delivered cell is returned unforced, and the tail
    after done is never forced.
    """
    if limit < 1:
        raise ValueError("limit must be at least 1")
    events = []
    for _ in range(limit):
        cell = force(cursor)
        if not cell.is_cons:
            raise SolverError("stream ended without a done event")
        event = event_to_json(cell.head)
        events.append(event)
        if event["event"] == "done":
            return Taken(events, None, True)
        cursor = cell.tail
    return Taken(events, cursor, False)
