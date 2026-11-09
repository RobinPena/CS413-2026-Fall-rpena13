"""The service's RPC methods and their parameter rules (RPC.md section 3).

    build_methods(config) -> {method name: callable(params) -> result}

Each method checks its params and either returns a result object or raises
RpcError. The JSON-RPC envelope is the dispatcher's concern, not this module's.
"""
from __future__ import annotations

from collections.abc import Collection, Mapping

from .errors import INVALID_PARAMS, RpcError
from .rpc import Method

API_VERSION = "1.0"


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


def health(params: dict | list | None) -> dict:
    require_named_params(params, allowed=())
    return {"status": "ok", "version": API_VERSION}


def build_methods(config: Mapping[str, object]) -> dict[str, Method]:
    """The method table for an app configured with config."""
    return {"service.health": health}
