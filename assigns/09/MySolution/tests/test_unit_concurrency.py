"""Business-rule atomicity under real threads (service.py and the store lock).

All threads wait at a barrier and then call the service together; the
RendezvousStore (race_support.py) makes a missing lock show up as two
winners. test_concurrency.py repeats the required same-revision race through
a real threaded HTTP server.
"""
from __future__ import annotations

import unittest

from MySolution.errors import ApiError
from MySolution.limits import Limits
from MySolution.service import StudioService

from .race_support import RendezvousStore, run_together
from .unit_support import ServiceTestCase, case_input, collection_input, if_match, program_input

THREADS = 16


def codes(outcomes):
    return sorted(o.code if isinstance(o, ApiError) else "ok" for o in outcomes)


def call_together(calls):
    return run_together(calls, catch=ApiError)


class ConcurrentMutationTests(ServiceTestCase):

    def setUp(self):
        super().setUp()
        self.store = RendezvousStore()
        self.service = StudioService(self.store, self.limits, snapshots=self.snapshots)

    def test_same_revision_updates_exactly_one_wins(self):
        program = self.service.create_program(program_input("p"))
        self.store.arm()
        outcomes = call_together([
            (lambda n=n: self.service.replace_program(program.id, if_match(1), program_input("p", f"v{n}")))
            for n in range(THREADS)])
        self.assertEqual(codes(outcomes), ["ok"] + ["revision_conflict"] * (THREADS - 1))
        winner = next(o for o in outcomes if not isinstance(o, ApiError))
        stored = self.service.get_program(program.id)
        self.assertEqual(stored.revision, 2)
        self.assertEqual(stored.source, winner.source)

    def test_same_revision_case_adds_exactly_one_wins(self):
        collection = self.service.create_collection(collection_input("c"))
        self.store.arm()
        outcomes = call_together([
            (lambda n=n: self.service.add_case(collection.id, if_match(1), case_input(f"case {n}")))
            for n in range(THREADS)])
        self.assertEqual(codes(outcomes), ["ok"] + ["revision_conflict"] * (THREADS - 1))
        stored = self.service.get_collection(collection.id)
        self.assertEqual((stored.revision, len(stored.cases)), (2, 1))

    def test_same_name_creates_exactly_one_wins(self):
        self.store.arm()
        outcomes = call_together([lambda: self.service.create_program(program_input("same"))] * THREADS)
        self.assertEqual(codes(outcomes), ["duplicate_name"] * (THREADS - 1) + ["ok"])
        self.assertEqual(self.store.program_count(), 1)

    def test_update_and_delete_race_leaves_a_consistent_store(self):
        program = self.service.create_program(program_input("p"))
        self.store.arm()
        outcomes = call_together([
            lambda: self.service.replace_program(program.id, if_match(1), program_input("p", "new")),
            lambda: self.service.delete_program(program.id, if_match(1)),
        ])
        # Whichever ran first wins; the other sees a newer revision or no record.
        self.assertEqual(sum(not isinstance(o, ApiError) for o in outcomes), 1, outcomes)
        self.assertTrue(set(codes(outcomes)) <= {"ok", "revision_conflict", "record_not_found"})


class ConcurrentCapacityTests(ServiceTestCase):

    limits = Limits(max_programs=5)

    def test_capacity_is_never_exceeded(self):
        outcomes = call_together([
            (lambda n=n: self.service.create_program(program_input(f"p{n}"))) for n in range(THREADS)])
        self.assertEqual(codes(outcomes), ["capacity_limit"] * (THREADS - 5) + ["ok"] * 5)
        self.assertEqual(self.store.program_count(), 5)


if __name__ == "__main__":
    unittest.main()
