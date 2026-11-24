"""Unit checks of the business rules (service.py with the in-memory store).

They cover the state invariants of DESIGN.md section 7: revisions, the
precondition order, uniqueness scopes, capacities, unchanged state after a
failure, the ordered case lifecycle, cascade deletion, program/case
independence, and immutable returned records.
"""
from __future__ import annotations

import dataclasses
import unittest

from MySolution.limits import Limits
from MySolution.models import ExpectedError, collection_json, program_json
from MySolution.validation import parse_if_match

from .unit_support import (
    NO_IF_MATCH, ServiceTestCase, case_input, collection_input, if_match, page, program_input,
)


class ProgramRuleTests(ServiceTestCase):

    def test_create_starts_at_revision_one(self):
        program = self.service.create_program(program_input("  fact  ", "fact(6)"))
        self.assertEqual((program.name, program.source, program.description, program.revision),
                         ("fact", "fact(6)", "", 1))
        self.assertEqual(program.created_at, program.updated_at)
        self.assertTrue(program.id.startswith("prg_"))

    def test_ids_are_unique_and_opaque(self):
        ids = {self.service.create_program(program_input(f"p{n}")).id for n in range(50)}
        self.assertEqual(len(ids), 50)

    def test_each_update_adds_exactly_one_revision(self):
        program = self.service.create_program(program_input("p"))
        for expected_revision in (2, 3, 4):
            # Identical values still count as an update.
            program = self.service.replace_program(program.id, if_match(program.revision),
                                                   program_input("p"))
            self.assertEqual(program.revision, expected_revision)
        self.assertGreater(program.updated_at, program.created_at)

    def test_update_replaces_all_fields_and_keeps_created_at(self):
        created = self.service.create_program(program_input("p", "1", description="old"))
        updated = self.service.replace_program(created.id, if_match(1), program_input("q", "2"))
        self.assertEqual((updated.id, updated.name, updated.source, updated.description),
                         (created.id, "q", "2", ""))     # omitted description resets to ""
        self.assertEqual(updated.created_at, created.created_at)

    def test_stale_revision_conflicts_and_changes_nothing(self):
        program = self.service.create_program(program_input("p"))
        current = self.service.replace_program(program.id, if_match(1), program_input("p", "2"))
        self.assertApiError("revision_conflict", self.service.replace_program,
                            program.id, if_match(1), program_input("p", "3"), current_revision=2)
        self.assertApiError("revision_conflict", self.service.delete_program,
                            program.id, if_match(3), current_revision=2)
        self.assertIs(self.service.get_program(program.id), current)

    def test_precondition_order_on_existing_record(self):
        program = self.service.create_program(program_input("p"))
        self.assertApiError("precondition_required", self.service.replace_program,
                            program.id, NO_IF_MATCH, program_input("p"))
        self.assertApiError("invalid_request", self.service.delete_program,
                            program.id, parse_if_match("*"), reason="malformed_if_match", field="If-Match")
        self.assertEqual(self.service.get_program(program.id).revision, 1)

    def test_missing_record_wins_over_any_precondition(self):
        for header in (None, '"7"', '"1"', "*"):
            self.assertApiError("record_not_found", self.service.replace_program,
                                "prg_missing", parse_if_match(header), program_input("p"))
            self.assertApiError("record_not_found", self.service.delete_program,
                                "prg_missing", parse_if_match(header))
        self.assertApiError("record_not_found", self.service.get_program, "prg_missing")

    def test_delete_checks_revision_and_removes(self):
        program = self.service.create_program(program_input("p"))
        self.assertIsNone(self.service.delete_program(program.id, if_match(1)))
        self.assertApiError("record_not_found", self.service.get_program, program.id)
        self.assertEqual(self.store.program_count(), 0)


