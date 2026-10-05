"""Every sample file behaves as samples/README.md says."""
from pathlib import Path

import pytest

from lambda_web.backend.lambda_backend import LambdaBackend
from lambda_web.model import ValidationError, decode_upload

SAMPLES = Path(__file__).parent.parent / "samples"

# file: (lint outcome, lint message fragment, interpret outcome, fragment)
EXPECTED = {
    "factorial.txt": ("ok", "No free", "ok", "3628800"),
    "fibonacci.txt": ("ok", "No free", "ok", "arg1=55"),
    "undeclared-variable.txt": ("language error", ": y", "language error",
                                "Runtime error"),
    "division-by-zero.txt": ("ok", "No free", "language error",
                             "ZeroDivisionError"),
    "malformed-input.txt": ("input error", "Invalid input", "input error",
                            "Invalid input"),
    "rejected-code.txt": ("input error", "Invalid input", "input error",
                          "Invalid input"),
    "html-like-text.txt": ("language error", "<i>x</i>", "language error",
                           "Runtime error"),
    "slow-fibonacci.txt": ("ok", "No free", "backend failure", "Timed out"),
}
BACKEND = LambdaBackend(timeout=0.5)


def text_of(result) -> str:
    return f"{result.message} {result.output}"


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_sample_behaves_as_documented(name):
    lint_outcome, lint_text, run_outcome, run_text = EXPECTED[name]
    source = decode_upload((SAMPLES / name).read_bytes())
    lint = BACKEND.lint(source, 1)
    assert (lint.outcome.value, lint_text in text_of(lint)) == \
        (lint_outcome, True)
    run = BACKEND.interpret(source, 1)
    assert (run.outcome.value, run_text in text_of(run)) == \
        (run_outcome, True)


def test_invalid_utf8_sample_is_rejected_on_upload():
    with pytest.raises(ValidationError, match="UTF-8"):
        decode_upload((SAMPLES / "invalid-utf8.txt").read_bytes())


def test_every_sample_is_documented_and_tested():
    files = {p.name for p in SAMPLES.glob("*.txt")}
    readme = (SAMPLES / "README.md").read_text(encoding="utf-8")
    assert files == set(EXPECTED) | {"invalid-utf8.txt"}
    assert all(f"`{name}`" in readme for name in files)
