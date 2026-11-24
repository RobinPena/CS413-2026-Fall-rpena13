"""The API error codes (API.md section 8) and the exception that carries one.

Any layer raises ApiError to end a request with a documented error. The
error knows its stable code, a human-readable message, and any extra members
(field, reason, limit, ...). It does not know HTTP status codes; the HTTP
layer maps each code to its status.
"""
from __future__ import annotations

INVALID_REQUEST = "invalid_request"
RECORD_NOT_FOUND = "record_not_found"
METHOD_NOT_ALLOWED = "method_not_allowed"
DUPLICATE_NAME = "duplicate_name"
REVISION_CONFLICT = "revision_conflict"
CAPACITY_LIMIT = "capacity_limit"
PAYLOAD_TOO_LARGE = "payload_too_large"
UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
PRECONDITION_REQUIRED = "precondition_required"
INTERNAL_ERROR = "internal_error"


class ApiError(Exception):
    """A documented API error: a stable code, a message, and extra members."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_json(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, **self.details}}


def invalid_request(field: str | None, reason: str, message: str, **extra: object) -> ApiError:
    """400 invalid_request; field names the body field, parameter, or header at fault."""
    return ApiError(INVALID_REQUEST, message, field=field, reason=reason, **extra)


def record_not_found(kind: str, record_id: str) -> ApiError:
    return ApiError(RECORD_NOT_FOUND, f"No {kind} has ID {record_id!r}.")


def case_not_found(case_id: str) -> ApiError:
    return ApiError(RECORD_NOT_FOUND, f"No case has ID {case_id!r} in this collection.")


def duplicate_name(kind: str, name: str) -> ApiError:
    return ApiError(DUPLICATE_NAME, f"Another {kind} is already named {name!r}.", field="name")


def revision_conflict(kind: str, sent: int, current: int) -> ApiError:
    return ApiError(REVISION_CONFLICT,
                    f'If-Match "{sent}" is stale; the {kind} is at revision {current}.',
                    current_revision=current)


def precondition_required() -> ApiError:
    return ApiError(PRECONDITION_REQUIRED,
                    "This request requires If-Match with the record's current ETag.")


def malformed_if_match() -> ApiError:
    return invalid_request("If-Match", "malformed_if_match",
                           'If-Match must be one quoted revision number, such as "3".')


def capacity_limit(resource: str, limit: int, message: str) -> ApiError:
    return ApiError(CAPACITY_LIMIT, message, resource=resource, limit=limit)
