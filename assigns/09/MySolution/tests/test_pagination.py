"""Lists, cursors, and snapshots through HTTP (API.md section 6)."""
from __future__ import annotations

import unittest

from .http_support import ApiTestCase, etag, with_cursor
from .unit_support import FakeMonotonic

NEVER_ISSUED = "q8ZtN3wXyR5vK1mB7cJd0A.2"


def names(response):
    return [item["name"] for item in response.json["items"]]


class PageSizeTests(ApiTestCase):

    def test_default_page_size_is_50(self):
        for n in range(51):
            self.create_program(f"p{n:02}")
        first = self.api("GET", "/programs")
        self.assertEqual(len(first.json["items"]), 50)
        second = self.api("GET", with_cursor("/programs", first.json["next_cursor"]))
        self.assertEqual((names(second), second.json["next_cursor"]), (["p50"], None))

    def test_limit_boundaries(self):
        for n in range(3):
            self.create_program(f"p{n}")
        self.assertEqual(names(self.api("GET", "/programs?limit=1")), ["p0"])
        self.assertEqual(names(self.api("GET", "/programs?limit=100")), ["p0", "p1", "p2"])
        self.assertEqual(names(self.api("GET", "/programs?limit=002")), ["p0", "p1"])
        for value in ("0", "101", "000", "99999999999999999999"):
            with self.subTest(limit=value):
                error = self.assertInvalid(self.api("GET", f"/programs?limit={value}"), "limit", "out_of_range",
                                           limit=100)
                self.assertEqual(error["message"], "limit must be a whole number from 1 to 100.")

    def test_limit_must_be_decimal_digits(self):
        for value in ("", "ten", "-1", "%2B5", "5.0", "1e2", "%205", "%C2%B2", "0x10"):
            with self.subTest(limit=value):
                self.assertInvalid(self.api("GET", f"/collections?limit={value}"), "limit", "invalid_value")

    def test_unknown_and_repeated_parameters(self):
        self.assertInvalid(self.api("GET", "/programs?page=2"), "page", "unknown_parameter")
        self.assertInvalid(self.api("GET", "/programs?limit=1&limit=2"), "limit", "repeated_parameter")
        self.assertInvalid(self.api("GET", f"/programs?cursor={NEVER_ISSUED}&cursor={NEVER_ISSUED}"),
                           "cursor", "repeated_parameter")

    def test_parameter_names_then_limit_then_cursor(self):
        self.assertInvalid(self.api("GET", "/programs?limit=0&page=2"), "page", "unknown_parameter")
        self.assertInvalid(self.api("GET", "/programs?cursor=bad&limit=0"), "limit", "out_of_range")

    def test_empty_list(self):
        response = self.api("GET", "/collections")
        self.assertEqual(response.json, {"items": [], "next_cursor": None})

    def test_head_on_a_list(self):
        self.assertEqual(self.api("HEAD", "/programs?limit=5").status_code, 200)


