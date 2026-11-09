"""Batches: correlation by id, omitted notifications, invalid members, and
the empty and oversized cases (RPC.md section 6).
"""
from MySolution.rpc import MAX_BATCH_SIZE
from MySolution.tests.support import RpcTestCase, request_object

HEALTH_RESULT = {"status": "ok", "version": "1.0"}


def health(request_id=None, notification=False) -> dict:
    if notification:
        return request_object("service.health", {})
    return request_object("service.health", {}, request_id)


class BatchTests(RpcTestCase):
    def post_batch(self, members: list) -> list:
        status, body = self.post(members)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)
        return body

    def by_id(self, responses: list) -> dict:
        """Index responses by id; ids must be unique in the batches that use this."""
        index = {response["id"]: response for response in responses}
        self.assertEqual(len(index), len(responses))
        return index

    def test_mixed_batch_matches_by_id_and_omits_notification(self):
        responses = self.by_id(self.post_batch([
            health("a"),
            health(notification=True),
            request_object("does.not.exist", {}, "x"),
            health(2),
            "not-a-request",
        ]))
        self.assertEqual(set(responses), {"a", "x", 2, None})
        self.assertEqual(responses["a"]["result"], HEALTH_RESULT)
        self.assertEqual(responses[2]["result"], HEALTH_RESULT)
        self.assertEqual(responses["x"]["error"]["code"], -32601)
        self.assertEqual(responses[None]["error"]["code"], -32600)
        self.assertEqual(responses[None]["error"]["data"], {"reason": "not_an_object"})

    def test_notification_only_batch_is_204_empty(self):
        members = [health(notification=True), request_object("does.not.exist", {}),
                   request_object("service.health", [])]
        self.assertEqual(self.post(members), (204, None))

    def test_empty_batch_is_one_invalid_request_object(self):
        error = self.assert_error(self.post([]), None, -32600)
        self.assertEqual(error["data"], {"reason": "empty_batch"})

    def test_invalid_members_get_null_id(self):
        members = [1, "x", None, True, [], [health(1)], {}, {"jsonrpc": "1.0", "method": "service.health", "id": 5}]
        responses = self.post_batch(members)
        self.assertEqual(len(responses), len(members))
        reasons = [response["error"]["data"]["reason"] for response in responses]
        self.assertEqual(reasons, ["not_an_object"] * 6 + ["bad_jsonrpc"] * 2)
        for response in responses:
            self.assertIsNone(response["id"])
            self.assertEqual(response["error"]["code"], -32600)

    def test_duplicate_ids_are_answered_separately(self):
        responses = self.post_batch([health(1), health(1), request_object("service.health", [], 1)])
        self.assertEqual([response["id"] for response in responses], [1, 1, 1])
        self.assertEqual(sum("result" in response for response in responses), 2)
        self.assertEqual(sum("error" in response for response in responses), 1)

    def test_batch_at_size_limit(self):
        responses = self.by_id(self.post_batch([health(i) for i in range(MAX_BATCH_SIZE)]))
        self.assertEqual(set(responses), set(range(MAX_BATCH_SIZE)))

    def test_batch_over_size_limit_is_one_invalid_request_object(self):
        error = self.assert_error(self.post([health(i) for i in range(MAX_BATCH_SIZE + 1)]), None, -32600)
        self.assertEqual(error["data"], {"reason": "batch_too_large", "limit": MAX_BATCH_SIZE})


def _record(calls: list):
    def method(params):
        calls.append(params["n"])
        return {"type": "sint"}
    return method


def _crash(params):
    raise RuntimeError("boom")


CALLS: list = []


class BatchProcessingTests(RpcTestCase):
    """A test double records which batch members actually ran, and in what order."""

    methods = {"stub.record": _record(CALLS), "stub.crash": _crash}

    def setUp(self):
        super().setUp()
        CALLS.clear()

    def test_members_run_in_order_including_notifications(self):
        members = [request_object("stub.record", {"n": n}, *([] if n % 2 else [n])) for n in range(5)]
        status, body = self.post(members)
        self.assertEqual(CALLS, [0, 1, 2, 3, 4])
        self.assertEqual(sorted(response["id"] for response in body), [0, 2, 4])

    def test_member_failure_does_not_affect_others(self):
        with self.assertLogs("MySolution.rpc", level="ERROR"):
            status, body = self.post([
                request_object("stub.record", {"n": 1}, "before"),
                request_object("stub.crash", {}, "crash"),
                request_object("stub.record", {"n": 2}, "after"),
            ])
        responses = {response["id"]: response for response in body}
        self.assertEqual(responses["crash"]["error"]["code"], -32603)
        self.assertIn("result", responses["before"])
        self.assertIn("result", responses["after"])
        self.assertEqual(CALLS, [1, 2])

    def test_oversized_batch_runs_nothing(self):
        self.post([request_object("stub.record", {"n": n}, n) for n in range(MAX_BATCH_SIZE + 1)])
        self.assertEqual(CALLS, [])
