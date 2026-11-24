"""Business-rule atomicity under real threads (service.py and the store lock).

All threads wait at a barrier and then call the service together; no test
sleeps. Operations are so short that threads would rarely overlap by chance,
so RendezvousStore widens the window: the first two threads to read a record
wait for each other right after the read. With the store lock in place the
second thread cannot reach that point until the first has finished, so the
wait simply times out and the outcome is the same as without it. Without the
lock, both threads would read the same revision and both "win", which these
tests would report. The HTTP suite repeats the required same-revision race
through a real threaded server.
"""
from __future__ import annotations

import threading
import unittest

from MySolution.errors import ApiError
from MySolution.limits import Limits
from MySolution.service import StudioService
from MySolution.store import InMemoryStore

from .unit_support import ServiceTestCase, case_input, collection_input, if_match, program_input

THREADS = 16
RENDEZVOUS_SECONDS = 0.25  # how long the first reader waits for a second one


class RendezvousStore(InMemoryStore):
    """An in-memory store whose first two record reads, once armed, wait for each other."""

    def __init__(self) -> None:
        super().__init__()
        self.rendezvous: threading.Barrier | None = None   # armed by the test

    def _meet(self, result):
        if self.rendezvous is None:
            return result
        try:
            self.rendezvous.wait(timeout=RENDEZVOUS_SECONDS)
        except threading.BrokenBarrierError:
            pass        # expected with a working lock: the other thread is blocked on it
        return result

    def get_program(self, program_id):
        return self._meet(super().get_program(program_id))

    def get_collection(self, collection_id):
        return self._meet(super().get_collection(collection_id))

    def find_program_by_name(self, name):
        return self._meet(super().find_program_by_name(name))


def run_together(calls):
    """Start every call at the same moment; return each one's result or ApiError code."""
    barrier = threading.Barrier(len(calls))
    outcomes = [None] * len(calls)

    def worker(index, call):
        barrier.wait()
        try:
            outcomes[index] = call()
        except ApiError as error:
            outcomes[index] = error.code

    threads = [threading.Thread(target=worker, args=pair) for pair in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive(), "a worker thread did not finish"
    return outcomes


def codes(outcomes):
    return sorted(o if isinstance(o, str) else "ok" for o in outcomes)


class ConcurrentMutationTests(ServiceTestCase):

    def setUp(self):
        super().setUp()
        self.store = RendezvousStore()
        self.service = StudioService(self.store, self.limits, snapshots=self.snapshots)

    def arm_rendezvous(self):
        """Arm the rendezvous after setup, so only the raced calls use it."""
        self.store.rendezvous = threading.Barrier(2)

    def test_same_revision_updates_exactly_one_wins(self):
        program = self.service.create_program(program_input("p"))
        self.arm_rendezvous()
        outcomes = run_together([
            (lambda n=n: self.service.replace_program(program.id, if_match(1), program_input("p", f"v{n}")))
            for n in range(THREADS)])
        self.assertEqual(codes(outcomes), ["ok"] + ["revision_conflict"] * (THREADS - 1))
        winner = next(o for o in outcomes if not isinstance(o, str))
        stored = self.service.get_program(program.id)
        self.assertEqual(stored.revision, 2)
        self.assertEqual(stored.source, winner.source)

    def test_same_revision_case_adds_exactly_one_wins(self):
        collection = self.service.create_collection(collection_input("c"))
        self.arm_rendezvous()
        outcomes = run_together([
            (lambda n=n: self.service.add_case(collection.id, if_match(1), case_input(f"case {n}")))
            for n in range(THREADS)])
        self.assertEqual(codes(outcomes), ["ok"] + ["revision_conflict"] * (THREADS - 1))
        stored = self.service.get_collection(collection.id)
        self.assertEqual((stored.revision, len(stored.cases)), (2, 1))

    def test_same_name_creates_exactly_one_wins(self):
        self.arm_rendezvous()
        outcomes = run_together([lambda: self.service.create_program(program_input("same"))] * THREADS)
        self.assertEqual(codes(outcomes), ["duplicate_name"] * (THREADS - 1) + ["ok"])
        self.assertEqual(self.store.program_count(), 1)

    def test_update_and_delete_race_leaves_a_consistent_store(self):
        program = self.service.create_program(program_input("p"))
        self.arm_rendezvous()
        outcomes = run_together([
            lambda: self.service.replace_program(program.id, if_match(1), program_input("p", "new")),
            lambda: self.service.delete_program(program.id, if_match(1)),
        ])
        # Whichever ran first wins; the other sees a newer revision or no record.
        self.assertEqual(sum(not isinstance(o, str) for o in outcomes), 1, outcomes)
        self.assertTrue(set(codes(outcomes)) <= {"ok", "revision_conflict", "record_not_found"})


class ConcurrentCapacityTests(ServiceTestCase):

    limits = Limits(max_programs=5)

    def test_capacity_is_never_exceeded(self):
        outcomes = run_together([
            (lambda n=n: self.service.create_program(program_input(f"p{n}"))) for n in range(THREADS)])
        self.assertEqual(codes(outcomes), ["capacity_limit"] * (THREADS - 5) + ["ok"] * 5)
        self.assertEqual(self.store.program_count(), 5)


if __name__ == "__main__":
    unittest.main()
