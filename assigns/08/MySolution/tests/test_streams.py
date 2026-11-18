"""Stream table tests: IDs, independence, bounded reads, exhaustion, close,
expiry, the open-stream limit, failures and concurrency (TESTING.md R6).

Successful reads use the real adapter and LAMBDA3. The doubles are a fake
clock, a take that fails, and a take that sleeps to make races likely.
"""
from __future__ import annotations

import gc
import json
import threading
import time
import unittest
import uuid
import weakref

from MySolution import lambda_adapter
from MySolution.errors import STREAM_NOT_FOUND, TOO_MANY_STREAMS, RpcError
from MySolution.streams import MAX_STREAMS, StreamTable
from MySolution.tests.http_support import FakeClock
from MySolution.tests.support import count_applications, trace

TTL = 300.0


class StreamTableTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.table = StreamTable(clock=self.clock, ttl=TTL)

    def open(self, size: int = 8) -> str:
        return self.table.open(size)["stream_id"]

    def read_all(self, stream_id: str, limit: int = 32) -> list[dict]:
        events = []
        while True:
            result = self.table.next(stream_id, limit)
            events += result["events"]
            if result["done"]:
                return events

    def assert_not_found(self, operation, *args):
        with self.assertRaises(RpcError) as caught:
            operation(*args)
        self.assertEqual(caught.exception.code, STREAM_NOT_FOUND)

    def test_open_returns_uuid_and_does_not_force(self):
        with count_applications() as counts:
            result = self.table.open(8)
        self.assertEqual(set(result), {"stream_id", "size"})
        self.assertEqual(result["size"], 8)
        self.assertEqual(uuid.UUID(result["stream_id"]).version, 4)
        self.assertEqual((counts["search"], counts["check_safe"]), (0, 0))
        self.assertFalse(self.table.entries[result["stream_id"]].cursor.evaluated)
        self.assertNotEqual(self.open(8), result["stream_id"])

    def test_streams_are_independent(self):
        a, b, c = self.open(6), self.open(6), self.open(4)
        seen = {a: [], b: [], c: []}
        for stream_id, limit in [(a, 3), (b, 5), (a, 4), (c, 2), (b, 2), (a, 1), (c, 6)]:
            seen[stream_id] += self.table.next(stream_id, limit)["events"]
        self.assertEqual(seen[a], list(trace(6)[:8]))
        self.assertEqual(seen[b], list(trace(6)[:7]))
        self.assertEqual(seen[c], list(trace(4)[:8]))

    def test_next_never_forces_beyond_limit(self):
        stream_id = self.open(8)
        read = 0
        for limit in (1, 5, 32):
            result = self.table.next(stream_id, limit)
            read += limit
            self.assertEqual(result, {"events": list(trace(8)[read - limit:read]), "done": False})
            self.assertFalse(self.table.entries[stream_id].cursor.evaluated)
        # Terminal case: stop exactly one event before done, then read past it.
        stream_id = self.open(4)
        for limit in (32, 32, 32, 32, 10):  # 138 of the 139 events
            self.assertFalse(self.table.next(stream_id, limit)["done"])
        self.assertFalse(self.table.entries[stream_id].cursor.evaluated)
        self.assertEqual(self.table.next(stream_id, 32), {"events": [{"event": "done"}], "done": True})

    def test_exhaustion_releases_solver_state(self):
        stream_id = self.open(4)
        self.table.next(stream_id, 130)
        last_cursor = weakref.ref(self.table.entries[stream_id].cursor)
        result = self.table.next(stream_id, 32)
        self.assertEqual(len(result["events"]), 9)
        self.assertTrue(result["done"])
        entry = self.table.entries[stream_id]
        self.assertIsNone(entry.cursor)
        self.assertTrue(entry.exhausted)
        gc.collect()
        self.assertIsNone(last_cursor())  # the solver state is really gone

    def test_repeated_next_after_exhaustion(self):
        stream_id = self.open(4)
        self.assertEqual(self.read_all(stream_id), list(trace(4)))
        for _ in range(3):
            self.assertEqual(self.table.next(stream_id, 1), {"events": [], "done": True})

    def test_close_then_next_is_stream_not_found(self):
        live, exhausted = self.open(8), self.open(4)
        self.read_all(exhausted)
        for stream_id in (live, exhausted):
            with self.subTest(stream_id=stream_id):
                self.assertEqual(self.table.close(stream_id), {"closed": True})
                self.assertNotIn(stream_id, self.table.entries)
                self.assert_not_found(self.table.next, stream_id, 1)
                self.assert_not_found(self.table.close, stream_id)

    def test_unknown_id_is_stream_not_found(self):
        for stream_id in ("", "nope", str(uuid.uuid4())):
            with self.subTest(stream_id=stream_id):
                self.assert_not_found(self.table.next, stream_id, 1)
                self.assert_not_found(self.table.close, stream_id)

    def test_active_stream_expires_after_ttl(self):
        kept, idle = self.open(), self.open()
        self.clock.advance(TTL - 0.001)
        self.assertEqual(len(self.table.next(kept, 1)["events"]), 1)  # still alive
        self.clock.advance(0.001)  # idle has now been unused for exactly TTL
        self.assert_not_found(self.table.next, idle, 1)
        self.assertEqual(len(self.table.next(kept, 1)["events"]), 1)

    def test_activity_refreshes_deadline(self):
        stream_id = self.open()
        self.assertEqual(self.table.entries[stream_id].expires_at, self.clock.now + TTL)
        for _ in range(3):  # 600 s in total, never more than 200 s idle
            self.clock.advance(200)
            self.table.next(stream_id, 1)
            self.assertEqual(self.table.entries[stream_id].expires_at, self.clock.now + TTL)
        self.clock.advance(TTL)
        self.assert_not_found(self.table.next, stream_id, 1)

    def test_exhausted_record_expires(self):
        stream_id = self.open(4)
        self.read_all(stream_id)
        self.clock.advance(TTL - 1)
        self.assertEqual(self.table.next(stream_id, 1), {"events": [], "done": True})
        self.clock.advance(TTL)
        self.assert_not_found(self.table.next, stream_id, 1)

    def test_sweep_reclaims_expired_entries(self):
        old = [self.open() for _ in range(3)]
        self.clock.advance(TTL)
        self.assertEqual(set(self.table.entries), set(old))  # nothing has run yet
        new = self.open()
        self.assertEqual(set(self.table.entries), {new})

    def test_open_limit(self):
        ids = [self.open() for _ in range(MAX_STREAMS)]
        with self.assertRaises(RpcError) as caught:
            self.table.open(8)
        self.assertEqual((caught.exception.code, caught.exception.data),
                         (TOO_MANY_STREAMS, {"limit": MAX_STREAMS}))
        self.assertEqual(len(self.table), MAX_STREAMS)
        self.table.close(ids[0])  # closing frees a slot
        self.open()
        self.clock.advance(TTL)  # so does expiry
        self.open()
        self.assertEqual(len(self.table), 1)

    def test_internal_failure_removes_stream(self):
        def failing_take(cursor, limit):
            raise RuntimeError("interpreter failure")

        table = StreamTable(clock=self.clock, take=failing_take)
        stream_id = table.open(8)["stream_id"]
        with self.assertRaises(RuntimeError):
            table.next(stream_id, 1)
        self.assert_not_found(table.next, stream_id, 1)

    def test_concurrent_next_has_no_duplicates_or_gaps(self):
        def slow_take(cursor, limit):
            time.sleep(0.002)  # widen the window between reading and storing the cursor
            return lambda_adapter.take(cursor, limit)

        table = StreamTable(clock=self.clock, take=slow_take)
        stream_id = table.open(6)["stream_id"]
        received, received_lock = [], threading.Lock()

        def reader():
            for _ in range(20):
                events = table.next(stream_id, 2)["events"]
                with received_lock:
                    received.extend(events)

        threads = [threading.Thread(target=reader) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        expected = trace(6)[:160]
        self.assertEqual(len(received), 160)
        self.assertEqual(sorted(map(json.dumps, received)), sorted(map(json.dumps, expected)))


if __name__ == "__main__":
    unittest.main()
