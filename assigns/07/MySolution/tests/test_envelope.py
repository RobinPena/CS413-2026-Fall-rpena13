"""The JSON-RPC envelope: parse errors, invalid requests, IDs, unknown methods,
notifications, and the boundary between the dispatcher and the methods it
calls (RPC.md sections 2 and 4).
"""
import json

from MySolution.errors import LAMBDA_TYPE_ERROR, RpcError
from MySolution.tests.support import ABSENT, RpcTestCase, request_object

HEALTH_RESULT = {"status": "ok", "version": "1.0"}


class ParseErrorTests(RpcTestCase):
    def assert_parse_error(self, body: bytes, data: dict) -> None:
        error = self.assert_error(self.post_bytes(body), None, -32700)
        self.assertEqual(error["message"], "Parse error")
        self.assertEqual(error["data"], data)

    def test_truncated_json(self):
        self.assert_parse_error(b'{"jsonrpc":', {"reason": "invalid_json", "line": 1, "column": 12})

    def test_position_on_later_line(self):
        self.assert_parse_error(b'{\n  "jsonrpc": "2.0",\n  "method": }',
                                {"reason": "invalid_json", "line": 3, "column": 13})

    def test_empty_and_blank_bodies(self):
        self.assert_parse_error(b"", {"reason": "invalid_json", "line": 1, "column": 1})
        self.assert_parse_error(b"  \n ", {"reason": "invalid_json", "line": 2, "column": 2})

    def test_other_invalid_json(self):
        for body in (b"{} {}", b"[1,]", b"{'jsonrpc': '2.0'}", b'{"id": 01}', b"undefined"):
            with self.subTest(body=body):
                error = self.assert_error(self.post_bytes(body), None, -32700)
                self.assertEqual(error["data"]["reason"], "invalid_json")

    def test_invalid_utf8(self):
        self.assert_parse_error(b'{"jsonrpc": "2.0", "method": "\xff", "id": 1}', {"reason": "invalid_utf8"})

    def test_byte_order_mark(self):
        error = self.assert_error(self.post_bytes(b"\xef\xbb\xbf{}"), None, -32700)
        self.assertEqual(error["data"]["reason"], "invalid_json")

    def test_nonstandard_constants(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant):
                body = f'{{"jsonrpc": "2.0", "method": "service.health", "params": {{}}, "id": {constant}}}'
                self.assert_parse_error(body.encode(), {"reason": "unsupported_number"})

    def test_numbers_that_cannot_be_echoed(self):
        for number in ("1e400", "-1e400", "1" * 4301):
            with self.subTest(number=number[:12]):
                body = f'{{"jsonrpc": "2.0", "method": "service.health", "params": {{}}, "id": {number}}}'
                self.assert_parse_error(body.encode(), {"reason": "unsupported_number"})

    def test_deeply_nested_json(self):
        self.assert_parse_error(b"[" * 200_000 + b"]" * 200_000, {"reason": "nesting_too_deep"})


class InvalidRequestTests(RpcTestCase):
    def assert_invalid(self, payload: object, reason: str) -> None:
        error = self.assert_error(self.post(payload), None, -32600)
        self.assertEqual(error["message"], "Invalid Request")
        self.assertEqual(error["data"], {"reason": reason})

    def test_non_object_values(self):
        for payload in (1, "service.health", None, True, 2.5):
            with self.subTest(payload=payload):
                self.assert_invalid(payload, "not_an_object")

    def test_unexpected_member(self):
        self.assert_invalid({**request_object("service.health", {}, 1), "extra": 0}, "unexpected_member")

    def test_bad_jsonrpc(self):
        for version in (ABSENT, "1.0", 2.0, "2.0 ", None):
            with self.subTest(version=version):
                payload = request_object("service.health", {}, 1)
                if version is ABSENT:
                    del payload["jsonrpc"]
                else:
                    payload["jsonrpc"] = version
                self.assert_invalid(payload, "bad_jsonrpc")

    def test_bad_method(self):
        for method in (ABSENT, 5, None, ["service.health"]):
            with self.subTest(method=method):
                payload = request_object("service.health", {}, 1)
                if method is ABSENT:
                    del payload["method"]
                else:
                    payload["method"] = method
                self.assert_invalid(payload, "bad_method")

    def test_bad_params(self):
        for params in ("x", 3, None, True):
            with self.subTest(params=params):
                self.assert_invalid(request_object("service.health", params, 1), "bad_params")

    def test_bad_id(self):
        for request_id in (True, False, {}, [], [1]):
            with self.subTest(request_id=request_id):
                self.assert_invalid(request_object("service.health", {}, request_id), "bad_id")

    def test_usable_id_is_not_echoed(self):
        self.assert_invalid({"jsonrpc": "1.0", "method": "service.health", "id": 1}, "bad_jsonrpc")

    def test_invalid_request_without_id_is_still_answered(self):
        self.assert_invalid({"method": "service.health", "params": {}}, "bad_jsonrpc")


