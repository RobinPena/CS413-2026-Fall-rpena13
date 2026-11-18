"""JSON-RPC tests through the HTTP layer: envelope, methods, params,
notifications, errors and transport (TESTING.md R7, R8).
"""
from __future__ import annotations

import json
import uuid

from MySolution.app import MAX_BODY_BYTES, create_app
from MySolution.streams import MAX_STREAMS, StreamTable
from MySolution.tests.http_support import ABSENT, HttpTestCase, request_object
from MySolution.tests.support import trace

HEALTH = json.dumps(request_object("service.health", {}, 1)).encode()


class EnvelopeTests(HttpTestCase):
    def test_ids_are_echoed(self):
        for request_id in (0, -1, 7, 2**53, "abc", "", "0", 1.5, None):
            with self.subTest(request_id=request_id):
                body = self.call("service.health", {}, request_id)
                self.assertIs(type(body["id"]), type(request_id))
                self.assertEqual(body["result"], {"status": "ok", "version": "1.0"})

    def test_invalid_envelopes(self):
        good = request_object("service.health", {}, 1)
        cases = {
            "jsonrpc 1.0": {**good, "jsonrpc": "1.0"},
            "jsonrpc as number": {**good, "jsonrpc": 2.0},
            "no jsonrpc": {k: v for k, v in good.items() if k != "jsonrpc"},
            "no method": {k: v for k, v in good.items() if k != "method"},
            "method not a string": {**good, "method": 5},
            "params a number": {**good, "params": 3},
            "params a string": {**good, "params": "size"},
            "params null": {**good, "params": None},
            "id true": {**good, "id": True},
            "id an object": {**good, "id": {}},
            "id an array": {**good, "id": [1]},
            "extra member": {**good, "extra": 0},
            "body a number": 3,
            "body a string": "service.health",
            "body null": None,
            "body true": True,
        }
        for label, payload in cases.items():
            with self.subTest(label):
                body = self.post(payload)
                self.assertEqual(body["id"], None)
                self.assertEqual(body["error"]["code"], -32600)
                self.assertEqual(body["error"]["message"], "Invalid Request")
                self.assertIn("reason", body["error"]["data"])

    def test_invalid_request_without_id_still_answered(self):
        for payload in ({"jsonrpc": "1.0", "method": "service.health"},
                        {"jsonrpc": "2.0", "method": 5}):
            with self.subTest(payload=payload):
                body = self.post(payload)  # HTTP 200 with a body, not a 204
                self.assertEqual((body["error"]["code"], body["id"]), (-32600, None))

    def test_parse_errors(self):
        cases = {
            "truncated": b'{"jsonrpc": "2.0", "method": ',
            "empty body": b"",
            "trailing comma": b'{"jsonrpc": "2.0", "method": "service.health", "id": 1,}',
            "invalid UTF-8": b'{"jsonrpc": "2.0", "method": "\xff", "id": 1}',
            "NaN": b'{"jsonrpc": "2.0", "method": "queens.open", "params": {"size": NaN}, "id": 1}',
            "infinite float": b'{"jsonrpc": "2.0", "method": "queens.open", "params": {"size": 1e999}, "id": 1}',
        }
        for label, raw in cases.items():
            with self.subTest(label):
                response = self.post_raw(raw)
                self.assertEqual(response.status_code, 200)
                body = response.get_json()
                self.assertEqual((body["error"]["code"], body["id"]), (-32700, None))
        self.assertEqual(len(self.table), 0)

    def test_batches_not_supported(self):
        for payload in ([], [request_object("service.health", {}, 1)],
                        [request_object("queens.open", {"size": 8}, 1)]):
            with self.subTest(payload=payload):
                body = self.post(payload)
                self.assertEqual(body, {"jsonrpc": "2.0", "id": None, "error": {
                    "code": -32600, "message": "Invalid Request", "data": {"reason": "batch_not_supported"}}})
        self.assertEqual(len(self.table), 0)  # the queens.open inside the batch never ran


class MethodTests(HttpTestCase):
    def test_health(self):
        for params in (ABSENT, {}):
            self.assertEqual(self.result("service.health", params), {"status": "ok", "version": "1.0"})
        self.assertEqual(self.error("service.health", [])["data"], {"reason": "not_an_object"})
        self.assertEqual(self.error("service.health", {"verbose": True})["data"],
                         {"reason": "unexpected", "fields": ["verbose"]})

    def test_unknown_methods(self):
        for name in ("queens.reset", "lambda.interpret", "__init__", "", "Service.health",
                     "queens.open ", "rpc.discover", "build_methods"):
            with self.subTest(name=name):
                self.assertEqual(self.error(name, {}), {"code": -32601, "message": "Method not found"})

    def test_open_next_close_round_trip(self):
        opened = self.result("queens.open", {"size": 8})
        self.assertEqual(set(opened), {"stream_id", "size"})
        self.assertEqual(opened["size"], 8)
        self.assertEqual(uuid.UUID(opened["stream_id"]).version, 4)
        stream_id = opened["stream_id"]
        self.assertEqual(self.result("queens.next", {"stream_id": stream_id, "limit": 3}), {
            "events": [
                {"event": "try", "column": 0, "row": 0, "board": []},
                {"event": "place", "column": 0, "row": 0, "board": [0]},
                {"event": "try", "column": 0, "row": 1, "board": [0]},
            ],
            "done": False,
        })
        self.assertEqual(self.result("queens.close", {"stream_id": stream_id}), {"closed": True})


