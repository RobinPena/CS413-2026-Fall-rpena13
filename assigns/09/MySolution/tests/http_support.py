"""Helpers for the HTTP tests: a fresh app per test, driven through Flask's
test client, with all data created through the public API.

ApiTestCase.api() checks every response against the transport rules of
API.md (sections 1, 5 and 8) and validates every JSON body against the
route's schema in api.schema.json. Each test therefore also checks the
contract's shapes, Content-Type, and ETag rules without repeating them.
"""
from __future__ import annotations

import json
import re
import unittest
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from jsonschema import Draft202012Validator

from MySolution.app import create_app
from MySolution.limits import Limits

SOLUTION_DIR = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((SOLUTION_DIR / "api.schema.json").read_text(encoding="utf-8"))
API = "/api/v1"
ABSENT = object()     # marks a request body that is left out entirely

TIMESTAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z")

FACTORIAL = ("let fact : sint -> sint = fix fact(n: sint): sint => "
             "if n <= 1 then 1 else n * fact(n - 1) in fact(6) end")


def schema_validator(definition: str) -> Draft202012Validator:
    """A validator for one entry point under the schema's $defs."""
    return Draft202012Validator({**SCHEMA, "$ref": f"#/$defs/{definition}"})


# The success body schema for each route (API.md section 3), by method and path.
_ID = r"/[^/]+"
SUCCESS_SCHEMAS = [
    ("GET", r"/health", "Health"),
    ("GET", r"/programs", "ProgramPage"),
    ("POST", r"/programs", "ProgramResponse"),
    ("GET|PUT", rf"/programs{_ID}", "ProgramResponse"),
    ("GET", r"/collections", "CollectionPage"),
    ("POST", r"/collections", "CollectionResponse"),
    ("GET|PUT", rf"/collections{_ID}", "CollectionResponse"),
    ("POST", rf"/collections{_ID}/cases", "CollectionResponse"),
    ("PUT|DELETE", rf"/collections{_ID}/cases{_ID}", "CollectionResponse"),
]
VALIDATORS = {name: schema_validator(name) for name in
              {name for _, _, name in SUCCESS_SCHEMAS} | {"ErrorResponse"}}


def success_schema(method: str, path: str) -> str:
    route = path.split("?")[0]
    for methods, pattern, name in SUCCESS_SCHEMAS:
        if re.fullmatch(methods, method) and re.fullmatch(pattern, route):
            return name
    raise AssertionError(f"no success schema for {method} {path}")


def etag(revision: int) -> str:
    return f'"{revision}"'


def with_cursor(path: str, cursor: str, limit: int | None = None) -> str:
    """A list path with a cursor (URL-encoded) and an optional limit."""
    query = f"cursor={quote(cursor, safe='')}"
    return f"{path}?{query}" + (f"&limit={limit}" if limit is not None else "")


class ApiTestCase(unittest.TestCase):
    """Base class: self.api() talks to a new app built with `limits`."""

    limits = Limits()

    def setUp(self) -> None:
        self.app = create_app(self.limits, **self.app_options())
        self.client = self.app.test_client()

    def app_options(self) -> dict:
        """Extra create_app keyword arguments for a test class."""
        return {}

    # ------------------------------------------------------------ requests

    def api(self, method: str, path: str, body: object = ABSENT, *, if_match: str | None = None,
            raw: bytes | None = None, content_type: str | None = "application/json",
            headers: dict | None = None):
        """Send one request to API + path and return the checked test response.

        body is JSON-encoded; raw sends bytes as they are instead. A
        Content-Type is sent only when there is a body.
        """
        headers = dict(headers or {})
        data = raw if raw is not None else (None if body is ABSENT else json.dumps(body).encode())
        if data is not None and content_type is not None:
            headers["Content-Type"] = content_type
        if if_match is not None:
            headers["If-Match"] = if_match
        response = self.client.open(API + path, method=method, data=data, headers=headers)
        self.check_response(method, path, response)
        return response

    def check_response(self, method: str, path: str, response) -> None:
        """The rules every response follows, whatever the route."""
        status = response.status_code
        if status == 204:
            self.assertEqual(response.data, b"")
            self.assertNotIn("Content-Type", response.headers)
            self.assertNotIn("ETag", response.headers)
            return
        self.assertEqual(response.headers["Content-Type"], "application/json")
        if method == "HEAD":
            self.assertEqual(response.data, b"")
            return
        body = json.loads(response.data)
        schema = "ErrorResponse" if status >= 400 else success_schema(method, path)
        errors = [error.message for error in VALIDATORS[schema].iter_errors(body)]
        self.assertEqual(errors, [], f"{method} {path} -> {status} is not a valid {schema}")
        record = (body.get("program") or body.get("collection")) if status < 300 else None
        if record is not None:
            self.assertEqual(response.headers.get("ETag"), etag(record["revision"]))
        else:
            self.assertNotIn("ETag", response.headers)   # lists and errors carry none

    # ------------------------------------------------------- data helpers

    def create_program(self, name: str = "square", source: str = "(lam (x: sint) => x * x)(7)",
                       **extra) -> dict:
        response = self.api("POST", "/programs", {"name": name, "source": source, **extra})
        self.assertEqual(response.status_code, 201, response.json)
        return response.json["program"]

    def create_collection(self, name: str = "smoke tests", **extra) -> dict:
        response = self.api("POST", "/collections", {"name": name, **extra})
        self.assertEqual(response.status_code, 201, response.json)
        return response.json["collection"]

    def add_case(self, collection: dict, name: str = "factorial 6", source: str = FACTORIAL,
                 expected: dict | None = None, **extra) -> dict:
        """Append a case using the collection's current revision; return the new collection."""
        body = {"name": name, "source": source,
                "expected": expected or {"kind": "value", "value": "720"}, **extra}
        response = self.api("POST", f"/collections/{collection['id']}/cases", body,
                            if_match=etag(collection["revision"]))
        self.assertEqual(response.status_code, 201, response.json)
        return response.json["collection"]

    def get_record(self, path: str) -> dict:
        """GET a program or collection and return its representation."""
        response = self.api("GET", path)
        self.assertEqual(response.status_code, 200, response.json)
        return response.json.get("program") or response.json["collection"]

    # --------------------------------------------------------- assertions

    def assertError(self, response, status: int, code: str, **members) -> dict:
        """The response is a `status` error with `code` and these member values."""
        self.assertEqual(response.status_code, status, response.json)
        error = response.json["error"]
        self.assertEqual(error["code"], code, error)
        for name, value in members.items():
            self.assertEqual(error.get(name), value, error)
        return error

    def assertInvalid(self, response, field: str | None, reason: str, **members) -> dict:
        return self.assertError(response, 400, "invalid_request", field=field, reason=reason, **members)

    def assertUtcTimestamp(self, text: str) -> None:
        """YYYY-MM-DDTHH:MM:SS.sssZ, a valid UTC time (API.md section 2)."""
        self.assertRegex(text, TIMESTAMP)
        self.assertEqual(datetime.fromisoformat(text).utcoffset().total_seconds(), 0)

    def assertUnchanged(self, path: str, before: dict) -> None:
        """A failed request left the record exactly as it was."""
        self.assertEqual(self.get_record(path), before)
