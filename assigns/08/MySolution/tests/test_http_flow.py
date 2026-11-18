"""End-to-end HTTP tests (TESTING.md R8, R9).

HttpLazinessTests counts interpreter work around real HTTP requests.
FullFlowTests runs the app on a real local socket and reads a whole 8x8
search through POST /rpc, exactly as the browser client does.
"""
from __future__ import annotations

import json
import logging
import threading
import unittest
import urllib.request
from collections import Counter

from werkzeug.serving import make_server

from MySolution.app import create_app
from MySolution.tests.http_support import HttpTestCase, request_object
from MySolution.tests.support import count_applications, is_valid_partial, reference_solutions, trace


class HttpLazinessTests(HttpTestCase):
    def test_open_and_next_force_only_what_is_returned(self):
        with count_applications() as counts:
            stream_id = self.open_stream(8)
        self.assertEqual(counts, Counter({"<lam>": 1}))  # only queens_stream itself
        self.assertFalse(self.table.entries[stream_id].cursor.evaluated)
        read = 0
        for limit in (1, 7, 32):
            with count_applications() as counts:
                events = self.result("queens.next", {"stream_id": stream_id, "limit": limit})["events"]
            read += limit
            self.assertEqual(events, list(trace(8)[read - limit:read]))
            self.assertFalse(self.table.entries[stream_id].cursor.evaluated)  # event read+1 untouched
            self.assertLessEqual(counts["search"], limit)
        # Exact boundary and terminal case on a 4x4 stream (139 events).
        stream_id = self.open_stream(4)
        for limit in (32, 32, 32, 32, 10):
            self.assertFalse(self.result("queens.next", {"stream_id": stream_id, "limit": limit})["done"])
        self.assertFalse(self.table.entries[stream_id].cursor.evaluated)
        self.assertEqual(self.result("queens.next", {"stream_id": stream_id, "limit": 32}),
                         {"events": [{"event": "done"}], "done": True})
        self.assertIsNone(self.table.entries[stream_id].cursor)


class FullFlowTests(unittest.TestCase):
    """A real server on 127.0.0.1 with an OS-chosen port."""

    @classmethod
    def setUpClass(cls):
        cls.werkzeug_logger = logging.getLogger("werkzeug")
        cls.saved_level = cls.werkzeug_logger.level
        cls.werkzeug_logger.setLevel(logging.WARNING)  # no access-log line per request
        cls.server = make_server("127.0.0.1", 0, create_app(), threaded=True)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/rpc"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()
        cls.werkzeug_logger.setLevel(cls.saved_level)

    def rpc(self, method: str, params: dict, request_id: int = 1) -> dict:
        body = json.dumps(request_object(method, params, request_id)).encode()
        request = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get_content_type(), "application/json")
            answer = json.load(response)
        self.assertEqual(answer["id"], request_id)
        self.assertNotIn("error", answer, answer)
        return answer["result"]

    def read_to_done(self, stream_id: str) -> tuple[list[dict], int]:
        events, requests = [], 0
        while True:
            requests += 1
            result = self.rpc("queens.next", {"stream_id": stream_id, "limit": 32}, requests)
            self.assertLessEqual(len(result["events"]), 32)
            events += result["events"]
            if result["done"]:
                self.assertEqual(result["events"][-1], {"event": "done"})
                return events, requests
            self.assertEqual(len(result["events"]), 32)  # only the last response is short

    def test_size8_http_open_to_done(self):
        self.assertEqual(self.rpc("service.health", {}), {"status": "ok", "version": "1.0"})
        opened = self.rpc("queens.open", {"size": 8})
        self.assertEqual(opened["size"], 8)
        events, requests = self.read_to_done(opened["stream_id"])
        self.assertEqual(len(events), 33589)
        self.assertEqual(requests, -(-33589 // 32))
        boards = [e["board"] for e in events if e["event"] == "solution"]
        self.assertEqual(len(boards), 92)
        self.assertTrue(all(is_valid_partial(board, 8) and len(board) == 8 for board in boards))
        self.assertEqual(boards, reference_solutions(8))
        self.assertEqual([e for e in events if e["event"] == "done"], [{"event": "done"}])
        self.assertEqual(events, list(trace(8)))  # exactly the solver's stream, nothing lost or added

    def test_repeated_terminal_reads_then_close(self):
        stream_id = self.rpc("queens.open", {"size": 4})["stream_id"]
        events, _ = self.read_to_done(stream_id)
        self.assertEqual(len(events), 139)
        for _ in range(3):
            self.assertEqual(self.rpc("queens.next", {"stream_id": stream_id, "limit": 32}),
                             {"events": [], "done": True})
        self.assertEqual(self.rpc("queens.close", {"stream_id": stream_id}), {"closed": True})
        body = json.dumps(request_object("queens.next", {"stream_id": stream_id, "limit": 1}, 5)).encode()
        request = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            self.assertEqual(json.load(response),
                             {"jsonrpc": "2.0", "error": {"code": -32020, "message": "Stream not found"}, "id": 5})


if __name__ == "__main__":
    unittest.main()
