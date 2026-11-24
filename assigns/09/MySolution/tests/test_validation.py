"""Request-body validation through HTTP (API.md section 4).

Missing, wrongly typed, blank, oversized, unknown, and server-managed
fields; the exact expected-outcome shapes; check order; name trimming; and
name uniqueness in each scope. Every rule is checked on create and on
update, and a failed update must leave the record unchanged.
"""
from __future__ import annotations

import unittest

from .http_support import ApiTestCase, etag

VALUE_42 = {"kind": "value", "value": "42"}

PROGRAM_FAILURES = [
    ({"source": "1"}, "name", "missing"),
    ({"name": 5, "source": "1"}, "name", "wrong_type"),
    ({"name": None, "source": "1"}, "name", "wrong_type"),
    ({"name": ["p"], "source": "1"}, "name", "wrong_type"),
    ({"name": " \t\n ", "source": "1"}, "name", "blank"),
    ({"name": "", "source": "1"}, "name", "blank"),
    ({"name": "p"}, "source", "missing"),
    ({"name": "p", "source": 42}, "source", "wrong_type"),
    ({"name": "p", "source": None}, "source", "wrong_type"),
    ({"name": "p", "source": ""}, "source", "blank"),
    ({"name": "p", "source": " \n\t "}, "source", "blank"),
    ({"name": "p", "source": "1", "description": 3}, "description", "wrong_type"),
    ({"name": "p", "source": "1", "description": None}, "description", "wrong_type"),
    ({"name": "p", "source": "1", "author": "me"}, "author", "unknown_field"),
    ({"name": "p", "source": "1", "cases": []}, "cases", "unknown_field"),
    ({"name": "p", "source": "1", "id": "prg_mine"}, "id", "server_managed_field"),
    ({"name": "p", "source": "1", "created_at": "2026-01-01T00:00:00.000Z"}, "created_at", "server_managed_field"),
    ({"name": "p", "source": "1", "updated_at": "2026-01-01T00:00:00.000Z"}, "updated_at", "server_managed_field"),
    ({"name": "p", "source": "1", "revision": 7}, "revision", "server_managed_field"),
]

COLLECTION_FAILURES = [
    ({}, "name", "missing"),
    ({"name": True}, "name", "wrong_type"),
    ({"name": "   "}, "name", "blank"),
    ({"name": "c", "description": {}}, "description", "wrong_type"),
    ({"name": "c", "source": "1"}, "source", "unknown_field"),
    ({"name": "c", "cases": []}, "cases", "server_managed_field"),
    ({"name": "c", "id": "col_mine"}, "id", "server_managed_field"),
    ({"name": "c", "revision": 1}, "revision", "server_managed_field"),
]


def case_body(expected=VALUE_42, **fields):
    return {"name": "k", "source": "6 * 7", "expected": expected, **fields}


CASE_FAILURES = [
    ({"source": "1", "expected": VALUE_42}, "name", "missing"),
    (case_body(source="  "), "source", "blank"),
    ({"name": "k", "source": "1"}, "expected", "missing"),
    (case_body("720"), "expected", "wrong_type"),
    (case_body(None), "expected", "wrong_type"),
    (case_body([]), "expected", "wrong_type"),
    (case_body({"value": "720"}), "expected.kind", "missing"),
    (case_body({"kind": 1, "value": "720"}), "expected.kind", "wrong_type"),
    (case_body({"kind": "Value", "value": "720"}), "expected.kind", "invalid_value"),
    (case_body({"kind": "success", "value": "720"}), "expected.kind", "invalid_value"),
    (case_body({"kind": "value"}), "expected.value", "missing"),
    (case_body({"kind": "value", "value": 720}), "expected.value", "wrong_type"),
    (case_body({"kind": "value", "value": None}), "expected.value", "wrong_type"),
    (case_body({"kind": "error"}), "expected.category", "missing"),
    (case_body({"kind": "error", "category": 1}), "expected.category", "wrong_type"),
    (case_body({"kind": "error", "category": "runtime"}), "expected.category", "invalid_value"),
    (case_body({"kind": "error", "category": "timeout"}), "expected.category", "invalid_value"),
    (case_body({"kind": "error", "category": "Syntax"}), "expected.category", "invalid_value"),
    (case_body({"kind": "error", "category": "type", "value": "1"}), "expected.value", "unknown_field"),
    (case_body({"kind": "value", "value": "1", "category": "type"}), "expected.category", "unknown_field"),
    (case_body({"kind": "value", "value": "1", "note": "x"}), "expected.note", "unknown_field"),
    (case_body(description=[]), "description", "wrong_type"),
    (case_body(id="case_mine"), "id", "server_managed_field"),
    (case_body(program_id="prg_x"), "program_id", "unknown_field"),
]


