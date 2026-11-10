"""Run one LAMBDA3 operation in a fresh worker process under a deadline (RPC.md sections 3 and 5).

    run(operation, source, target=None, *, deadline_seconds) -> outcome dict

operation is "typecheck", "interpret" or "compile" (compile also takes target
"python" or "javascript"). The outcome is one of

    {"kind": "result", "result": {...}}       the method's result object
    {"kind": "syntax_error", "data": {...}}   LambdaSyntaxError while parsing
    {"kind": "type_error", "data": {...}}     TypeCheckError while type checking
    {"kind": "runtime_error", "data": {...}}  a failure the type checker cannot rule out
    {"kind": "timeout"}                       the deadline expired first

and contains only strings and integers. Anything else (a worker that dies
without a result, or an exception that LAMBDA3's errors do not explain)
raises WorkerFailure, whose message is for the server log only.

The worker is a spawned process, so it starts with a fresh interpreter and
loads LAMBDA3 from this assignment's LAMBDA3 directory by absolute path. The
parent stops it when the deadline expires: terminate, then kill if it is still
alive after a grace period, then wait for it to exit.
"""
from __future__ import annotations

import multiprocessing
import os
import sys
import time
import traceback
from collections.abc import Callable
from multiprocessing.connection import Connection
from pathlib import Path

LAMBDA3_DIR = (Path(__file__).resolve().parent.parent / "LAMBDA3").resolve()

DEFAULT_DEADLINE_SECONDS = 2.0
GRACE_SECONDS = 0.5
MAX_DIAGNOSTIC_CHARS = 1000

_NO_PAYLOAD = object()


class WorkerFailure(Exception):
    """The worker ended without a usable outcome; the message is for the log."""


def run(
    operation: str,
    source: str,
    target: str | None = None,
    *,
    deadline_seconds: float = DEFAULT_DEADLINE_SECONDS,
    entry: Callable[..., None] | None = None,
) -> dict:
    """Run operation in a new worker process and return its outcome.

    entry replaces the worker's entry point (tests only). It must be a
    module-level function so the spawned process can import it.
    """
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=entry or worker_main,
        args=(sender, str(LAMBDA3_DIR), operation, source, target),
        daemon=True,
    )
    deadline = time.monotonic() + deadline_seconds
    with receiver:
        try:
            process.start()
        finally:
            sender.close()  # the worker now holds the only writer, so its exit ends the pipe
        try:
            payload = _receive(receiver, deadline)
            if payload is not None:
                process.join(GRACE_SECONDS)  # it has answered or closed the pipe, so it is exiting
        finally:
            _stop(process)
            exitcode = process.exitcode
            process.close()
    if payload is None:
        return {"kind": "timeout"}
    if payload is _NO_PAYLOAD:
        raise WorkerFailure(f"worker exited with code {exitcode} without sending an outcome")
    if payload["kind"] == "internal":
        raise WorkerFailure(f"unexpected exception in the worker:\n{payload['details']}")
    return payload


def _receive(receiver: Connection, deadline: float) -> object:
    """The worker's payload, None if the deadline passes first, or _NO_PAYLOAD on EOF.

    Reading before joining matters: a payload larger than the pipe buffer
    keeps the worker blocked in send until the parent reads it.
    """
    if not receiver.poll(max(0.0, deadline - time.monotonic())):
        return None
    try:
        return receiver.recv()
    except EOFError:
        return _NO_PAYLOAD


def _stop(process: multiprocessing.process.BaseProcess) -> None:
    """Make sure the worker has exited: terminate, then kill, then reap it."""
    if process.is_alive():
        process.terminate()
        process.join(GRACE_SECONDS)
    if process.is_alive():
        process.kill()
    process.join()


def worker_main(
    conn: Connection, lambda3_dir: str, operation: str, source: str, target: str | None,
) -> None:
    """Entry point of the worker process: send exactly one payload, then exit."""
    sys.stdout = open(os.devnull, "w", encoding="utf-8")  # LAMBDA print output is discarded
    try:
        payload = execute(load_lambda3(lambda3_dir), operation, source, target)
    except Exception:
        payload = {"kind": "internal", "details": traceback.format_exc()}
    conn.send(payload)
    conn.close()


def load_lambda3(lambda3_dir: str):
    """Import lambda3 (and the basics0 it imports) from lambda3_dir only."""
    sys.dont_write_bytecode = True  # leave no __pycache__ in the LAMBDA3 directory
    sys.path.insert(0, lambda3_dir)
    import lambda3
    for module in (lambda3, sys.modules["basics0"]):
        if Path(module.__file__).resolve().parent != Path(lambda3_dir):
            raise ImportError(f"{module.__name__} was loaded from {module.__file__}")
    return lambda3


def execute(lambda3, operation: str, source: str, target: str | None) -> dict:
    """Parse and type-check source, then run operation on it, inside the worker."""
    try:
        expression, typ = lambda3.d0exp_parse_and_typecheck(source)
    except lambda3.LambdaSyntaxError as error:
        return _failure("syntax_error", error.msg, line=error.lineno, column=error.offset)
    except lambda3.TypeCheckError as error:
        return _failure("type_error", str(error))
    except RecursionError as error:
        if _raised_within(error, lambda3.d0exp_typecheck):
            return _failure("type_error", "the program is nested too deeply to type-check")
        return _failure("syntax_error", "the program is nested too deeply to parse")
    except ValueError as error:  # int() on a literal with too many digits
        if not _raised_within(error, lambda3.d0exp_parse):
            raise
        limit = sys.get_int_max_str_digits()
        return _failure("syntax_error", f"an integer literal has more than {limit:,} digits")

    if operation == "typecheck":
        return {"kind": "result", "result": {"type": lambda3.format_type(typ)}}
    if operation == "interpret":
        try:
            value = lambda3.d0val_format(lambda3.d0exp_evaluate(expression))
        except RecursionError:
            return _failure("runtime_error", "recursion too deep: Python's recursion limit was reached")
        except MemoryError:
            return _failure("runtime_error", "the program ran out of memory")
        except (ArithmeticError, ValueError, IndexError) as error:
            return _failure("runtime_error", _runtime_diagnostic(lambda3, error))
        return {"kind": "result", "result": {"type": lambda3.format_type(typ), "value": value}}
    if operation == "compile":
        compilers = {"python": lambda3.d0exp_compile, "javascript": lambda3.d0exp_compile_js}
        return {"kind": "result", "result": {"target": target, "code": compilers[target](expression)}}
    raise ValueError(f"unknown operation {operation!r}")


def _runtime_diagnostic(lambda3, error: Exception) -> str:
    """The evaluator's message, except for Python's integer formatting limit."""
    if isinstance(error, ValueError) and _raised_within(error, lambda3.d0val_format):
        limit = sys.get_int_max_str_digits()  # str() refuses longer integers
        return f"an integer has more than {limit:,} digits and cannot be formatted"
    return str(error)


def _failure(kind: str, diagnostic: str, **location: int | None) -> dict:
    """A language-error payload; line and column are left out when unknown."""
    if len(diagnostic) > MAX_DIAGNOSTIC_CHARS:
        diagnostic = diagnostic[:MAX_DIAGNOSTIC_CHARS - 3] + "..."
    data = {"diagnostic": diagnostic}
    data.update((name, value) for name, value in location.items() if value is not None)
    return {"kind": kind, "data": data}


def _raised_within(error: BaseException, function: Callable) -> bool:
    """Whether function was on the stack when error was raised."""
    frame = error.__traceback__
    while frame is not None:
        if frame.tb_frame.f_code is function.__code__:
            return True
        frame = frame.tb_next
    return False
