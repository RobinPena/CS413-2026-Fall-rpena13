"""Helpers for the unit tests of the business rules (no HTTP involved).

Inputs are built through validation.py, just as the HTTP layer will build
them, so names are trimmed and defaults applied exactly as in production.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from itertools import count

from MySolution.errors import ApiError
from MySolution.limits import Limits
from MySolution.pagination import SnapshotRegistry
from MySolution.service import StudioService
from MySolution.store import InMemoryStore
from MySolution.validation import (
    IfMatch, PageRequest, case_fields, collection_fields, parse_if_match, program_fields,
)

LIMITS = Limits()
NO_IF_MATCH = parse_if_match(None)


def if_match(revision: int) -> IfMatch:
    return parse_if_match(f'"{revision}"')


def page(limit: int, cursor: str | None = None) -> PageRequest:
    return PageRequest(limit=limit, cursor=cursor)


def program_input(name: str, source: str = "1 + 2", **extra):
    return program_fields({"name": name, "source": source, **extra}, LIMITS)


def collection_input(name: str, **extra):
    return collection_fields({"name": name, **extra}, LIMITS)


def case_input(name: str, source: str = "6 * 7", expected=None, **extra):
    expected = expected or {"kind": "value", "value": "42"}
    return case_fields({"name": name, "source": source, "expected": expected, **extra}, LIMITS)


class FakeMonotonic:
    """A monotonic clock the test moves by hand, so expiry needs no sleeping."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def ticking_clock():
    """A wall clock that advances one second per reading, so every change gets a new timestamp."""
    start = datetime(2026, 11, 24, 15, 0, 0, tzinfo=timezone.utc)
    seconds = count()
    return lambda: (start + timedelta(seconds=next(seconds))).isoformat(
        timespec="milliseconds").replace("+00:00", "Z")


class ServiceTestCase(unittest.TestCase):
    """A fresh store and service for every test."""

    limits = LIMITS

    def setUp(self) -> None:
        self.store = InMemoryStore()
        self.monotonic = FakeMonotonic()
        self.snapshots = SnapshotRegistry(self.limits.max_snapshots,
                                          self.limits.snapshot_idle_seconds, clock=self.monotonic)
        self.service = StudioService(self.store, self.limits, snapshots=self.snapshots,
                                     clock=ticking_clock())

    def assertApiError(self, code: str, call, *args, **details) -> ApiError:
        """call(*args) raises ApiError with `code` and, if given, these detail values."""
        with self.assertRaises(ApiError) as caught:
            call(*args)
        self.assertEqual(caught.exception.code, code, caught.exception.to_json())
        for key, value in details.items():
            self.assertEqual(caught.exception.details.get(key), value, caught.exception.to_json())
        return caught.exception
