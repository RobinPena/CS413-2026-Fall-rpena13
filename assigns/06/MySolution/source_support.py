"""Source-side support: the supplied AST, plus printing and name collection.

The source AST classes and D0ExpVisitor come from Assignment 5's lambda1_vp.py,
which is loaded unchanged from its file path. Loading by path, instead of
putting assigns/05 on sys.path, means no import can resolve to another
assignment's MySolution directory, and the tests can check exactly which file
supplied the classes.

PrettyPrintVisitor and AllNamesVisitor are adapted from my Assignment 5
solution, assigns/05/MySolution/lambda1_visitors.py.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SUPPLIED_AST_PATH = Path(__file__).resolve().parents[2] / "05" / "lambda1_vp.py"
_MODULE_NAME = "lambda1_vp"


def load_supplied_ast() -> ModuleType:
    """Return the supplied module, loading it from SUPPLIED_AST_PATH only once.

    A `lambda1_vp` module loaded from anywhere else is refused, so the classes
    used here can never silently be some other copy of the file.
    """
    loaded = sys.modules.get(_MODULE_NAME)
    if loaded is not None:
        origin = getattr(loaded, "__file__", None)
        if origin is None or Path(origin).resolve() != SUPPLIED_AST_PATH:
            raise ImportError(
                f"{_MODULE_NAME} is already loaded from {origin}, "
                f"not from {SUPPLIED_AST_PATH}")
        return loaded
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, SUPPLIED_AST_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {SUPPLIED_AST_PATH}")
    module = importlib.util.module_from_spec(spec)
    # Register before running it, as a normal import does: the dataclass
    # decorator looks the module up while the class bodies execute.
    sys.modules[_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[_MODULE_NAME]
        raise
    return module


_supplied = load_supplied_ast()

D0E000 = _supplied.D0E000
D0Eint = _supplied.D0Eint
D0Ebtf = _supplied.D0Ebtf
D0Evar = _supplied.D0Evar
D0Elam = _supplied.D0Elam
D0Eapp = _supplied.D0Eapp
D0Eop1 = _supplied.D0Eop1
D0Eop2 = _supplied.D0Eop2
D0Eif0 = _supplied.D0Eif0
D0Elet = _supplied.D0Elet
D0Epair = _supplied.D0Epair
D0Epfst = _supplied.D0Epfst
D0Epsnd = _supplied.D0Epsnd
D0Efix = _supplied.D0Efix
D0ExpVisitor = _supplied.D0ExpVisitor

# The supplied free-variable visitor already follows the binding rules of
# Assign06: let binds only in its body, fix binds both names in its body.
source_fv = _supplied.d0exp_fvset


class PrettyPrintVisitor(D0ExpVisitor[str]):
    """Render a source expression on one line without evaluating it."""

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


def show_source(dexp: D0E000) -> str:
    """Return the one-line printed form of a source expression."""
    return dexp.accept(PrettyPrintVisitor())


class AllNamesVisitor(D0ExpVisitor[frozenset[str]]):
    """Collect every variable and binder name, whether bound or free."""

    def visit_int(self, dexp: D0Eint) -> frozenset[str]:
        return frozenset()

    def visit_btf(self, dexp: D0Ebtf) -> frozenset[str]:
        return frozenset()

    def visit_op1(self, dexp: D0Eop1) -> frozenset[str]:
        return dexp.arg1.accept(self)

    def visit_op2(self, dexp: D0Eop2) -> frozenset[str]:
        return dexp.arg1.accept(self) | dexp.arg2.accept(self)

    def visit_var(self, dexp: D0Evar) -> frozenset[str]:
        return frozenset({dexp.arg1})

    def visit_lam(self, dexp: D0Elam) -> frozenset[str]:
        return dexp.arg2.accept(self) | {dexp.arg1}

    def visit_fix(self, dexp: D0Efix) -> frozenset[str]:
        return dexp.arg3.accept(self) | {dexp.arg1, dexp.arg2}

    def visit_app(self, dexp: D0Eapp) -> frozenset[str]:
        return dexp.arg1.accept(self) | dexp.arg2.accept(self)

    def visit_if0(self, dexp: D0Eif0) -> frozenset[str]:
        return (dexp.arg1.accept(self) | dexp.arg2.accept(self)
                | dexp.arg3.accept(self))

    def visit_let(self, dexp: D0Elet) -> frozenset[str]:
        return dexp.arg2.accept(self) | dexp.arg3.accept(self) | {dexp.arg1}

    def visit_pair(self, dexp: D0Epair) -> frozenset[str]:
        return dexp.arg1.accept(self) | dexp.arg2.accept(self)

    def visit_pfst(self, dexp: D0Epfst) -> frozenset[str]:
        return dexp.arg1.accept(self)

    def visit_psnd(self, dexp: D0Epsnd) -> frozenset[str]:
        return dexp.arg1.accept(self)


def source_names(dexp: D0E000) -> frozenset[str]:
    """Return every name in a source expression, binders and bound uses included."""
    return dexp.accept(AllNamesVisitor())
