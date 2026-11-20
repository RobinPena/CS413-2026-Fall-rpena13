"""Adapter tests: interpreter location, solver type, JSON conversion, and take (TESTING.md R4, R5)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from MySolution import lambda_adapter as adapter
from MySolution.lambda_adapter import L, SolverError
from MySolution.tests.support import evaluate, trace

KEYS = {
    "try": {"event", "column", "row", "board"},
    "place": {"event", "column", "row", "board"},
    "reject": {"event", "column", "row", "board"},
    "backtrack": {"event", "column", "row", "board"},
    "solution": {"event", "board"},
    "done": {"event"},
}


class AdapterTests(unittest.TestCase):
    def test_imports_assignment_08_lambda3(self):
        expected = Path(__file__).resolve().parents[2] / "LAMBDA3"
        self.assertEqual(Path(L.__file__).resolve().parent, expected)
        self.assertEqual(adapter.LAMBDA3_DIR, expected)

    def test_solver_type(self):
        factory = L.D0Elets(adapter.DECLARATIONS, L.D0Evar("queens_stream"))
        self.assertEqual(L.format_type(L.d0exp_typecheck(factory)),
                         "sint -> Lazy[Stcn[(sint, sint, sint, List[sint])]]")

    def test_event_json_fields_and_row_order(self):
        kinds = set()
        for e in trace(4):
            self.assertEqual(set(e), KEYS[e["event"]], e)
            kinds.add(e["event"])
        self.assertEqual(kinds, set(KEYS))
        # Internal boards are newest row first; JSON boards are in row order.
        # Tags become names, and the -1 sentinels never appear.
        board = "list_cons(2, list_cons(0, list_nil()))"  # rows: 0 -> column 0, 1 -> column 2
        cases = {
            f"queens_ev_try(3, 2, {board})": {"event": "try", "column": 3, "row": 2, "board": [0, 2]},
            f"queens_ev_place(2, 1, {board})": {"event": "place", "column": 2, "row": 1, "board": [0, 2]},
            f"queens_ev_reject(1, 2, {board})": {"event": "reject", "column": 1, "row": 2, "board": [0, 2]},
            f"queens_ev_backtrack(3, 2, {board})": {"event": "backtrack", "column": 3, "row": 2, "board": [0, 2]},
            "queens_ev_solution(list_cons(2, list_cons(0, list_cons(3, list_cons(1, list_nil())))))":
                {"event": "solution", "board": [1, 3, 0, 2]},
            "queens_ev_done(())": {"event": "done"},
        }
        for source, expected in cases.items():
            with self.subTest(source):
                self.assertEqual(adapter.event_to_json(evaluate(source)), expected)

    def test_client_fixture_matches_solver(self):
        # The client tests replay this file; it must be the solver's real 4x4 trace.
        fixture = Path(__file__).resolve().parent / "js" / "fixtures" / "size4-trace.json"
        self.assertEqual(json.loads(fixture.read_text()), list(trace(4)))

    def test_take_continues_without_repeats_or_gaps(self):
        whole = adapter.take(adapter.open_stream(6), 40).events
        first = adapter.take(adapter.open_stream(6), 15)
        rest = adapter.take(first.cursor, 25)
        self.assertEqual(first.events + rest.events, whole)

    def test_take_returns_fewer_events_at_end_of_stream(self):
        taken = adapter.take(adapter.open_stream(4), 1000)
        self.assertEqual((len(taken.events), taken.done, taken.cursor), (139, True, None))
        # Exact boundary: the limit lands on the last event before done.
        first = adapter.take(adapter.open_stream(4), 138)
        self.assertFalse(first.done)
        self.assertFalse(first.cursor.evaluated)
        last = adapter.take(first.cursor, 1)
        self.assertEqual((last.events, last.done), ([{"event": "done"}], True))

    def test_open_stream_rejects_bad_sizes(self):
        for size in (3, 11, 0, -8, True, 8.0, "8", None):
            with self.subTest(size=size), self.assertRaises(ValueError):
                adapter.open_stream(size)
        for size in (4, 10):
            self.assertFalse(adapter.open_stream(size).evaluated)

    def test_stream_without_done_is_an_error(self):
        stream = evaluate(
            "queens_emit(queens_ev_try(0, 0, list_nil()), lam (u: unit) => queens_strm_nil(()))")
        with self.assertRaises(SolverError):
            adapter.take(stream, 5)

    def test_unknown_event_tag_is_an_error(self):
        stream = evaluate("queens_emit((9, 0, 0, list_nil()), lam (u: unit) => queens_strm_nil(()))")
        with self.assertRaises(SolverError):
            adapter.take(stream, 1)


if __name__ == "__main__":
    unittest.main()
