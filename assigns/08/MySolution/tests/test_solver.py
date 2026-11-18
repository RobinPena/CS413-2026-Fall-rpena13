"""Solver tests: safety, CPS paths, exhaustive search, and events (TESTING.md R1-R4).

Every test runs solver.lam on the supplied LAMBDA3 interpreter.
"""
from __future__ import annotations

import unittest
from collections import Counter

from MySolution.tests.support import (
    STRM_E, attacker, board_source, count_applications, evaluate, fresh_trace,
    is_valid_partial, raw_events, reference_solutions, solutions, to_python, trace,
)

TRY, PLACE, REJECT, BACKTRACK = 0, 1, 2, 3
MARK_FAILURE, MARK_SUCCESS = 7, 8  # tags emitted only by test continuations

# The first 16 events of the 4x4 search.
SIZE4_OPENING = [
    {"event": "try", "column": 0, "row": 0, "board": []},
    {"event": "place", "column": 0, "row": 0, "board": [0]},
    {"event": "try", "column": 0, "row": 1, "board": [0]},
    {"event": "reject", "column": 0, "row": 1, "board": [0]},
    {"event": "try", "column": 1, "row": 1, "board": [0]},
    {"event": "reject", "column": 1, "row": 1, "board": [0]},
    {"event": "try", "column": 2, "row": 1, "board": [0]},
    {"event": "place", "column": 2, "row": 1, "board": [0, 2]},
    {"event": "try", "column": 0, "row": 2, "board": [0, 2]},
    {"event": "reject", "column": 0, "row": 2, "board": [0, 2]},
    {"event": "try", "column": 1, "row": 2, "board": [0, 2]},
    {"event": "reject", "column": 1, "row": 2, "board": [0, 2]},
    {"event": "try", "column": 2, "row": 2, "board": [0, 2]},
    {"event": "reject", "column": 2, "row": 2, "board": [0, 2]},
    {"event": "try", "column": 3, "row": 2, "board": [0, 2]},
    {"event": "reject", "column": 3, "row": 2, "board": [0, 2]},
]


def attacks(row1: int, col1: int, row2: int, col2: int) -> bool:
    return to_python(evaluate(f"queens_attacks({row1}, {col1}, {row2}, {col2})"))


def check_safe(row: int, column: int, board: list[int]) -> str:
    """Run queens_check_safe at answer type sint; report which continuation it took."""
    answer = to_python(evaluate(
        f"queens_check_safe({row}, {column}, 1, {board_source(board)}, "
        "lam (u: unit) => 1, lam (u: unit) => 0)"))
    return {1: "safe", 0: "conflict"}[answer]


def search_with_markers(n: int, row: int, column: int, board: list[int]) -> list[tuple]:
    """Run queens_search from any state, with test continuations that emit markers.

    The success continuation emits (8, 80, 80, board) and then calls the
    resume continuation it was given; the failure continuation emits
    (7, 70, 70, []) and ends the stream.
    """
    sk = f"lam (p: (List[sint], unit -> {STRM_E})) => queens_emit((8, 80, 80, p.0), p.1)"
    fk = "lam (u: unit) => queens_emit((7, 70, 70, list_nil()), lam (v: unit) => queens_strm_nil(()))"
    return raw_events(evaluate(
        f"queens_search({n}, {row}, {column}, {board_source(board)}, {sk}, {fk})"))


def event(kind: str, column: int, row: int, board: list[int]) -> dict:
    return {"event": kind, "column": column, "row": row, "board": board}


def resume_after(column: int, row: int, board: list[int], size: int) -> dict:
    """The event that must follow a finished candidate (column, row) on board.

    The next column of the same row if there is one; otherwise the parent
    row's failure continuation: its backtrack, or done at the root.
    """
    if column + 1 < size:
        return event("try", column + 1, row, board)
    if row > 0:
        return event("backtrack", board[-1], row - 1, board[:-1])
    return {"event": "done"}


