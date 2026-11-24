"""List pages cut from snapshots, and the opaque cursors that name them
(API.md section 6).

A snapshot is a tuple of references to immutable records captured in one
atomic step by the service. Because records are never changed in place, a
snapshot shows them exactly as they were when it was taken, however the
store changes afterwards. Nothing is copied and no ID is looked up again.

A cursor is "<snapshot key>.<offset>": a random 128-bit key (22 URL-safe
characters) and the position of the next record. Clients treat it as opaque.

Snapshots live only in this process. Each expires `idle_seconds` after it was
last used. At most `max_snapshots` are open; past that, a new snapshot is
refused (capacity_limit) rather than evicting one a client may still be
reading.
"""
from __future__ import annotations

import re
import secrets
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from .errors import capacity_limit, invalid_request

_CURSOR = re.compile(r"([A-Za-z0-9_-]{22})\.([1-9][0-9]{0,5})")


@dataclass(frozen=True)
class Page:
    items: tuple
    next_cursor: str | None


@dataclass
class _Snapshot:
    kind: str              # "programs" or "collections": the list it belongs to
    records: tuple
    last_used: float       # time.monotonic() of the latest request that used it


class SnapshotRegistry:
    """Open snapshots, least recently used first."""

    def __init__(self, max_snapshots: int, idle_seconds: float,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._max_snapshots = max_snapshots
        self._idle_seconds = idle_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._snapshots: OrderedDict[str, _Snapshot] = OrderedDict()

    def first_page(self, kind: str, records: tuple, limit: int) -> Page:
        """The first page of a freshly captured list. Keeps a snapshot only if more pages follow."""
        if len(records) <= limit:
            return Page(records, None)
        with self._lock:
            now = self._clock()
            self._discard_expired(now)
            if len(self._snapshots) >= self._max_snapshots:
                raise capacity_limit("list_snapshots", self._max_snapshots,
                                     f"At most {self._max_snapshots} multi-page lists can be open; "
                                     "finish or abandon one (they expire after "
                                     f"{self._idle_seconds:g} seconds unused), or use a larger limit.")
            key = self._new_key()
            self._snapshots[key] = _Snapshot(kind, records, now)
        return Page(records[:limit], f"{key}.{limit}")

    def next_page(self, kind: str, cursor: str, limit: int) -> Page:
        """The page at `cursor`, cut from the same snapshot as the pages before it."""
        match = _CURSOR.fullmatch(cursor)
        if match is None:
            raise invalid_request("cursor", "malformed_cursor",
                                  "cursor is not a value this service issued.")
        key, offset = match.group(1), int(match.group(2))
        with self._lock:
            now = self._clock()
            self._discard_expired(now)
            snapshot = self._snapshots.get(key)
            if snapshot is None or snapshot.kind != kind or offset >= len(snapshot.records):
                raise invalid_request("cursor", "unknown_cursor",
                                      "cursor does not name an open list snapshot; it may have "
                                      "expired or come from another list. Start again without a cursor.")
            snapshot.last_used = now
            self._snapshots.move_to_end(key)   # keep least-recently-used order
        end = offset + limit
        next_cursor = f"{key}.{end}" if end < len(snapshot.records) else None
        return Page(snapshot.records[offset:end], next_cursor)

    def open_count(self) -> int:
        with self._lock:
            self._discard_expired(self._clock())
            return len(self._snapshots)

    def _discard_expired(self, now: float) -> None:
        """Drop expired snapshots. The oldest-used come first, so stop at the first live one."""
        while self._snapshots:
            key, snapshot = next(iter(self._snapshots.items()))
            if now - snapshot.last_used < self._idle_seconds:
                break
            del self._snapshots[key]

    def _new_key(self) -> str:
        while True:
            key = secrets.token_urlsafe(16)     # 128 random bits, 22 characters
            if key not in self._snapshots:
                return key
