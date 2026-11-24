"""Unit checks of request validation (validation.py, API.md sections 4-6).

The HTTP suite covers the same rules end to end; these pin down check order,
trimming, and the exact limit boundaries without a server.
"""
from __future__ import annotations

import unittest

from MySolution.errors import ApiError
from MySolution.limits import Limits
from MySolution.models import ExpectedError, ExpectedValue
from MySolution.validation import (
    case_fields, collection_fields, no_query_parameters, page_request, parse_if_match,
    program_fields,
)

LIMITS = Limits()


class ValidationTestCase(unittest.TestCase):

    def assertInvalid(self, call, field, reason, **extra):
        with self.assertRaises(ApiError) as caught:
            call()
        error = caught.exception
        self.assertEqual(error.code, "invalid_request")
        self.assertEqual((error.details["field"], error.details["reason"]), (field, reason),
                         error.to_json())
        for key, value in extra.items():
            self.assertEqual(error.details[key], value)


class ProgramBodyTests(ValidationTestCase):

    def test_name_is_trimmed_source_and_description_are_not(self):
        fields = program_fields({"name": "\t fact \n", "source": "  1 + 2\n", "description": " d "}, LIMITS)
        self.assertEqual((fields.name, fields.source, fields.description), ("fact", "  1 + 2\n", " d "))

    def test_description_defaults_to_empty(self):
        self.assertEqual(program_fields({"name": "a", "source": "1"}, LIMITS).description, "")

    def test_body_must_be_an_object(self):
        for body in ([], "x", 3, None):
            self.assertInvalid(lambda: program_fields(body, LIMITS), None, "not_object")

    def test_member_names_are_checked_in_body_order_before_values(self):
        self.assertInvalid(lambda: program_fields({"name": 5, "revision": 1, "x": 1}, LIMITS),
                           "revision", "server_managed_field")
        self.assertInvalid(lambda: program_fields({"x": 1, "revision": 1}, LIMITS), "x", "unknown_field")
        self.assertInvalid(lambda: program_fields({"name": "a", "source": "1", "cases": []}, LIMITS),
                           "cases", "unknown_field")   # cases are not a program field at all

    def test_every_server_managed_field_is_named(self):
        for key in ("id", "created_at", "updated_at", "revision"):
            self.assertInvalid(lambda: program_fields({"name": "a", "source": "1", key: 1}, LIMITS),
                               key, "server_managed_field")

    def test_fields_are_checked_name_then_source(self):
        self.assertInvalid(lambda: program_fields({"source": 1}, LIMITS), "name", "missing")
        self.assertInvalid(lambda: program_fields({"name": "a", "source": 1}, LIMITS), "source", "wrong_type")
        self.assertInvalid(lambda: program_fields({"name": "a"}, LIMITS), "source", "missing")

    def test_wrong_types_including_null(self):
        self.assertInvalid(lambda: program_fields({"name": None, "source": "1"}, LIMITS), "name", "wrong_type")
        self.assertInvalid(lambda: program_fields({"name": "a", "source": "1", "description": None}, LIMITS),
                           "description", "wrong_type")
        self.assertInvalid(lambda: program_fields({"name": ["a"], "source": "1"}, LIMITS), "name", "wrong_type")

    def test_blank_name_and_blank_source(self):
        self.assertInvalid(lambda: program_fields({"name": " \t\n", "source": "1"}, LIMITS), "name", "blank")
        self.assertInvalid(lambda: program_fields({"name": "", "source": "1"}, LIMITS), "name", "blank")
        self.assertInvalid(lambda: program_fields({"name": "a", "source": ""}, LIMITS), "source", "blank")
        self.assertInvalid(lambda: program_fields({"name": "a", "source": " \n "}, LIMITS), "source", "blank")

    def test_unpaired_surrogate_is_invalid_text(self):
        self.assertInvalid(lambda: program_fields({"name": "a\ud800", "source": "1"}, LIMITS),
                           "name", "invalid_text")
        self.assertInvalid(lambda: program_fields({"name": "a", "source": "\udfff"}, LIMITS),
                           "source", "invalid_text")

    def test_name_limit_counts_characters_after_trimming(self):
        name = "n" * LIMITS.max_name_chars
        self.assertEqual(program_fields({"name": f"  {name}  ", "source": "1"}, LIMITS).name, name)
        self.assertInvalid(lambda: program_fields({"name": name + "n", "source": "1"}, LIMITS),
                           "name", "too_long", limit=100)

    def test_source_limit_counts_utf8_bytes(self):
        at_limit = "é" * (LIMITS.max_source_bytes // 2)              # 2 bytes each
        self.assertEqual(len(program_fields({"name": "a", "source": at_limit}, LIMITS).source),
                         LIMITS.max_source_bytes // 2)
        self.assertInvalid(lambda: program_fields({"name": "a", "source": at_limit + "x"}, LIMITS),
                           "source", "too_large", limit=65_536)

    def test_description_limit_counts_characters(self):
        at_limit = "é" * LIMITS.max_description_chars
        self.assertEqual(program_fields({"name": "a", "source": "1", "description": at_limit},
                                        LIMITS).description, at_limit)
        self.assertInvalid(lambda: program_fields({"name": "a", "source": "1", "description": at_limit + "é"},
                                                  LIMITS), "description", "too_long", limit=1000)


class CollectionBodyTests(ValidationTestCase):

    def test_accepts_name_and_description_only(self):
        fields = collection_fields({"name": " smoke ", "description": "d"}, LIMITS)
        self.assertEqual((fields.name, fields.description), ("smoke", "d"))
        self.assertInvalid(lambda: collection_fields({"name": "a", "cases": []}, LIMITS),
                           "cases", "server_managed_field")
        self.assertInvalid(lambda: collection_fields({"name": "a", "source": "1"}, LIMITS),
                           "source", "unknown_field")


class CaseBodyTests(ValidationTestCase):

    def case(self, expected, **extra):
        return case_fields({"name": "c", "source": "1", "expected": expected, **extra}, LIMITS)

    def test_the_three_expected_shapes(self):
        self.assertEqual(self.case({"kind": "value", "value": "720"}).expected, ExpectedValue("720"))
        self.assertEqual(self.case({"kind": "value", "value": ""}).expected, ExpectedValue(""))
        self.assertEqual(self.case({"kind": "error", "category": "syntax"}).expected, ExpectedError("syntax"))
        self.assertEqual(self.case({"category": "type", "kind": "error"}).expected, ExpectedError("type"))

    def test_expected_value_is_stored_exactly(self):
        self.assertEqual(self.case({"kind": "value", "value": " 720 "}).expected.value, " 720 ")

    def test_expected_is_required_and_an_object(self):
        self.assertInvalid(lambda: case_fields({"name": "c", "source": "1"}, LIMITS), "expected", "missing")
        self.assertInvalid(lambda: self.case("720"), "expected", "wrong_type")
        self.assertInvalid(lambda: self.case(None), "expected", "wrong_type")

    def test_kind_is_checked_first(self):
        self.assertInvalid(lambda: self.case({"value": "1"}), "expected.kind", "missing")
        self.assertInvalid(lambda: self.case({"kind": 1}), "expected.kind", "wrong_type")
        self.assertInvalid(lambda: self.case({"kind": "Value", "value": "1"}), "expected.kind", "invalid_value")

    def test_mixed_and_extra_members_are_rejected(self):
        self.assertInvalid(lambda: self.case({"kind": "error", "category": "type", "value": "1"}),
                           "expected.value", "unknown_field")
        self.assertInvalid(lambda: self.case({"kind": "value", "value": "1", "category": "type"}),
                           "expected.category", "unknown_field")
        self.assertInvalid(lambda: self.case({"kind": "value", "value": "1", "note": "x"}),
                           "expected.note", "unknown_field")

    def test_variant_fields(self):
        self.assertInvalid(lambda: self.case({"kind": "value"}), "expected.value", "missing")
        self.assertInvalid(lambda: self.case({"kind": "value", "value": 720}), "expected.value", "wrong_type")
        self.assertInvalid(lambda: self.case({"kind": "error"}), "expected.category", "missing")
        self.assertInvalid(lambda: self.case({"kind": "error", "category": "runtime"}),
                           "expected.category", "invalid_value")
        self.assertInvalid(lambda: self.case({"kind": "error", "category": "Syntax"}),
                           "expected.category", "invalid_value")

    def test_expected_value_byte_limit(self):
        at_limit = "v" * LIMITS.max_expected_value_bytes
        self.assertEqual(self.case({"kind": "value", "value": at_limit}).expected.value, at_limit)
        self.assertInvalid(lambda: self.case({"kind": "value", "value": at_limit + "v"}),
                           "expected.value", "too_large", limit=8192)

    def test_id_is_server_managed_for_cases(self):
        self.assertInvalid(lambda: self.case({"kind": "value", "value": "1"}, id="case_x"),
                           "id", "server_managed_field")

    def test_field_order_name_source_expected_description(self):
        self.assertInvalid(lambda: case_fields({"name": "c", "source": "", "expected": 1}, LIMITS),
                           "source", "blank")
        self.assertInvalid(lambda: case_fields({"name": "c", "source": "1", "expected": 1, "description": 1},
                                               LIMITS), "expected", "wrong_type")


class QueryParameterTests(ValidationTestCase):

    def test_defaults(self):
        request = page_request({}, LIMITS)
        self.assertEqual((request.limit, request.cursor), (50, None))

    def test_limit_boundaries(self):
        self.assertEqual(page_request({"limit": ["1"]}, LIMITS).limit, 1)
        self.assertEqual(page_request({"limit": ["100"]}, LIMITS).limit, 100)
        self.assertEqual(page_request({"limit": ["050"]}, LIMITS).limit, 50)
        for text in ("0", "101", "000", "99999999999999999999999"):
            self.assertInvalid(lambda: page_request({"limit": [text]}, LIMITS), "limit", "out_of_range",
                               limit=100)

    def test_limit_must_be_ascii_digits(self):
        for text in ("", "-1", "+5", "5.0", "ten", " 5", "²", "٥"):
            self.assertInvalid(lambda: page_request({"limit": [text]}, LIMITS), "limit", "invalid_value")

    def test_unknown_and_repeated_parameters(self):
        self.assertInvalid(lambda: page_request({"page": ["2"]}, LIMITS), "page", "unknown_parameter")
        self.assertInvalid(lambda: page_request({"limit": ["1", "2"]}, LIMITS), "limit", "repeated_parameter")
        self.assertInvalid(lambda: no_query_parameters({"limit": ["5"]}), "limit", "unknown_parameter")
        no_query_parameters({})

    def test_cursor_is_passed_through_unparsed(self):
        self.assertEqual(page_request({"cursor": ["anything"]}, LIMITS).cursor, "anything")


class IfMatchTests(unittest.TestCase):

    def test_well_formed(self):
        self.assertEqual(parse_if_match('"3"').revision, 3)
        self.assertEqual(parse_if_match('  "12" ').revision, 12)
        self.assertEqual(parse_if_match('"' + "9" * 18 + '"').revision, int("9" * 18))

    def test_missing(self):
        self.assertFalse(parse_if_match(None).present)

    def test_malformed_values_are_present_without_a_revision(self):
        for header in ("3", 'W/"3"', "*", '"3", "4"', "", '""', '"0"', '"03"', '"-1"', "'3'",
                       '"' + "9" * 19 + '"'):
            parsed = parse_if_match(header)
            self.assertTrue(parsed.present, header)
            self.assertIsNone(parsed.revision, header)


if __name__ == "__main__":
    unittest.main()