class IdTests(RpcTestCase):
    def test_valid_ids_are_echoed_unchanged(self):
        for request_id in ("health-1", "", 0, -7, 1.5, 2 ** 100, int("9" * 4300), None):
            with self.subTest(request_id=str(request_id)[:20]):
                result = self.assert_result(self.call("service.health", {}, request_id), request_id)
                self.assertEqual(result, HEALTH_RESULT)

    def test_explicit_null_id_is_a_call_not_a_notification(self):
        status, body = self.call("service.health", {}, None)
        self.assertEqual(status, 200)
        self.assertIsNone(body["id"])
        self.assertEqual(body["result"], HEALTH_RESULT)

    def test_errors_keep_the_id(self):
        self.assert_error(self.call("no.such.method", {}, "keep-me"), "keep-me", -32601)
        self.assert_error(self.call("service.health", [], 0), 0, -32602)


class MethodNotFoundTests(RpcTestCase):
    def test_unknown_method(self):
        error = self.assert_error(self.call("does.not.exist", {}, "unknown"), "unknown", -32601)
        self.assertEqual(error, {"code": -32601, "message": "Method not found"})

    def test_method_names_are_case_sensitive(self):
        for method in ("Service.Health", "SERVICE.HEALTH", "service.health ", "service_health"):
            with self.subTest(method=method):
                self.assert_error(self.call(method, {}, 1), 1, -32601)

    def test_reserved_and_empty_names(self):
        for method in ("rpc.discover", ""):
            with self.subTest(method=method):
                self.assert_error(self.call(method, {}, 1), 1, -32601)

    def test_method_lookup_comes_before_params(self):
        self.assert_error(self.call("does.not.exist", ["positional"], 1), 1, -32601)


def _record(calls: list) -> callable:
    def method(params):
        calls.append(params)
        return {"type": "sint"}
    return method


def _raise_type_error(params):
    raise RpcError(LAMBDA_TYPE_ERROR, {"diagnostic": "unbound variable 'x'"})


def _crash(params):
    raise ValueError("secret detail in /Users/someone/private/file.py")


CALLS: list = []
STUB_METHODS = {
    "stub.record": _record(CALLS),
    "stub.type_error": _raise_type_error,
    "stub.crash": _crash,
    "service.health": lambda params: HEALTH_RESULT,
}


class DispatchBoundaryTests(RpcTestCase):
    """A test double replaces the method table to reach the dispatcher's edges."""

    methods = STUB_METHODS

    def setUp(self):
        super().setUp()
        CALLS.clear()

    def test_params_are_passed_through(self):
        self.call("stub.record", {"source": "1"}, 1)
        self.call("stub.record", ["a", 1], 2)
        self.call("stub.record", ABSENT, 3)
        self.assertEqual(CALLS, [{"source": "1"}, ["a", 1], None])

    def test_documented_error_from_method_keeps_id_and_data(self):
        error = self.assert_error(self.call("stub.type_error", {}, "t"), "t", -32011)
        self.assertEqual(error, {"code": -32011, "message": "LAMBDA type error",
                                 "data": {"diagnostic": "unbound variable 'x'"}})

    def test_unexpected_exception_is_logged_not_returned(self):
        with self.assertLogs("MySolution.rpc", level="ERROR") as logs:
            response = self.post_raw(json.dumps(request_object("stub.crash", {}, 9)).encode())
        error = self.assert_error(self.decode(response), 9, -32603)
        self.assertEqual(error["message"], "Internal error")
        self.assertRegex(error["data"]["incident"], r"^[0-9a-f]{12}$")
        for leak in (b"secret", b"/Users", b"Traceback", b"ValueError", b".py"):
            self.assertNotIn(leak, response.data)
        record = logs.records[0]
        self.assertIn(error["data"]["incident"], record.getMessage())
        self.assertIsInstance(record.exc_info[1], ValueError)


class NotificationTests(RpcTestCase):
    methods = STUB_METHODS

    def setUp(self):
        super().setUp()
        CALLS.clear()

    def test_single_notification_is_204_empty(self):
        self.assertEqual(self.call("service.health", {}, ABSENT), (204, None))

    def test_notification_is_processed(self):
        self.assertEqual(self.call("stub.record", {"n": 1}, ABSENT), (204, None))
        self.assertEqual(CALLS, [{"n": 1}])

    def test_failing_notifications_get_no_response(self):
        for method in ("does.not.exist", "stub.type_error"):
            with self.subTest(method=method):
                self.assertEqual(self.call(method, {}, ABSENT), (204, None))
        with self.assertLogs("MySolution.rpc", level="ERROR"):
            self.assertEqual(self.call("stub.crash", {}, ABSENT), (204, None))
