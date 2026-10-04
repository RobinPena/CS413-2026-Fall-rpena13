"""Model: the application's state and the rules that govern it.

Pure Python with no Flask, HTML or HTTP objects, so the rules hold no
matter how the state is displayed or changed, and can be tested directly.
The model never calls the language backend; it only records the Results
the controller hands it.
"""
import threading
from dataclasses import dataclass
from enum import Enum

from lambda_web.backend.contract import Artifact, Result

MANUAL_NAME = "Manual input"


class Origin(Enum):
    UPLOAD = "upload"
    MANUAL = "manual"
    CANNED = "canned"


class StateError(Exception):
    """The requested change is not allowed in the current state."""


@dataclass(frozen=True)
class Source:
    """An applied source: the text the tools operate on."""
    name: str
    origin: Origin
    text: str
    revision: int


@dataclass(frozen=True)
class Snapshot:
    """Read-only view of the session state, safe to hand to the view."""
    source: Source | None
    draft: str | None
    results: tuple[Result, ...]
    has_artifact: bool

    @property
    def has_unapplied_edits(self) -> bool:
        return self.draft is not None


class Session:
    """State for one user. Every public method is atomic under a lock,
    and a rejected change raises before anything is modified."""

    def __init__(self):
        self._lock = threading.Lock()
        self._revision = 0
        self._source: Source | None = None
        self._draft: str | None = None
        self._draft_target: tuple[str, Origin] | None = None
        self._results: list[Result] = []
        self._artifact: Artifact | None = None

    # --- source changes -------------------------------------------------

    def load(self, name: str, text: str, origin: Origin) -> Snapshot:
        """Replace the applied source (upload or canned example)."""
        with self._lock:
            self._require_no_draft("load new source")
            self._new_revision(name, origin, text)
            return self._snapshot()

    def open_manual(self) -> Snapshot:
        """Start a blank draft that becomes "Manual input" when applied."""
        with self._lock:
            self._require_no_draft("open manual input")
            self._draft = ""
            self._draft_target = (MANUAL_NAME, Origin.MANUAL)
            return self._snapshot()

    def edit(self, text: str) -> Snapshot:
        """Replace the draft text. Edits the applied source if there is
        one; otherwise the draft becomes manual input."""
        with self._lock:
            if self._draft is None:
                self._draft_target = (
                    (self._source.name, self._source.origin) if self._source
                    else (MANUAL_NAME, Origin.MANUAL))
            self._draft = text
            return self._snapshot()

    def apply(self) -> Snapshot:
        """Make the draft the applied source, as a new revision."""
        with self._lock:
            if self._draft is None:
                raise StateError("There are no unapplied edits to apply.")
            name, origin = self._draft_target
            self._new_revision(name, origin, self._draft)
            return self._snapshot()

    def discard(self) -> Snapshot:
        """Drop the draft; the applied source is unchanged."""
        with self._lock:
            if self._draft is None:
                raise StateError("There are no unapplied edits to discard.")
            self._clear_draft()
            return self._snapshot()

    # --- results --------------------------------------------------------

    def record(self, result: Result) -> bool:
        """Store a result for the current revision. A result for an older
        revision is stale and ignored; returns whether it was stored."""
        with self._lock:
            if (self._source is None
                    or result.revision != self._source.revision):
                return False
            self._results.append(result)
            return True

    def snapshot(self) -> Snapshot:
        with self._lock:
            return self._snapshot()

    # --- internals (caller holds the lock) ------------------------------

    def _require_no_draft(self, action: str) -> None:
        if self._draft is not None:
            raise StateError(
                f"Apply or discard your edits before you {action}.")

    def _new_revision(self, name: str, origin: Origin, text: str) -> None:
        self._revision += 1
        self._source = Source(name, origin, text, self._revision)
        self._results.clear()
        self._artifact = None
        self._clear_draft()

    def _clear_draft(self) -> None:
        self._draft = None
        self._draft_target = None

    def _snapshot(self) -> Snapshot:
        return Snapshot(self._source, self._draft, tuple(self._results),
                        self._artifact is not None)
