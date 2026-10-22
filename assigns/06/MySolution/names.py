"""Identifier rule and the deterministic fresh-name supply.

FreshNames is adapted from my Assignment 5 solution,
assigns/05/MySolution/lambda1_visitors.py.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

# The Assignment 5 identifier convention, shared by source and target names.
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def is_identifier(name: str) -> bool:
    return IDENTIFIER.fullmatch(name) is not None


class FreshNames:
    """Deterministic supply of names that are unused within one operation.

    For a base name y, the fresh name is the first of y_1, y_2, y_3, ... that
    is not already used. Each returned name joins the used set, so later
    requests never repeat it. The suffix is added to the whole base, so a
    base of y_1 gives y_1_1, never y_2.

    Each top-level operation seeds its own supply with every name it must
    avoid. There is no global counter, so identical calls give identical
    names, and no name is reserved: a program may itself use y_1, because
    every candidate is checked against the seed.
    """

    def __init__(self, used: Iterable[str]) -> None:
        self.used = set(used)

    def fresh(self, base: str) -> str:
        k = 1
        while f"{base}_{k}" in self.used:
            k += 1
        name = f"{base}_{k}"
        self.used.add(name)
        return name
