"""JSON-RPC error codes, their fixed messages, and the exception that carries one.

Any layer can raise RpcError to end a call with a documented error; the
dispatcher turns it into a response object. The codes and messages are the
ones listed in DESIGN.md section 7.5. Adapted from Assign07's errors.py.
"""
from __future__ import annotations

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
STREAM_NOT_FOUND = -32020
TOO_MANY_STREAMS = -32021

MESSAGES = {
    PARSE_ERROR: "Parse error",
    INVALID_REQUEST: "Invalid Request",
    METHOD_NOT_FOUND: "Method not found",
    INVALID_PARAMS: "Invalid params",
    INTERNAL_ERROR: "Internal error",
    STREAM_NOT_FOUND: "Stream not found",
    TOO_MANY_STREAMS: "Too many open streams",
}


class RpcError(Exception):
    """A documented JSON-RPC error: a code from MESSAGES plus optional data."""

    def __init__(self, code: int, data: dict | None = None):
        super().__init__(MESSAGES[code])
        self.code = code
        self.data = data

    def to_object(self) -> dict:
        """The JSON-RPC error object; data is left out when there is none."""
        error = {"code": self.code, "message": MESSAGES[self.code]}
        if self.data is not None:
            error["data"] = self.data
        return error
