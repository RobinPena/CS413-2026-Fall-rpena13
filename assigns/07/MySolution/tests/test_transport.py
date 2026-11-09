"""HTTP transport: statuses, media types, body size, and empty 204 bodies (RPC.md section 1)."""
import json

from MySolution.app import MAX_BODY_BYTES
from MySolution.tests.support import RpcTestCase, request_object

HEALTH = json.dumps(request_object("service.health", {}, 1)).encode("utf-8")


class TransportTests(RpcTestCase):
    def assert_transport_error(self, response, status: int) -> None:
        """A transport failure: the status, a plain-text body, and no JSON-RPC envelope."""
        self.assertEqual(response.status_code, status, response.data[:200])
        self.assertEqual(response.mimetype, "text/plain")
        self.assertNotIn(b"jsonrpc", response.data)

    def test_rpc_response_is_200_json(self):
        response = self.post_raw(HEALTH)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/json")
        self.assertEqual(json.loads(response.data)["result"], {"status": "ok", "version": "1.0"})

    def test_notification_is_204_with_zero_byte_body(self):
        response = self.post_raw(json.dumps(request_object("service.health", {})).encode())
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, b"")
        self.assertNotIn("Content-Type", response.headers)

    def test_missing_content_type_is_415(self):
        self.assert_transport_error(self.post_raw(HEALTH, content_type=None), 415)

    def test_other_media_types_are_415(self):
        for content_type in ("text/plain", "application/x-www-form-urlencoded",
                             "application/json-rpc", "application/jsonx", "multipart/form-data"):
            with self.subTest(content_type=content_type):
                self.assert_transport_error(self.post_raw(HEALTH, content_type=content_type), 415)

    def test_non_utf8_charset_is_415(self):
        for content_type in ("application/json; charset=latin-1", "application/json; charset=utf-16"):
            with self.subTest(content_type=content_type):
                self.assert_transport_error(self.post_raw(HEALTH, content_type=content_type), 415)

    def test_json_media_type_ignores_case_and_allows_utf8_charset(self):
        for content_type in ("application/json", "Application/JSON",
                             "application/json; charset=utf-8", "application/json;charset=UTF-8"):
            with self.subTest(content_type=content_type):
                self.assertEqual(self.post_raw(HEALTH, content_type=content_type).status_code, 200)

    def test_other_http_methods_are_405_with_allow_post(self):
        for verb in ("GET", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
            with self.subTest(verb=verb):
                response = self.client.open("/rpc", method=verb, data=HEALTH,
                                            headers={"Content-Type": "application/json"})
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response.headers["Allow"], "POST")
                if verb != "HEAD":  # a HEAD response never has a body
                    self.assert_transport_error(response, 405)

    def test_unknown_paths_are_404(self):
        for path in ("/", "/rpc/", "/RPC", "/rpc/service.health", "/lambda.typecheck"):
            with self.subTest(path=path):
                self.assert_transport_error(self.post_raw(HEALTH, path=path), 404)

    def test_body_over_limit_is_413(self):
        self.assert_transport_error(self.post_raw(HEALTH + b" " * (MAX_BODY_BYTES + 1 - len(HEALTH))), 413)

    def test_body_at_limit_is_accepted(self):
        body = HEALTH + b" " * (MAX_BODY_BYTES - len(HEALTH))
        self.assertEqual(len(body), MAX_BODY_BYTES)
        self.assertEqual(self.post_raw(body).status_code, 200)

    def test_transport_checks_run_in_documented_order(self):
        oversized = b" " * (MAX_BODY_BYTES + 1)
        self.assert_transport_error(self.post_raw(oversized, content_type="text/plain", path="/x"), 404)
        response = self.client.get("/rpc", data=oversized, headers={"Content-Type": "text/plain"})
        self.assert_transport_error(response, 405)
        self.assert_transport_error(self.post_raw(oversized, content_type="text/plain"), 415)
        self.assert_transport_error(self.post_raw(oversized), 413)

    def test_jsonrpc_errors_still_use_200(self):
        for body in (b'{"jsonrpc":', b"[]", b'{"jsonrpc": "1.0", "method": "service.health", "id": 1}'):
            with self.subTest(body=body):
                status, answer = self.post_bytes(body)
                self.assertEqual(status, 200)
                self.assertIn(answer["error"]["code"], (-32700, -32600))
