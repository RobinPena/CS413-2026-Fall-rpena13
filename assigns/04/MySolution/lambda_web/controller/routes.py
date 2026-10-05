"""Controller: turns HTTP requests into model calls and returns the
resulting state as JSON. It holds no rules; whether a change is allowed
is always the model's decision."""
from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from lambda_web.backend.contract import (Artifact, LanguageBackend,
                                         Operation, Result)
from lambda_web.controller import examples
from lambda_web.controller.serialize import snapshot_to_dict
from lambda_web.model import (Job, Origin, Session, StateError,
                              ValidationError)

bp = Blueprint("controller", __name__)

_ACTIONS = {op.name.lower(): op for op in Operation}


class RequestError(Exception):
    """The request itself is malformed (missing file or text field)."""


def _session() -> Session:
    return current_app.extensions["lambda_web"]["session"]


def _backend() -> LanguageBackend:
    return current_app.extensions["lambda_web"]["backend"]


def _respond(status: int = 200, kind: str | None = None,
             message: str | None = None):
    error = None if kind is None else {"kind": kind, "message": message}
    return jsonify(state=snapshot_to_dict(_session().snapshot()),
                   error=error), status


@bp.errorhandler(StateError)
def _state_error(e):
    return _respond(409, "state", str(e))


@bp.errorhandler(ValidationError)
def _validation_error(e):
    return _respond(422, "validation", str(e))


@bp.errorhandler(RequestError)
def _request_error(e):
    return _respond(400, "request", str(e))


@bp.errorhandler(RequestEntityTooLarge)
def _too_large(e):
    return _respond(413, "validation", "The upload is larger than 64 KiB.")


@bp.app_errorhandler(404)
@bp.app_errorhandler(405)
def _no_route(e):
    """Unknown API paths answer in the same JSON shape as every other
    API response; other paths keep Flask's default page."""
    if not request.path.startswith("/api/"):
        return e
    return _respond(e.code, "request",
                    f"No such endpoint: {request.method} {request.path}")


@bp.get("/")
def index():
    return ("LAMBDA web front-end: scaffold running.\n", 200,
            {"Content-Type": "text/plain; charset=utf-8"})


@bp.get("/api/state")
def state():
    return _respond()


@bp.post("/api/source/upload")
def upload():
    file = request.files.get("file")
    if file is None or not file.filename:
        raise RequestError("Choose a file to upload.")
    _session().load_upload(file.filename, file.read())
    return _respond()


@bp.post("/api/source/canned/<key>")
def canned(key: str):
    example = examples.get(key)
    if example is None:
        return _respond(404, "request", f"Unknown example {key!r}.")
    _session().load(example.title, example.text, Origin.CANNED)
    return _respond()


@bp.post("/api/source/manual")
def manual():
    _session().open_manual()
    return _respond()


@bp.post("/api/source/edit")
def edit():
    _session().edit(_text_field())
    return _respond()


@bp.post("/api/source/apply")
def apply():
    session = _session()
    session.edit(_text_field())
    session.apply()
    return _respond()


@bp.post("/api/source/discard")
def discard():
    _session().discard()
    return _respond()


@bp.post("/api/actions/<action_id>")
def action(action_id: str):
    """Run one tool action: the model decides whether it may start, the
    backend does the work, and the model records the outcome. Any
    unexpected error still ends the operation, so the page never stays
    busy."""
    operation = _ACTIONS.get(action_id)
    if operation is None:
        return _respond(404, "request", f"Unknown action {action_id!r}.")
    session = _session()
    job = session.begin(operation)
    try:
        result, artifact = _dispatch(_backend(), job)
        session.finish(result, artifact)
    except Exception as e:
        current_app.logger.exception("%s failed", operation.value)
        session.fail(f"Backend error: {type(e).__name__}: {e}")
    return _respond()


def _dispatch(backend: LanguageBackend,
              job: Job) -> tuple[Result, Artifact | None]:
    """Call the backend operation for `job`. Only Compile can produce an
    artifact; Execute consumes the one the model handed out."""
    match job.operation:
        case Operation.LINT:
            return backend.lint(job.text, job.revision), None
        case Operation.INTERPRET:
            return backend.interpret(job.text, job.revision), None
        case Operation.TYPECHECK:
            return backend.typecheck(job.text, job.revision), None
        case Operation.COMPILE:
            return backend.compile(job.text, job.revision)
        case Operation.EXECUTE:
            return backend.execute(job.artifact), None


def _text_field() -> str:
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("text"), str):
        raise RequestError('Expected a JSON body with a "text" string.')
    return data["text"]
