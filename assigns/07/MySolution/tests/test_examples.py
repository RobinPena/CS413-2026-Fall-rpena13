"""Every RPC.md section 7 example, replayed against the service (RPC.md section 7).

The exchanges are read from RPC.md itself, so the documented requests,
statuses and responses cannot drift from what the service does. Every
example runs through the real spawned worker and the real LAMBDA3.
"""
import json
import re
from http import HTTPStatus
from typing import NamedTuple

from MySolution.tests.support import SOLUTION_DIR, RpcTestCase


class Example(NamedTuple):
    request: bytes
    content_type: str
    status: str                       # as RPC.md writes it, e.g. "200 OK"
    response: tuple[str, str] | None  # (language, text) of the block after the status
    fixture: str | None               # examples/ file holding the full response, if linked


def rpc_md_examples() -> dict[str, Example]:
    """Section number ("7.1", ...) -> the exchange that RPC.md section 7 documents."""
    text = (SOLUTION_DIR / "RPC.md").read_text(encoding="utf-8")
    examples_text = text[text.index("## 7. Examples"):text.index("## 8. ")]
    parts = re.split(r"^### (7\.\d+) .*$", examples_text, flags=re.M)
    examples = {}
    for number, section in zip(parts[1::2], parts[2::2]):
        status = re.search(r"`(\d{3} [A-Za-z ]+)`", section)
        blocks = [(match.start(), match.group(1), match.group(2))
                  for match in re.finditer(r"^```(\w+)\n(.*?)^```", section, re.M | re.S)]
        inline = re.search(r"^Request body [^`]*`([^`]+)`", section, re.M)  # 7.13
        if inline:
            request = inline.group(1)
        else:
            requests = [body for start, language, body in blocks
                        if language == "json" and start < status.start()]
            request = requests[0] if requests else "any body"  # 7.19 sends no JSON
        content_type = re.search(r"`Content-Type: ([^`]+)`", section)
        fixture = re.search(r"\(examples/([^)]+\.json)\)", section)
        examples[number] = Example(
            request=request.encode("utf-8"),
            content_type=content_type.group(1) if content_type else "application/json",
            status=status.group(1),
            response=next(((language, body) for start, language, body in blocks
                           if start > status.start()), None),
            fixture=fixture.group(1) if fixture else None,
        )
    return examples


def canonical(value: object) -> str:
    """JSON text that tells 1, 1.0 and true apart and ignores key order."""
    return json.dumps(value, sort_keys=True)


class RpcMdExampleTests(RpcTestCase):
    def test_documented_exchanges(self):
        examples = rpc_md_examples()
        self.assertEqual(list(examples), [f"7.{n}" for n in range(1, 20)])
        for number, example in examples.items():
            with self.subTest(example=number):
                self.replay(example)

    def replay(self, example: Example) -> None:
        response = self.post_raw(example.request, example.content_type)
        code, phrase = example.status.split(" ", 1)
        self.assertEqual(response.status_code, int(code))
        self.assertEqual(phrase, HTTPStatus(int(code)).phrase)  # the standard phrase, which clients ignore
        if example.content_type != "application/json":  # a transport error
            self.assertEqual(response.mimetype, "text/plain")
            self.assertNotIn(b"jsonrpc", response.data)
            return
        status, body = self.decode(response)
        if example.response is None:
            self.assertEqual(status, 204)  # decode has checked that the body is empty
            return
        language, documented = example.response
        if example.fixture:  # RPC.md abbreviates the code; the fixture has all of it
            fixture = (SOLUTION_DIR / "examples" / example.fixture).read_text(encoding="utf-8")
            self.assertEqual(canonical(body), canonical(json.loads(fixture)))
            length = re.search(r"<([\d,]+) characters", documented).group(1)
            self.assertEqual(len(body["result"]["code"]), int(length.replace(",", "")))
            return
        self.assertEqual(language, "json")
        expected = json.loads(documented)
        if isinstance(expected, list):  # batch entries are matched by id, in any order
            self.assertEqual(sorted(map(canonical, body)), sorted(map(canonical, expected)))
        else:
            self.assertEqual(canonical(body), canonical(expected))
