"""The contract documents, checked against each other and against the app.

- api.schema.json is valid JSON Schema (draft 2020-12) and rejects bodies
  that break the contract.
- Every example in API.md section 11 is consistent: bodies validate against
  their route's schema, statuses match error codes, and headers follow the
  ETag and If-Match rules.
- The route table in API.md matches Assign09.md and the Flask app's routes.
- Error codes, reasons, and statuses agree across API.md, the schema, and
  app.py.
- Links and requirement IDs in API.md resolve.
"""
from __future__ import annotations

import json
import re
import unittest

from jsonschema import Draft202012Validator

from MySolution.app import METHOD_ORDER, STATUS_FOR_CODE, create_app

from .http_support import API, SCHEMA, SOLUTION_DIR, schema_validator, success_schema

API_MD = (SOLUTION_DIR / "API.md").read_text(encoding="utf-8")
DESIGN_MD = (SOLUTION_DIR / "DESIGN.md").read_text(encoding="utf-8")
ASSIGNMENT = SOLUTION_DIR.parent / "Assign09.md"
CONTRACT_GROUPS = ("CON", "VAL", "DATA", "REV", "PAGE")

REQUEST_SCHEMAS = [
    ("POST", r"/programs", "ProgramInput"),
    ("PUT", r"/programs/[^/]+", "ProgramInput"),
    ("POST", r"/collections", "CollectionInput"),
    ("PUT", r"/collections/[^/]+", "CollectionInput"),
    ("POST", r"/collections/[^/]+/cases", "CaseInput"),
    ("PUT", r"/collections/[^/]+/cases/[^/]+", "CaseInput"),
]


