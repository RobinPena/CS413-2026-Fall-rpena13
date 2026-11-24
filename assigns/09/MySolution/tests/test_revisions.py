"""Revisions, ETags, and If-Match through HTTP (API.md sections 5 and 9).

Every update and delete route is checked for: 428 without If-Match, 400 for a
malformed If-Match, 409 with current_revision for a stale one, 404 for a
missing record whatever If-Match says, and no change after any failure.
"""
from __future__ import annotations

import unittest

from .http_support import ApiTestCase, etag

MALFORMED_IF_MATCH = ['1', 'W/"1"', '*', '"1", "2"', '"1","1"', '""', '"01"', '"0"', '"-1"', "'1'",
                      '"1', '"1.0"', '"' + "9" * 19 + '"']
CASE_BODY = {"name": "k", "source": "1", "expected": {"kind": "value", "value": "1"}}


class RevisionTests(ApiTestCase):

    def test_program_revisions_increase_by_exactly_one(self):
        program = self.create_program("p")
        path = f"/programs/{program['id']}"
        self.assertEqual(program["revision"], 1)
        for revision in (2, 3, 4):
            # Even an update that changes nothing is a new revision.
            response = self.api("PUT", path, {"name": "p", "source": program["source"]},
                                if_match=etag(revision - 1))
            self.assertEqual((response.json["program"]["revision"], response.headers["ETag"]),
                             (revision, etag(revision)))
        self.assertEqual(self.api("GET", path).headers["ETag"], etag(4))

    def test_collection_revision_counts_metadata_and_case_changes(self):
        collection = self.create_collection("c")
        path = f"/collections/{collection['id']}"
        steps = [
            ("POST", f"{path}/cases", CASE_BODY),
            ("PUT", path, {"name": "renamed"}),
        ]
        responses = [self.api(method, url, body, if_match=etag(n + 1)) for n, (method, url, body) in enumerate(steps)]
        case_id = responses[0].json["collection"]["cases"][0]["id"]
        responses.append(self.api("PUT", f"{path}/cases/{case_id}", {**CASE_BODY, "name": "k2"}, if_match=etag(3)))
        responses.append(self.api("DELETE", f"{path}/cases/{case_id}", if_match=etag(4)))
        self.assertEqual([r.headers["ETag"] for r in responses], [etag(2), etag(3), etag(4), etag(5)])
        self.assertEqual([r.json["collection"]["revision"] for r in responses], [2, 3, 4, 5])

    def test_if_match_is_ignored_on_create(self):
        response = self.api("POST", "/programs", {"name": "p", "source": "1"}, if_match='"99"')
        self.assertEqual(response.json["program"]["revision"], 1)

    def test_spaces_around_if_match_are_ignored(self):
        program = self.create_program("p")
        response = self.api("PUT", f"/programs/{program['id']}", {"name": "p", "source": "2"}, if_match='  "1"  ')
        self.assertEqual(response.status_code, 200)

    def test_program_delete_checks_the_revision(self):
        program = self.create_program("p")
        path = f"/programs/{program['id']}"
        self.api("PUT", path, {"name": "p", "source": "2"}, if_match=etag(1))
        self.assertError(self.api("DELETE", path, if_match=etag(1)), 409, "revision_conflict",
                         current_revision=2)
        self.assertEqual(self.get_record(path)["revision"], 2)
        response = self.api("DELETE", path, if_match=etag(2))
        self.assertEqual(response.status_code, 204)       # no new revision, so no ETag


