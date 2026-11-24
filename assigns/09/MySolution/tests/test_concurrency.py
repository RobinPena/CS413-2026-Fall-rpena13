"""Concurrent same-revision requests through a real threaded HTTP server
(API.md section 7; Assign09 test item 7).

The service runs in Werkzeug's threaded server, the same server model as
`python -m MySolution`, so each request is handled on its own thread.
Client threads wait at a barrier and then send their requests together.
RendezvousStore (race_support.py) only widens the window in which a
missing lock would let both requests read the same revision; the HTTP
layer, validation, business rules, and in-memory store are the real ones.
"""
from __future__ import annotations

import http.client
import json
import logging
import threading
import unittest

from werkzeug.serving import make_server

from MySolution.app import create_app

from .http_support import API, etag
from .race_support import RendezvousStore, run_together

CASE = {"name": "k", "source": "1", "expected": {"kind": "value", "value": "1"}}


class ThreadedServerTestCase(unittest.TestCase):
    """A real threaded HTTP server on a free local port, one per test."""

    def setUp(self):
        werkzeug_log = logging.getLogger("werkzeug")
        level = werkzeug_log.level
        werkzeug_log.setLevel(logging.WARNING)           # no request log lines in test output
        self.addCleanup(werkzeug_log.setLevel, level)

        self.store = RendezvousStore()
        self.server = make_server("127.0.0.1", 0, create_app(store=self.store), threaded=True)
        # A short poll interval makes shutdown quick at the end of each test.
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05},
                                  daemon=True)
        thread.start()
        # Cleanups run last-in, first-out: stop serving, wait, close the socket.
        self.addCleanup(self.server.server_close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.server.shutdown)

    def request(self, method: str, path: str, body: object = None, if_match: str | None = None):
        """One request on its own connection; returns (status, headers, decoded body)."""
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        try:
            headers = {} if if_match is None else {"If-Match": if_match}
            data = None
            if body is not None:
                data = json.dumps(body).encode()
                headers["Content-Type"] = "application/json"
            connection.request(method, API + path, body=data, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            return response.status, dict(response.getheaders()), json.loads(payload) if payload else None
        finally:
            connection.close()


class SameRevisionRaceTests(ThreadedServerTestCase):

    def test_two_updates_with_the_same_revision_exactly_one_succeeds(self):
        status, _, body = self.request("POST", "/programs", {"name": "p", "source": "original"})
        path = f"/programs/{body['program']['id']}"
        self.store.arm()
        outcomes = run_together([
            lambda: self.request("PUT", path, {"name": "p", "source": "from client A"}, etag(1)),
            lambda: self.request("PUT", path, {"name": "p", "source": "from client B"}, etag(1)),
        ])
        statuses = sorted(status for status, _, _ in outcomes)
        self.assertEqual(statuses, [200, 409])
        winner = next(body for status, _, body in outcomes if status == 200)
        loser = next(body for status, _, body in outcomes if status == 409)
        self.assertEqual(loser["error"]["code"], "revision_conflict")
        self.assertEqual(loser["error"]["current_revision"], 2)

        status, headers, body = self.request("GET", path)
        self.assertEqual((status, headers["ETag"]), (200, etag(2)))
        self.assertEqual(body["program"]["revision"], 2)
        self.assertEqual(body["program"]["source"], winner["program"]["source"])

    def test_eight_case_adds_with_the_same_revision_exactly_one_succeeds(self):
        _, _, body = self.request("POST", "/collections", {"name": "c"})
        path = f"/collections/{body['collection']['id']}"
        self.store.arm()
        outcomes = run_together([
            (lambda n=n: self.request("POST", f"{path}/cases", {**CASE, "name": f"case {n}"}, etag(1)))
            for n in range(8)])
        self.assertEqual(sorted(status for status, _, _ in outcomes), [201] + [409] * 7)
        _, _, body = self.request("GET", path)
        self.assertEqual((body["collection"]["revision"], len(body["collection"]["cases"])), (2, 1))

    def test_update_and_delete_with_the_same_revision_exactly_one_succeeds(self):
        _, _, body = self.request("POST", "/programs", {"name": "p", "source": "1"})
        path = f"/programs/{body['program']['id']}"
        self.store.arm()
        outcomes = run_together([
            lambda: self.request("PUT", path, {"name": "p", "source": "2"}, etag(1)),
            lambda: self.request("DELETE", path, if_match=etag(1)),
        ])
        statuses = sorted(status for status, _, _ in outcomes)
        # Whichever ran first wins. After the update, the delete sees revision 2
        # (409); after the delete, the update finds no record (404).
        self.assertIn(statuses, ([200, 409], [204, 404]))


if __name__ == "__main__":
    unittest.main()
