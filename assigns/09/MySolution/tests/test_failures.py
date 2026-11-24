"""Unexpected failures become a sanitized 500 internal_error (API.md section 8).

A store that fails on purpose stands in for a bug. The data the tests use
is still created through the public API; only the failure is injected.
"""
from __future__ import annotations

import unittest

from werkzeug.exceptions import BadRequest

from MySolution.store import InMemoryStore

from .http_support import ApiTestCase

SECRET = "token=hunter2 at /Users/someone/MySolution/store.py line 42"
LEAKS = ("Traceback", "RuntimeError", "BadRequest", "hunter2", "/Users", ".py", "line 42")


class FailingStore(InMemoryStore):
    """Raises an internal exception, with details that must never reach a client,
    from the operation named in `fail_on`."""

    def __init__(self) -> None:
        super().__init__()
        self.fail_on: str | None = None
        self.exception: Exception = RuntimeError(SECRET)

    def _maybe_fail(self, operation: str) -> None:
        if self.fail_on == operation:
            raise self.exception

    def all_programs(self):
        self._maybe_fail("all_programs")
        return super().all_programs()

    def save_program(self, program):
        self._maybe_fail("save_program")
        super().save_program(program)


class InternalErrorTests(ApiTestCase):

    def app_options(self):
        self.store = FailingStore()
        return {"store": self.store}

    def assertSanitized500(self, response) -> None:
        error = self.assertError(response, 500, "internal_error")
        self.assertEqual(error, {"code": "internal_error",
                                 "message": "The service failed unexpectedly. The failure was logged."})
        for leak in LEAKS:
            self.assertNotIn(leak.encode(), response.data)

    def test_failure_is_a_sanitized_json_500_and_is_logged(self):
        self.store.fail_on = "all_programs"
        with self.assertLogs("MySolution.app", "ERROR") as logs:
            self.assertSanitized500(self.api("GET", "/programs"))
        # The details go to the server log, not to the client.
        self.assertIn("Unexpected failure in GET /api/v1/programs", logs.output[0])
        self.assertIn(SECRET, logs.output[0])
        self.assertIn("Traceback", logs.output[0])

    def test_an_undocumented_http_error_is_also_an_internal_error(self):
        self.store.fail_on = "all_programs"
        self.store.exception = BadRequest(SECRET)
        with self.assertLogs("MySolution.app", "ERROR"):
            self.assertSanitized500(self.api("GET", "/programs"))

    def test_failed_mutation_changes_nothing_and_the_service_keeps_working(self):
        program = self.create_program("p")
        self.store.fail_on = "save_program"
        with self.assertLogs("MySolution.app", "ERROR"):
            self.assertSanitized500(self.api("PUT", f"/programs/{program['id']}",
                                             {"name": "p", "source": "changed"}, if_match='"1"'))
            self.assertSanitized500(self.api("POST", "/programs", {"name": "q", "source": "1"}))
        self.store.fail_on = None
        # The store lock was released and nothing was half-written.
        self.assertUnchanged(f"/programs/{program['id']}", program)
        self.assertEqual([p["name"] for p in self.api("GET", "/programs").json["items"]], ["p"])
        self.assertEqual(self.api("POST", "/programs", {"name": "q", "source": "1"}).status_code, 201)


if __name__ == "__main__":
    unittest.main()
