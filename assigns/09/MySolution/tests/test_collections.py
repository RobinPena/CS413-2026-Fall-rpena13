"""Collection CRUD through HTTP (API.md sections 2 and 3)."""
from __future__ import annotations

import unittest

from .http_support import ApiTestCase, etag

COLLECTION_FIELDS = ["id", "name", "description", "created_at", "updated_at", "revision", "cases"]


class CollectionCrudTests(ApiTestCase):

    def test_create_returns_the_complete_record_with_no_cases(self):
        response = self.api("POST", "/collections", {"name": "smoke tests", "description": "quick"})
        self.assertEqual(response.status_code, 201)
        collection = response.json["collection"]
        self.assertEqual(list(collection), COLLECTION_FIELDS)
        self.assertEqual((collection["name"], collection["description"], collection["revision"],
                          collection["cases"]), ("smoke tests", "quick", 1, []))
        self.assertUtcTimestamp(collection["created_at"])
        self.assertEqual(collection["updated_at"], collection["created_at"])

    def test_description_defaults_to_empty(self):
        self.assertEqual(self.create_collection("c")["description"], "")

    def test_get_returns_the_collection_with_ordered_cases(self):
        collection = self.create_collection("c")
        for name in ("one", "two", "three"):
            collection = self.add_case(collection, name=name)
        fetched = self.get_record(f"/collections/{collection['id']}")
        self.assertEqual(fetched, collection)
        self.assertEqual([case["name"] for case in fetched["cases"]], ["one", "two", "three"])

    def test_update_changes_metadata_only(self):
        collection = self.create_collection("c", description="old")
        for name in ("one", "two"):
            collection = self.add_case(collection, name=name)
        response = self.api("PUT", f"/collections/{collection['id']}", {"name": "renamed"},
                            if_match=etag(3))
        self.assertEqual((response.status_code, response.headers["ETag"]), (200, etag(4)))
        updated = response.json["collection"]
        self.assertEqual((updated["name"], updated["description"], updated["revision"]), ("renamed", "", 4))
        self.assertEqual(updated["cases"], collection["cases"])           # same cases, same order
        self.assertEqual((updated["id"], updated["created_at"]), (collection["id"], collection["created_at"]))
        self.assertEqual(self.get_record(f"/collections/{collection['id']}"), updated)

    def test_delete_removes_the_collection_and_its_cases(self):
        collection = self.add_case(self.add_case(self.create_collection("c"), name="one"), name="two")
        path = f"/collections/{collection['id']}"
        case_path = f"{path}/cases/{collection['cases'][0]['id']}"
        self.assertEqual(self.api("DELETE", path, if_match=etag(3)).status_code, 204)

        self.assertError(self.api("GET", path), 404, "record_not_found")
        body = {"name": "one", "source": "1", "expected": {"kind": "value", "value": "1"}}
        self.assertError(self.api("PUT", case_path, body, if_match=etag(3)), 404, "record_not_found")
        self.assertError(self.api("DELETE", case_path, if_match=etag(3)), 404, "record_not_found")
        self.assertError(self.api("POST", f"{path}/cases", body, if_match=etag(3)), 404, "record_not_found")
        self.assertEqual(self.api("GET", "/collections").json["items"], [])
        # A new collection with the same name starts empty.
        self.assertEqual(self.create_collection("c")["cases"], [])

    def test_list_returns_full_collections_with_their_cases(self):
        first = self.add_case(self.add_case(self.create_collection("first"), name="a"), name="b")
        second = self.create_collection("second")
        items = self.api("GET", "/collections").json["items"]
        self.assertEqual(items, [first, second])
        self.assertEqual([case["name"] for case in items[0]["cases"]], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