class UniquenessTests(ServiceTestCase):

    def test_program_names_are_unique_after_trimming(self):
        self.service.create_program(program_input("fact"))
        self.assertApiError("duplicate_name", self.service.create_program, program_input(" fact\t"),
                            field="name")
        self.assertEqual(self.store.program_count(), 1)

    def test_names_are_not_case_folded(self):
        self.service.create_program(program_input("fact"))
        self.service.create_program(program_input("Fact"))
        self.assertEqual(self.store.program_count(), 2)

    def test_scopes_are_separate(self):
        self.service.create_program(program_input("shared"))
        first = self.service.create_collection(collection_input("shared"))
        second = self.service.create_collection(collection_input("other"))
        self.service.add_case(first.id, if_match(1), case_input("shared"))
        self.service.add_case(second.id, if_match(1), case_input("shared"))
        self.assertApiError("duplicate_name", self.service.add_case,
                            first.id, if_match(2), case_input("shared "))
        self.assertApiError("duplicate_name", self.service.create_collection, collection_input("shared"))

    def test_rename_to_own_name_is_allowed_but_not_to_anothers(self):
        a = self.service.create_program(program_input("a"))
        b = self.service.create_program(program_input("b"))
        self.service.replace_program(a.id, if_match(1), program_input("a", "new source"))
        self.assertApiError("duplicate_name", self.service.replace_program,
                            b.id, if_match(1), program_input("a"))
        self.assertEqual(self.service.get_program(b.id).name, "b")
        self.assertEqual(self.service.get_program(b.id).revision, 1)

    def test_case_rename_rules(self):
        collection = self.service.create_collection(collection_input("c"))
        collection = self.service.add_case(collection.id, if_match(1), case_input("one"))
        collection = self.service.add_case(collection.id, if_match(2), case_input("two"))
        one, two = collection.cases
        collection = self.service.replace_case(collection.id, one.id, if_match(3), case_input("one", "2"))
        self.assertApiError("duplicate_name", self.service.replace_case,
                            collection.id, two.id, if_match(4), case_input("one"))
        self.assertEqual(self.service.get_collection(collection.id).revision, 4)

    def test_revision_is_checked_before_uniqueness(self):
        self.service.create_program(program_input("a"))
        b = self.service.create_program(program_input("b"))
        self.assertApiError("revision_conflict", self.service.replace_program,
                            b.id, if_match(9), program_input("a"))


class CapacityTests(ServiceTestCase):

    limits = Limits(max_programs=2, max_collections=1, max_cases_per_collection=2)

    def test_program_capacity_frees_on_delete(self):
        first = self.service.create_program(program_input("1"))
        self.service.create_program(program_input("2"))
        self.assertApiError("capacity_limit", self.service.create_program, program_input("3"),
                            resource="programs", limit=2)
        self.assertEqual(self.store.program_count(), 2)
        self.service.delete_program(first.id, if_match(1))
        self.service.create_program(program_input("3"))

    def test_duplicate_is_reported_before_capacity(self):
        self.service.create_program(program_input("1"))
        self.service.create_program(program_input("2"))
        self.assertApiError("duplicate_name", self.service.create_program, program_input("1"))

    def test_collection_capacity(self):
        self.service.create_collection(collection_input("c"))
        self.assertApiError("capacity_limit", self.service.create_collection, collection_input("d"),
                            resource="collections", limit=1)

    def test_case_capacity_leaves_collection_unchanged(self):
        collection = self.service.create_collection(collection_input("c"))
        self.service.add_case(collection.id, if_match(1), case_input("a"))
        full = self.service.add_case(collection.id, if_match(2), case_input("b"))
        self.assertApiError("capacity_limit", self.service.add_case,
                            collection.id, if_match(3), case_input("c"), resource="cases", limit=2)
        self.assertIs(self.service.get_collection(collection.id), full)