class SafetyTests(unittest.TestCase):
    def test_attacks_same_row(self):
        self.assertTrue(attacks(3, 0, 3, 5))
        self.assertTrue(attacks(0, 7, 0, 1))

    def test_attacks_same_column(self):
        self.assertTrue(attacks(0, 2, 5, 2))
        self.assertTrue(attacks(6, 0, 1, 0))

    def test_attacks_down_right_diagonal(self):  # row - column is equal
        self.assertTrue(attacks(1, 1, 4, 4))
        self.assertTrue(attacks(5, 2, 3, 0))

    def test_attacks_down_left_diagonal(self):  # row + column is equal
        self.assertTrue(attacks(0, 5, 3, 2))
        self.assertTrue(attacks(4, 1, 2, 3))

    def test_attacks_safe_pair(self):
        for squares in [(0, 0, 1, 2), (0, 0, 2, 1), (2, 3, 5, 1), (7, 7, 0, 1)]:
            with self.subTest(squares=squares):
                self.assertFalse(attacks(*squares))

    def test_check_safe_calls_on_safe(self):
        self.assertEqual(check_safe(0, 3, []), "safe")
        self.assertEqual(check_safe(2, 4, [0, 2]), "safe")
        self.assertEqual(check_safe(3, 2, [1, 3, 0]), "safe")  # completes [1, 3, 0, 2]

    def test_check_safe_conflicts_column_and_both_diagonals(self):
        # (row, column, board, row of the only attacking queen)
        cases = {
            "column, adjacent row": (1, 2, [2], 0),
            "column, two rows back": (2, 2, [2, 0], 0),
            "down-right diagonal, adjacent row": (1, 1, [0], 0),
            "down-right diagonal, two rows back": (2, 3, [1, 5], 0),
            "down-left diagonal, adjacent row": (1, 2, [3], 0),
            "down-left diagonal, two rows back": (2, 1, [3, 6], 0),
        }
        for label, (row, column, board, attacking_row) in cases.items():
            with self.subTest(label):
                self.assertTrue(is_valid_partial(board, 8))
                self.assertEqual(attacker(board, column, row), attacking_row)
                self.assertEqual(check_safe(row, column, board), "conflict")

    def test_check_safe_stops_at_first_conflict(self):
        # On [1, 3, 0], the queen in row 2 (column 0) shares column 0 with (3, 0).
        with count_applications() as counts:
            self.assertEqual(check_safe(3, 0, [1, 3, 0]), "conflict")
        self.assertEqual(counts["check_safe"], 1)
        # A safe candidate is checked against all three queens, then the empty board.
        with count_applications() as counts:
            self.assertEqual(check_safe(3, 2, [1, 3, 0]), "safe")
        self.assertEqual(counts["check_safe"], 4)


class CpsTests(unittest.TestCase):
    def test_complete_board_calls_success_with_resume(self):
        # row = n: success gets the board, and the resume it gets is exactly fk.
        self.assertEqual(search_with_markers(4, 4, 0, [1, 3, 0, 2]),
                         [(MARK_SUCCESS, 80, 80, [1, 3, 0, 2]), (MARK_FAILURE, 70, 70, [])])

    def test_exhausted_row_calls_failure(self):
        # Size 4 on [0, 2]: every column of row 2 is attacked, so fk runs.
        expected = []
        for column in range(4):
            expected += [(TRY, column, 2, [0, 2]), (REJECT, column, 2, [0, 2])]
        self.assertEqual(search_with_markers(4, 2, 0, [0, 2]),
                         expected + [(MARK_FAILURE, 70, 70, [])])
        # Starting mid-row resumes at that column, not at column 0.
        self.assertEqual(search_with_markers(4, 2, 2, [0, 2]),
                         expected[4:] + [(MARK_FAILURE, 70, 70, [])])

    def test_success_then_resume_at_next_candidate(self):
        board = [1, 3, 0]
        self.assertEqual(search_with_markers(4, 3, 0, board), [
            (TRY, 0, 3, board), (REJECT, 0, 3, board),
            (TRY, 1, 3, board), (REJECT, 1, 3, board),
            (TRY, 2, 3, board), (PLACE, 2, 3, board + [2]),
            (MARK_SUCCESS, 80, 80, board + [2]),
            # resume: the child's failure continuation backtracks, then tries column 3.
            (BACKTRACK, 2, 3, board),
            (TRY, 3, 3, board), (REJECT, 3, 3, board),
            (MARK_FAILURE, 70, 70, []),
        ])

    def test_reject_resumes_at_next_column(self):
        events = trace(8)
        wrong = [i for i, e in enumerate(events) if e["event"] == "reject"
                 and events[i + 1] != resume_after(e["column"], e["row"], e["board"], 8)]
        self.assertEqual(wrong, [])

    def test_backtrack_resumes_at_next_column_in_parent_row(self):
        events = trace(8)
        wrong = [i for i, e in enumerate(events) if e["event"] == "backtrack"
                 and events[i + 1] != resume_after(e["column"], e["row"], e["board"], 8)]
        self.assertEqual(wrong, [])

    def test_solution_resumes_with_backtrack_of_last_row(self):
        events = trace(8)
        for i, e in enumerate(events):
            if e["event"] == "solution":
                board = e["board"]
                self.assertEqual(events[i - 1], event("place", board[-1], 7, board))
                self.assertEqual(events[i + 1], event("backtrack", board[-1], 7, board[:-1]))


