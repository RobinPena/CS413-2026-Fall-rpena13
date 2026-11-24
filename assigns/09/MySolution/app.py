"""HTTP layer: the REST routes of API.md as thin adapters around StudioService.

    create_app(limits=Limits(), *, store=None, snapshot_clock=time.monotonic,
               studio_origins=DEFAULT_STUDIO_ORIGINS) -> Flask app

A route does only HTTP work, in the order of API.md section 9:

1. check the media type;
2. read the body within the size limit;
3. decode it as strict JSON;
4. hand the query parameters, body, and If-Match header to validation.py;
5. call one service operation;
6. turn the returned record into a JSON response with its status and headers.

Every failure becomes the JSON error envelope of API.md section 8. That
includes Flask and Werkzeug's own 404, 405, and 413 responses and any
unexpected exception, which is logged here and never shown to the client.
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterable

from flask import Flask, Response, request
from werkzeug.exceptions import MethodNotAllowed, NotFound, RequestEntityTooLarge
from werkzeug.http import parse_options_header

from . import errors
from .errors import ApiError
from .limits import Limits
from .models import Collection, Program, collection_json, program_json
from .pagination import Page, SnapshotRegistry
from .service import StudioService
from .store import InMemoryStore, Storage
from .validation import (
    IfMatch, case_fields, collection_fields, no_query_parameters, page_request, parse_if_match,
    program_fields,
)

API = "/api/v1"
API_VERSION = "1.0"
DEFAULT_STUDIO_ORIGINS = ("http://127.0.0.1:8010", "http://localhost:8010")

# The HTTP status for each error code (API.md section 8).
STATUS_FOR_CODE = {
    errors.INVALID_REQUEST: 400,
    errors.RECORD_NOT_FOUND: 404,
    errors.METHOD_NOT_ALLOWED: 405,
    errors.DUPLICATE_NAME: 409,
    errors.REVISION_CONFLICT: 409,
    errors.CAPACITY_LIMIT: 409,
    errors.PAYLOAD_TOO_LARGE: 413,
    errors.UNSUPPORTED_MEDIA_TYPE: 415,
    errors.PRECONDITION_REQUIRED: 428,
    errors.INTERNAL_ERROR: 500,
}

# The order in which the Allow header lists methods.
METHOD_ORDER = ("GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS")

logger = logging.getLogger(__name__)


def create_app(limits: Limits = Limits(), *, store: Storage | None = None,
               snapshot_clock: Callable[[], float] = time.monotonic,
               studio_origins: Iterable[str] = DEFAULT_STUDIO_ORIGINS) -> Flask:
    """Build the service around a new, empty in-memory store.

    The keyword arguments exist for tests: `store` replaces the backend (for
    example with one that fails on purpose), and `snapshot_clock` lets list
    snapshots expire without waiting.
    """
    snapshots = SnapshotRegistry(limits.max_snapshots, limits.snapshot_idle_seconds,
                                 clock=snapshot_clock)
    service = StudioService(store if store is not None else InMemoryStore(), limits,
                            snapshots=snapshots)

    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = limits.max_body_bytes
    # Paths match exactly (API.md section 1): "//" is not redirected to "/".
    # This must be set before the routes are added.
    app.url_map.merge_slashes = False
    _add_health_route(app)
    _add_program_routes(app, service, limits)
    _add_collection_routes(app, service, limits)
    _add_case_routes(app, service, limits)
    _add_options_and_cors(app, frozenset(studio_origins))
    _add_error_handlers(app, limits)
    return app


# ------------------------------------------------------------------ routes

def _add_health_route(app: Flask) -> None:

    @app.get(f"{API}/health")
    def health():
        no_query_parameters(query_arguments())
        return json_response(200, {"status": "ok", "version": API_VERSION})


def _add_program_routes(app: Flask, service: StudioService, limits: Limits) -> None:

    @app.post(f"{API}/programs")
    def create_program():
        program = service.create_program(checked_body(program_fields, limits))
        return program_response(201, program, location=f"{API}/programs/{program.id}")

    @app.get(f"{API}/programs")
    def list_programs():
        page = service.list_programs(page_request(query_arguments(), limits))
        return page_response(page, program_json)

    @app.get(f"{API}/programs/<program_id>")
    def get_program(program_id: str):
        no_query_parameters(query_arguments())
        return program_response(200, service.get_program(program_id))

    @app.put(f"{API}/programs/<program_id>")
    def replace_program(program_id: str):
        fields = checked_body(program_fields, limits)
        return program_response(200, service.replace_program(program_id, if_match(), fields))

    @app.delete(f"{API}/programs/<program_id>")
    def delete_program(program_id: str):
        no_query_parameters(query_arguments())
        service.delete_program(program_id, if_match())
        return no_content()


def _add_collection_routes(app: Flask, service: StudioService, limits: Limits) -> None:

    @app.post(f"{API}/collections")
    def create_collection():
        collection = service.create_collection(checked_body(collection_fields, limits))
        return collection_response(201, collection, location=f"{API}/collections/{collection.id}")

    @app.get(f"{API}/collections")
    def list_collections():
        page = service.list_collections(page_request(query_arguments(), limits))
        return page_response(page, collection_json)

    @app.get(f"{API}/collections/<collection_id>")
    def get_collection(collection_id: str):
        no_query_parameters(query_arguments())
        return collection_response(200, service.get_collection(collection_id))

    @app.put(f"{API}/collections/<collection_id>")
    def replace_collection(collection_id: str):
        fields = checked_body(collection_fields, limits)
        return collection_response(200, service.replace_collection(collection_id, if_match(), fields))

    @app.delete(f"{API}/collections/<collection_id>")
    def delete_collection(collection_id: str):
        no_query_parameters(query_arguments())
        service.delete_collection(collection_id, if_match())
        return no_content()


def _add_case_routes(app: Flask, service: StudioService, limits: Limits) -> None:
    """Case mutations answer with the whole parent collection and its new ETag."""

    @app.post(f"{API}/collections/<collection_id>/cases")
    def add_case(collection_id: str):
        fields = checked_body(case_fields, limits)
        return collection_response(201, service.add_case(collection_id, if_match(), fields))

    @app.put(f"{API}/collections/<collection_id>/cases/<case_id>")
    def replace_case(collection_id: str, case_id: str):
        fields = checked_body(case_fields, limits)
        return collection_response(200, service.replace_case(collection_id, case_id, if_match(), fields))

    @app.delete(f"{API}/collections/<collection_id>/cases/<case_id>")
    def delete_case(collection_id: str, case_id: str):
        no_query_parameters(query_arguments())
        return collection_response(200, service.delete_case(collection_id, case_id, if_match()))


# --------------------------------------------------------------- requests

class _DuplicateMember(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict:
    """json.loads hook: build an object, refusing a member name that repeats."""
    members = {}
    for name, value in pairs:
        if name in members:
            raise _DuplicateMember(name)
        members[name] = value
    return members


def _reject_constant(name: str) -> object:
    raise ValueError(f"{name} is not JSON")


def is_json_media_type(content_type: str | None) -> bool:
    """application/json in any letter case, with no charset or charset=utf-8."""
    if not content_type:
        return False
    media_type, options = parse_options_header(content_type)
    charset = options.get("charset")
    return media_type.lower() == "application/json" and (charset is None or charset.lower() == "utf-8")


def decode_json(raw: bytes) -> object:
    """The body as strict UTF-8 JSON (API.md section 1), or invalid_request."""
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_object_without_duplicates,
                          parse_constant=_reject_constant)
    except _DuplicateMember as duplicate:
        raise errors.invalid_request(None, "duplicate_member",
                                     f"Member {duplicate.name!r} appears more than once in one object.") from None
    # ValueError covers invalid UTF-8, JSON syntax errors (including a
    # byte-order mark), NaN/Infinity, and integers too long to convert.
    except (ValueError, RecursionError):
        raise errors.invalid_request(None, "malformed_json", "The request body is not valid JSON.") from None


def checked_body(validate: Callable[[object, Limits], object], limits: Limits):
    """Steps 3-6 of API.md section 9 for POST and PUT: media type, size, JSON,
    query parameters, then the body's fields."""
    if not is_json_media_type(request.headers.get("Content-Type")):
        raise ApiError(errors.UNSUPPORTED_MEDIA_TYPE,
                       "Request bodies must be sent with Content-Type: application/json.")
    body = decode_json(request.get_data(cache=False))   # 413 past MAX_CONTENT_LENGTH
    no_query_parameters(query_arguments())
    return validate(body, limits)


