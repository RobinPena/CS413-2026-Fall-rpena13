"""Model: source state, revisions, drafts, and results.

Runs without a browser or web server: the model is plain Python.
"""
import ast
import dataclasses
from pathlib import Path

import pytest

from lambda_web.backend.contract import Operation, Outcome, Result
from lambda_web.model import MANUAL_NAME, Origin, Session, StateError
from tests.programs import ADD_42, fact


def result_for(revision: int) -> Result:
    return Result(Operation.LINT, revision, Outcome.OK, "ok")


# --- loading --------------------------------------------------------

def test_new_session_is_empty():
    snap = Session().snapshot()
    assert snap.source is None and snap.draft is None
    assert snap.results == () and not snap.has_artifact


def test_load_creates_first_revision():
    snap = Session().load("Factorial", fact(5), Origin.CANNED)
    assert (snap.source.name, snap.source.origin, snap.source.revision) == \
        ("Factorial", Origin.CANNED, 1)
    assert snap.source.text == fact(5)


def test_load_replaces_source_with_new_revision():
    s = Session()
    s.load("a.txt", ADD_42, Origin.UPLOAD)
    snap = s.load("Factorial", fact(5), Origin.CANNED)
    assert (snap.source.name, snap.source.revision) == ("Factorial", 2)


# --- manual input and editing ----------------------------------------

def test_manual_input_opens_blank_draft_then_applies():
    s = Session()
    snap = s.open_manual()
    assert snap.draft == "" and snap.source is None
    s.edit(ADD_42)
    snap = s.apply()
    assert (snap.source.name, snap.source.origin, snap.source.text) == \
        (MANUAL_NAME, Origin.MANUAL, ADD_42)
    assert snap.source.revision == 1 and snap.draft is None


def test_typing_without_upload_becomes_manual_input():
    s = Session()
    s.edit(ADD_42)
    assert s.apply().source.name == MANUAL_NAME


def test_editing_keeps_applied_source_until_apply():
    s = Session()
    s.load("Factorial", fact(5), Origin.CANNED)
    snap = s.edit(fact(6))
    assert snap.source.text == fact(5) and snap.draft == fact(6)
    assert snap.has_unapplied_edits
    snap = s.apply()
    assert (snap.source.name, snap.source.text, snap.source.revision) == \
        ("Factorial", fact(6), 2)


def test_discard_restores_applied_source():
    s = Session()
    s.load("Factorial", fact(5), Origin.CANNED)
    s.edit("garbage")
    snap = s.discard()
    assert snap.draft is None
    assert (snap.source.text, snap.source.revision) == (fact(5), 1)


@pytest.mark.parametrize("change", [
    lambda s: s.load("other", ADD_42, Origin.UPLOAD),
    lambda s: s.open_manual(),
], ids=["load", "open-manual"])
def test_draft_blocks_source_replacement(change):
    s = Session()
    s.load("Factorial", fact(5), Origin.CANNED)
    s.edit(fact(6))
    with pytest.raises(StateError, match="Apply or discard"):
        change(s)
    snap = s.snapshot()
    assert (snap.source.text, snap.source.revision, snap.draft) == \
        (fact(5), 1, fact(6))


@pytest.mark.parametrize("action", ["apply", "discard"])
def test_apply_or_discard_without_draft_is_rejected(action):
    s = Session()
    s.load("Factorial", fact(5), Origin.CANNED)
    with pytest.raises(StateError):
        getattr(s, action)()
    assert s.snapshot().source.revision == 1


# --- results ----------------------------------------------------------

def test_result_for_current_revision_is_recorded():
    s = Session()
    s.load("Factorial", fact(5), Origin.CANNED)
    assert s.record(result_for(1))
    assert s.snapshot().results == (result_for(1),)


@pytest.mark.parametrize("change", [
    lambda s: s.load("other", ADD_42, Origin.UPLOAD),
    lambda s: (s.edit(fact(6)), s.apply()),
], ids=["load", "apply"])
def test_new_revision_clears_results(change):
    s = Session()
    s.load("Factorial", fact(5), Origin.CANNED)
    s.record(result_for(1))
    change(s)
    assert s.snapshot().results == ()


def test_stale_result_is_ignored():
    s = Session()
    s.load("Factorial", fact(5), Origin.CANNED)
    s.load("other", ADD_42, Origin.UPLOAD)
    assert not s.record(result_for(1))
    assert s.snapshot().results == ()


def test_snapshot_is_read_only():
    s = Session()
    s.load("Factorial", fact(5), Origin.CANNED)
    snap = s.snapshot()
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.draft = "x"
    assert isinstance(snap.results, tuple)


# --- architectural boundary --------------------------------------------

def test_model_does_not_depend_on_web_or_backend_implementation():
    allowed = {"threading", "dataclasses", "enum",
               "lambda_web.backend.contract", "lambda_web.model.session"}
    model_dir = Path(__file__).parent.parent / "lambda_web" / "model"
    for path in model_dir.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module]
            else:
                continue
            assert set(names) <= allowed, f"{path.name} imports {names}"