class ExhaustiveSearchTests(unittest.TestCase):
    def test_size4_reference_trace(self):
        events = trace(4)
        self.assertEqual(list(events[:16]), SIZE4_OPENING)
        self.assertEqual(solutions(events), [[1, 3, 0, 2], [2, 0, 3, 1]])
        self.assertEqual(len(events), 139)

    def test_size8_has_92_valid_unique_solutions(self):
        boards = solutions(trace(8))
        self.assertEqual(len(boards), 92)
        self.assertEqual(len({tuple(board) for board in boards}), 92)
        for board in boards:
            self.assertEqual(len(board), 8)
            self.assertTrue(is_valid_partial(board, 8), board)

    def test_size8_lexicographic_dfs_order(self):
        self.assertEqual(solutions(trace(8)), reference_solutions(8))

    def test_size8_deterministic_across_fresh_streams(self):
        self.assertEqual(fresh_trace(8), list(trace(8)))

    def test_small_size_solution_counts(self):
        for size, count in [(4, 2), (5, 10), (6, 4)]:
            with self.subTest(size=size):
                boards = solutions(trace(size))
                self.assertEqual(len(boards), count)
                self.assertEqual(boards, reference_solutions(size))


class EventTests(unittest.TestCase):
    def test_all_event_kinds_present(self):
        kinds = Counter(e["event"] for e in trace(8))
        self.assertEqual(kinds, Counter(
            {"try": 15720, "reject": 13664, "place": 2056, "backtrack": 2056, "solution": 92, "done": 1}))
        # Every try is decided exactly once, and every placed queen is later removed.
        self.assertEqual(kinds["try"], kinds["place"] + kinds["reject"])
        self.assertEqual(kinds["place"], kinds["backtrack"])

    def test_one_queen_per_row_invariant(self):
        for size in (4, 8):
            for e in trace(size):
                if "board" not in e:
                    continue
                with self.subTest(size=size, event=e):
                    board = e["board"]
                    self.assertTrue(is_valid_partial(board, size))
                    if e["event"] == "solution":
                        self.assertEqual(len(board), size)
                        continue
                    self.assertTrue(0 <= e["row"] < size and 0 <= e["column"] < size)
                    # One queen in each row above the candidate's row.
                    expected = e["row"] + 1 if e["event"] == "place" else e["row"]
                    self.assertEqual(len(board), expected)

    def test_snapshot_semantics(self):
        """Replay the trace against a model board kept by the test itself."""
        events = trace(8)
        model: list[int] = []
        for i, e in enumerate(events):
            kind = e["event"]
            if kind == "try":
                self.assertEqual((e["row"], e["board"]), (len(model), model), i)
            elif kind in ("place", "reject"):
                self.assertEqual(events[i - 1], event("try", e["column"], e["row"], model), i)
                if kind == "place":
                    model = model + [e["column"]]
                self.assertEqual(e["board"], model, i)
            elif kind == "backtrack":
                self.assertEqual((model[-1], len(model) - 1), (e["column"], e["row"]), i)
                model = model[:-1]
                self.assertEqual(e["board"], model, i)
            elif kind == "solution":
                self.assertEqual(e["board"], model, i)
            else:
                self.assertEqual((kind, model), ("done", []), i)

    def test_every_reject_has_an_attacking_queen(self):
        for e in trace(8):
            if e["event"] in ("reject", "place"):
                found = attacker(e["board"], e["column"], e["row"]) if e["event"] == "reject" \
                    else attacker(e["board"][:-1], e["column"], e["row"])
                self.assertEqual(found is not None, e["event"] == "reject", e)

    def test_done_exactly_once_and_last(self):
        for size in (4, 5, 6, 8):
            with self.subTest(size=size):
                events = trace(size)
                self.assertEqual([e for e in events if e["event"] == "done"], [{"event": "done"}])
                self.assertEqual(events[-1], {"event": "done"})


if __name__ == "__main__":
    unittest.main()
