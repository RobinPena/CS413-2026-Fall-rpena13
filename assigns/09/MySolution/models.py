"""The stored records (API.md section 2) and their JSON representations.

Every record is an immutable value: a frozen dataclass whose cases are held
in a tuple. Changing a record means building a new value with
dataclasses.replace, so a value that was handed out (to a response or a
list snapshot) can never change afterwards. The *_json functions build fresh
dictionaries on every call, so callers can never reach stored state through
them either.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ExpectedValue:
    """The case should run successfully and format exactly as `value`."""
    value: str


@dataclass(frozen=True)
class ExpectedError:
    """The case should fail LAMBDA3 parsing ("syntax") or type checking ("type")."""
    category: str


Expected = ExpectedValue | ExpectedError


@dataclass(frozen=True)
class Program:
    id: str
    name: str
    source: str
    description: str
    created_at: str
    updated_at: str
    revision: int


@dataclass(frozen=True)
class Case:
    id: str
    name: str
    source: str
    expected: Expected
    description: str


@dataclass(frozen=True)
class Collection:
    id: str
    name: str
    description: str
    created_at: str
    updated_at: str
    revision: int
    cases: tuple[Case, ...] = ()


def utc_timestamp() -> str:
    """The current UTC time as YYYY-MM-DDTHH:MM:SS.sssZ."""
    now = datetime.now(timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def expected_json(expected: Expected) -> dict:
    if isinstance(expected, ExpectedValue):
        return {"kind": "value", "value": expected.value}
    return {"kind": "error", "category": expected.category}


def case_json(case: Case) -> dict:
    return {
        "id": case.id,
        "name": case.name,
        "source": case.source,
        "expected": expected_json(case.expected),
        "description": case.description,
    }


def program_json(program: Program) -> dict:
    return {
        "id": program.id,
        "name": program.name,
        "source": program.source,
        "description": program.description,
        "created_at": program.created_at,
        "updated_at": program.updated_at,
        "revision": program.revision,
    }


def collection_json(collection: Collection) -> dict:
    return {
        "id": collection.id,
        "name": collection.name,
        "description": collection.description,
        "created_at": collection.created_at,
        "updated_at": collection.updated_at,
        "revision": collection.revision,
        "cases": [case_json(case) for case in collection.cases],
    }
