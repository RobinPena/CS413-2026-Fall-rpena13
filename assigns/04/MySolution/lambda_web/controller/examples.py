"""Canned examples: editable constructor expressions kept in samples/."""
from dataclasses import dataclass
from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"

_CATALOG = {
    "factorial": ("Factorial", "factorial.txt"),
    "fibonacci": ("Fibonacci", "fibonacci.txt"),
}


@dataclass(frozen=True)
class Example:
    key: str
    title: str
    text: str


def get(key: str) -> Example | None:
    """Return the example for `key`, read fresh from samples/."""
    if key not in _CATALOG:
        return None
    title, filename = _CATALOG[key]
    return Example(key, title,
                   (SAMPLES_DIR / filename).read_text(encoding="utf-8"))


def catalog() -> list[tuple[str, str]]:
    """(key, title) pairs for the Load source menu."""
    return [(key, title) for key, (title, _) in _CATALOG.items()]
