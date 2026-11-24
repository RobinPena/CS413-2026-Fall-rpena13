"""Business rules for programs, collections, and their cases.

    StudioService(store, limits) -> service
    service.create_program(fields) -> Program, and so on for every route

Each operation takes already-validated input (validation.py) and returns an
immutable record or Page, or raises ApiError. Every operation that reads or
changes records runs entirely inside one store transaction, in the order of
API.md section 9:

    existence -> If-Match present -> If-Match well formed -> revision
    -> name unique -> capacity -> change

so a failure at any step leaves the store exactly as it was, and two requests
can never interleave. Nothing here knows about HTTP, and nothing here looks
inside LAMBDA source: sources and expectations are opaque data.
"""
from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import replace

from . import errors
from .limits import Limits
from .models import Case, Collection, Program, utc_timestamp
from .pagination import Page, SnapshotRegistry
from .store import Storage
from .validation import CaseFields, CollectionFields, IfMatch, PageRequest, ProgramFields

ID_PREFIXES = {"program": "prg_", "collection": "col_", "case": "case_"}


class StudioService:

    def __init__(self, store: Storage, limits: Limits, *,
                 snapshots: SnapshotRegistry | None = None,
                 clock: Callable[[], str] = utc_timestamp) -> None:
        self._store = store
        self._limits = limits
        self._snapshots = snapshots or SnapshotRegistry(limits.max_snapshots,
                                                        limits.snapshot_idle_seconds)
        self._clock = clock

    # ------------------------------------------------------------ programs

    def create_program(self, fields: ProgramFields) -> Program:
        with self._store.transaction():
            self._require_unique_program_name(fields.name)
            if self._store.program_count() >= self._limits.max_programs:
                raise errors.capacity_limit("programs", self._limits.max_programs,
                                            f"The service holds at most {self._limits.max_programs} programs.")
            now = self._clock()
            program = Program(id=self._new_id("program", self._store.get_program),
                              name=fields.name, source=fields.source,
                              description=fields.description,
                              created_at=now, updated_at=now, revision=1)
            self._store.save_program(program)
            return program

    def get_program(self, program_id: str) -> Program:
        with self._store.transaction():
            return self._existing_program(program_id)

    def replace_program(self, program_id: str, if_match: IfMatch, fields: ProgramFields) -> Program:
        with self._store.transaction():
            current = self._existing_program(program_id)
            _check_precondition("program", current.revision, if_match)
            self._require_unique_program_name(fields.name, except_id=program_id)
            program = replace(current, name=fields.name, source=fields.source,
                              description=fields.description,
                              updated_at=self._clock(), revision=current.revision + 1)
            self._store.save_program(program)
            return program

    def delete_program(self, program_id: str, if_match: IfMatch) -> None:
        # Cases hold their own source snapshots, so no case is affected.
        with self._store.transaction():
            current = self._existing_program(program_id)
            _check_precondition("program", current.revision, if_match)
            self._store.delete_program(program_id)

    def list_programs(self, request: PageRequest) -> Page:
        if request.cursor is not None:
            return self._snapshots.next_page("programs", request.cursor, request.limit)
        with self._store.transaction():
            records = self._store.all_programs()      # captured in one atomic step
        return self._snapshots.first_page("programs", records, request.limit)

    # --------------------------------------------------------- collections

    def create_collection(self, fields: CollectionFields) -> Collection:
        with self._store.transaction():
            self._require_unique_collection_name(fields.name)
            if self._store.collection_count() >= self._limits.max_collections:
                raise errors.capacity_limit("collections", self._limits.max_collections,
                                            f"The service holds at most {self._limits.max_collections} collections.")
            now = self._clock()
            collection = Collection(id=self._new_id("collection", self._store.get_collection),
                                    name=fields.name, description=fields.description,
                                    created_at=now, updated_at=now, revision=1, cases=())
            self._store.save_collection(collection)
            return collection

    def get_collection(self, collection_id: str) -> Collection:
        with self._store.transaction():
            return self._existing_collection(collection_id)

    def replace_collection(self, collection_id: str, if_match: IfMatch,
                           fields: CollectionFields) -> Collection:
        """Replace name and description only; cases and their order stay as they are."""
        with self._store.transaction():
            current = self._existing_collection(collection_id)
            _check_precondition("collection", current.revision, if_match)
            self._require_unique_collection_name(fields.name, except_id=collection_id)
            return self._save_next_revision(current, name=fields.name,
                                            description=fields.description)

    def delete_collection(self, collection_id: str, if_match: IfMatch) -> None:
        """Delete the collection; its cases live inside it, so they go with it."""
        with self._store.transaction():
            current = self._existing_collection(collection_id)
            _check_precondition("collection", current.revision, if_match)
            self._store.delete_collection(collection_id)

    def list_collections(self, request: PageRequest) -> Page:
        if request.cursor is not None:
            return self._snapshots.next_page("collections", request.cursor, request.limit)
        with self._store.transaction():
            records = self._store.all_collections()
        return self._snapshots.first_page("collections", records, request.limit)

    # --------------------------------------------------------------- cases

    def add_case(self, collection_id: str, if_match: IfMatch, fields: CaseFields) -> Collection:
        """Append one case; the collection's revision goes up by one."""
        with self._store.transaction():
            collection = self._existing_collection(collection_id)
            _check_precondition("collection", collection.revision, if_match)
            _require_unique_case_name(collection, fields.name)
            limit = self._limits.max_cases_per_collection
            if len(collection.cases) >= limit:
                raise errors.capacity_limit("cases", limit, f"A collection holds at most {limit} cases.")
            taken = {case.id for case in collection.cases}
            case = Case(id=self._new_id("case", taken.__contains__), name=fields.name,
                        source=fields.source, expected=fields.expected,
                        description=fields.description)
            return self._save_next_revision(collection, cases=collection.cases + (case,))

    def replace_case(self, collection_id: str, case_id: str, if_match: IfMatch,
                     fields: CaseFields) -> Collection:
        """Replace one case's fields, keeping its ID and position."""
        with self._store.transaction():
            collection = self._existing_collection(collection_id)
            index = _case_index(collection, case_id)
            _check_precondition("collection", collection.revision, if_match)
            _require_unique_case_name(collection, fields.name, except_id=case_id)
            case = Case(id=case_id, name=fields.name, source=fields.source,
                        expected=fields.expected, description=fields.description)
            cases = collection.cases[:index] + (case,) + collection.cases[index + 1:]
            return self._save_next_revision(collection, cases=cases)

    def delete_case(self, collection_id: str, case_id: str, if_match: IfMatch) -> Collection:
        """Remove one case; the others keep their order."""
        with self._store.transaction():
            collection = self._existing_collection(collection_id)
            index = _case_index(collection, case_id)
            _check_precondition("collection", collection.revision, if_match)
            cases = collection.cases[:index] + collection.cases[index + 1:]
            return self._save_next_revision(collection, cases=cases)

    # ------------------------------------------------------------- helpers
    # These run inside a transaction that the caller already holds.

    def _existing_program(self, program_id: str) -> Program:
        program = self._store.get_program(program_id)
        if program is None:
            raise errors.record_not_found("program", program_id)
        return program

    def _existing_collection(self, collection_id: str) -> Collection:
        collection = self._store.get_collection(collection_id)
        if collection is None:
            raise errors.record_not_found("collection", collection_id)
        return collection

    def _require_unique_program_name(self, name: str, except_id: str | None = None) -> None:
        holder = self._store.find_program_by_name(name)
        if holder is not None and holder.id != except_id:
            raise errors.duplicate_name("program", name)

    def _require_unique_collection_name(self, name: str, except_id: str | None = None) -> None:
        holder = self._store.find_collection_by_name(name)
        if holder is not None and holder.id != except_id:
            raise errors.duplicate_name("collection", name)

    def _save_next_revision(self, collection: Collection, **changes) -> Collection:
        """Store the collection with `changes`, one revision later, and return it."""
        updated = replace(collection, **changes, updated_at=self._clock(),
                          revision=collection.revision + 1)
        self._store.save_collection(updated)
        return updated

    @staticmethod
    def _new_id(kind: str, taken: Callable[[str], object]) -> str:
        """A fresh opaque ID: 96 random bits, checked against the existing ones."""
        while True:
            candidate = ID_PREFIXES[kind] + secrets.token_urlsafe(12)
            if not taken(candidate):
                return candidate


def _check_precondition(kind: str, current_revision: int, if_match: IfMatch) -> None:
    """The If-Match rules of API.md section 5, for a record known to exist."""
    if not if_match.present:
        raise errors.precondition_required()
    if if_match.revision is None:
        raise errors.malformed_if_match()
    if if_match.revision != current_revision:
        raise errors.revision_conflict(kind, if_match.revision, current_revision)


def _case_index(collection: Collection, case_id: str) -> int:
    for index, case in enumerate(collection.cases):
        if case.id == case_id:
            return index
    raise errors.case_not_found(case_id)


def _require_unique_case_name(collection: Collection, name: str, except_id: str | None = None) -> None:
    if any(case.name == name and case.id != except_id for case in collection.cases):
        raise errors.duplicate_name("case in this collection", name)
