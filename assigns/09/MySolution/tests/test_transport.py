"""Transport rules through HTTP (API.md sections 1, 3, 8, 9, and 10).

Health, unknown routes, wrong methods, media types, body size, malformed
JSON, HEAD and OPTIONS, query parameters on every route, and CORS.
"""
from __future__ import annotations

import json
import unittest

from .http_support import ApiTestCase, etag

STUDIO = "http://127.0.0.1:8010"
VALID_PROGRAM = b'{"name": "answer", "source": "42"}'


class HealthTests(ApiTestCase):

    def test_health(self):
        response = self.api("GET", "/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok", "version": "1.0"})

    def test_head_answers_like_get_without_a_body(self):
        response = self.api("HEAD", "/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Length"], str(len(b'{"status": "ok", "version": "1.0"}')))

    def test_health_takes_no_query_parameters(self):
        self.assertInvalid(self.api("GET", "/health?verbose=1"), "verbose", "unknown_parameter")


class RouteTests(ApiTestCase):

    def test_unknown_paths_are_404_record_not_found(self):
        for path in ("/tests", "/programs/", "/collections/", "//programs", "/programs/x/y",
                     "/collections/x/cases/", "/collections/x/cases/y/z", "/health/"):
            with self.subTest(path=path):
                error = self.assertError(self.api("GET", path), 404, "record_not_found")
                self.assertEqual(error["message"], "No API route matches this path.")
        for url in ("/", "/api/v2/health", "/api/v1"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json["error"]["code"], "record_not_found")
                self.assertEqual(response.headers["Content-Type"], "application/json")

    def test_wrong_method_is_405_with_allow(self):
        cases = [
            ("POST", "/health", "GET, HEAD, OPTIONS"),
            ("DELETE", "/programs", "GET, HEAD, POST, OPTIONS"),
            ("PUT", "/collections", "GET, HEAD, POST, OPTIONS"),
            ("PATCH", "/programs/prg_x", "GET, HEAD, PUT, DELETE, OPTIONS"),
            ("POST", "/collections/col_x", "GET, HEAD, PUT, DELETE, OPTIONS"),
            ("GET", "/collections/col_x/cases", "POST, OPTIONS"),
            ("GET", "/collections/col_x/cases/case_x", "PUT, DELETE, OPTIONS"),
            ("POST", "/collections/col_x/cases/case_x", "PUT, DELETE, OPTIONS"),
        ]
        for method, path, allow in cases:
            with self.subTest(method=method, path=path):
                response = self.api(method, path)
                error = self.assertError(response, 405, "method_not_allowed")
                self.assertEqual(response.headers["Allow"], allow)
                self.assertIn(method, error["message"])

    def test_path_is_checked_before_method_and_method_before_media_type(self):
        self.assertError(self.api("PATCH", "/nowhere"), 404, "record_not_found")
        self.assertError(self.api("PATCH", "/programs/x", raw=b"x", content_type="text/plain"),
                         405, "method_not_allowed")

    def test_options_lists_the_accepted_methods(self):
        cases = [
            ("/health", "GET, HEAD, OPTIONS"),
            ("/programs", "GET, HEAD, POST, OPTIONS"),
            ("/collections", "GET, HEAD, POST, OPTIONS"),
            ("/programs/prg_x", "GET, HEAD, PUT, DELETE, OPTIONS"),
            ("/collections/col_x", "GET, HEAD, PUT, DELETE, OPTIONS"),
            ("/collections/col_x/cases", "POST, OPTIONS"),
            ("/collections/col_x/cases/case_x", "PUT, DELETE, OPTIONS"),
        ]
        for path, allow in cases:
            with self.subTest(path=path):
                response = self.api("OPTIONS", path)
                self.assertEqual(response.status_code, 204)
                self.assertEqual(response.headers["Allow"], allow)

    def test_location_names_the_new_record(self):
        response = self.api("POST", "/programs", {"name": "p", "source": "1"})
        self.assertEqual(response.headers["Location"], f"/api/v1/programs/{response.json['program']['id']}")
        response = self.api("POST", "/collections", {"name": "c"})
        collection = response.json["collection"]
        self.assertEqual(response.headers["Location"], f"/api/v1/collections/{collection['id']}")
        response = self.api("POST", f"/collections/{collection['id']}/cases",
                            {"name": "k", "source": "1", "expected": {"kind": "value", "value": "1"}},
                            if_match=etag(1))
        self.assertNotIn("Location", response.headers)     # cases have no URL of their own

    def test_head_on_a_record_carries_its_etag(self):
        program = self.create_program()
        response = self.api("HEAD", f"/programs/{program['id']}")
        self.assertEqual((response.status_code, response.headers["ETag"]), (200, etag(1)))


