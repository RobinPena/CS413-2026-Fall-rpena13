"""Helpers for tests that go through the HTTP layer.

HttpTestCase builds a fresh app for each test, with a stream table driven by
a fake clock, and talks to it through Flask's test client, so every request
passes through the real transport, dispatcher, methods and stream table.
"""
from __future__ import annotations

import json
import unittest

from MySolution.app import create_app
from MySolution.streams import StreamTable

ABSENT = object()  # marks a request member that is left out entirely


class FakeClock:
    """A monotonic clock that only moves when a test advances it."""

    def __init__(self, now: float = 1000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def request_object(method: object, params: object = ABSENT, request_id: object = ABSENT) -> dict:
    """A JSON-RPC 2.0 request; leave request_id out to build a notification."""
    request = {"jsonrpc": "2.0", "method": method}
    if params is not ABSENT:
        request["params"] = params
    if request_id is not ABSENT:
        request["id"] = request_id
    return request


class HttpTestCase(unittest.TestCase):
    """Base class: self.client posts to an app whose table uses self.clock."""

    def setUp(self) -> None:
        self.clock = FakeClock()
        self.table = StreamTable(clock=self.clock)
        self.app = create_app(table=self.table)
        self.client = self.app.test_client()

    def post_raw(self, body: bytes, content_type: str | None = "application/json", path: str = "/rpc"):
        headers = {} if content_type is None else {"Content-Type": content_type}
        return self.client.post(path, data=body, headers=headers)

    def post(self, payload: object) -> dict:
        """POST a JSON value and return the body of the HTTP 200 JSON response."""
        response = self.post_raw(json.dumps(payload).encode())
        self.assertEqual(response.status_code, 200, response.data[:300])
        self.assertEqual(response.mimetype, "application/json")
        return response.get_json()

    def call(self, method: str, params: object = ABSENT, request_id: object = 1) -> dict:
        body = self.post(request_object(method, params, request_id))
        self.assertEqual(body["id"], request_id)
        return body

    def result(self, method: str, params: object = ABSENT):
        body = self.call(method, params)
        self.assertIn("result", body, body)
        return body["result"]

    def error(self, method: str, params: object = ABSENT) -> dict:
        body = self.call(method, params)
        self.assertIn("error", body, body)
        self.assertNotIn("result", body)
        return body["error"]

    def notify(self, method: str, params: object = ABSENT) -> None:
        """Send a notification and check the empty 204 answer."""
        response = self.post_raw(json.dumps(request_object(method, params)).encode())
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, b"")
        self.assertNotIn("Content-Type", response.headers)

    def open_stream(self, size: int = 8) -> str:
        return self.result("queens.open", {"size": size})["stream_id"]
