"""rpc.schema.json against itself, the RPC.md examples and the compile fixtures (RPC.md section 8)."""
import json
import re
import unittest

from jsonschema import Draft202012Validator

from MySolution.tests.support import SCHEMA, SOLUTION_DIR, schema_validator

# RPC.md section 7 examples whose requests are invalid on purpose.
INVALID_REQUEST_EXAMPLES = {"7.11", "7.12", "7.14", "7.15", "7.18"}


def rpc_md_json_blocks() -> list[tuple[str, object]]:
    """(section heading, value) for each JSON value in RPC.md's ```json blocks."""
    text = (SOLUTION_DIR / "RPC.md").read_text(encoding="utf-8")
    heading, values = "", []
    for match in re.finditer(r"^(#{2,3} [^\n]+)$|^```json\n(.*?)^```", text, re.M | re.S):
        if match.group(1):
            heading = match.group(1)
            continue
        block = match.group(2)
        try:
            values.append((heading, json.loads(block)))
        except json.JSONDecodeError:  # several one-line values in one block
            values.extend((heading, json.loads(line)) for line in block.splitlines() if line.strip())
    return values


def is_response(value: object) -> bool:
    first = value[0] if isinstance(value, list) and value else value
    return isinstance(first, dict) and ("result" in first or "error" in first)


class SchemaTests(unittest.TestCase):
    def test_schema_is_valid_draft_2020_12(self):
        Draft202012Validator.check_schema(SCHEMA)

    def test_compile_fixtures_are_valid_responses(self):
        response = schema_validator("SuccessResponse")
        for target in ("python", "javascript"):
            with self.subTest(target=target):
                body = json.loads((SOLUTION_DIR / "examples" / f"compile-{target}-response.json").read_text())
                response.validate(body)
                self.assertEqual(body["result"]["target"], target)

    def test_rpc_md_examples_match_the_schema(self):
        responses, requests = schema_validator("ResponseBody"), schema_validator("RequestBody")
        blocks = rpc_md_json_blocks()
        self.assertGreaterEqual(sum(is_response(value) for _, value in blocks), 16)
        for heading, value in blocks:
            with self.subTest(heading=heading, value=str(value)[:60]):
                if is_response(value):
                    responses.validate(value)
                else:
                    section = heading.split()[1] if heading.startswith("### ") else ""
                    self.assertEqual(requests.is_valid(value), section not in INVALID_REQUEST_EXAMPLES)

    def test_schema_rejects_contract_violations(self):
        responses = schema_validator("ResponseBody")
        internal = {"code": -32603, "message": "Internal error", "data": {"incident": "0123456789ab"}}
        violations = {
            "result and error together": {"jsonrpc": "2.0", "result": {"type": "sint"}, "error": internal, "id": 1},
            "invalid request with an id": {"jsonrpc": "2.0", "id": 1, "error": {
                "code": -32600, "message": "Invalid Request", "data": {"reason": "bad_jsonrpc"}}},
            "boolean id": {"jsonrpc": "2.0", "result": {"type": "sint"}, "id": True},
            "undocumented code": {"jsonrpc": "2.0", "error": {"code": -32099, "message": "x"}, "id": 1},
            "wrong message for code": {"jsonrpc": "2.0", "error": {**internal, "message": "oops"}, "id": 1},
            "empty response array": [],
        }
        for name, value in violations.items():
            with self.subTest(name=name):
                self.assertFalse(responses.is_valid(value))

    def test_envelope_and_method_levels_are_separate(self):
        positional = {"jsonrpc": "2.0", "method": "service.health", "params": [], "id": 1}
        self.assertTrue(schema_validator("EnvelopeRequest").is_valid(positional))
        self.assertFalse(schema_validator("MethodRequest").is_valid(positional))
        self.assertFalse(schema_validator("EnvelopeRequest").is_valid({**positional, "params": "x"}))