def query_arguments() -> dict[str, list[str]]:
    """Every query parameter with all of its values, in request order."""
    return {name: request.args.getlist(name) for name in request.args}


def if_match() -> IfMatch:
    return parse_if_match(request.headers.get("If-Match"))


# -------------------------------------------------------------- responses

def json_response(status: int, body: dict, *, revision: int | None = None,
                  location: str | None = None) -> Response:
    response = Response(json.dumps(body), status=status, mimetype="application/json")
    if revision is not None:
        response.headers["ETag"] = f'"{revision}"'
    if location is not None:
        response.headers["Location"] = location
    return response


def program_response(status: int, program: Program, location: str | None = None) -> Response:
    return json_response(status, {"program": program_json(program)},
                         revision=program.revision, location=location)


def collection_response(status: int, collection: Collection, location: str | None = None) -> Response:
    return json_response(status, {"collection": collection_json(collection)},
                         revision=collection.revision, location=location)


def page_response(page: Page, record_json: Callable[[object], dict]) -> Response:
    """A list page. It carries no ETag: each item has its own revision."""
    items = [record_json(record) for record in page.items]
    return json_response(200, {"items": items, "next_cursor": page.next_cursor})


def no_content() -> Response:
    response = Response(status=204)
    del response.headers["Content-Type"]   # no body, so no media type
    return response


