"""Program CRUD through HTTP (API.md sections 2 and 3)."""
from __future__ import annotations

import unittest

from .http_support import FACTORIAL, ApiTestCase, etag

PROGRAM_FIELDS = ["id", "name", "source", "description", "created_at", "updated_at", "revision"]


class ProgramCrudTests(ApiTestCase):

    def test_create_returns_the_complete_record(self):
        response = self.api("POST", "/programs", {"name": "factorial", "source": FACTORIAL})
        self.assertEqual(response.status_code, 201)
        program = response.json["program"]
        self.assertEqual(list(program), PROGRAM_FIELDS)
        self.assertEqual((program["name"], program["source"], program["description"], program["revision"]),
                         ("factorial", FACTORIAL, "", 1))
        self.assertIsInstance(program["id"], str)
        self.assertUtcTimestamp(program["created_at"])
        self.assertEqual(program["updated_at"], program["created_at"])

    def test_ids_are_generated_and_distinct(self):
        ids = {self.create_program(f"p{n}")["id"] for n in range(20)}
        self.assertEqual(len(ids), 20)

    def test_get_returns_the_saved_record_to_a_new_client(self):
        program = self.create_program("p", description="saved")
        # A browser reload is a new client; the record lives in the service process.
        response = self.app.test_client().get(f"/api/v1/programs/{program['id']}")
        self.assertEqual((response.status_code, response.headers["ETag"]), (200, etag(1)))
        self.assertEqual(response.json, {"program": program})

    def test_update_replaces_name_source_and_description(self):
        program = self.create_program("p", source="1", description="old")
        response = self.api("PUT", f"/programs/{program['id']}",
                            {"name": "q", "source": "2", "description": "new"}, if_match=etag(1))
        self.assertEqual((response.status_code, response.headers["ETag"]), (200, etag(2)))
        updated = response.json["program"]
        self.assertEqual({k: updated[k] for k in ("id", "name", "source", "description", "created_at", "revision")},
                         {"id": program["id"], "name": "q", "source": "2", "description": "new",
                          "created_at": program["created_at"], "revision": 2})
        self.assertUtcTimestamp(updated["updated_at"])
        self.assertGreaterEqual(updated["updated_at"], program["created_at"])
        self.assertEqual(self.get_record(f"/programs/{program['id']}"), updated)

    def test_update_without_description_resets_it(self):
        program = self.create_program("p", description="old")
        response = self.api("PUT", f"/programs/{program['id']}", {"name": "p", "source": "1"}, if_match=etag(1))
        self.assertEqual(response.json["program"]["description"], "")

    def test_delete_removes_the_program(self):
        program = self.create_program("p")
        path = f"/programs/{program['id']}"
        self.assertEqual(self.api("DELETE", path, if_match=etag(1)).status_code, 204)
        error = self.assertError(self.api("GET", path), 404, "record_not_found")
        self.assertEqual(error["message"], f"No program has ID {program['id']!r}.")
        self.assertError(self.api("PUT", path, {"name": "p", "source": "1"}, if_match=etag(1)),
                         404, "record_not_found")
        self.assertError(self.api("DELETE", path, if_match=etag(1)), 404, "record_not_found")
        self.assertEqual(self.api("GET", "/programs").json["items"], [])

    def test_unknown_ids_are_404(self):
        self.create_program("p")
        for method in ("GET", "DELETE"):
            with self.subTest(method=method):
                self.assertError(self.api(method, "/programs/prg_doesNotExist0", if_match=etag(1)),
                                 404, "record_not_found")

    def test_list_returns_full_records_in_creation_order(self):
        created = [self.create_program(name) for name in ("zeta", "alpha", "mid")]
        self.api("PUT", f"/programs/{created[0]['id']}", {"name": "zeta", "source": "9"}, if_match=etag(1))
        items = self.api("GET", "/programs").json["items"]
        self.assertEqual([p["name"] for p in items], ["zeta", "alpha", "mid"])
        self.assertEqual(items[1:], created[1:])
        self.assertEqual((items[0]["source"], items[0]["revision"]), ("9", 2))


class ProgramIndependenceTests(ApiTestCase):

    def test_updating_or_deleting_a_program_leaves_case_sources_intact(self):
        program = self.create_program("factorial", source=FACTORIAL)
        # The studio copies the program's source into the case when saving it.
        collection = self.add_case(self.create_collection("c"), source=program["source"])
        self.api("PUT", f"/programs/{program['id']}", {"name": "factorial", "source": "0"}, if_match=etag(1))
        self.assertEqual(self.get_record(f"/collections/{collection['id']}"), collection)
        self.api("DELETE", f"/programs/{program['id']}", if_match=etag(2))
        self.assertEqual(self.get_record(f"/collections/{collection['id']}"), collection)
        self.assertEqual(collection["cases"][0]["source"], FACTORIAL)


if __name__ == "__main__":
    unittest.main()
