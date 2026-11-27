"""The studio host (studio/host.py): the page, its configuration, and the
LAMBDA3 forwarder.

The forwarder is checked against a small stand-in upstream server, which
records what it receives and answers as told, and then against the real,
unchanged Assign07 LAMBDA3 service.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
import unittest

from werkzeug.serving import make_server
from werkzeug.wrappers import Request, Response

from MySolution.studio.host import create_studio_app

from .process_support import ASSIGN07_MISSING, ASSIGN09_DIR, free_port, start_lambda3

DATABASE_URL = "http://127.0.0.1:8009/api/v1"
FACTORIAL = ("let fact : sint -> sint = fix fact(n: sint): sint => "
             "if n <= 1 then 1 else n * fact(n - 1) in fact(6) end")


def rpc(method: str, params: dict, request_id: int = 1) -> bytes:
    return json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": request_id}).encode()


class StandInUpstream:
    """A local HTTP server that records each request and answers with `self.answer`."""

    def __init__(self) -> None:
        self.received: list[tuple[bytes, str | None]] = []
        self.answer = Response(b'{"jsonrpc": "2.0", "result": {}, "id": 1}', 200, content_type="application/json")
        self.release = threading.Event()    # set it to let a held request finish
        self.hold = False
        self.server = make_server("127.0.0.1", 0, self.application, threaded=True)
        self.url = f"http://127.0.0.1:{self.server.server_port}/rpc"
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()

    @Request.application
    def application(self, request: Request) -> Response:
        self.received.append((request.get_data(), request.headers.get("Content-Type")))
        if self.hold:
            self.release.wait(10)
        return self.answer

    def stop(self) -> None:
        self.release.set()
        self.server.shutdown()
        self.thread.join(5)
        self.server.server_close()


class PageTests(unittest.TestCase):

    def setUp(self):
        self.client = create_studio_app("http://127.0.0.1:1/rpc", DATABASE_URL).test_client()

    def get(self, path: str) -> tuple[int, str, bytes]:
        """Status, media type, and body; the response is closed (static files are file-backed)."""
        with self.client.get(path) as response:
            return response.status_code, response.mimetype, response.get_data()

    def test_page_and_modules_are_served(self):
        status, media_type, page = self.get("/")
        self.assertEqual((status, media_type), (200, "text/html"))
        self.assertIn(b'<script type="module" src="static/js/main.js">', page)
        self.assertIn(b"erased when the database service stops or restarts", page)
        for path in ("main.js", "storage.js", "lambda3.js", "runner.js"):
            with self.subTest(path=path):
                self.assertEqual(self.get(f"/static/js/{path}")[:2], (200, "text/javascript"))
        self.assertEqual(self.get("/static/style.css")[:2], (200, "text/css"))

    def test_config_tells_the_page_where_the_database_is(self):
        response = self.client.get("/config.json")
        self.assertEqual(response.json, {"database_url": DATABASE_URL})

    def test_only_post_is_forwarded(self):
        self.assertEqual(self.client.get("/lambda/rpc").status_code, 405)
        self.assertEqual(self.client.get("/nowhere").status_code, 404)

    def test_the_studio_host_does_not_load_the_database_service(self):
        # It is a separate process with no access to the store (DESIGN.md D4).
        loaded = subprocess.run(
            [sys.executable, "-B", "-c", "import sys, MySolution.studio.host; "
             "print(sorted(m for m in sys.modules if m.startswith('MySolution')))"],
            cwd=ASSIGN09_DIR, capture_output=True, text=True, check=True).stdout
        self.assertEqual(loaded.strip(), "['MySolution', 'MySolution.studio', 'MySolution.studio.host']")


class ForwarderTests(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.WARNING)          # the gateway errors below are expected
        self.addCleanup(logging.disable, logging.NOTSET)
        self.upstream = StandInUpstream()
        self.addCleanup(self.upstream.stop)
        self.client = create_studio_app(self.upstream.url, DATABASE_URL, timeout=0.5).test_client()

    def forward(self, body: bytes, content_type: str | None = "application/json"):
        headers = {"Content-Type": content_type} if content_type else {}
        return self.client.post("/lambda/rpc", data=body, headers=headers)

    def test_body_and_content_type_are_forwarded_unchanged(self):
        body = rpc("lambda.interpret", {"source": "  1 + 2\n"}) + b"  "
        response = self.forward(body, "application/json; charset=utf-8")
        self.assertEqual(self.upstream.received, [(body, "application/json; charset=utf-8")])
        self.assertEqual((response.status_code, response.mimetype), (200, "application/json"))
        self.assertEqual(response.data, self.upstream.answer.get_data())

    def test_upstream_statuses_are_relayed(self):
        cases = [
            (Response(b"415 Unsupported Media Type\n", 415, content_type="text/plain"), 415, "text/plain"),
            (Response(b"413 Content Too Large\n", 413, content_type="text/plain"), 413, "text/plain"),
            (Response(b"", 204), 204, None),
        ]
        for answer, status, media_type in cases:
            with self.subTest(status=status):
                self.upstream.answer = answer
                response = self.forward(b"{}", "text/plain")
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.headers.get("Content-Type", "").split(";")[0] or None, media_type)
                self.assertEqual(response.data, answer.get_data())

    def test_unreachable_lambda3_is_502(self):
        client = create_studio_app(f"http://127.0.0.1:{free_port()}/rpc", DATABASE_URL).test_client()
        response = client.post("/lambda/rpc", data=b"{}", headers={"Content-Type": "application/json"})
        self.assertEqual((response.status_code, response.mimetype), (502, "text/plain"))
        self.assertIn(b"could not be reached", response.data)

    def test_slow_lambda3_is_504(self):
        self.upstream.hold = True
        response = self.forward(rpc("lambda.interpret", {"source": "1"}))
        self.assertEqual((response.status_code, response.mimetype), (504, "text/plain"))
        self.assertIn(b"did not answer within 0.5 seconds", response.data)

    def test_oversized_body_is_refused_before_forwarding(self):
        response = self.forward(b" " * (1_048_576 + 1))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.upstream.received, [])


@unittest.skipIf(ASSIGN07_MISSING, ASSIGN07_MISSING)
class RealLambda3Tests(unittest.TestCase):
    """The forwarder in front of the real Assign07 service, started from ../07."""

    @classmethod
    def setUpClass(cls):
        cls.lambda3 = start_lambda3()
        cls.client = create_studio_app(f"{cls.lambda3.url}/rpc", DATABASE_URL).test_client()

    @classmethod
    def tearDownClass(cls):
        cls.lambda3.stop()

    def interpret(self, source: str) -> dict:
        response = self.client.post("/lambda/rpc", data=rpc("lambda.interpret", {"source": source}, 7),
                                    headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["id"], 7)
        return response.json

    def test_value(self):
        self.assertEqual(self.interpret(FACTORIAL)["result"], {"type": "sint", "value": "720"})

    def test_syntax_error(self):
        self.assertEqual(self.interpret("if then")["error"]["code"], -32010)

    def test_type_error(self):
        self.assertEqual(self.interpret("(lam (x: sint) => x)(true)")["error"]["code"], -32011)

    def test_runtime_error(self):
        self.assertEqual(self.interpret("1 / 0")["error"]["code"], -32013)


if __name__ == "__main__":
    unittest.main()