class PreconditionTests(ApiTestCase):
    """The same precondition rules on all seven mutation routes."""

    def setUp(self):
        super().setUp()
        self.program = self.create_program("p")
        self.collection = self.add_case(self.create_collection("c"), name="k1")
        case_id = self.collection["cases"][0]["id"]
        program_path = f"/programs/{self.program['id']}"
        collection_path = f"/collections/{self.collection['id']}"
        self.case_path = f"{collection_path}/cases/{case_id}"
        # (method, path, body, path of the record whose revision applies, its revision)
        self.mutations = [
            ("PUT", program_path, {"name": "p", "source": "2"}, program_path, 1),
            ("DELETE", program_path, None, program_path, 1),
            ("PUT", collection_path, {"name": "c2"}, collection_path, 2),
            ("DELETE", collection_path, None, collection_path, 2),
            ("POST", f"{collection_path}/cases", {**CASE_BODY, "name": "k2"}, collection_path, 2),
            ("PUT", self.case_path, {**CASE_BODY, "name": "k1"}, collection_path, 2),
            ("DELETE", self.case_path, None, collection_path, 2),
        ]

    def send(self, method, path, body, **headers):
        return self.api(method, path, body, **headers) if body is not None else self.api(method, path, **headers)

    def snapshot(self):
        return self.get_record(f"/programs/{self.program['id']}"), \
            self.get_record(f"/collections/{self.collection['id']}")

    def test_missing_if_match_is_428(self):
        before = self.snapshot()
        for method, path, body, _, _ in self.mutations:
            with self.subTest(method=method, path=path):
                error = self.assertError(self.send(method, path, body), 428, "precondition_required")
                self.assertNotIn("current_revision", error)
        self.assertEqual(self.snapshot(), before)

    def test_malformed_if_match_is_400(self):
        before = self.snapshot()
        for method, path, body, _, _ in self.mutations:
            for value in MALFORMED_IF_MATCH:
                with self.subTest(method=method, path=path, if_match=value):
                    self.assertInvalid(self.send(method, path, body, if_match=value),
                                       "If-Match", "malformed_if_match")
        self.assertEqual(self.snapshot(), before)

    def test_stale_if_match_is_409_with_the_current_revision(self):
        before = self.snapshot()
        for method, path, body, _, revision in self.mutations:
            for stale in (revision - 1 or 99, revision + 1):
                with self.subTest(method=method, path=path, if_match=stale):
                    error = self.assertError(self.send(method, path, body, if_match=etag(stale)),
                                             409, "revision_conflict", current_revision=revision)
                    self.assertIn(f'If-Match "{stale}" is stale', error["message"])
        self.assertEqual(self.snapshot(), before)

    def test_current_if_match_succeeds_on_every_route(self):
        # Case routes first, then each record's update before its delete.
        for index in (5, 4, 6, 2, 3, 0, 1):
            method, path, body, record_path, _ = self.mutations[index]
            with self.subTest(method=method, path=path):
                revision = self.get_record(record_path)["revision"]
                response = self.send(method, path, body, if_match=etag(revision))
                self.assertIn(response.status_code, (200, 201, 204), response.json)

    def test_missing_record_wins_over_any_if_match(self):
        missing = [
            ("PUT", "/programs/missing", {"name": "p", "source": "2"}),
            ("DELETE", "/programs/missing", None),
            ("PUT", "/collections/missing", {"name": "c2"}),
            ("DELETE", "/collections/missing", None),
            ("POST", "/collections/missing/cases", CASE_BODY),
            ("PUT", "/collections/missing/cases/missing", CASE_BODY),
            ("DELETE", "/collections/missing/cases/missing", None),
            # The collection exists, but the case does not.
            ("PUT", f"/collections/{self.collection['id']}/cases/missing", CASE_BODY),
            ("DELETE", f"/collections/{self.collection['id']}/cases/missing", None),
        ]
        for method, path, body in missing:
            for headers in ({}, {"if_match": etag(99)}, {"if_match": "*"}, {"if_match": etag(2)}):
                with self.subTest(method=method, path=path, **headers):
                    self.assertError(self.send(method, path, body, **headers), 404, "record_not_found")

    def test_revision_is_checked_before_the_name(self):
        other = self.create_program("other")
        self.assertError(self.api("PUT", f"/programs/{other['id']}", {"name": "p", "source": "1"},
                                  if_match=etag(5)), 409, "revision_conflict")
        self.assertError(self.api("PUT", f"/programs/{other['id']}", {"name": "p", "source": "1"},
                                  if_match=etag(1)), 409, "duplicate_name")


if __name__ == "__main__":
    unittest.main()
