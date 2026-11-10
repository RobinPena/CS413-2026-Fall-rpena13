"""Deadlines, worker failures and internal errors (RPC.md sections 4 and 5).

The timeout tests use the real worker and real LAMBDA3 programs that run past
the deadline. The other tests swap in a worker entry point from
worker_doubles, which still runs in a real spawned process under the real
supervisor in MySolution.worker.
"""
import json
import logging
import multiprocessing
import os
import tempfile
import time
from pathlib import Path

from MySolution import worker
from MySolution.service import build_methods
from MySolution.tests import worker_doubles
from MySolution.tests.support import FACTORIAL, FIB_26, RpcTestCase, request_object

LEAKS = (b"Traceback", b"RuntimeError", b"/Users", b".py", b"secret")

# Unannotated, nested self-application: each level doubles the inferred type.
TYPE_BLOWUP = "(lam (x) => (x, x))(" * 18 + "1" + ")" * 18


class TimeoutTests(RpcTestCase):
    def test_slow_interpretation_times_out(self):
        started = time.monotonic()
        answer = self.call("lambda.interpret", {"source": FIB_26}, "slow")
        elapsed = time.monotonic() - started
        error = self.assert_error(answer, "slow", -32012)
        self.assertEqual(error["data"], {"limit_seconds": 2.0})
        self.assertGreaterEqual(elapsed, 2.0)
        self.assertLess(elapsed, 3.5)
        self.assertEqual(multiprocessing.active_children(), [])

    def test_service_answers_after_a_timeout(self):
        self.assert_error(self.call("lambda.interpret", {"source": FIB_26}, 1), 1, -32012)
        result = self.assert_result(self.call("lambda.interpret", {"source": FACTORIAL}, 2), 2)
        self.assertEqual(result, {"type": "sint", "value": "720"})

    def test_slow_type_checking_times_out(self):
        self.assertLess(len(TYPE_BLOWUP.encode()), 400)
        self.assert_error(self.call("lambda.typecheck", {"source": TYPE_BLOWUP}, "tc"), "tc", -32012)


class ConfiguredDeadlineTests(RpcTestCase):
    app_config = {"DEADLINE_SECONDS": 0.5}

    def test_deadline_comes_from_the_app_config(self):
        started = time.monotonic()
        error = self.assert_error(self.call("lambda.interpret", {"source": FIB_26}, 1), 1, -32012)
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertEqual(error["data"], {"limit_seconds": 0.5})


class HungWorkerTests(RpcTestCase):
    """A worker that ignores SIGTERM: the supervisor has to kill it."""

    DEADLINE = 0.5
    methods = build_methods({"DEADLINE_SECONDS": DEADLINE}, worker_entry=worker_doubles.hang)

    def run_hung(self, request_id=None) -> tuple[float, int, tuple]:
        """Send one call (or a notification); return (elapsed, worker pid, answer)."""
        with tempfile.TemporaryDirectory() as directory:
            pid_file = Path(directory) / "worker.pid"
            started = time.monotonic()
            if request_id is None:
                answer = self.decode(self.post_raw(json.dumps(
                    request_object("lambda.interpret", {"source": str(pid_file)})).encode()))
            else:
                answer = self.call("lambda.interpret", {"source": str(pid_file)}, request_id)
            elapsed = time.monotonic() - started
            return elapsed, int(pid_file.read_text()), answer

    def assert_killed(self, elapsed: float, pid: int) -> None:
        # Terminate is ignored, so the worker lives through the grace period until the kill.
        self.assertGreaterEqual(elapsed, self.DEADLINE + worker.GRACE_SECONDS)
        self.assertLess(elapsed, self.DEADLINE + worker.GRACE_SECONDS + 1.5)
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)  # no such process: it was killed and reaped

    def test_hung_worker_is_killed_and_the_call_times_out(self):
        elapsed, pid, answer = self.run_hung(request_id=0)
        error = self.assert_error(answer, 0, -32012)
        self.assertEqual(error["data"], {"limit_seconds": self.DEADLINE})
        self.assert_killed(elapsed, pid)

    def test_notification_runs_under_the_same_deadline(self):
        elapsed, pid, answer = self.run_hung()
        self.assertEqual(answer, (204, None))
        self.assert_killed(elapsed, pid)


class InternalErrorTestCase(RpcTestCase):
    def call_logged(self, method: str, params: dict, request_id: object) -> logging.LogRecord:
        """Expect a -32603 that leaks nothing; return the server's log record for it."""
        with self.assertLogs("MySolution.rpc", level="ERROR") as logs:
            response = self.post_raw(json.dumps(request_object(method, params, request_id)).encode())
        error = self.assert_error(self.decode(response), request_id, -32603)
        self.assertEqual(error["message"], "Internal error")
        self.assertRegex(error["data"]["incident"], r"^[0-9a-f]{12}$")
        for leak in LEAKS:
            self.assertNotIn(leak, response.data)
        record = logs.records[0]
        self.assertIn(error["data"]["incident"], record.getMessage())
        return record


class CrashedWorkerTests(InternalErrorTestCase):
    methods = build_methods({}, worker_entry=worker_doubles.exit_without_outcome)

    def test_worker_that_exits_without_an_outcome(self):
        record = self.call_logged("lambda.interpret", {"source": "1 + 2"}, "crash")
        self.assertIsInstance(record.exc_info[1], worker.WorkerFailure)
        self.assertIn("exited with code 3", str(record.exc_info[1]))


class BackendExceptionTests(InternalErrorTestCase):
    methods = build_methods({}, worker_entry=worker_doubles.compiler_raises)

    def test_unexpected_backend_exception_in_the_worker(self):
        record = self.call_logged("lambda.compile", {"source": "1 + 2", "target": "python"}, 5)
        # The log has the details, from the traceback the child sent back.
        details = str(record.exc_info[1])
        self.assertIn(f"RuntimeError: {worker_doubles.SECRET}", details)
        self.assertIn("broken_compile", details)

    def test_other_operations_still_work(self):
        result = self.assert_result(
            self.call("lambda.compile", {"source": "1 + 2", "target": "javascript"}, 6), 6)
        self.assertEqual(result["target"], "javascript")
