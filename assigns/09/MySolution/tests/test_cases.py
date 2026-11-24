"""Ordered test cases inside a collection, through HTTP (API.md section 3)."""
from __future__ import annotations

import unittest

from .http_support import FACTORIAL, ApiTestCase, etag

CASE_FIELDS = ["id", "name", "source", "expected", "description"]
SYNTAX = {"kind": "error", "category": "syntax"}
TYPE = {"kind": "error", "category": "type"}


def case_body(name, source="1", expected=None, **extra):
    return {"name": name, "source": source, "expected": expected or {"kind": "value", "value": "1"}, **extra}


class CaseLifecycleTests(ApiTestCase):

    def setUp(self):
        super().setUp()
        collection = self.create_collection("smoke tests")
        collection = self.add_case(collection, name="factorial 6", source=FACTORIAL)
        collection = self.add_case(collection, name="bad syntax", source="if then", expected=SYNTAX)
        self.collection = self.add_case(collection, name="bad argument",
                                        source="(lam (x: sint) => x)(true)", expected=TYPE)
        self.path = f"/collections/{self.collection['id']}"

    def names(self, collection):
        return [case["name"] for case in collection["cases"]]

    def test_add_appends_complete_cases_in_order(self):
        self.assertEqual(self.names(self.collection), ["factorial 6", "bad syntax", "bad argument"])
        first = self.collection["cases"][0]
        self.assertEqual(list(first), CASE_FIELDS)
        self.assertEqual(first, {"id": first["id"], "name": "factorial 6", "source": FACTORIAL,
                                 "expected": {"kind": "value", "value": "720"}, "description": ""})
        self.assertEqual(len({case["id"] for case in self.collection["cases"]}), 3)
        self.assertEqual(self.get_record(self.path), self.collection)

    def test_add_returns_201_with_the_collection_and_its_new_etag(self):
        response = self.api("POST", f"{self.path}/cases", case_body("fourth"), if_match=etag(4))
        self.assertEqual((response.status_code, response.headers["ETag"]), (201, etag(5)))
        self.assertEqual(self.names(response.json["collection"])[-1], "fourth")

    def test_update_changes_the_case_in_place(self):
        middle = self.collection["cases"][1]
        response = self.api("PUT", f"{self.path}/cases/{middle['id']}",
                            case_body("bad syntax", "let x = in x end", SYNTAX, description="missing expression"),
                            if_match=etag(4))
        self.assertEqual((response.status_code, response.headers["ETag"]), (200, etag(5)))
        cases = response.json["collection"]["cases"]
        self.assertEqual(cases[1], {"id": middle["id"], "name": "bad syntax", "source": "let x = in x end",
                                    "expected": SYNTAX, "description": "missing expression"})
        self.assertEqual([cases[0], cases[2]], [self.collection["cases"][0], self.collection["cases"][2]])
        self.assertEqual(self.get_record(self.path)["cases"], cases)

    def test_update_can_change_the_expected_shape(self):
        first = self.collection["cases"][0]
        response = self.api("PUT", f"{self.path}/cases/{first['id']}", case_body("factorial 6", "1 +", SYNTAX),
                            if_match=etag(4))
        self.assertEqual(response.json["collection"]["cases"][0]["expected"], SYNTAX)

    def test_delete_keeps_the_remaining_order_and_returns_the_collection(self):
        first = self.collection["cases"][0]
        response = self.api("DELETE", f"{self.path}/cases/{first['id']}", if_match=etag(4))
        self.assertEqual((response.status_code, response.headers["ETag"]), (200, etag(5)))
        collection = response.json["collection"]
        self.assertEqual(self.names(collection), ["bad syntax", "bad argument"])
        self.assertEqual(collection["cases"], self.collection["cases"][1:])
        self.assertError(self.api("DELETE", f"{self.path}/cases/{first['id']}", if_match=etag(5)),
                         404, "record_not_found")
        self.assertEqual(self.get_record(self.path), collection)

    def test_delete_middle_then_add_appends_at_the_end(self):
        middle = self.collection["cases"][1]
        self.api("DELETE", f"{self.path}/cases/{middle['id']}", if_match=etag(4))
        collection = self.add_case(self.get_record(self.path), name="new")
        self.assertEqual(self.names(collection), ["factorial 6", "bad argument", "new"])

    def test_unknown_collection_and_case_ids_are_404(self):
        body = case_body("x")
        missing_collection = "/collections/col_doesNotExist0"
        error = self.assertError(self.api("POST", f"{missing_collection}/cases", body, if_match=etag(1)),
                                 404, "record_not_found")
        self.assertIn("collection", error["message"])
        case_id = self.collection["cases"][0]["id"]
        self.assertError(self.api("PUT", f"{missing_collection}/cases/{case_id}", body, if_match=etag(4)),
                         404, "record_not_found")
        error = self.assertError(self.api("PUT", f"{self.path}/cases/case_doesNotExist", body, if_match=etag(4)),
                                 404, "record_not_found")
        self.assertEqual(error["message"], "No case has ID 'case_doesNotExist' in this collection.")
        self.assertError(self.api("DELETE", f"{self.path}/cases/case_doesNotExist", if_match=etag(4)),
                         404, "record_not_found")
        self.assertUnchanged(self.path, self.collection)

    def test_a_case_id_from_another_collection_is_not_found(self):
        other = self.add_case(self.create_collection("other"), name="theirs")
        foreign = other["cases"][0]["id"]
        self.assertError(self.api("DELETE", f"{self.path}/cases/{foreign}", if_match=etag(4)),
                         404, "record_not_found")
        self.assertUnchanged(f"/collections/{other['id']}", other)


if __name__ == "__main__":
    unittest.main()
