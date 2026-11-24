"""Helpers for the concurrency tests (unit and HTTP).

Operations are so short that threads would rarely overlap by chance, so
RendezvousStore widens the window: once armed, the first two threads to read
a record wait for each other right after the read. With the store lock in
place the second thread cannot reach that point until the first has
finished, so the wait simply times out and the outcome is the same as
without it. Without the lock, both threads would read the same revision and
both "win", which the tests would report. No test sleeps.
"""
from __future__ import annotations

import threading

from MySolution.store import InMemoryStore

RENDEZVOUS_SECONDS = 0.25  # how long the first reader waits for a second one


class RendezvousStore(InMemoryStore):
    """An in-memory store whose first two record reads, once armed, wait for each other."""

    def __init__(self) -> None:
        super().__init__()
        self.rendezvous: threading.Barrier | None = None   # armed by the test

    def arm(self) -> None:
        """Arm after setup, so only the raced calls use the rendezvous."""
        self.rendezvous = threading.Barrier(2)

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


def run_together(calls, catch=()):
    """Start every call at the same moment and return their results in order.

    An exception of a type in `catch` becomes that call's result instead.
    """
    barrier = threading.Barrier(len(calls))
    outcomes = [None] * len(calls)

    def worker(index, call):
        barrier.wait()
        try:
            outcomes[index] = call()
        except catch as error:
            outcomes[index] = error

    threads = [threading.Thread(target=worker, args=pair) for pair in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive(), "a worker thread did not finish"
    return outcomes
