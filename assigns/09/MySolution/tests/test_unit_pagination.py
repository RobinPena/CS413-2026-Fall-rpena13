"""Unit checks of snapshot pagination (pagination.py through service.py, API.md section 6)."""
from __future__ import annotations

import unittest

from MySolution.limits import Limits

from .unit_support import ServiceTestCase, case_input, collection_input, if_match, page, program_input


class SnapshotTests(ServiceTestCase):

    def setUp(self):
        super().setUp()
        self.a, self.b, self.c = (self.service.create_program(program_input(name, f"{n} + {n}"))
                                  for n, name in enumerate("ABC", start=1))

    def names(self, result):
        return [record.name for record in result.items]

    def test_order_is_creation_order_and_unchanged_by_updates(self):
        self.service.replace_program(self.a.id, if_match(1), program_input("A", "updated"))
        self.assertEqual(self.names(self.service.list_programs(page(10))), ["A", "B", "C"])

    def test_single_page_keeps_no_snapshot(self):
        result = self.service.list_programs(page(3))
        self.assertEqual((self.names(result), result.next_cursor), (["A", "B", "C"], None))
        self.assertEqual(self.snapshots.open_count(), 0)

    def test_empty_list(self):
        result = self.service.list_collections(page(50))
        self.assertEqual((result.items, result.next_cursor), ((), None))

    def test_later_pages_come_from_the_captured_snapshot(self):
        first = self.service.list_programs(page(2))
        self.assertEqual(self.names(first), ["A", "B"])
        self.assertIsNotNone(first.next_cursor)

        # Meanwhile: update C, delete A, add D.
        self.service.replace_program(self.c.id, if_match(1), program_input("C", "changed"))
        self.service.delete_program(self.a.id, if_match(1))
        self.service.create_program(program_input("D"))

        second = self.service.list_programs(page(2, first.next_cursor))
        self.assertEqual(self.names(second), ["C"])
        self.assertIs(second.items[0], self.c)                 # the captured value, revision 1
        self.assertEqual(second.items[0].source, "3 + 3")
        self.assertIsNone(second.next_cursor)

        fresh = self.service.list_programs(page(10))
        self.assertEqual(self.names(fresh), ["B", "C", "D"])
        self.assertEqual(fresh.items[1].revision, 2)

    def test_a_cursor_can_be_repeated_and_limit_can_change(self):
        first = self.service.list_programs(page(1))
        again = self.service.list_programs(page(1, first.next_cursor))
        self.assertEqual(self.names(again), ["B"])
        self.assertEqual(self.service.list_programs(page(1, first.next_cursor)), again)
        rest = self.service.list_programs(page(5, first.next_cursor))
        self.assertEqual((self.names(rest), rest.next_cursor), (["B", "C"], None))

    def test_whole_chain_visits_every_record_once(self):
        for n in range(17):
            self.service.create_program(program_input(f"extra {n}"))
        seen, cursor = [], None
        while True:
            result = self.service.list_programs(page(4, cursor))
            seen += self.names(result)
            cursor = result.next_cursor
            if cursor is None:
                break
        self.assertEqual(seen, ["A", "B", "C"] + [f"extra {n}" for n in range(17)])

    def test_collection_snapshots_keep_captured_cases(self):
        collection = self.service.create_collection(collection_input("one"))
        collection = self.service.add_case(collection.id, if_match(1), case_input("case"))
        self.service.create_collection(collection_input("two"))
        first = self.service.list_collections(page(1))
        self.service.delete_case(collection.id, collection.cases[0].id, if_match(2))
        self.assertEqual([case.name for case in first.items[0].cases], ["case"])
        second = self.service.list_collections(page(1, first.next_cursor))
        self.assertEqual(self.names(second), ["two"])

    def test_malformed_cursors(self):
        for cursor in ("", "abc", "q8ZtN3wXyR5vK1mB7cJd0A", "q8ZtN3wXyR5vK1mB7cJd0A.0",
                       "q8ZtN3wXyR5vK1mB7cJd0A.-1", "q8ZtN3wXyR5vK1mB7cJd0A.02", "q8ZtN3wXyR5vK1mB7cJd0!.2",
                       " q8ZtN3wXyR5vK1mB7cJd0A.2"):
            self.assertApiError("invalid_request", self.service.list_programs, page(2, cursor),
                                field="cursor", reason="malformed_cursor")

    def test_unknown_cursors(self):
        first = self.service.list_programs(page(2))
        key = first.next_cursor.split(".")[0]
        for cursor in ("q8ZtN3wXyR5vK1mB7cJd0A.2",      # never issued
                       f"{key}.3", f"{key}.99"):        # past the end of the snapshot
            self.assertApiError("invalid_request", self.service.list_programs, page(2, cursor),
                                reason="unknown_cursor")
        # A programs cursor is not valid for the collections list.
        self.assertApiError("invalid_request", self.service.list_collections, page(2, first.next_cursor),
                            reason="unknown_cursor")

    def test_snapshot_expires_after_idle_time_and_use_renews_it(self):
        first = self.service.list_programs(page(1))
        self.monotonic.now += 599
        self.service.list_programs(page(1, first.next_cursor))      # renews the timer
        self.monotonic.now += 599
        self.service.list_programs(page(1, first.next_cursor))
        self.monotonic.now += 600
        self.assertApiError("invalid_request", self.service.list_programs, page(1, first.next_cursor),
                            reason="unknown_cursor")
        self.assertEqual(self.snapshots.open_count(), 0)


class SnapshotCapacityTests(ServiceTestCase):

    limits = Limits(max_snapshots=2)

    def test_full_registry_refuses_new_snapshots_without_evicting(self):
        for name in "ABC":
            self.service.create_program(program_input(name))
        first = self.service.list_programs(page(1))
        second = self.service.list_programs(page(1))
        self.assertApiError("capacity_limit", self.service.list_programs, page(1),
                            resource="list_snapshots", limit=2)
        # Both open snapshots still work, and a single-page list needs no snapshot.
        self.service.list_programs(page(1, first.next_cursor))
        self.service.list_programs(page(1, second.next_cursor))
        self.assertEqual(len(self.service.list_programs(page(10)).items), 3)

    def test_expired_snapshots_make_room(self):
        for name in "ABC":
            self.service.create_program(program_input(name))
        self.service.list_programs(page(1))
        self.service.list_programs(page(1))
        self.monotonic.now += 600
        self.service.list_programs(page(1))
        self.assertEqual(self.snapshots.open_count(), 1)


if __name__ == "__main__":
    unittest.main()
