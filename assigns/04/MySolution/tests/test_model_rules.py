"""Model rules: source validation, busy state, and action gating.

Runs without a browser or web server.
"""
import threading
import time

import pytest

from lambda_web.backend.contract import Artifact, Operation, Outcome, Result
from lambda_web.model import (EXECUTE_UNAVAILABLE, MAX_SOURCE_BYTES, Origin,
                              Session, StateError, ValidationError)
from tests.programs import ADD_42, fact

TOOLS = [Operation.LINT, Operation.INTERPRET, Operation.TYPECHECK,
         Operation.COMPILE]


def loaded() -> Session:
    s = Session()
    s.load("Factorial", fact(5), Origin.CANNED)
    return s


def ok(op: Operation, revision: int) -> Result:
    return Result(op, revision, Outcome.OK, "ok")


# --- validation (F3) ---------------------------------------------------

@pytest.mark.parametrize("text", ["", "   ", "\n\t \n"])
def test_load_rejects_empty_source_and_keeps_previous(text):
    s = loaded()
    with pytest.raises(ValidationError, match="empty"):
        s.load("blank", text, Origin.UPLOAD)
    assert (s.snapshot().source.text, s.snapshot().source.revision) == \
        (fact(5), 1)


def test_rejected_apply_keeps_draft_for_correction():
    s = loaded()
    s.edit("   ")
    with pytest.raises(ValidationError):
        s.apply()
    snap = s.snapshot()
    assert snap.draft == "   " and snap.source.text == fact(5)


