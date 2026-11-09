"""JSON-RPC 2.0 processing: decoding, envelope checks, dispatch and batches.

    Dispatcher(methods).handle_body(body: bytes) -> response value | None

This module knows nothing about HTTP or LAMBDA3. It turns the raw bytes of a
request body into the value to send back: a response object, a list of
response objects for a batch, or None when no response is due (a single
notification, or a batch whose members are all notifications).

A method is any callable that takes the request's params (a dict, a list, or
None when the member is absent) and returns a JSON-serializable result. It
reports a documented failure by raising RpcError. Any other exception becomes
an Internal error; its details are logged under an incident id and never
returned to the client.
"""
from __future__ import annotations

import json
import logging
import math
import secrets
from collections.abc import Callable, Mapping

from .errors import (
    INTERNAL_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, PARSE_ERROR, RpcError,
)

MAX_BATCH_SIZE = 20

_ENVELOPE_MEMBERS = frozenset({"jsonrpc", "method", "params", "id"})

logger = logging.getLogger(__name__)

Method = Callable[[dict | list | None], object]


class _UnsupportedNumber(Exception):
    """A number that is not JSON or cannot be represented and echoed back."""


def _reject_constant(name: str) -> float:
    raise _UnsupportedNumber(name)


def _parse_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise _UnsupportedNumber(text)
    return value


def _parse_int(text: str) -> int:
    try:
        return int(text)
    except ValueError:  # more digits than Python will convert (4,300 by default)
        raise _UnsupportedNumber(text) from None


def decode_body(body: bytes) -> object:
    """Decode a request body as strict UTF-8 JSON, or raise a Parse error."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise RpcError(PARSE_ERROR, {"reason": "invalid_utf8"}) from None
    try:
        return json.loads(
            text,
            parse_constant=_reject_constant,
            parse_float=_parse_float,
            parse_int=_parse_int,
        )
    except _UnsupportedNumber:
        raise RpcError(PARSE_ERROR, {"reason": "unsupported_number"}) from None
    except json.JSONDecodeError as error:
        raise RpcError(PARSE_ERROR, {
            "reason": "invalid_json", "line": error.lineno, "column": error.colno,
        }) from None
    except RecursionError:
        raise RpcError(PARSE_ERROR, {"reason": "nesting_too_deep"}) from None


def is_valid_id(value: object) -> bool:
    """A JSON-RPC id is a string, a number or null; a boolean is not a number."""
    if isinstance(value, bool):
        return False
    return value is None or isinstance(value, (str, int, float))


def envelope_problem(request: object) -> str | None:
    """The reason a request object fails the envelope checks, or None if it passes."""
    if not isinstance(request, dict):
        return "not_an_object"
    if not request.keys() <= _ENVELOPE_MEMBERS:
        return "unexpected_member"
    if request.get("jsonrpc") != "2.0":
        return "bad_jsonrpc"
    if not isinstance(request.get("method"), str):
        return "bad_method"
    if "params" in request and not isinstance(request["params"], (dict, list)):
        return "bad_params"
    if "id" in request and not is_valid_id(request["id"]):
        return "bad_id"
    return None


def error_response(error: RpcError, request_id: object = None) -> dict:
    return {"jsonrpc": "2.0", "error": error.to_object(), "id": request_id}


def success_response(result: object, request_id: object) -> dict:
    return {"jsonrpc": "2.0", "result": result, "id": request_id}


class Dispatcher:
    """Answers JSON-RPC request bodies using a table of named methods."""

    def __init__(self, methods: Mapping[str, Method], max_batch_size: int = MAX_BATCH_SIZE):
        self.methods = dict(methods)
        self.max_batch_size = max_batch_size

    def handle_body(self, body: bytes) -> dict | list | None:
        try:
            payload = decode_body(body)
        except RpcError as error:
            return error_response(error)
        if not isinstance(payload, list):
            return self.handle_request(payload)
        if not payload:
            return error_response(RpcError(INVALID_REQUEST, {"reason": "empty_batch"}))
        if len(payload) > self.max_batch_size:
            return error_response(RpcError(INVALID_REQUEST, {
                "reason": "batch_too_large", "limit": self.max_batch_size,
            }))
        responses = [self.handle_request(member) for member in payload]
        return [response for response in responses if response is not None] or None

    def handle_request(self, request: object) -> dict | None:
        """Process one request object; None means it was a notification."""
        problem = envelope_problem(request)
        if problem is not None:
            return error_response(RpcError(INVALID_REQUEST, {"reason": problem}))
        response = self._call(request["method"], request.get("params"), request.get("id"))
        return response if "id" in request else None

    def _call(self, name: str, params: dict | list | None, request_id: object) -> dict:
        try:
            method = self.methods.get(name)
            if method is None:
                raise RpcError(METHOD_NOT_FOUND)
            return success_response(method(params), request_id)
        except RpcError as error:
            return error_response(error, request_id)
        except Exception:
            incident = secrets.token_hex(6)
            logger.exception("Internal error, incident %s, method %.100r", incident, name)
            return error_response(RpcError(INTERNAL_ERROR, {"incident": incident}), request_id)