class MediaTypeTests(ApiTestCase):

    def test_json_media_types_are_accepted(self):
        for n, content_type in enumerate(("application/json", "Application/JSON",
                                          "application/json; charset=utf-8",
                                          "application/json;charset=UTF-8")):
            with self.subTest(content_type=content_type):
                response = self.api("POST", "/programs", raw=b'{"name": "p%d", "source": "1"}' % n,
                                    content_type=content_type)
                self.assertEqual(response.status_code, 201)

    def test_other_media_types_are_415(self):
        for content_type in (None, "text/plain", "application/x-www-form-urlencoded",
                             "application/json; charset=latin-1", "application/jsonx",
                             "application/merge-patch+json", "multipart/form-data"):
            with self.subTest(content_type=content_type):
                self.assertError(self.api("POST", "/programs", raw=VALID_PROGRAM, content_type=content_type),
                                 415, "unsupported_media_type")

    def test_every_body_route_checks_the_media_type_before_the_record(self):
        for method, path in (("POST", "/collections"), ("PUT", "/programs/missing"),
                             ("PUT", "/collections/missing"), ("POST", "/collections/missing/cases"),
                             ("PUT", "/collections/missing/cases/missing")):
            with self.subTest(method=method, path=path):
                self.assertError(self.api(method, path, raw=b"{}", content_type="text/plain"),
                                 415, "unsupported_media_type")

    def test_media_type_is_checked_before_size(self):
        too_big = b" " * (self.limits.max_body_bytes + 1)
        self.assertError(self.api("POST", "/programs", raw=too_big, content_type="text/plain"),
                         415, "unsupported_media_type")


class BodySizeTests(ApiTestCase):

    def padded(self, size: int) -> bytes:
        """A valid program body padded with JSON whitespace to exactly `size` bytes."""
        return VALID_PROGRAM + b" " * (size - len(VALID_PROGRAM))

    def test_body_at_the_limit_is_accepted(self):
        response = self.api("POST", "/programs", raw=self.padded(self.limits.max_body_bytes))
        self.assertEqual(response.status_code, 201)

    def test_body_over_the_limit_is_413(self):
        self.assertError(self.api("POST", "/programs", raw=self.padded(self.limits.max_body_bytes + 1)),
                         413, "payload_too_large", limit=1_048_576)

    def test_size_is_checked_before_json(self):
        self.assertError(self.api("PUT", "/programs/missing", raw=b"{" * (self.limits.max_body_bytes + 1)),
                         413, "payload_too_large")


class MalformedJsonTests(ApiTestCase):

    def test_malformed_bodies(self):
        # The deepest nesting a body within the size limit can hold. Python's
        # decoder runs out of stack long before that (between 100,000 and
        # 200,000 levels with Python 3.14), whichever thread it runs on.
        depth = self.limits.max_body_bytes // 2
        bodies = {
            "empty": b"",
            "truncated": b'{"name": "broken",',
            "trailing text": VALID_PROGRAM + b" x",
            "two values": VALID_PROGRAM + VALID_PROGRAM,
            "single quotes": b"{'name': 'p', 'source': '1'}",
            "NaN": b'{"name": "p", "source": "1", "description": NaN}',
            "Infinity": b'{"name": "p", "source": "1", "description": Infinity}',
            "-Infinity": b'{"name": "p", "source": "1", "description": -Infinity}',
            "invalid UTF-8": b'{"name": "\xff", "source": "1"}',
            "UTF-8 encoded surrogate": b'{"name": "\xed\xa0\x80", "source": "1"}',
            "byte-order mark": b"\xef\xbb\xbf" + VALID_PROGRAM,
            "UTF-16": VALID_PROGRAM.decode().encode("utf-16"),
            "nesting too deep": b"[" * depth + b"]" * depth,
            "integer too long to convert": b'{"name": "p", "source": "1", "description": ' + b"9" * 5000 + b"}",
        }
        for label, raw in bodies.items():
            with self.subTest(label):
                error = self.assertInvalid(self.api("POST", "/programs", raw=raw), None, "malformed_json")
                self.assertEqual(error["message"], "The request body is not valid JSON.")

    def test_duplicate_members_are_rejected(self):
        for raw in (b'{"name": "p", "source": "1", "name": "q"}',
                    b'{"name": "c", "source": "1", "expected": {"kind": "value", "kind": "error"}}'):
            with self.subTest(raw=raw):
                self.assertInvalid(self.api("POST", "/programs", raw=raw), None, "duplicate_member")

    def test_body_must_be_an_object(self):
        for raw in (b"[]", b'"text"', b"42", b"null", b"true"):
            with self.subTest(raw=raw):
                self.assertInvalid(self.api("POST", "/collections", raw=raw), None, "not_object")

    def test_json_is_checked_before_the_record(self):
        self.assertInvalid(self.api("PUT", "/programs/missing", raw=b"{"), None, "malformed_json")

    def test_bodies_of_get_and_delete_are_ignored(self):
        program = self.create_program()
        path = f"/programs/{program['id']}"
        self.assertEqual(self.api("GET", path, raw=b"not json", content_type="text/plain").status_code, 200)
        self.assertEqual(self.api("DELETE", path, raw=b"not json", if_match=etag(1)).status_code, 204)


