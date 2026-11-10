"""Worker entry points that fail on purpose, for the failure tests.

Each has the signature of MySolution.worker.worker_main and is passed to
build_methods(worker_entry=...). They run inside the spawned worker process,
so the failure really happens in the child; nothing is patched in the parent.
"""
import os
import signal
import time
from pathlib import Path

from MySolution import worker

SECRET = "secret detail from /Users/example/lambda3.py"


def hang(conn, lambda3_dir, operation, source, target):
    """Never answer and ignore SIGTERM, so the parent must escalate to kill.

    source is a file path: the worker writes its process id there so the
    test can check afterwards that the process is gone.
    """
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    Path(source).write_text(str(os.getpid()))
    while True:
        time.sleep(60)


def exit_without_outcome(conn, lambda3_dir, operation, source, target):
    """Die at once without sending anything, as a crashed worker would."""
    os._exit(3)


def compiler_raises(conn, lambda3_dir, operation, source, target):
    """The real worker, except that LAMBDA3's Python compiler fails unexpectedly."""
    lambda3 = worker.load_lambda3(lambda3_dir)

    def broken_compile(expression):
        raise RuntimeError(SECRET)

    lambda3.d0exp_compile = broken_compile
    worker.worker_main(conn, lambda3_dir, operation, source, target)
