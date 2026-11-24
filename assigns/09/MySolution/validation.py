"""Request validation (API.md sections 4-6): decoded JSON bodies, query
parameters, and the If-Match header become checked input values.

Each public function either returns a checked value or raises ApiError
(400 invalid_request) for the first failure, in the documented order. Nothing
here touches the store, so a failed validation can never change state.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .errors import invalid_request
from .limits import Limits
from .models import Expected, ExpectedError, ExpectedValue

# Fields that appear in a record's representation but only the service sets.
PROGRAM_MANAGED = ("id", "created_at", "updated_at", "revision")
COLLECTION_MANAGED = ("id", "created_at", "updated_at", "revision", "cases")
CASE_MANAGED = ("id",)

EXPECTED_KINDS = ("value", "error")
ERROR_CATEGORIES = ("syntax", "type")

# One strong entity tag in the service's form: a quoted positive decimal.
# 18 digits is far beyond any reachable revision and keeps int() cheap.
_ETAG = re.compile(r'"([1-9][0-9]{0,17})"')
_DIGITS = re.compile(r"[0-9]+")


@dataclass(frozen=True)
class ProgramFields:
    name: str
    source: str
    description: str


@dataclass(frozen=True)
class CollectionFields:
    name: str
    description: str


@dataclass(frozen=True)
class CaseFields:
    name: str
    source: str
    expected: Expected
    description: str


@dataclass(frozen=True)
class PageRequest:
    limit: int
    cursor: str | None


@dataclass(frozen=True)
class IfMatch:
    """The If-Match header as sent. revision is None when present but malformed.

    The header is only parsed here. Whether it is required, and whether it is
    current, is decided later under the store lock, because a missing record
    must win over a missing or stale precondition (API.md section 5).
    """
    present: bool
    revision: int | None


# ---------------------------------------------------------------- bodies

def program_fields(body: object, limits: Limits) -> ProgramFields:
    members = _require_object(body)
    _check_member_names(members, ("name", "source", "description"), PROGRAM_MANAGED)
    name = _name(members, limits)
    source = _source(members, limits)
    description = _description(members, limits)
    return ProgramFields(name, source, description)


def collection_fields(body: object, limits: Limits) -> CollectionFields:
    members = _require_object(body)
    _check_member_names(members, ("name", "description"), COLLECTION_MANAGED)
    name = _name(members, limits)
    description = _description(members, limits)
    return CollectionFields(name, description)


def case_fields(body: object, limits: Limits) -> CaseFields:
    members = _require_object(body)
    _check_member_names(members, ("name", "source", "expected", "description"), CASE_MANAGED)
    name = _name(members, limits)
    source = _source(members, limits)
    expected = _expected(members, limits)
    description = _description(members, limits)
    return CaseFields(name, source, expected, description)


def _require_object(body: object) -> dict:
    if not isinstance(body, dict):
        raise invalid_request(None, "not_object", "The request body must be a JSON object.")
    return body


def _check_member_names(members: dict, accepted: Sequence[str], managed: Sequence[str]) -> None:
    """Reject the first member, in body order, that this body does not accept."""
    for key in members:
        if key in accepted:
            continue
        if key in managed:
            raise invalid_request(key, "server_managed_field",
                                  f"Field {key!r} is set by the service and cannot be sent.")
        raise invalid_request(key, "unknown_field", f"Field {key!r} is not accepted.")


def _required_string(members: dict, key: str, field: str) -> str:
    """members[key] as a string that can be encoded as UTF-8."""
    if key not in members:
        raise invalid_request(field, "missing", f"Field {field!r} is required.")
    return _string(members[key], field)


def _string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise invalid_request(field, "wrong_type", f"Field {field!r} must be a string.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:  # an unpaired surrogate such as "\ud800"
        raise invalid_request(field, "invalid_text",
                              f"Field {field!r} contains text that cannot be encoded as UTF-8.") from None
    return value


def _utf8_size(text: str) -> int:
    return len(text.encode("utf-8"))


def _name(members: dict, limits: Limits) -> str:
    """The trimmed name: nonblank and at most max_name_chars characters."""
    name = _required_string(members, "name", "name").strip()
    if not name:
        raise invalid_request("name", "blank", "name must contain a non-whitespace character.")
    if len(name) > limits.max_name_chars:
        raise invalid_request("name", "too_long",
                              f"name is {len(name)} characters after trimming; "
                              f"the limit is {limits.max_name_chars}.",
                              limit=limits.max_name_chars)
    return name


def _source(members: dict, limits: Limits) -> str:
    """The source exactly as sent: never trimmed, within the byte limit, not blank."""
    source = _required_string(members, "source", "source")
    size = _utf8_size(source)
    if size > limits.max_source_bytes:
        raise invalid_request("source", "too_large",
                              f"source is {size} UTF-8 bytes; the limit is {limits.max_source_bytes}.",
                              limit=limits.max_source_bytes)
    if not source.strip():
        raise invalid_request("source", "blank", "source must contain a non-whitespace character.")
    return source


def _description(members: dict, limits: Limits) -> str:
    """The optional description, untrimmed; "" when omitted."""
    if "description" not in members:
        return ""
    description = _string(members["description"], "description")
    if len(description) > limits.max_description_chars:
        raise invalid_request("description", "too_long",
                              f"description is {len(description)} characters; "
                              f"the limit is {limits.max_description_chars}.",
                              limit=limits.max_description_chars)
    return description


def _expected(members: dict, limits: Limits) -> Expected:
    """One of the three tagged shapes, with no other members (API.md section 2)."""
    if "expected" not in members:
        raise invalid_request("expected", "missing", "Field 'expected' is required.")
    expected = members["expected"]
    if not isinstance(expected, dict):
        raise invalid_request("expected", "wrong_type", "Field 'expected' must be an object.")

    kind = _required_string(expected, "kind", "expected.kind")
    if kind not in EXPECTED_KINDS:
        raise invalid_request("expected.kind", "invalid_value",
                              "expected.kind must be \"value\" or \"error\".")

    if kind == "value":
        _check_shape_members(expected, ("kind", "value"), "an expected value")
        value = _required_string(expected, "value", "expected.value")
        size = _utf8_size(value)
        if size > limits.max_expected_value_bytes:
            raise invalid_request("expected.value", "too_large",
                                  f"expected.value is {size} UTF-8 bytes; "
                                  f"the limit is {limits.max_expected_value_bytes}.",
                                  limit=limits.max_expected_value_bytes)
        return ExpectedValue(value)

    _check_shape_members(expected, ("kind", "category"), "an expected error")
    category = _required_string(expected, "category", "expected.category")
    if category not in ERROR_CATEGORIES:
        raise invalid_request("expected.category", "invalid_value",
                              "expected.category must be \"syntax\" or \"type\".")
    return ExpectedError(category)


def _check_shape_members(expected: dict, accepted: Sequence[str], shape: str) -> None:
    for key in expected:
        if key not in accepted:
            raise invalid_request(f"expected.{key}", "unknown_field",
                                  f"Field 'expected.{key}' is not accepted for {shape}.")


# ------------------------------------------------------- query parameters

def no_query_parameters(args: Mapping[str, Sequence[str]]) -> None:
    """Routes other than the lists define no query parameters."""
    _query_parameters(args, ())


def page_request(args: Mapping[str, Sequence[str]], limits: Limits) -> PageRequest:
    """limit and cursor for a list route, checked in that order (API.md section 6).

    The cursor's own form is checked by the snapshot registry, which owns it.
    """
    params = _query_parameters(args, ("limit", "cursor"))
    limit = limits.default_page_size
    if "limit" in params:
        limit = _page_size(params["limit"], limits)
    return PageRequest(limit=limit, cursor=params.get("cursor"))


def _query_parameters(args: Mapping[str, Sequence[str]], allowed: Sequence[str]) -> dict[str, str]:
    """args maps each parameter name to all of its values, in request order."""
    params = {}
    for name, values in args.items():
        if name not in allowed:
            raise invalid_request(name, "unknown_parameter",
                                  f"Query parameter {name!r} is not accepted on this route.")
        if len(values) != 1:
            raise invalid_request(name, "repeated_parameter",
                                  f"Query parameter {name!r} may be given only once.")
        params[name] = values[0]
    return params


def _page_size(text: str, limits: Limits) -> int:
    message = f"limit must be a whole number from 1 to {limits.max_page_size}."
    if not _DIGITS.fullmatch(text):
        raise invalid_request("limit", "invalid_value", message)
    digits = text.lstrip("0") or "0"
    # Compare lengths first so a very long digit string is never converted.
    if len(digits) > len(str(limits.max_page_size)) or not 1 <= int(digits) <= limits.max_page_size:
        raise invalid_request("limit", "out_of_range", message, limit=limits.max_page_size)
    return int(digits)


# --------------------------------------------------------------- headers

def parse_if_match(header: str | None) -> IfMatch:
    """Parse If-Match without judging it; see IfMatch."""
    if header is None:
        return IfMatch(present=False, revision=None)
    match = _ETAG.fullmatch(header.strip())
    return IfMatch(present=True, revision=int(match.group(1)) if match else None)