def between(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def request_schema(method: str, path: str) -> str | None:
    for schema_method, pattern, name in REQUEST_SCHEMAS:
        if method == schema_method and re.fullmatch(pattern, path):
            return name
    return None


def parse_message(block: str) -> tuple[str, dict, str]:
    """(start line, headers, body text) of one ```http block."""
    head, _, body = block.partition("\n\n")
    start, *header_lines = head.strip().splitlines()
    headers = dict(line.split(": ", 1) for line in header_lines)
    return start, headers, body.strip()


def http_examples() -> list[tuple[str, tuple | None, tuple]]:
    """(heading, request or None, response) for every response in API.md section 11.

    A response is paired with the request block right before it, if any.
    """
    examples, heading, request = [], "", None
    section = API_MD.split("## 11. Examples", 1)[1]
    for match in re.finditer(r"^(#{3} [^\n]+)$|^```http\n(.*?)^```", section, re.M | re.S):
        if match.group(1):
            heading, request = match.group(1), None
            continue
        message = parse_message(match.group(2))
        if message[0].startswith("HTTP/1.1"):
            examples.append((heading, request, message))
            request = None
        else:
            request = message
    return examples


def route_table(text: str) -> dict[tuple[str, str], str | None]:
    """{(method, path): success status} from a markdown route table."""
    routes = {}
    for line in text.splitlines():
        match = re.match(r"\| `(GET|POST|PUT|DELETE) (/[^`?]*)[^|]*\|(.*)", line)
        if match:
            status = re.search(r"`(20[014])`", match.group(3))
            routes[(match.group(1), match.group(2))] = status.group(1) if status else None
    return routes


def requirement_ids(text: str) -> set[str]:
    """Requirement IDs cited in brackets, with ranges such as [DATA-1–3] expanded."""
    cited = set()
    for group in re.findall(r"\[((?:CON|VAL|DATA|REV|PAGE|STU|DOC)[^\]]*)\]", text):
        for prefix, first, last in re.findall(r"([A-Z]+)-(\d+)(?:–(\d+))?", group):
            cited |= {f"{prefix}-{n}" for n in range(int(first), int(last or first) + 1)}
    return cited


class SchemaDocumentTests(unittest.TestCase):

    def test_schema_is_valid_draft_2020_12(self):
        Draft202012Validator.check_schema(SCHEMA)

    def test_schema_rejects_contract_violations(self):
        program = {"id": "prg_x", "name": "p", "source": "1", "description": "",
                   "created_at": "2026-11-24T15:00:00.000Z", "updated_at": "2026-11-24T15:00:00.000Z",
                   "revision": 1}
        self.assertTrue(schema_validator("ProgramResponse").is_valid({"program": program}))
        violations = {
            "ProgramResponse": [
                {"program": {k: v for k, v in program.items() if k != "description"}},
                {"program": {**program, "revision": 0}},
                {"program": {**program, "created_at": "2026-11-24T15:00:00+00:00"}},
                {"program": {**program, "name": " p"}},
                {"program": {**program, "extra": 1}},
            ],
            "ProgramInput": [{"name": "p", "source": "1", "id": "x"}, {"name": "p", "source": "  "},
                             {"name": "p"}, {"name": "p", "source": "1", "description": None}],
            "CaseInput": [{"name": "k", "source": "1", "expected": {"kind": "value", "value": "1",
                                                                     "category": "type"}},
                          {"name": "k", "source": "1", "expected": {"kind": "error", "category": "runtime"}}],
            "ErrorResponse": [
                {"error": {"code": "invalid_request", "message": "m"}},                  # no field/reason
                {"error": {"code": "revision_conflict", "message": "m"}},                # no current_revision
                {"error": {"code": "record_not_found", "message": "m", "reason": "missing"}},
                {"error": {"code": "capacity_limit", "message": "m", "limit": 5}},       # no resource
                {"error": {"code": "teapot", "message": "m"}},
                {"error": {"code": "internal_error", "message": "m", "trace": "..."}},
            ],
            "ProgramPage": [{"items": []}, {"items": [], "next_cursor": ""}],
        }
        for definition, bodies in violations.items():
            validator = schema_validator(definition)
            for body in bodies:
                with self.subTest(definition=definition, body=body):
                    self.assertFalse(validator.is_valid(body))


class ExampleTests(unittest.TestCase):

    def setUp(self):
        self.examples = http_examples()

    def test_every_example_body_matches_its_schema_and_status(self):
        self.assertGreaterEqual(len(self.examples), 25)
        for heading, request, (start, headers, body) in self.examples:
            status = int(start.split()[1])
            with self.subTest(heading=heading, response=start):
                if status == 204:
                    self.assertEqual(body, "")
                    self.assertNotIn("ETag", headers)
                    continue
                self.assertEqual(headers.get("Content-Type"), "application/json")
                value = json.loads(body)
                if status >= 400:
                    schema_validator("ErrorResponse").validate(value)
                    self.assertEqual(STATUS_FOR_CODE[value["error"]["code"]], status)
                else:
                    method, target = request[0].split()[:2]
                    schema_validator(success_schema(method, target.removeprefix(API))).validate(value)

    def test_example_request_bodies_match_their_schema(self):
        checked = 0
        for heading, request, _ in self.examples:
            if request is None or not request[2]:
                continue
            method, target = request[0].split()[:2]
            name = request_schema(method, target.removeprefix(API))
            try:
                value = json.loads(request[2])
            except json.JSONDecodeError:
                continue          # the malformed-JSON and text/plain examples, on purpose
            with self.subTest(heading=heading, request=request[0]):
                # Only section 11.6 shows bodies the schema itself rejects.
                self.assertEqual(schema_validator(name).is_valid(value), not heading.startswith("### 11.6"))
                checked += 1
        self.assertGreaterEqual(checked, 10)

    def test_example_headers_follow_the_etag_rules(self):
        for heading, request, (start, headers, body) in self.examples:
            status = int(start.split()[1])
            value = json.loads(body) if body else {}
            record = value.get("program") or value.get("collection")
            with self.subTest(heading=heading, response=start):
                if status == 405:
                    self.assertIn("Allow", headers)
                if value.get("error", {}).get("code") == "revision_conflict":
                    sent = int(request[1]["If-Match"].strip('"'))
                    self.assertNotEqual(value["error"]["current_revision"], sent)
                if record is None:
                    self.assertNotIn("ETag", headers)
                    continue
                self.assertEqual(headers["ETag"], f'"{record["revision"]}"')
                method, target = request[0].split()[:2]
                if method in ("PUT", "DELETE") or target.endswith("/cases"):
                    sent = int(request[1]["If-Match"].strip('"'))
                    self.assertEqual(record["revision"], sent + 1)
                if status == 201 and not target.endswith("/cases"):
                    self.assertEqual(headers["Location"], f"{target}/{record['id']}")


class RouteTableTests(unittest.TestCase):

    def api_md_routes(self) -> dict:
        return route_table(between(API_MD, "## 3. Routes", "**Methods accepted"))

    @unittest.skipUnless(ASSIGNMENT.exists(), "Assign09.md is not next to MySolution/")
    def test_routes_and_success_statuses_match_the_assignment(self):
        assignment = route_table(ASSIGNMENT.read_text(encoding="utf-8"))
        documented = {(method, API + path): status for (method, path), status in self.api_md_routes().items()}
        self.assertEqual(len(assignment), 14)
        self.assertEqual(documented, assignment)

    def test_app_serves_exactly_the_documented_routes_and_methods(self):
        served: dict[str, set[str]] = {}
        for rule in create_app().url_map.iter_rules():
            path = rule.rule.replace("<case_id>", "{case_id}")
            path = re.sub(r"<\w+_id>", "{id}", path).removeprefix(API)
            served.setdefault(path, set()).update(rule.methods)
        routes = {(method, path) for path, methods in served.items()
                  for method in methods - {"HEAD", "OPTIONS"}}
        self.assertEqual(routes, set(self.api_md_routes()))

        allow_table = between(API_MD, "| Path | `Allow` |", "\n\n")
        documented_allow = {}
        for paths, allow in re.findall(r"^\| (`/[^|]+) \| `([A-Z, ]+)` \|$", allow_table, re.M):
            for path in re.findall(r"`([^`]+)`", paths):
                documented_allow[path] = allow
        served_allow = {path: ", ".join(m for m in METHOD_ORDER if m in methods)
                        for path, methods in served.items()}
        self.assertEqual(served_allow, documented_allow)


class ErrorTableTests(unittest.TestCase):

    def test_codes_and_statuses_agree_across_api_md_schema_and_app(self):
        documented = dict((code, int(status)) for status, code in
                          re.findall(r"^\| `(\d{3})` \| `([a-z_]+)`", API_MD, re.M))
        self.assertEqual(documented, STATUS_FOR_CODE)
        self.assertEqual(set(SCHEMA["$defs"]["Error"]["properties"]["code"]["enum"]), set(STATUS_FOR_CODE))
        for required in ("invalid_request", "record_not_found", "duplicate_name", "revision_conflict",
                         "capacity_limit", "internal_error"):
            self.assertIn(required, documented)
        self.assertEqual(set(documented.values()), {400, 404, 405, 409, 413, 415, 428, 500})

    def test_reasons_agree_between_api_md_and_schema(self):
        table = between(API_MD, "| `reason` | Meaning |", "\n\n")
        documented = set(re.findall(r"^\| `([a-z_]+)` \|", table, re.M))
        self.assertEqual(documented, set(SCHEMA["$defs"]["Error"]["properties"]["reason"]["enum"]))
        self.assertEqual(len(documented), 18)


class CrossReferenceTests(unittest.TestCase):

    def test_contents_links_resolve(self):
        headings = {re.sub(r"[^a-z0-9 -]", "", heading.lower()).replace(" ", "-")
                    for heading in re.findall(r"^## (.+)$", API_MD, re.M)}
        for anchor in re.findall(r"\]\(#([^)]+)\)", API_MD):
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, headings)

    def test_every_contract_requirement_is_cited_and_every_citation_exists(self):
        defined = set(re.findall(r"^\| ((?:CON|VAL|DATA|REV|PAGE|STU|DOC)-\d+) \|", DESIGN_MD, re.M))
        cited = requirement_ids(API_MD)
        self.assertEqual(cited - defined, set())
        contract = {rid for rid in defined if rid.split("-")[0] in CONTRACT_GROUPS}
        self.assertEqual(contract - cited, set())


if __name__ == "__main__":
    unittest.main()
