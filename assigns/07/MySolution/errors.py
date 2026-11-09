"""JSON-RPC error codes, their fixed messages, and the exception that carries one.

Any layer can raise RpcError to end a call with a documented error; the
dispatcher turns it into a response object. The codes and messages are the
ones listed in RPC.md section 4.
"""
from __future__ import annotations

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
LAMBDA_SYNTAX_ERROR = -32010
LAMBDA_TYPE_ERROR = -32011
EXECUTION_TIMEOUT = -32012
LAMBDA_RUNTIME_ERROR = -32013

MESSAGES = {
    PARSE_ERROR: "Parse error",
    INVALID_REQUEST: "Invalid Request",
    METHOD_NOT_FOUND: "Method not found",
    INVALID_PARAMS: "Invalid params",
    INTERNAL_ERROR: "Internal error",
    LAMBDA_SYNTAX_ERROR: "LAMBDA syntax error",
    LAMBDA_TYPE_ERROR: "LAMBDA type error",
    EXECUTION_TIMEOUT: "Execution timed out",
    LAMBDA_RUNTIME_ERROR: "LAMBDA runtime error",
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