class NotificationTests(HttpTestCase):
    def test_valid_notification_changes_state_and_returns_204(self):
        stream_id = self.open_stream(8)
        self.notify("queens.next", {"stream_id": stream_id, "limit": 1})  # consumes try(0, 0)
        self.assertEqual(self.result("queens.next", {"stream_id": stream_id, "limit": 1})["events"],
                         [{"event": "place", "column": 0, "row": 0, "board": [0]}])
        self.notify("queens.open", {"size": 5})
        self.assertEqual(len(self.table), 2)
        self.notify("queens.close", {"stream_id": stream_id})
        self.assertEqual(self.error("queens.next", {"stream_id": stream_id, "limit": 1})["code"], -32020)
        self.notify("service.health")

    def test_failing_notifications_return_204(self):
        self.notify("no.such.method", {})
        self.notify("queens.open", {"size": 99})
        self.notify("queens.open", [8])
        self.notify("queens.next", {"stream_id": "missing", "limit": 1})
        self.notify("queens.close", {"stream_id": 5})
        self.assertEqual(len(self.table), 0)


class ErrorTests(HttpTestCase):
    def test_stream_not_found_application_error(self):
        not_found = {"code": -32020, "message": "Stream not found"}
        self.assertEqual(self.error("queens.next", {"stream_id": str(uuid.uuid4()), "limit": 1}), not_found)
        closed = self.open_stream()
        self.result("queens.close", {"stream_id": closed})
        self.assertEqual(self.error("queens.next", {"stream_id": closed, "limit": 1}), not_found)
        self.assertEqual(self.error("queens.close", {"stream_id": closed}), not_found)
        expired = self.open_stream()
        self.clock.advance(300)
        self.assertEqual(self.error("queens.next", {"stream_id": expired, "limit": 1}), not_found)

    def test_too_many_streams_application_error(self):
        for _ in range(MAX_STREAMS):
            self.open_stream()
        self.assertEqual(self.error("queens.open", {"size": 8}),
                         {"code": -32021, "message": "Too many open streams", "data": {"limit": MAX_STREAMS}})

    def test_internal_error_is_sanitized(self):
        def failing_take(cursor, limit):
            raise RuntimeError("secret detail at /Users/someone/lambda3.py")

        self.table = StreamTable(clock=self.clock, take=failing_take)
        self.client = create_app(table=self.table).test_client()
        stream_id = self.open_stream()
        with self.assertLogs("MySolution.rpc", "ERROR") as logs:
            response = self.post_raw(json.dumps(request_object(
                "queens.next", {"stream_id": stream_id, "limit": 1}, 9)).encode())
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["id"], 9)
        self.assertEqual(set(body["error"]), {"code", "message", "data"})
        self.assertEqual((body["error"]["code"], body["error"]["message"]), (-32603, "Internal error"))
        self.assertEqual(set(body["error"]["data"]), {"incident"})
        incident = body["error"]["data"]["incident"]
        self.assertRegex(incident, r"^[0-9a-f]{12}$")
        text = response.get_data(as_text=True)
        for leak in ("secret", "/Users", "Traceback", "RuntimeError", "lambda3"):
            self.assertNotIn(leak, text)
        self.assertIn(incident, "\n".join(logs.output))  # the details stay in the server log
        # The failed stream was dropped.
        self.assertEqual(self.error("queens.next", {"stream_id": stream_id, "limit": 1})["code"], -32020)


