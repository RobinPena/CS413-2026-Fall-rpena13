"""Starting real service processes for integration tests.

Each service runs as its own process on a free local port, exactly as its
README starts it, and is stopped when the test is done. The Assign07 LAMBDA3
service is started from ../07 with that assignment's own virtual
environment; tests that need it are skipped, with the reason, when it is
not set up.
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

SOLUTION_DIR = Path(__file__).resolve().parent.parent       # assigns/09/MySolution
ASSIGN09_DIR = SOLUTION_DIR.parent
ASSIGN07_DIR = ASSIGN09_DIR.parent / "07"
ASSIGN07_PYTHON = ASSIGN07_DIR / "MySolution" / ".venv" / "bin" / "python"
ASSIGN07_MISSING = (None if ASSIGN07_PYTHON.exists() else
                    f"the Assign07 LAMBDA3 service is not set up ({ASSIGN07_PYTHON} is missing)")

# Never send local test traffic through an HTTP proxy from the environment.
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def post_json(url: str, body: object, timeout: float = 10.0) -> tuple[int, object]:
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
    with _opener.open(request, timeout=timeout) as reply:
        return reply.status, json.loads(reply.read())


def get(url: str, timeout: float = 5.0) -> tuple[int, bytes, str]:
    with _opener.open(url, timeout=timeout) as reply:
        return reply.status, reply.read(), reply.headers.get("Content-Type", "")


class ServiceProcess:
    """A service started with `python -B -m <module> --port <port> ...`, stopped by stop()."""

    def __init__(self, name: str, python: Path | str, cwd: Path, module: str, *options: str) -> None:
        self.name = name
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        command = [str(python), "-B", "-m", module, "--port", str(self.port), *options]
        # The log goes to a temporary file: a pipe that nobody reads would
        # fill up with request lines and stall the service.
        self.log = tempfile.TemporaryFile()
        self.process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                        stdout=self.log, stderr=subprocess.STDOUT)

    def log_text(self) -> str:
        self.log.seek(0)
        return self.log.read().decode(errors="replace")

    def wait_until_ready(self, probe, seconds: float = 20.0) -> None:
        """Poll probe() (which raises until the service answers) or fail with its log."""
        deadline = time.monotonic() + seconds
        while True:
            if self.process.poll() is not None:
                raise RuntimeError(f"{self.name} exited:\n{self.log_text()}")
            try:
                probe()
                return
            except OSError:
                if time.monotonic() > deadline:
                    log = self.log_text()
                    self.stop()
                    raise RuntimeError(f"{self.name} did not start within {seconds} s:\n{log}") from None
                time.sleep(0.05)

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.log.close()


def start_lambda3() -> ServiceProcess:
    """The real, unchanged Assign07 LAMBDA3 service; its endpoint is service.url + "/rpc"."""
    service = ServiceProcess("LAMBDA3", ASSIGN07_PYTHON, ASSIGN07_DIR, "MySolution")
    service.wait_until_ready(lambda: post_json(f"{service.url}/rpc",
                                               {"jsonrpc": "2.0", "method": "service.health", "params": {}, "id": 1}))
    return service


def start_database(*options: str) -> ServiceProcess:
    service = ServiceProcess("database service", sys.executable, ASSIGN09_DIR, "MySolution", *options)
    service.wait_until_ready(lambda: get(f"{service.url}/api/v1/health"))
    return service


def start_studio(lambda_url: str, database_url: str, *options: str) -> ServiceProcess:
    service = ServiceProcess("studio host", sys.executable, ASSIGN09_DIR, "MySolution.studio",
                             "--lambda-url", lambda_url, "--database-url", database_url, *options)
    service.wait_until_ready(lambda: get(f"{service.url}/config.json"))
    return service