class QueryParameterTests(ApiTestCase):

    def test_every_route_without_parameters_rejects_them_before_looking_up_records(self):
        program = {"name": "p", "source": "1"}
        case = {"name": "k", "source": "1", "expected": {"kind": "value", "value": "1"}}
        routes = [
            ("GET", "/health", None), ("POST", "/programs", program),
            ("GET", "/programs/missing", None), ("PUT", "/programs/missing", program),
            ("DELETE", "/programs/missing", None), ("POST", "/collections", {"name": "c"}),
            ("GET", "/collections/missing", None), ("PUT", "/collections/missing", {"name": "c"}),
            ("DELETE", "/collections/missing", None), ("POST", "/collections/missing/cases", case),
            ("PUT", "/collections/missing/cases/missing", case),
            ("DELETE", "/collections/missing/cases/missing", None),
        ]
        for method, path, body in routes:
            with self.subTest(method=method, path=path):
                response = self.api(method, f"{path}?limit=5", body) if body else self.api(method, f"{path}?limit=5")
                self.assertInvalid(response, "limit", "unknown_parameter")


class ResponseFormatTests(ApiTestCase):

    def test_json_bodies_are_utf8_json(self):
        program = self.create_program("café ☕", source="1 + 1")
        response = self.api("GET", f"/programs/{program['id']}")
        self.assertEqual(json.loads(response.data.decode("utf-8"))["program"]["name"], "café ☕")


class CorsTests(ApiTestCase):

    def test_allowed_origin_can_read_responses_and_etags(self):
        response = self.api("POST", "/programs", {"name": "p", "source": "1"}, headers={"Origin": STUDIO})
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], STUDIO)
        self.assertEqual(response.headers["Access-Control-Expose-Headers"], "ETag, Location")
        self.assertIn("Origin", response.headers["Vary"])

    def test_errors_carry_cors_headers_too(self):
        response = self.api("GET", "/programs/missing", headers={"Origin": "http://localhost:8010"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "http://localhost:8010")

    def test_preflight_allows_if_match(self):
        response = self.api("OPTIONS", "/programs/prg_x", headers={
            "Origin": STUDIO, "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type, if-match"})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], STUDIO)
        self.assertEqual(response.headers["Access-Control-Allow-Methods"], "GET, HEAD, POST, PUT, DELETE")
        self.assertEqual(response.headers["Access-Control-Allow-Headers"], "Content-Type, If-Match")
        self.assertEqual(response.headers["Access-Control-Max-Age"], "600")

    def test_other_origins_get_no_cors_headers(self):
        for headers in ({"Origin": "http://evil.example"}, {"Origin": "http://127.0.0.1:8010/"}, {}):
            with self.subTest(headers=headers):
                response = self.api("GET", "/health", headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("Access-Control-Allow-Origin", response.headers)
                self.assertIn("Origin", response.headers["Vary"])


class ConfiguredOriginTests(ApiTestCase):

    def app_options(self):
        return {"studio_origins": ["http://studio.test:9000"]}

    def test_configured_origins_replace_the_defaults(self):
        allowed = self.api("GET", "/health", headers={"Origin": "http://studio.test:9000"})
        self.assertEqual(allowed.headers["Access-Control-Allow-Origin"], "http://studio.test:9000")
        default = self.api("GET", "/health", headers={"Origin": STUDIO})
        self.assertNotIn("Access-Control-Allow-Origin", default.headers)


if __name__ == "__main__":
    unittest.main()