class TransportTests(HttpTestCase):
    def assert_plain_text(self, response, status: int):
        self.assertEqual(response.status_code, status, response.data[:200])
        self.assertEqual(response.mimetype, "text/plain")
        self.assertTrue(response.get_data(as_text=True).startswith(str(status)))

    def test_media_type_and_method_checks(self):
        for content_type in (None, "text/plain", "application/x-www-form-urlencoded",
                             "application/json; charset=latin-1"):
            with self.subTest(content_type=content_type):
                self.assert_plain_text(self.post_raw(HEALTH, content_type=content_type), 415)
        for content_type in ("Application/JSON", "application/json; charset=UTF-8"):
            with self.subTest(content_type=content_type):
                self.assertEqual(self.post_raw(HEALTH, content_type=content_type).status_code, 200)
        for method in ("GET", "PUT", "DELETE"):
            with self.subTest(method=method):
                response = self.client.open("/rpc", method=method, headers={"Content-Type": "application/json"})
                self.assert_plain_text(response, 405)
                self.assertEqual(response.headers["Allow"], "POST")
        self.assert_plain_text(self.post_raw(HEALTH, path="/nowhere"), 404)

    def test_body_size_limit(self):
        at_limit = HEALTH + b" " * (MAX_BODY_BYTES - len(HEALTH))
        self.assertEqual(self.post_raw(at_limit).status_code, 200)
        self.assert_plain_text(self.post_raw(at_limit + b" "), 413)


class ParamsTests(HttpTestCase):
    def assert_invalid(self, method: str, params, data: dict):
        self.assertEqual(self.error(method, params), {"code": -32602, "message": "Invalid params", "data": data})

    def test_size_bounds(self):
        for size in (4, 10):
            self.assertEqual(self.result("queens.open", {"size": size})["size"], size)
        out_of_range = {"field": "size", "reason": "out_of_range", "minimum": 4, "maximum": 10}
        for size in (3, 11, 0, -8, 2**70):
            with self.subTest(size=size):
                self.assert_invalid("queens.open", {"size": size}, out_of_range)
        for size in (8.0, 8.5, True, False, "8", None, [8], {}):
            with self.subTest(size=size):
                self.assert_invalid("queens.open", {"size": size}, {"field": "size", "reason": "not_an_integer"})
        for params in ({}, ABSENT):
            self.assert_invalid("queens.open", params, {"field": "size", "reason": "missing"})

    def test_limit_bounds(self):
        stream_id = self.open_stream()
        for limit in (1, 32):
            self.assertEqual(len(self.result("queens.next", {"stream_id": stream_id, "limit": limit})["events"]), limit)
        for limit in (0, 33, -1):
            with self.subTest(limit=limit):
                self.assert_invalid("queens.next", {"stream_id": stream_id, "limit": limit},
                                    {"field": "limit", "reason": "out_of_range", "minimum": 1, "maximum": 32})
        for limit in (1.5, 1.0, True, "1", None):
            with self.subTest(limit=limit):
                self.assert_invalid("queens.next", {"stream_id": stream_id, "limit": limit},
                                    {"field": "limit", "reason": "not_an_integer"})
        self.assert_invalid("queens.next", {"stream_id": stream_id}, {"field": "limit", "reason": "missing"})

    def test_shape_errors(self):
        self.assert_invalid("queens.open", [8], {"reason": "not_an_object"})
        self.assert_invalid("queens.open", {"size": 8, "speed": 2}, {"reason": "unexpected", "fields": ["speed"]})
        self.assert_invalid("queens.next", {"stream_id": "x", "limit": 1, "a": 0, "b": 0},
                            {"reason": "unexpected", "fields": ["a", "b"]})
        for stream_id in (5, None, [], {"id": "x"}):
            with self.subTest(stream_id=stream_id):
                self.assert_invalid("queens.next", {"stream_id": stream_id, "limit": 1},
                                    {"field": "stream_id", "reason": "not_a_string"})
                self.assert_invalid("queens.close", {"stream_id": stream_id},
                                    {"field": "stream_id", "reason": "not_a_string"})
        for method in ("queens.next", "queens.close"):
            for params in ({}, ABSENT):
                self.assert_invalid(method, params, {"field": "stream_id", "reason": "missing"})

    def test_invalid_params_allocate_nothing(self):
        for params in ({"size": 3}, {"size": "8"}, {"size": True}, {}, [8], {"size": 8, "x": 1}):
            self.error("queens.open", params)
        self.assertEqual(len(self.table), 0)
        stream_id = self.open_stream()
        cursor = self.table.entries[stream_id].cursor
        for params in ({"stream_id": stream_id, "limit": 0}, {"stream_id": stream_id}, {"stream_id": stream_id, "limit": 1, "x": 1}):
            self.error("queens.next", params)
        self.assertIs(self.table.entries[stream_id].cursor, cursor)  # no event was consumed
        self.assertFalse(cursor.evaluated)

    def test_next_returns_at_most_limit(self):
        stream_id = self.open_stream(4)
        self.assertEqual(len(self.result("queens.next", {"stream_id": stream_id, "limit": 1})["events"]), 1)
        for _ in range(4):  # events 2-129
            self.assertEqual(len(self.result("queens.next", {"stream_id": stream_id, "limit": 32})["events"]), 32)
        last = self.result("queens.next", {"stream_id": stream_id, "limit": 32})
        self.assertEqual((last["events"], last["done"]), (list(trace(4)[129:]), True))
        self.assertEqual(len(last["events"]), 10)
