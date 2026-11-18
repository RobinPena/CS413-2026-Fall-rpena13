"""The four RPC methods and their parameter validation (DESIGN.md section 7.3).

    build_methods(table) -> {"service.health": ..., "queens.open": ..., ...}

Every check here runs before the stream table is touched, so invalid params
never allocate a stream. A method takes the request's params (dict, list or
None) and returns its JSON result, or raises RpcError(INVALID_PARAMS, data)
with data naming the field and the reason.
"""
from __future__ import annotations

from .errors import INVALID_PARAMS, RpcError
from .lambda_adapter import MAX_SIZE, MIN_SIZE
from .streams import StreamTable

MIN_LIMIT = 1
MAX_LIMIT = 32

VERSION = "1.0"


def invalid(field: str | None, reason: str, **details) -> RpcError:
    data = {"reason": reason, **details} if field is None else {"field": field, "reason": reason, **details}
    return RpcError(INVALID_PARAMS, data)


def params_object(params: dict | list | None, fields: tuple[str, ...]) -> dict:
    """params as a dict with no keys outside fields; absent params count as {}."""
    if params is None:
        return {}
    if not isinstance(params, dict):
        raise invalid(None, "not_an_object")
    unexpected = sorted(set(params) - set(fields))
    if unexpected:
        raise invalid(None, "unexpected", fields=unexpected)
    return params


def integer(params: dict, field: str, minimum: int, maximum: int) -> int:
    """A required JSON integer in [minimum, maximum]; booleans and floats are refused."""
    if field not in params:
        raise invalid(field, "missing")
    value = params[field]
    if isinstance(value, bool) or not isinstance(value, int):
        raise invalid(field, "not_an_integer")
    if not minimum <= value <= maximum:
        raise invalid(field, "out_of_range", minimum=minimum, maximum=maximum)
    return value


def string(params: dict, field: str) -> str:
    if field not in params:
        raise invalid(field, "missing")
    value = params[field]
    if not isinstance(value, str):
        raise invalid(field, "not_a_string")
    return value


def build_methods(table: StreamTable) -> dict:
    def health(params):
        params_object(params, ())
        return {"status": "ok", "version": VERSION}

    def queens_open(params):
        params = params_object(params, ("size",))
        return table.open(integer(params, "size", MIN_SIZE, MAX_SIZE))

    def queens_next(params):
        params = params_object(params, ("stream_id", "limit"))
        stream_id = string(params, "stream_id")
        limit = integer(params, "limit", MIN_LIMIT, MAX_LIMIT)
        return table.next(stream_id, limit)

    def queens_close(params):
        params = params_object(params, ("stream_id",))
        return table.close(string(params, "stream_id"))

    return {
        "service.health": health,
        "queens.open": queens_open,
        "queens.next": queens_next,
        "queens.close": queens_close,
    }