def test_size_limit_is_in_bytes():
    s = Session()
    s.load("max", "x" * MAX_SOURCE_BYTES, Origin.UPLOAD)
    with pytest.raises(ValidationError, match="64 KiB"):
        s.load("big", "x" * (MAX_SOURCE_BYTES + 1), Origin.UPLOAD)
    with pytest.raises(ValidationError, match="64 KiB"):
        s.load("wide", "é" * (MAX_SOURCE_BYTES // 2 + 1), Origin.UPLOAD)
    assert s.snapshot().source.name == "max"


def test_oversized_edit_is_kept_but_cannot_apply():
    s = loaded()
    s.edit("x" * (MAX_SOURCE_BYTES + 1))
    with pytest.raises(ValidationError):
        s.apply()
    assert s.snapshot().has_unapplied_edits


def test_upload_accepts_utf8_and_drops_bom():
    s = Session()
    data = '﻿# café\nD0Eint(1)'.encode("utf-8")
    snap = s.load_upload("prog.txt", data)
    assert snap.source.text == "# café\nD0Eint(1)"
    assert snap.source.origin is Origin.UPLOAD


@pytest.mark.parametrize("data", [b"\xff\xfeD0Eint(1)", b"D0Eint(\xc3)"])
def test_upload_rejects_invalid_utf8_and_keeps_previous(data):
    s = loaded()
    with pytest.raises(ValidationError, match="UTF-8"):
        s.load_upload("bad.bin", data)
    assert s.snapshot().source.revision == 1


def test_oversized_upload_rejected_before_decoding():
    s = loaded()
    with pytest.raises(ValidationError, match="64 KiB"):
        s.load_upload("big.bin", b"\xff" * (MAX_SOURCE_BYTES + 1))


# --- busy state (F10) --------------------------------------------------

def test_begin_returns_job_and_marks_busy():
    s = loaded()
    job = s.begin(Operation.INTERPRET)
    assert (job.operation, job.revision, job.text) == \
        (Operation.INTERPRET, 1, fact(5))
    assert s.snapshot().busy is Operation.INTERPRET


@pytest.mark.parametrize("change", [
    lambda s: s.begin(Operation.LINT),
    lambda s: s.load("x", ADD_42, Origin.UPLOAD),
    lambda s: s.open_manual(),
    lambda s: s.edit(ADD_42),
], ids=["begin", "load", "open-manual", "edit"])
def test_busy_blocks_conflicting_changes(change):
    s = loaded()
    s.begin(Operation.INTERPRET)
    with pytest.raises(StateError, match="Interpret"):
        change(s)
    snap = s.snapshot()
    assert (snap.source.text, snap.draft, snap.busy) == \
        (fact(5), None, Operation.INTERPRET)


def test_finish_records_result_and_restores_controls():
    s = loaded()
    s.begin(Operation.LINT)
    assert s.finish(ok(Operation.LINT, 1))
    snap = s.snapshot()
    assert snap.busy is None and len(snap.results) == 1
    assert snap.action(Operation.LINT).enabled


def test_finish_must_match_running_operation():
    s = loaded()
    with pytest.raises(StateError):
        s.finish(ok(Operation.LINT, 1))
    s.begin(Operation.LINT)
    with pytest.raises(StateError):
        s.finish(ok(Operation.INTERPRET, 1))


def test_fail_records_backend_failure_then_retry_succeeds():
    s = loaded()
    s.begin(Operation.INTERPRET)
    failure = s.fail("worker crashed")
    assert (failure.operation, failure.outcome) == \
        (Operation.INTERPRET, Outcome.BACKEND_FAILURE)
    snap = s.snapshot()
    assert snap.busy is None and snap.source.text == fact(5)
    s.begin(Operation.INTERPRET)
    assert s.finish(ok(Operation.INTERPRET, 1))
    assert len(s.snapshot().results) == 2


def test_only_one_of_two_simultaneous_begins_wins():
    s = loaded()
    real_check = s._action_state

    def slow_check(op):
        # Widen the gap between checking and marking busy, so a missing
        # lock lets both clicks through instead of passing by luck.
        state = real_check(op)
        time.sleep(0.05)
        return state
    s._action_state = slow_check
    barrier = threading.Barrier(2)
    outcomes = []

    def click():
        barrier.wait()
        try:
            s.begin(Operation.INTERPRET)
            outcomes.append("ran")
        except StateError:
            outcomes.append("refused")

    threads = [threading.Thread(target=click) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(outcomes) == ["ran", "refused"]


# --- action gating (F2, F4, F7) ----------------------------------------

def test_no_source_disables_every_action():
    snap = Session().snapshot()
    assert [a.operation for a in snap.actions] == list(Operation)
    assert all(not a.enabled and "Load or enter source" in a.reason
               for a in snap.actions)


def test_applied_source_enables_tools_but_not_execute():
    snap = loaded().snapshot()
    assert all(snap.action(op).enabled for op in TOOLS)
    execute = snap.action(Operation.EXECUTE)
    assert not execute.enabled and execute.reason == EXECUTE_UNAVAILABLE


def test_unapplied_edits_disable_actions():
    s = loaded()
    s.edit(fact(6))
    snap = s.snapshot()
    assert all(not a.enabled and "Apply or discard" in a.reason
               for a in snap.actions)
    assert snap.can_apply_or_discard and not snap.can_change_source


def test_busy_disables_actions_and_source_changes():
    s = loaded()
    s.begin(Operation.LINT)
    snap = s.snapshot()
    assert all(not a.enabled and "Lint is running" in a.reason
               for a in snap.actions)
    assert not snap.can_change_source and not snap.can_apply_or_discard


def test_begin_refuses_disabled_action_with_its_reason():
    s = loaded()
    with pytest.raises(StateError, match="generated by Compile"):
        s.begin(Operation.EXECUTE)
    assert s.snapshot().busy is None


def test_compile_artifact_enables_execute_until_source_changes():
    s = loaded()
    s.begin(Operation.COMPILE)
    s.finish(ok(Operation.COMPILE, 1), Artifact(1, "python", "code"))
    assert s.snapshot().action(Operation.EXECUTE).enabled
    job = s.begin(Operation.EXECUTE)
    assert job.artifact.code == "code"
    s.finish(ok(Operation.EXECUTE, 1))

    s.edit(fact(6))
    s.apply()
    assert not s.snapshot().action(Operation.EXECUTE).enabled


def test_failed_compile_invalidates_previous_artifact():
    s = loaded()
    s.begin(Operation.COMPILE)
    s.finish(ok(Operation.COMPILE, 1), Artifact(1, "python", "code"))
    s.begin(Operation.COMPILE)
    s.finish(Result(Operation.COMPILE, 1, Outcome.LANGUAGE_ERROR, "err"))
    assert not s.snapshot().has_artifact


def test_artifact_for_other_revision_is_not_accepted():
    s = loaded()
    s.begin(Operation.COMPILE)
    s.finish(ok(Operation.COMPILE, 1), Artifact(99, "python", "code"))
    assert not s.snapshot().has_artifact
