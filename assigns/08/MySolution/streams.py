"""Process-local table of open solver streams (DESIGN.md section 6).

    StreamTable().open(size)              -> {"stream_id": ..., "size": ...}
    StreamTable().next(stream_id, limit)  -> {"events": [...], "done": ...}
    StreamTable().close(stream_id)        -> {"closed": True}

Each entry keeps the stream's current lazy cursor, never a list of events.
One lock makes every operation atomic, including the forcing done by next,
so no two requests advance the same stream and close never interleaves with
a read. Arguments are assumed valid; methods.py checks them first.
"""
from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from . import lambda_adapter
from .errors import STREAM_NOT_FOUND, TOO_MANY_STREAMS, RpcError

DEFAULT_TTL_SECONDS = 300.0
MAX_STREAMS = 64


@dataclass
class Stream:
    size: int
    cursor: object | None  # the unforced tail to read next; None once released
    exhausted: bool
    expires_at: float  # monotonic seconds


class StreamTable:
    """Stream IDs mapped to lazy cursors, with expiry and an open-stream limit.

    clock, open_stream and take can be replaced in tests (a fake clock, or a
    take that fails); in normal use they are time.monotonic and the adapter.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        ttl: float = DEFAULT_TTL_SECONDS,
        max_streams: int = MAX_STREAMS,
        open_stream: Callable = lambda_adapter.open_stream,
        take: Callable = lambda_adapter.take,
    ):
        self.clock = clock
        self.ttl = ttl
        self.max_streams = max_streams
        self._open_stream = open_stream
        self._take = take
        self._lock = threading.Lock()
        self.entries: dict[str, Stream] = {}  # inspected by tests; changed only under the lock

    def __len__(self) -> int:
        with self._lock:
            return len(self.entries)

    def open(self, size: int) -> dict:
        with self._lock:
            now = self._sweep()
            if len(self.entries) >= self.max_streams:
                raise RpcError(TOO_MANY_STREAMS, {"limit": self.max_streams})
            stream_id = str(uuid.uuid4())
            self.entries[stream_id] = Stream(size, self._open_stream(size), False, now + self.ttl)
            return {"stream_id": stream_id, "size": size}

    def next(self, stream_id: str, limit: int) -> dict:
        with self._lock:
            now = self._sweep()
            stream = self._find(stream_id)
            stream.expires_at = now + self.ttl
            if stream.exhausted:
                return {"events": [], "done": True}
            try:
                taken = self._take(stream.cursor, limit)
            except Exception:
                # The interpreter state may be inconsistent: drop the stream.
                del self.entries[stream_id]
                raise
            # After done, taken.cursor is None, which releases the solver and
            # its continuations; the small record left behind answers later reads.
            stream.cursor = taken.cursor
            stream.exhausted = taken.done
            return {"events": taken.events, "done": taken.done}

    def close(self, stream_id: str) -> dict:
        with self._lock:
            self._sweep()
            self._find(stream_id)
            del self.entries[stream_id]
            return {"closed": True}

    def _find(self, stream_id: str) -> Stream:
        stream = self.entries.get(stream_id)
        if stream is None:
            raise RpcError(STREAM_NOT_FOUND)
        return stream

    def _sweep(self) -> float:
        """Remove expired entries; return the current time. Call with the lock held."""
        now = self.clock()
        for stream_id in [k for k, s in self.entries.items() if s.expires_at <= now]:
            del self.entries[stream_id]
        return now
