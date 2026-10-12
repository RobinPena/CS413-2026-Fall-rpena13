"""Visitors over the supplied LAMBDA expression classes.

The supplied interpreter, lambda1_vp.py, lives one directory above this file
and is imported unchanged.
"""
from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

_ASSIGN_DIR = Path(__file__).resolve().parent.parent
if str(_ASSIGN_DIR) not in sys.path:
    sys.path.insert(0, str(_ASSIGN_DIR))

from lambda1_vp import (  # noqa: E402  (needs the path above)
    D0E000, D0Eapp, D0Ebtf, D0Efix, D0Eif0, D0Eint, D0Elam, D0Elet,
    D0Eop1, D0Eop2, D0Epair, D0Epfst, D0Epsnd, D0Evar,
    D0ExpVisitor, d0exp, d0exp_fvset, dvar,
)


class PrettyPrintVisitor(D0ExpVisitor[str]):
    """Render an expression on one line without evaluating it."""

    def visit_int(self, dexp: D0Eint) -> str:
        return str(dexp.arg1)

    def visit_btf(self, dexp: D0Ebtf) -> str:
        return "true" if dexp.arg1 else "false"

    def visit_op1(self, dexp: D0Eop1) -> str:
        return f"({dexp.name} {dexp.arg1.accept(self)})"

    def visit_op2(self, dexp: D0Eop2) -> str:
        return f"({dexp.arg1.accept(self)} {dexp.name} {dexp.arg2.accept(self)})"

    def visit_var(self, dexp: D0Evar) -> str:
        return dexp.arg1

    def visit_lam(self, dexp: D0Elam) -> str:
        return f"(lam {dexp.arg1}. {dexp.arg2.accept(self)})"

    def visit_fix(self, dexp: D0Efix) -> str:
        return f"(fix {dexp.arg1}({dexp.arg2}). {dexp.arg3.accept(self)})"

    def visit_app(self, dexp: D0Eapp) -> str:
        return f"({dexp.arg1.accept(self)} {dexp.arg2.accept(self)})"

    def visit_if0(self, dexp: D0Eif0) -> str:
        return (f"(if {dexp.arg1.accept(self)} then {dexp.arg2.accept(self)}"
                f" else {dexp.arg3.accept(self)})")

    def visit_let(self, dexp: D0Elet) -> str:
        return (f"(let {dexp.arg1} = {dexp.arg2.accept(self)}"
                f" in {dexp.arg3.accept(self)})")

    def visit_pair(self, dexp: D0Epair) -> str:
        return f"(pair {dexp.arg1.accept(self)} {dexp.arg2.accept(self)})"

    def visit_pfst(self, dexp: D0Epfst) -> str:
        return f"(fst {dexp.arg1.accept(self)})"

    def visit_psnd(self, dexp: D0Epsnd) -> str:
        return f"(snd {dexp.arg1.accept(self)})"


def d0exp_pretty(dexp: d0exp) -> str:
    """Return the single-line printed form of an expression."""
    return dexp.accept(PrettyPrintVisitor())


class AllNamesVisitor(D0ExpVisitor[frozenset[dvar]]):
    """Collect every variable and binder name, whether bound or free."""

    def visit_int(self, dexp: D0Eint) -> frozenset[dvar]:
        return frozenset()

    def visit_btf(self, dexp: D0Ebtf) -> frozenset[dvar]:
        return frozenset()

    def visit_op1(self, dexp: D0Eop1) -> frozenset[dvar]:
        return dexp.arg1.accept(self)

    def visit_op2(self, dexp: D0Eop2) -> frozenset[dvar]:
        return dexp.arg1.accept(self) | dexp.arg2.accept(self)

    def visit_var(self, dexp: D0Evar) -> frozenset[dvar]:
        return frozenset({dexp.arg1})

    def visit_lam(self, dexp: D0Elam) -> frozenset[dvar]:
        return dexp.arg2.accept(self) | {dexp.arg1}

    def visit_fix(self, dexp: D0Efix) -> frozenset[dvar]:
        return dexp.arg3.accept(self) | {dexp.arg1, dexp.arg2}

    def visit_app(self, dexp: D0Eapp) -> frozenset[dvar]:
        return dexp.arg1.accept(self) | dexp.arg2.accept(self)

    def visit_if0(self, dexp: D0Eif0) -> frozenset[dvar]:
        return (dexp.arg1.accept(self) | dexp.arg2.accept(self)
                | dexp.arg3.accept(self))

    def visit_let(self, dexp: D0Elet) -> frozenset[dvar]:
        return dexp.arg2.accept(self) | dexp.arg3.accept(self) | {dexp.arg1}

    def visit_pair(self, dexp: D0Epair) -> frozenset[dvar]:
        return dexp.arg1.accept(self) | dexp.arg2.accept(self)

    def visit_pfst(self, dexp: D0Epfst) -> frozenset[dvar]:
        return dexp.arg1.accept(self)

    def visit_psnd(self, dexp: D0Epsnd) -> frozenset[dvar]:
        return dexp.arg1.accept(self)


def d0exp_allnames(dexp: d0exp) -> frozenset[dvar]:
    """Return every name in an expression, including binders and bound uses."""
    return dexp.accept(AllNamesVisitor())


class FreshNames:
    """Deterministic supply of names that are unused within one substitution.

    For a binder named y, the fresh name is the first of y_1, y_2, y_3, ...
    that is not already used. Each returned name is added to the used set, so
    later requests never repeat it.
    """

    def __init__(self, used: Iterable[dvar]) -> None:
        self.used = set(used)

    def fresh(self, base: dvar) -> dvar:
        k = 1
        while f"{base}_{k}" in self.used:
            k += 1
        name = f"{base}_{k}"
        self.used.add(name)
        return name
