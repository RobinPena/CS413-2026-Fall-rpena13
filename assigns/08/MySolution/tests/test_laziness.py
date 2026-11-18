"""Laziness tests (TESTING.md R5).

Laziness is observed directly, never inferred from a formatted <lazy> value:
an interpreter call counter, stream tails that raise if forced, the
interpreter's own evaluated flags, weak references, and a lowered recursion
limit.
"""
from __future__ import annotations

import gc
import inspect
import sys
import unittest
import weakref
from collections import Counter

from MySolution import lambda_adapter as adapter
from MySolution.tests.support import count_applications, evaluate

FIRST_EVENT = {"event": "try", "column": 0, "row": 0, "board": []}


class LazinessTests(unittest.TestCase):
    def test_construction_applies_no_search(self):
        # The only application is queens_stream itself (a lam).
        with count_applications() as counts:
            cursor = adapter.open_stream(8)
        self.assertEqual(counts, Counter({"<lam>": 1}))
        self.assertFalse(cursor.evaluated)
        # The same holds in LAMBDA3 source, without the adapter.
        with count_applications() as counts:
            stream = evaluate("queens_stream(8)")
        self.assertEqual(counts, Counter({"<lam>": 1}))
        self.assertFalse(stream.evaluated)

    def test_counter_sees_search_work(self):
        # Control for the counter itself: consuming a stream does register search work.
        with count_applications() as counts:
            adapter.take(adapter.open_stream(4), 1000)
        self.assertGreater(counts["search"], 50)
        self.assertGreater(counts["check_safe"], 50)

    def test_forcing_one_cell_leaves_tail_unforced(self):
        cursor = adapter.open_stream(8)
        with count_applications() as counts:
            taken = adapter.take(cursor, 1)
        self.assertEqual(taken.events, [FIRST_EVENT])
        self.assertTrue(cursor.evaluated)
        self.assertFalse(taken.cursor.evaluated)
        self.assertEqual(counts["search"], 1)
        self.assertEqual(counts["check_safe"], 0)

    def test_bounded_prefix_sizes_8_9_10(self):
        for size in (8, 9, 10):
            for k in (1, 10, 50):
                with self.subTest(size=size, k=k):
                    cursor = adapter.open_stream(size)
                    with count_applications() as counts:
                        taken = adapter.take(cursor, k)
                    self.assertEqual(len(taken.events), k)
                    self.assertFalse(taken.done)
                    self.assertFalse(taken.cursor.evaluated)  # event k+1 not computed
                    # Work grows with k, not with the search tree: at most one
                    # search call per event, and each safety walk visits at most
                    # size - 1 queens plus the empty board.
                    self.assertLessEqual(counts["search"], k)
                    self.assertLessEqual(counts["check_safe"], k * size)

    def test_unread_failing_tail_is_never_run(self):
        # Computing the second cell raises: list_head of an empty list.
        stream = evaluate(
            "queens_emit(queens_ev_try(0, 0, list_nil()), lam (u: unit) => list_head(list_nil()))")
        taken = adapter.take(stream, 1)
        self.assertEqual(taken.events, [FIRST_EVENT])
        self.assertFalse(taken.cursor.evaluated)
        with self.assertRaises(ValueError):  # control: the tail really does fail
            adapter.take(taken.cursor, 1)

    def test_take_stops_at_done_without_forcing_its_tail(self):
        stream = evaluate("queens_emit(queens_ev_done(()), lam (u: unit) => list_head(list_nil()))")
        taken = adapter.take(stream, 5)
        self.assertEqual(taken.events, [{"event": "done"}])
        self.assertTrue(taken.done)
        self.assertIsNone(taken.cursor)

    def test_delivered_cells_are_released(self):
        cursor = adapter.open_stream(8)
        root = weakref.ref(cursor)
        first_cell = weakref.ref(adapter.force(cursor))
        taken = adapter.take(cursor, 20)
        del cursor
        gc.collect()
        self.assertIsNone(root())
        self.assertIsNone(first_cell())
        # The rest of the stream is still there to read.
        self.assertFalse(taken.cursor.evaluated)
        self.assertEqual(len(adapter.take(taken.cursor, 5).events), 5)

    def test_stack_depth_stays_bounded(self):
        # If continuations piled up on the Python stack, depth would grow with
        # the number of events and 5,000 events would overflow this limit.
        saved = sys.getrecursionlimit()
        sys.setrecursionlimit(len(inspect.stack(0)) + 150)
        try:
            taken = adapter.take(adapter.open_stream(10), 5000)
        finally:
            sys.setrecursionlimit(saved)
        self.assertEqual(len(taken.events), 5000)


if __name__ == "__main__":
    unittest.main()