def error_response(error: ApiError) -> Response:
    return json_response(STATUS_FOR_CODE[error.code], error.to_json())


def allow_header(methods: Iterable[str]) -> str:
    return ", ".join(method for method in METHOD_ORDER if method in methods)


# ----------------------------------------------------- OPTIONS and errors

def _add_options_and_cors(app: Flask, studio_origins: frozenset[str]) -> None:
    """OPTIONS answers (API.md section 1) and CORS headers (section 10)."""

    # Every method accepted on each path. Several rules can share a path,
    # one per method, so Flask's automatic OPTIONS rule alone would not
    # list them all.
    methods_by_path: dict[str, set[str]] = {}
    for rule in app.url_map.iter_rules():
        methods_by_path.setdefault(rule.rule, set()).update(rule.methods or ())

    @app.before_request
    def answer_options():
        if request.method == "OPTIONS" and request.url_rule is not None:
            response = no_content()
            response.headers["Allow"] = allow_header(methods_by_path[request.url_rule.rule])
            return response
        return None

    @app.after_request
    def add_cors_headers(response: Response) -> Response:
        response.vary.add("Origin")
        origin = request.headers.get("Origin")
        if origin in studio_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Expose-Headers"] = "ETag, Location"
            if request.method == "OPTIONS":
                response.headers["Access-Control-Allow-Methods"] = "GET, HEAD, POST, PUT, DELETE"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, If-Match"
                response.headers["Access-Control-Max-Age"] = "600"
        return response


def _add_error_handlers(app: Flask, limits: Limits) -> None:

    @app.errorhandler(ApiError)
    def api_error(error: ApiError):
        return error_response(error)

    @app.errorhandler(NotFound)
    def unknown_route(_error: NotFound):
        return error_response(ApiError(errors.RECORD_NOT_FOUND, "No API route matches this path."))

    @app.errorhandler(MethodNotAllowed)
    def wrong_method(error: MethodNotAllowed):
        response = error_response(ApiError(errors.METHOD_NOT_ALLOWED,
                                           f"{request.method} is not allowed on this route."))
        response.headers["Allow"] = allow_header(error.valid_methods or ())
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def body_too_large(_error: RequestEntityTooLarge):
        return error_response(ApiError(errors.PAYLOAD_TOO_LARGE,
                                       f"Request bodies are limited to {limits.max_body_bytes} bytes.",
                                       limit=limits.max_body_bytes))

    @app.errorhandler(Exception)
    def unexpected_failure(error: Exception):
        # Any other exception, including an HTTP error the contract does not
        # define, is a bug. The traceback goes to the server log only.
        logger.error("Unexpected failure in %s %s", request.method, request.path, exc_info=error)
        return error_response(ApiError(errors.INTERNAL_ERROR,
                                       "The service failed unexpectedly. The failure was logged."))