class SnapshotTests(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.a, self.b, self.c = (self.create_program(name, source=f"{n} + {n}")
                                  for n, name in enumerate("ABC", start=1))

    def test_order_is_creation_order_and_repeatable(self):
        self.api("PUT", f"/programs/{self.a['id']}", {"name": "A", "source": "0"}, if_match=etag(1))
        self.assertEqual(names(self.api("GET", "/programs")), ["A", "B", "C"])
        self.assertEqual(names(self.api("GET", "/programs")), ["A", "B", "C"])

    def test_single_page_has_no_cursor(self):
        response = self.api("GET", "/programs?limit=3")
        self.assertEqual((names(response), response.json["next_cursor"]), (["A", "B", "C"], None))

    def test_later_pages_come_from_the_snapshot_despite_add_update_delete(self):
        first = self.api("GET", "/programs?limit=2")
        self.assertEqual(names(first), ["A", "B"])
        cursor = first.json["next_cursor"]
        self.assertIsInstance(cursor, str)

        self.api("PUT", f"/programs/{self.c['id']}", {"name": "C", "source": "changed"}, if_match=etag(1))
        self.api("DELETE", f"/programs/{self.a['id']}", if_match=etag(1))
        self.create_program("D")

        second = self.api("GET", with_cursor("/programs", cursor, limit=2))
        self.assertEqual(second.json, {"items": [self.c], "next_cursor": None})   # C as captured, revision 1
        fresh = self.api("GET", "/programs")
        self.assertEqual(names(fresh), ["B", "C", "D"])
        self.assertEqual(fresh.json["items"][1]["revision"], 2)

    def test_a_cursor_can_be_repeated_and_limit_can_change(self):
        cursor = self.api("GET", "/programs?limit=1").json["next_cursor"]
        again = self.api("GET", with_cursor("/programs", cursor, limit=1))
        self.assertEqual(names(again), ["B"])
        self.assertEqual(self.api("GET", with_cursor("/programs", cursor, limit=1)).json, again.json)
        rest = self.api("GET", with_cursor("/programs", cursor, limit=10))
        self.assertEqual((names(rest), rest.json["next_cursor"]), (["B", "C"], None))

    def test_whole_chain_visits_every_record_once(self):
        for n in range(10):
            self.create_program(f"extra {n}")
        seen, path = [], "/programs?limit=3"
        while path:
            response = self.api("GET", path)
            seen += names(response)
            cursor = response.json["next_cursor"]
            path = with_cursor("/programs", cursor, limit=3) if cursor else None
        self.assertEqual(seen, ["A", "B", "C"] + [f"extra {n}" for n in range(10)])

    def test_collection_snapshots_keep_their_captured_cases(self):
        one = self.add_case(self.create_collection("one"), name="original")
        self.create_collection("two")
        first = self.api("GET", "/collections?limit=1")
        self.assertEqual(first.json["items"], [one])
        # Change the captured collection and delete the second one.
        self.api("DELETE", f"/collections/{one['id']}/cases/{one['cases'][0]['id']}", if_match=etag(2))
        two = self.api("GET", "/collections?limit=5").json["items"][1]
        self.api("DELETE", f"/collections/{two['id']}", if_match=etag(1))
        second = self.api("GET", with_cursor("/collections", first.json["next_cursor"]))
        self.assertEqual(second.json, {"items": [two], "next_cursor": None})
        self.assertEqual(self.get_record(f"/collections/{one['id']}")["cases"], [])

    def test_malformed_cursors(self):
        for cursor in ("", "abc", "q8ZtN3wXyR5vK1mB7cJd0A", "q8ZtN3wXyR5vK1mB7cJd0A.", ".2",
                       "q8ZtN3wXyR5vK1mB7cJd0A.0", "q8ZtN3wXyR5vK1mB7cJd0A.02", "q8ZtN3wXyR5vK1mB7cJd0!.2",
                       "q8ZtN3wXyR5vK1mB7cJd0A.2.3", "q8ZtN3wXyR5vK1mB7cJd0A.1234567"):
            with self.subTest(cursor=cursor):
                self.assertInvalid(self.api("GET", with_cursor("/programs", cursor)), "cursor", "malformed_cursor")

    def test_unknown_cursors(self):
        cursor = self.api("GET", "/programs?limit=2").json["next_cursor"]
        key = cursor.split(".")[0]
        for unknown in (NEVER_ISSUED, f"{key}.3", f"{key}.50"):
            with self.subTest(cursor=unknown):
                self.assertInvalid(self.api("GET", with_cursor("/programs", unknown)), "cursor", "unknown_cursor")
        # A programs cursor does not work on the collections list.
        self.assertInvalid(self.api("GET", with_cursor("/collections", cursor)), "cursor", "unknown_cursor")


class SnapshotLifetimeTests(ApiTestCase):

    def app_options(self):
        self.clock = FakeMonotonic()
        return {"snapshot_clock": self.clock}

    def test_cursor_expires_600_seconds_after_its_last_use(self):
        for name in "ABC":
            self.create_program(name)
        cursor = self.api("GET", "/programs?limit=1").json["next_cursor"]
        self.clock.now += 599
        self.assertEqual(names(self.api("GET", with_cursor("/programs", cursor, limit=1))), ["B"])  # renews
        self.clock.now += 599
        self.assertEqual(names(self.api("GET", with_cursor("/programs", cursor, limit=1))), ["B"])
        self.clock.now += 600
        self.assertInvalid(self.api("GET", with_cursor("/programs", cursor, limit=1)), "cursor", "unknown_cursor")


if __name__ == "__main__":
    unittest.main()
