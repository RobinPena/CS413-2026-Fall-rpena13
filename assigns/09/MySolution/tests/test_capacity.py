"""Capacity limits at their configured values, through HTTP (API.md section 4).

The limit itself is accepted and one more is refused with 409
capacity_limit. A refused request changes nothing, and deleting a record
frees its place. Field-size boundaries are in test_validation.py and the
body-size boundary is in test_transport.py.
"""
from __future__ import annotations

import unittest

from .http_support import ApiTestCase, etag, with_cursor
from .unit_support import FakeMonotonic


class RecordCapacityTests(ApiTestCase):

    def test_500_programs_then_capacity_limit(self):
        for n in range(500):
            self.create_program(f"p{n}", source="1")
        error = self.assertError(self.api("POST", "/programs", {"name": "one more", "source": "1"}),
                                 409, "capacity_limit", resource="programs", limit=500)
        self.assertEqual(error["message"], "The service holds at most 500 programs.")
        # Uniqueness is checked before capacity.
        self.assertError(self.api("POST", "/programs", {"name": "p0", "source": "1"}), 409, "duplicate_name")
        # Deleting one frees its place.
        first = self.api("GET", "/programs?limit=1").json["items"][0]
        self.api("DELETE", f"/programs/{first['id']}", if_match=etag(1))
        self.assertEqual(self.create_program("one more")["name"], "one more")

    def test_100_collections_then_capacity_limit(self):
        for n in range(100):
            self.create_collection(f"c{n}")
        self.assertError(self.api("POST", "/collections", {"name": "one more"}),
                         409, "capacity_limit", resource="collections", limit=100)
        page = self.api("GET", "/collections?limit=100").json
        self.assertEqual((len(page["items"]), page["next_cursor"]), (100, None))

    def test_100_cases_per_collection_then_capacity_limit(self):
        collection = self.create_collection("full")
        for n in range(100):
            collection = self.add_case(collection, name=f"case {n}", source="1")
        path = f"/collections/{collection['id']}"
        body = {"name": "one more", "source": "1", "expected": {"kind": "value", "value": "1"}}
        error = self.assertError(self.api("POST", f"{path}/cases", body, if_match=etag(101)),
                                 409, "capacity_limit", resource="cases", limit=100)
        self.assertEqual(error["message"], "A collection holds at most 100 cases.")
        self.assertUnchanged(path, collection)
        # Another collection has its own capacity; deleting a case frees a place.
        self.add_case(self.create_collection("other"), name="one more")
        self.api("DELETE", f"{path}/cases/{collection['cases'][0]['id']}", if_match=etag(101))
        collection = self.add_case(self.get_record(path), name="one more")
        self.assertEqual(len(collection["cases"]), 100)


class SnapshotCapacityTests(ApiTestCase):

    def app_options(self):
        self.clock = FakeMonotonic()
        return {"snapshot_clock": self.clock}

    def test_100_open_snapshots_then_capacity_limit_without_eviction(self):
        for name in "AB":
            self.create_program(name)
        cursors = [self.api("GET", "/programs?limit=1").json["next_cursor"] for _ in range(100)]
        self.assertEqual(len(set(cursors)), 100)
        error = self.assertError(self.api("GET", "/programs?limit=1"), 409, "capacity_limit",
                                 resource="list_snapshots", limit=100)
        self.assertIn("600 seconds", error["message"])
        # No open snapshot was evicted, and a list that fits one page needs none.
        for cursor in (cursors[0], cursors[-1]):
            self.assertEqual(self.api("GET", with_cursor("/programs", cursor)).status_code, 200)
        self.assertEqual(len(self.api("GET", "/programs?limit=2").json["items"]), 2)
        # Expired snapshots make room again.
        self.clock.now += 600
        self.assertEqual(self.api("GET", "/programs?limit=1").status_code, 200)


if __name__ == "__main__":
    unittest.main()
