"""The service's RPC methods and their parameter rules (RPC.md section 3).

    build_methods(config) -> {method name: callable(params) -> result}

Each method checks its params and either returns a result object or raises
RpcError. The JSON-RPC envelope is the dispatcher's concern, not this module's.
The three lambda.* methods hand the checked source to a worker process
(worker.py) and turn its outcome into a result or a LAMBDA error code.
"""
from __future__ import annotations

from collections.abc import Callable, Collection, Mapping

from . import worker
from .errors import (
    EXECUTION_TIMEOUT, INVALID_PARAMS, LAMBDA_RUNTIME_ERROR, LAMBDA_SYNTAX_ERROR,
    LAMBDA_TYPE_ERROR, RpcError,
)
from .rpc import Method

API_VERSION = "1.0"
DEFAULT_MAX_SOURCE_BYTES = 65_536
TARGETS = ("python", "javascript")

_LANGUAGE_ERRORS = {
    "syntax_error": LAMBDA_SYNTAX_ERROR,
    "type_error": LAMBDA_TYPE_ERROR,
    "runtime_error": LAMBDA_RUNTIME_ERROR,
}


def invalid_params(param: str | None, reason: str, **details: object) -> RpcError:
    return RpcError(INVALID_PARAMS, {"param": param, "reason": reason, **details})


def require_named_params(params: dict | list | None, allowed: Collection[str]) -> dict:
    """Return params as a dict, rejecting absent, positional or unexpected params."""
    if params is None:
        raise invalid_params(None, "params_required")
    if not isinstance(params, dict):
        raise invalid_params(None, "params_not_object")
    if not params.keys() <= set(allowed):
        raise invalid_params(None, "unexpected_param", allowed=sorted(allowed))
    return params


def require_source(params: dict, max_bytes: int) -> str:
    """The source param, unchanged, after the checks of RPC.md section 3."""
    if "source" not in params:
        raise invalid_params("source", "missing")
    source = params["source"]
    if not isinstance(source, str):
        raise invalid_params("source", "wrong_type")
    try:
        size = len(source.encode("utf-8"))
    except UnicodeEncodeError:  # an unpaired surrogate such as "\ud800"
        raise invalid_params("source", "invalid_text") from None
    if size > max_bytes:
        raise invalid_params("source", "too_large", limit_bytes=max_bytes, size_bytes=size)
    if not source.strip():
        raise invalid_params("source", "blank")
    return source


def require_target(params: dict) -> str:
    if "target" not in params:
        raise invalid_params("target", "missing")
    target = params["target"]
    if not isinstance(target, str):
        raise invalid_params("target", "wrong_type")
    if target not in TARGETS:
        raise invalid_params("target", "unsupported_target", allowed=list(TARGETS))
    return target


def health(params: dict | list | None) -> dict:
    require_named_params(params, allowed=())
    return {"status": "ok", "version": API_VERSION}


def build_methods(
    config: Mapping[str, object],
    *,
    worker_entry: Callable[..., None] | None = None,
) -> dict[str, Method]:
    """The method table for an app configured with config.

    Config keys: DEADLINE_SECONDS and MAX_SOURCE_BYTES (RPC.md section 5).
    worker_entry replaces the worker's entry point (tests only).
    """
    deadline = float(config.get("DEADLINE_SECONDS", worker.DEFAULT_DEADLINE_SECONDS))
    max_source_bytes = int(config.get("MAX_SOURCE_BYTES", DEFAULT_MAX_SOURCE_BYTES))

    def run(operation: str, source: str, target: str | None = None) -> dict:
        outcome = worker.run(operation, source, target,
                             deadline_seconds=deadline, entry=worker_entry)
        if outcome["kind"] == "result":
            return outcome["result"]
        if outcome["kind"] == "timeout":
            raise RpcError(EXECUTION_TIMEOUT, {"limit_seconds": deadline})
        raise RpcError(_LANGUAGE_ERRORS[outcome["kind"]], outcome["data"])

    def typecheck(params: dict | list | None) -> dict:
        params = require_named_params(params, allowed=("source",))
        return run("typecheck", require_source(params, max_source_bytes))

    def interpret(params: dict | list | None) -> dict:
        params = require_named_params(params, allowed=("source",))
        return run("interpret", require_source(params, max_source_bytes))

    def compile_(params: dict | list | None) -> dict:
        params = require_named_params(params, allowed=("source", "target"))
        source = require_source(params, max_source_bytes)
        return run("compile", source, require_target(params))

    return {
        "service.health": health,
        "lambda.typecheck": typecheck,
        "lambda.interpret": interpret,
        "lambda.compile": compile_,
    }
