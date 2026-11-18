"""HTTP transport: POST /rpc, plus the browser client (DESIGN.md section 7.1).

    create_app(config=None, *, table=None, methods=None) -> Flask app

The transport checks only HTTP concerns (path, HTTP method, media type, body
size) and hands the raw body to the JSON-RPC dispatcher. Every dispatcher
answer is sent with HTTP 200, and "no answer" (a notification) with an empty
204. Transport failures get their HTTP status and a short plain-text body,
never a JSON-RPC body. GET / and GET /static/* serve the client from static/.
Adapted from Assign07's app.py.
"""
from __future__ import annotations

import json
from collections.abc import Mapping

from flask import Flask, Response, request
from werkzeug.exceptions import HTTPException
from werkzeug.http import parse_options_header

from .methods import build_methods
from .rpc import Dispatcher, Method
from .streams import DEFAULT_TTL_SECONDS, StreamTable

MAX_BODY_BYTES = 65_536

_UNSUPPORTED_MEDIA_TYPE = (
    "415 Unsupported Media Type: POST /rpc requires "
    "Content-Type: application/json (UTF-8).\n"
)


def is_json_media_type(content_type: str | None) -> bool:
    """application/json, in any letter case, with no charset or charset utf-8."""
    if not content_type:
        return False
    mimetype, options = parse_options_header(content_type)
    charset = options.get("charset")
    return mimetype.lower() == "application/json" and (
        charset is None or charset.lower() == "utf-8"
    )


def plain_text(status: int, text: str) -> Response:
    return Response(text, status=status, mimetype="text/plain")


def create_app(
    config: Mapping[str, object] | None = None,
    *,
    table: StreamTable | None = None,
    methods: Mapping[str, Method] | None = None,
) -> Flask:
    """Build the service.

    table replaces the stream table (tests inject a fake clock this way), and
    methods replaces the whole method table (tests only). The table in use is
    available as app.extensions["queens_streams"].
    """
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES
    app.config["STREAM_TTL_SECONDS"] = DEFAULT_TTL_SECONDS
    app.config.update(config or {})
    if table is None:
        table = StreamTable(ttl=app.config["STREAM_TTL_SECONDS"])
    app.extensions["queens_streams"] = table
    dispatcher = Dispatcher(build_methods(table) if methods is None else methods)

    @app.errorhandler(HTTPException)
    def transport_error(error: HTTPException) -> Response:
        response = error.get_response()  # keeps headers such as Allow on 405
        response.set_data(f"{error.code} {error.name}\n")
        response.mimetype = "text/plain"
        return response

    @app.post("/rpc", provide_automatic_options=False)
    def rpc() -> Response:
        if not is_json_media_type(request.headers.get("Content-Type")):
            return plain_text(415, _UNSUPPORTED_MEDIA_TYPE)
        answer = dispatcher.handle_body(request.get_data(cache=False))  # 413 past the limit
        if answer is None:
            response = Response(status=204)
            del response.headers["Content-Type"]  # no body, so no media type
            return response
        return Response(json.dumps(answer, allow_nan=False), status=200,
                        mimetype="application/json")

    @app.get("/")
    def index() -> Response:
        return app.send_static_file("index.html")

    return app
