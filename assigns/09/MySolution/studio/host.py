"""The studio host's routes.

    create_studio_app(lambda_url, database_url, *, timeout=10.0) -> Flask app

    GET  /              the studio page (static/index.html)
    GET  /static/...    its stylesheet and JavaScript modules
    GET  /config.json   {"database_url": ...}: where the page finds the database API
    POST /lambda/rpc    forwarded unchanged to the LAMBDA3 service at lambda_url

The forwarder holds no LAMBDA logic. It copies the request body and
Content-Type to LAMBDA3 and copies LAMBDA3's status, Content-Type, and body
back. When LAMBDA3 cannot be reached it answers 502 (or 504 after
`timeout` seconds) with a short plain-text explanation. The page treats any
answer other than 200 as a transport failure, never as a LAMBDA result.
"""
from __future__ import annotations

import logging
import urllib.error
import urllib.request

from flask import Flask, Response, request

MAX_BODY_BYTES = 1_048_576          # the same request limit as the LAMBDA3 service
MAX_REPLY_BYTES = 16 * 1_048_576    # a LAMBDA3 answer larger than this is refused

logger = logging.getLogger(__name__)

# Never send local LAMBDA3 calls through an HTTP proxy from the environment.
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def create_studio_app(lambda_url: str, database_url: str, *, timeout: float = 10.0) -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/config.json")
    def config():
        return {"database_url": database_url}

    @app.post("/lambda/rpc")
    def forward_to_lambda3():
        body = request.get_data(cache=False)            # 413 past MAX_BODY_BYTES
        return forward(lambda_url, body, request.headers.get("Content-Type"), timeout)

    return app


def forward(url: str, body: bytes, content_type: str | None, timeout: float) -> Response:
    """POST body to url and relay the answer, or explain why there is none."""
    headers = {"Content-Type": content_type} if content_type else {}
    upstream = urllib.request.Request(url, data=body, headers=headers, method="POST")
    too_slow = f"the LAMBDA3 service at {url} did not answer within {timeout:g} seconds"
    try:
        with _opener.open(upstream, timeout=timeout) as reply:
            return relay(reply.status, reply.headers.get("Content-Type"), read_bounded(reply))
    except urllib.error.HTTPError as error:       # LAMBDA3 answered 4xx/5xx: relay it (short text)
        with error:
            return relay(error.code, error.headers.get("Content-Type"), error.read(MAX_REPLY_BYTES))
    except urllib.error.URLError as error:        # no connection
        if isinstance(error.reason, TimeoutError):
            return gateway_error(504, too_slow)
        return gateway_error(502, f"the LAMBDA3 service at {url} could not be reached ({error.reason})")
    except TimeoutError:                          # connected, but no answer in time
        return gateway_error(504, too_slow)
    except (OSError, ValueError) as error:        # connection dropped, or the answer was too large
        return gateway_error(502, f"the LAMBDA3 service at {url} sent no usable answer ({error})")


def read_bounded(reply) -> bytes:
    data = reply.read(MAX_REPLY_BYTES + 1)
    if len(data) > MAX_REPLY_BYTES:
        raise ValueError(f"the answer was larger than {MAX_REPLY_BYTES} bytes")
    return data


def relay(status: int, content_type: str | None, body: bytes) -> Response:
    response = Response(body, status=status)
    if status == 204 or not content_type:
        del response.headers["Content-Type"]
    else:
        response.headers["Content-Type"] = content_type
    return response


def gateway_error(status: int, explanation: str) -> Response:
    logger.warning("LAMBDA3 forwarding failed: %s", explanation)
    title = "Bad Gateway" if status == 502 else "Gateway Timeout"
    return Response(f"{status} {title}: {explanation}.\n", status=status, mimetype="text/plain")