class CaseLifecycleTests(ServiceTestCase):

    def setUp(self):
        super().setUp()
        collection = self.service.create_collection(collection_input("smoke", description="d"))
        for revision, name in enumerate(("first", "second", "third"), start=1):
            collection = self.service.add_case(collection.id, if_match(revision), case_input(name))
        self.collection = collection

    def names(self, collection):
        return [case.name for case in collection.cases]

    def test_add_appends_in_order_and_counts_revisions(self):
        self.assertEqual(self.names(self.collection), ["first", "second", "third"])
        self.assertEqual(self.collection.revision, 4)
        self.assertEqual(len({case.id for case in self.collection.cases}), 3)
        self.assertTrue(all(case.id.startswith("case_") for case in self.collection.cases))

    def test_replace_keeps_id_and_position(self):
        middle = self.collection.cases[1]
        updated = self.service.replace_case(
            self.collection.id, middle.id, if_match(4),
            case_input("renamed", "if then", {"kind": "error", "category": "syntax"}))
        self.assertEqual(self.names(updated), ["first", "renamed", "third"])
        self.assertEqual(updated.cases[1].id, middle.id)
        self.assertEqual(updated.cases[1].expected, ExpectedError("syntax"))
        self.assertEqual(updated.cases[1].description, "")
        self.assertEqual(updated.revision, 5)
        self.assertEqual(updated.cases[0], self.collection.cases[0])

    def test_delete_keeps_remaining_order(self):
        first = self.collection.cases[0]
        updated = self.service.delete_case(self.collection.id, first.id, if_match(4))
        self.assertEqual(self.names(updated), ["second", "third"])
        self.assertEqual(updated.revision, 5)
        self.assertApiError("record_not_found", self.service.replace_case,
                            self.collection.id, first.id, if_match(5), case_input("x"))

    def test_metadata_update_leaves_cases_untouched(self):
        updated = self.service.replace_collection(self.collection.id, if_match(4),
                                                  collection_input("renamed"))
        self.assertEqual((updated.name, updated.description, updated.revision), ("renamed", "", 5))
        self.assertIs(updated.cases, self.collection.cases)

    def test_case_routes_check_collection_then_case_then_precondition(self):
        case_id = self.collection.cases[0].id
        self.assertApiError("record_not_found", self.service.delete_case, "col_missing", case_id, NO_IF_MATCH)
        self.assertApiError("record_not_found", self.service.delete_case,
                            self.collection.id, "case_missing", NO_IF_MATCH)
        self.assertApiError("record_not_found", self.service.replace_case,
                            self.collection.id, "case_missing", if_match(1), case_input("x"))
        self.assertApiError("precondition_required", self.service.add_case,
                            self.collection.id, NO_IF_MATCH, case_input("x"))
        self.assertApiError("revision_conflict", self.service.delete_case,
                            self.collection.id, case_id, if_match(3), current_revision=4)
        self.assertIs(self.service.get_collection(self.collection.id), self.collection)

    def test_deleting_a_collection_removes_its_cases(self):
        case_id = self.collection.cases[0].id
        self.service.delete_collection(self.collection.id, if_match(4))
        self.assertApiError("record_not_found", self.service.get_collection, self.collection.id)
        self.assertApiError("record_not_found", self.service.replace_case,
                            self.collection.id, case_id, if_match(4), case_input("x"))
        self.assertApiError("record_not_found", self.service.add_case,
                            self.collection.id, if_match(4), case_input("x"))
        self.assertEqual(self.store.all_collections(), ())

    def test_a_new_collection_with_the_old_name_starts_empty(self):
        self.service.delete_collection(self.collection.id, if_match(4))
        fresh = self.service.create_collection(collection_input("smoke"))
        self.assertEqual((fresh.cases, fresh.revision), ((), 1))


class IndependenceTests(ServiceTestCase):

    def test_program_changes_never_reach_case_snapshots(self):
        program = self.service.create_program(program_input("fact", "fact(6)"))
        collection = self.service.create_collection(collection_input("c"))
        collection = self.service.add_case(collection.id, if_match(1), case_input("t", program.source))
        self.service.replace_program(program.id, if_match(1), program_input("fact", "fact(7)"))
        self.service.delete_program(program.id, if_match(2))
        stored = self.service.get_collection(collection.id)
        self.assertEqual(stored.cases[0].source, "fact(6)")
        self.assertEqual(stored.revision, 2)


class ImmutabilityTests(ServiceTestCase):

    def test_records_cannot_be_changed_in_place(self):
        program = self.service.create_program(program_input("p"))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            program.name = "changed"
        collection = self.service.add_case(
            self.service.create_collection(collection_input("c")).id, if_match(1), case_input("a"))
        self.assertIsInstance(collection.cases, tuple)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            collection.cases[0].source = "changed"

    def test_json_representations_are_detached(self):
        program = self.service.create_program(program_input("p"))
        body = program_json(program)
        body["name"] = "changed"
        self.assertEqual(self.service.get_program(program.id).name, "p")
        collection = self.service.add_case(
            self.service.create_collection(collection_input("c")).id, if_match(1), case_input("a"))
        body = collection_json(collection)
        body["cases"][0]["expected"]["value"] = "changed"
        body["cases"].clear()
        stored = self.service.get_collection(collection.id)
        self.assertEqual(stored.cases[0].expected.value, "42")

    def test_returned_list_items_are_the_immutable_records(self):
        self.service.create_program(program_input("p"))
        items = self.service.list_programs(page(10)).items
        self.assertIsInstance(items, tuple)
        self.assertEqual(program_json(items[0])["name"], "p")


if __name__ == "__main__":
    unittest.main()