class ProgramFieldTests(ApiTestCase):

    def test_create_rejects_each_invalid_body(self):
        for body, field, reason in PROGRAM_FAILURES:
            with self.subTest(body=body):
                self.assertInvalid(self.api("POST", "/programs", body), field, reason)
        self.assertEqual(self.api("GET", "/programs").json["items"], [])

    def test_update_rejects_each_invalid_body_and_changes_nothing(self):
        program = self.create_program("p")
        path = f"/programs/{program['id']}"
        for body, field, reason in PROGRAM_FAILURES:
            with self.subTest(body=body):
                self.assertInvalid(self.api("PUT", path, body, if_match=etag(1)), field, reason)
        self.assertUnchanged(path, program)

    def test_unpaired_surrogate_is_invalid_text(self):
        self.assertInvalid(self.api("POST", "/programs", raw=b'{"name": "a\\ud800", "source": "1"}'),
                           "name", "invalid_text")
        self.assertInvalid(self.api("POST", "/programs", raw=b'{"name": "a", "source": "\\udfff"}'),
                           "source", "invalid_text")

    def test_check_order_members_first_then_name_source_description(self):
        self.assertInvalid(self.api("POST", "/programs", {"name": 5, "revision": 1}),
                           "revision", "server_managed_field")
        self.assertInvalid(self.api("POST", "/programs", {"x": 1, "id": "y"}), "x", "unknown_field")
        self.assertInvalid(self.api("POST", "/programs", {"description": 1, "source": 2, "name": 3}),
                           "name", "wrong_type")
        self.assertInvalid(self.api("POST", "/programs", {"description": 1, "name": "p", "source": ""}),
                           "source", "blank")

    def test_invalid_body_is_reported_before_a_missing_record(self):
        self.assertInvalid(self.api("PUT", "/programs/missing", {"name": ""}, if_match=etag(1)),
                           "name", "blank")

    def test_name_is_trimmed_source_and_description_are_stored_exactly(self):
        program = self.create_program("\t factorial \n", source="  1 + 2\n", description=" d ")
        self.assertEqual((program["name"], program["source"], program["description"]),
                         ("factorial", "  1 + 2\n", " d "))
        response = self.api("PUT", f"/programs/{program['id']}",
                            {"name": "  renamed ", "source": "\n3\n"}, if_match=etag(1))
        updated = response.json["program"]
        self.assertEqual((updated["name"], updated["source"], updated["description"]),
                         ("renamed", "\n3\n", ""))

    def test_field_size_boundaries(self):
        name = "n" * 100
        source = "é" * (65_536 // 2)          # 2 UTF-8 bytes each
        description = "d" * 1_000
        program = self.create_program(f"  {name}  ", source=source, description=description)
        self.assertEqual((program["name"], program["source"], program["description"]),
                         (name, source, description))
        cases = [
            ({"name": name + "n", "source": "1"}, "name", "too_long", 100),
            ({"name": "p", "source": source + "x"}, "source", "too_large", 65_536),
            ({"name": "p", "source": "1", "description": description + "d"}, "description", "too_long", 1_000),
        ]
        for body, field, reason, limit in cases:
            with self.subTest(field=field):
                self.assertInvalid(self.api("POST", "/programs", body), field, reason, limit=limit)
                self.assertInvalid(self.api("PUT", f"/programs/{program['id']}", body, if_match=etag(1)),
                                   field, reason, limit=limit)
        self.assertUnchanged(f"/programs/{program['id']}", program)


class CollectionFieldTests(ApiTestCase):

    def test_create_and_update_reject_each_invalid_body(self):
        collection = self.add_case(self.create_collection("c"))
        path = f"/collections/{collection['id']}"
        for body, field, reason in COLLECTION_FAILURES:
            with self.subTest(body=body):
                self.assertInvalid(self.api("POST", "/collections", body), field, reason)
                self.assertInvalid(self.api("PUT", path, body, if_match=etag(2)), field, reason)
        self.assertUnchanged(path, collection)
        self.assertEqual(len(self.api("GET", "/collections").json["items"]), 1)

    def test_name_trimming_and_description_limit(self):
        collection = self.create_collection("  smoke  ", description="x" * 1_000)
        self.assertEqual(collection["name"], "smoke")
        self.assertInvalid(self.api("POST", "/collections", {"name": "c", "description": "x" * 1_001}),
                           "description", "too_long", limit=1_000)


class CaseFieldTests(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.collection = self.add_case(self.create_collection("c"), name="existing")
        self.path = f"/collections/{self.collection['id']}"
        self.case_path = f"{self.path}/cases/{self.collection['cases'][0]['id']}"

    def test_add_and_update_reject_each_invalid_body_and_change_nothing(self):
        for body, field, reason in CASE_FAILURES:
            with self.subTest(body=body):
                self.assertInvalid(self.api("POST", f"{self.path}/cases", body, if_match=etag(2)), field, reason)
                self.assertInvalid(self.api("PUT", self.case_path, body, if_match=etag(2)), field, reason)
        self.assertUnchanged(self.path, self.collection)

    def test_the_three_expected_shapes_are_stored_exactly(self):
        shapes = [{"kind": "value", "value": " 720 "}, {"kind": "value", "value": ""},
                  {"category": "syntax", "kind": "error"}, {"kind": "error", "category": "type"}]
        collection = self.collection
        for n, expected in enumerate(shapes):
            collection = self.add_case(collection, name=f"shape {n}", expected=expected)
        stored = [case["expected"] for case in collection["cases"][1:]]
        self.assertEqual(stored, [{"kind": "value", "value": " 720 "}, {"kind": "value", "value": ""},
                                  {"kind": "error", "category": "syntax"}, {"kind": "error", "category": "type"}])

    def test_case_size_boundaries(self):
        source, value = "s" * 65_536, "v" * 8_192
        collection = self.add_case(self.collection, name="k" * 100, source=source,
                                   expected={"kind": "value", "value": value}, description="d" * 1_000)
        self.assertEqual(collection["cases"][1]["source"], source)
        cases = [
            (case_body(name="k" * 101), "name", "too_long", 100),
            (case_body(source=source + "s"), "source", "too_large", 65_536),
            (case_body({"kind": "value", "value": value + "v"}), "expected.value", "too_large", 8_192),
            (case_body(description="d" * 1_001), "description", "too_long", 1_000),
        ]
        for body, field, reason, limit in cases:
            with self.subTest(field=field):
                self.assertInvalid(self.api("POST", f"{self.path}/cases", body, if_match=etag(3)),
                                   field, reason, limit=limit)
                self.assertInvalid(self.api("PUT", self.case_path, body, if_match=etag(3)),
                                   field, reason, limit=limit)
        self.assertUnchanged(self.path, collection)


class NameUniquenessTests(ApiTestCase):

    def test_program_names_are_unique_after_trimming_on_create_and_update(self):
        a = self.create_program("a")
        b = self.create_program("b")
        error = self.assertError(self.api("POST", "/programs", {"name": " a\t", "source": "1"}),
                                 409, "duplicate_name", field="name")
        self.assertIn("'a'", error["message"])
        self.assertError(self.api("PUT", f"/programs/{b['id']}", {"name": "a ", "source": "1"},
                                  if_match=etag(1)), 409, "duplicate_name", field="name")
        self.assertUnchanged(f"/programs/{b['id']}", b)
        # Keeping its own name is not a conflict; names are not case-folded.
        self.assertEqual(self.api("PUT", f"/programs/{a['id']}", {"name": " a ", "source": "2"},
                                  if_match=etag(1)).status_code, 200)
        self.assertEqual(self.create_program("A")["name"], "A")

    def test_a_deleted_name_can_be_reused(self):
        program = self.create_program("a")
        self.api("DELETE", f"/programs/{program['id']}", if_match=etag(1))
        self.assertEqual(self.create_program("a")["name"], "a")

    def test_collection_names_are_unique_among_collections_only(self):
        self.create_program("shared")
        self.create_collection("shared")                   # a program may share the name
        other = self.create_collection("other")
        self.assertError(self.api("POST", "/collections", {"name": "shared "}), 409, "duplicate_name")
        self.assertError(self.api("PUT", f"/collections/{other['id']}", {"name": " shared"},
                                  if_match=etag(1)), 409, "duplicate_name", field="name")
        self.assertUnchanged(f"/collections/{other['id']}", other)

    def test_case_names_are_unique_within_one_collection(self):
        first = self.add_case(self.create_collection("first"), name="k")
        second = self.add_case(self.create_collection("second"), name="k")   # other collection: allowed
        self.assertEqual(second["cases"][0]["name"], "k")
        self.create_program("k")                                             # other kind: allowed

        cases_path = f"/collections/{first['id']}/cases"
        self.assertError(self.api("POST", cases_path, case_body(name=" k "), if_match=etag(2)),
                         409, "duplicate_name", field="name")
        first = self.add_case(first, name="k2")
        k2_path = f"{cases_path}/{first['cases'][1]['id']}"
        self.assertError(self.api("PUT", k2_path, case_body(name="k"), if_match=etag(3)),
                         409, "duplicate_name", field="name")
        self.assertUnchanged(f"/collections/{first['id']}", first)
        # A case keeps its own name without conflict.
        self.assertEqual(self.api("PUT", k2_path, case_body(name="k2 "), if_match=etag(3)).status_code, 200)


if __name__ == "__main__":
    unittest.main()
