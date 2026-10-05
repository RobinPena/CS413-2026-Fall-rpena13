"""Converts model snapshots to JSON-ready dictionaries of plain values.

Text is passed through unchanged: displaying it literally (never as
markup) is the view's job.
"""
from lambda_web.model import Snapshot


def snapshot_to_dict(snap: Snapshot) -> dict:
    src = snap.source
    return {
        "source": None if src is None else {
            "name": src.name,
            "origin": src.origin.value,
            "text": src.text,
            "revision": src.revision,
        },
        "draft": snap.draft,
        "busy": None if snap.busy is None else snap.busy.value,
        "can_change_source": snap.can_change_source,
        "can_apply_or_discard": snap.can_apply_or_discard,
        "has_artifact": snap.has_artifact,
        "actions": [
            {"id": a.operation.name.lower(), "label": a.operation.value,
             "enabled": a.enabled, "reason": a.reason}
            for a in snap.actions
        ],
        "results": [
            {"operation": r.operation.value, "revision": r.revision,
             "outcome": r.outcome.value, "ok": r.ok,
             "message": r.message, "output": r.output}
            for r in snap.results
        ],
    }
