"""Storage: the small interface the business rules need, and the required
in-memory backend.

The interface only keeps and finds records. It knows nothing about
revisions, names being unique, capacities, or HTTP; those are the business
rules in service.py. What storage does own is atomicity: the service holds
`transaction()` for the whole of each check-then-change operation, so no
other request can observe or change the store halfway through
(API.md section 7).

Records are immutable values (models.py), so the store can hand them out
without copying and callers can never change what is stored.
"""
from __future__ import annotations

import threading
from contextlib import AbstractContextManager
from typing import Protocol

from .models import Collection, Program


class Storage(Protocol):
    """What the business rules require from a storage backend."""

    def transaction(self) -> AbstractContextManager:
        """Exclusive access for one complete operation. Not reentrant."""

    def get_program(self, program_id: str) -> Program | None: ...
    def save_program(self, program: Program) -> None:
        """Insert a new program, or replace one in place (same creation position)."""
    def delete_program(self, program_id: str) -> None: ...
    def all_programs(self) -> tuple[Program, ...]:
        """Every program, oldest first (creation order)."""
    def find_program_by_name(self, name: str) -> Program | None: ...
    def program_count(self) -> int: ...

    def get_collection(self, collection_id: str) -> Collection | None: ...
    def save_collection(self, collection: Collection) -> None: ...
    def delete_collection(self, collection_id: str) -> None: ...
    def all_collections(self) -> tuple[Collection, ...]: ...
    def find_collection_by_name(self, name: str) -> Collection | None: ...
    def collection_count(self) -> int: ...


class InMemoryStore:
    """Records in two ordinary dictionaries, protected by one lock.

    A dict keeps insertion order, and assigning to an existing key keeps the
    key's position, so iteration order is creation order even after updates.
    Nothing is ever written to disk: the records disappear with the process.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._programs: dict[str, Program] = {}
        self._collections: dict[str, Collection] = {}

    def transaction(self) -> AbstractContextManager:
        return self._lock

    # Programs
    def get_program(self, program_id: str) -> Program | None:
        return self._programs.get(program_id)

    def save_program(self, program: Program) -> None:
        self._programs[program.id] = program

    def delete_program(self, program_id: str) -> None:
        del self._programs[program_id]

    def all_programs(self) -> tuple[Program, ...]:
        return tuple(self._programs.values())

    def find_program_by_name(self, name: str) -> Program | None:
        # A linear scan: at most 500 programs (API.md section 4), and it
        # avoids keeping a second index consistent with the records.
        return next((p for p in self._programs.values() if p.name == name), None)

    def program_count(self) -> int:
        return len(self._programs)

    # Collections (each one carries its own tuple of cases)
    def get_collection(self, collection_id: str) -> Collection | None:
        return self._collections.get(collection_id)

    def save_collection(self, collection: Collection) -> None:
        self._collections[collection.id] = collection

    def delete_collection(self, collection_id: str) -> None:
        del self._collections[collection_id]

    def all_collections(self) -> tuple[Collection, ...]:
        return tuple(self._collections.values())

    def find_collection_by_name(self, name: str) -> Collection | None:
        return next((c for c in self._collections.values() if c.name == name), None)

    def collection_count(self) -> int:
        return len(self._collections)
