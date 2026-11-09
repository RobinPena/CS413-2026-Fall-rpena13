"""Helpers shared by the HTTP-level tests.

RpcTestCase builds a fresh app for each test and talks to it through Flask's
test client, so every check goes through the real HTTP transport. Every
HTTP 200 body is validated against rpc.schema.json#/$defs/ResponseBody, and
every 204 is checked to have an empty body.
"""
from __future__ import annotations

import json
import unittest
from collections.abc import Callable, Mapping
from pathlib import Path

from jsonschema import Draft202012Validator

from MySolution import create_app

SOLUTION_DIR = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((SOLUTION_DIR / "rpc.schema.json").read_text(encoding="utf-8"))

ABSENT = object()  # marks a request member that is left out entirely


def schema_validator(definition: str) -> Draft202012Validator:
    """A validator for one entry point under the schema's $defs."""
    return Draft202012Validator({**SCHEMA, "$ref": f"#/$defs/{definition}"})


RESPONSE_BODY = schema_validator("ResponseBody")


def request_object(method: object, params: object = ABSENT, request_id: object = ABSENT) -> dict:
    """A JSON-RPC 2.0 request; leave request_id out to build a notification."""
    request = {"jsonrpc": "2.0", "method": method}
    if params is not ABSENT:
        request["params"] = params
    if request_id is not ABSENT:
        request["id"] = request_id
    return request


class RpcTestCase(unittest.TestCase):
    """Base class: self.client posts to an app built from app_config and methods."""

    app_config: Mapping[str, object] | None = None
    methods: Mapping[str, Callable] | None = None  # a test double for the method table

    def setUp(self) -> None:
        self.client = create_app(self.app_config, methods=self.methods).test_client()

    def post_raw(self, body: bytes, content_type: str | None = "application/json",
                 path: str = "/rpc"):
        """POST raw bytes and return the Flask test response unchanged."""
        headers = {} if content_type is None else {"Content-Type": content_type}
        return self.client.post(path, data=body, headers=headers)

    def post(self, payload: object) -> tuple[int, object]:
        """POST a JSON value; return (HTTP status, decoded body or None)."""
        return self.decode(self.post_raw(json.dumps(payload).encode("utf-8")))

    def post_bytes(self, body: bytes) -> tuple[int, object]:
        return self.decode(self.post_raw(body))

    def call(self, method: object, params: object = ABSENT, request_id: object = 1) -> tuple[int, object]:
        return self.post(request_object(method, params, request_id))

    def decode(self, response) -> tuple[int, object]:
        """Check the transport rules for a JSON-RPC answer and decode it."""
        if response.status_code == 204:
            self.assertEqual(response.data, b"", "a 204 must have an empty body")
            return 204, None
        self.assertEqual(response.status_code, 200, response.data[:300])
        self.assertEqual(response.mimetype, "application/json")
        body = json.loads(response.data)
        problems = [error.message for error in RESPONSE_BODY.iter_errors(body)]
        self.assertEqual(problems, [], f"response does not match the schema: {body!r}"[:500])
        return 200, body

    def assert_same_id(self, actual: object, expected: object) -> None:
        """Equal and of the same JSON type, so 0 is not false and 1 is not 1.0."""
        self.assertEqual(actual, expected)
        self.assertIs(type(actual), type(expected))

    def assert_result(self, answer: tuple[int, object], request_id: object) -> object:
        status, body = answer
        self.assertEqual(status, 200)
        self.assertIsInstance(body, dict)
        self.assertIn("result", body)
        self.assertNotIn("error", body)
        self.assert_same_id(body["id"], request_id)
        return body["result"]

    def assert_error(self, answer: tuple[int, object], request_id: object, code: int) -> dict:
        status, body = answer
        self.assertEqual(status, 200)
        self.assertIsInstance(body, dict)
        self.assertIn("error", body)
        self.assertNotIn("result", body)
        self.assert_same_id(body["id"], request_id)
        self.assertEqual(body["error"]["code"], code, body["error"])
        return body["error"]
