"""Source-side support: the supplied AST, printing, names, validation, substitution.

The source AST classes and D0ExpVisitor come from Assignment 5's lambda1_vp.py,
which is loaded unchanged from its file path. Loading by path, instead of
putting assigns/05 on sys.path, means no import can resolve to another
assignment's MySolution directory, and the tests can check exactly which file
supplied the classes.

PrettyPrintVisitor, AllNamesVisitor and SubstitutionVisitor are adapted from
my Assignment 5 solution, assigns/05/MySolution/lambda1_visitors.py.

These visitors recurse in Python, one level per AST level. Source programs
are small hand-built trees, so that is fine here; generated target terms,
which can be far deeper, are handled by target.py without recursion.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from .names import FreshNames
from .results import Data, UnsupportedSourceError

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


########################################################################
# The supported language, checked over the whole tree before anything runs.

ARITHMETIC_OPERATORS = frozenset({"+", "-", "*"})
COMPARISON_OPERATORS = frozenset({"<", "<=", ">", ">=", "==", "!="})
BOOLEAN_OPERATORS = frozenset({"and", "or"})
BINARY_OPERATORS = ARITHMETIC_OPERATORS | COMPARISON_OPERATORS | BOOLEAN_OPERATORS
UNARY_OPERATORS = frozenset({"not"})


class ValidationVisitor(D0ExpVisitor[None]):
    """Reject negative literals and unsupported operators anywhere in a tree.

    Every child is visited, including branches that would never be selected
    and bodies of functions that are never applied, because the program is
    inspected, not run. `path` describes where the visitor currently is, so
    an error can say where the unsupported form was found.
    """

    def __init__(self) -> None:
        self.path: list[str] = []

    def _child(self, label: str, dexp: D0E000) -> None:
        self.path.append(label)
        dexp.accept(self)
        self.path.pop()

    def _reject(self, detail: str) -> None:
        raise UnsupportedSourceError(detail, tuple(self.path))

    def visit_int(self, dexp: D0Eint) -> None:
        n = dexp.arg1
        if type(n) is not int:
            self._reject(f"literal {n!r} is not a natural number")
        if n < 0:
            self._reject(f"negative literal {n}")

    def visit_btf(self, dexp: D0Ebtf) -> None:
        pass

    def visit_var(self, dexp: D0Evar) -> None:
        pass

    def visit_op1(self, dexp: D0Eop1) -> None:
        if dexp.name not in UNARY_OPERATORS:
            self._reject(f"unsupported unary operator {dexp.name!r}")
        self._child(f"{dexp.name}: operand", dexp.arg1)

    def visit_op2(self, dexp: D0Eop2) -> None:
        if dexp.name not in BINARY_OPERATORS:
            hint = " (division is not in the language)" if dexp.name == "/" else ""
            self._reject(f"unsupported binary operator {dexp.name!r}{hint}")
        self._child(f"'{dexp.name}': left operand", dexp.arg1)
        self._child(f"'{dexp.name}': right operand", dexp.arg2)

    def visit_lam(self, dexp: D0Elam) -> None:
        self._child(f"lam {dexp.arg1}: body", dexp.arg2)

    def visit_fix(self, dexp: D0Efix) -> None:
        self._child(f"fix {dexp.arg1}({dexp.arg2}): body", dexp.arg3)

    def visit_app(self, dexp: D0Eapp) -> None:
        self._child("application: function", dexp.arg1)
        self._child("application: argument", dexp.arg2)

    def visit_if0(self, dexp: D0Eif0) -> None:
        self._child("if: condition", dexp.arg1)
        self._child("if: then branch", dexp.arg2)
        self._child("if: else branch", dexp.arg3)

    def visit_let(self, dexp: D0Elet) -> None:
        self._child(f"let {dexp.arg1}: initializer", dexp.arg2)
        self._child(f"let {dexp.arg1}: body", dexp.arg3)

    def visit_pair(self, dexp: D0Epair) -> None:
        self._child("pair: first", dexp.arg1)
        self._child("pair: second", dexp.arg2)

    def visit_pfst(self, dexp: D0Epfst) -> None:
        self._child("fst: operand", dexp.arg1)

    def visit_psnd(self, dexp: D0Epsnd) -> None:
        self._child("snd: operand", dexp.arg1)


def validate_source(dexp: D0E000) -> None:
    """Raise UnsupportedSourceError for the first unsupported form found."""
    dexp.accept(ValidationVisitor())


########################################################################
# Capture-avoiding substitution on source expressions.

class SubstitutionVisitor(D0ExpVisitor[D0E000]):
    """Replace the free occurrences of target with replacement.

    The visitor carries the substitution, the free names of the replacement
    and the fresh-name supply shared by the whole call. A binder that would
    capture a free name of the replacement is renamed first. Unchanged
    subtrees, including whole scopes where substitution stops, are reused.
    """

    def __init__(self, target: str, replacement: D0E000,
                 fresh: FreshNames) -> None:
        self.target = target
        self.replacement = replacement
        self.replacement_fv = source_fv(replacement)
        self.fresh = fresh

    def _stops_at(self, binders: set[str], body: D0E000) -> bool:
        """Whether nothing in body can change: target is bound or absent."""
        return self.target in binders or self.target not in source_fv(body)

    def _avoid_capture(self, binder: str, body: D0E000) -> tuple[str, D0E000]:
        """Rename binder in body if it would capture a free replacement name."""
        if binder not in self.replacement_fv:
            return binder, body
        renamed = self.fresh.fresh(binder)
        rename = SubstitutionVisitor(binder, D0Evar(renamed), self.fresh)
        return renamed, body.accept(rename)

    def visit_int(self, dexp: D0Eint) -> D0E000:
        return dexp

    def visit_btf(self, dexp: D0Ebtf) -> D0E000:
        return dexp

    def visit_op1(self, dexp: D0Eop1) -> D0E000:
        return D0Eop1(dexp.name, dexp.arg1.accept(self))

    def visit_op2(self, dexp: D0Eop2) -> D0E000:
        return D0Eop2(dexp.name, dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_var(self, dexp: D0Evar) -> D0E000:
        return self.replacement if dexp.arg1 == self.target else dexp

    def visit_lam(self, dexp: D0Elam) -> D0E000:
        param, body = dexp.arg1, dexp.arg2
        if self._stops_at({param}, body):
            return dexp
        param, body = self._avoid_capture(param, body)
        return D0Elam(param, body.accept(self))

    def visit_fix(self, dexp: D0Efix) -> D0E000:
        fname, param, body = dexp.arg1, dexp.arg2, dexp.arg3
        if self._stops_at({fname, param}, body):
            return dexp
        # The parameter goes first. When both binders share a name, the body's
        # occurrences belong to the parameter, which shadows the function name.
        param, body = self._avoid_capture(param, body)
        fname, body = self._avoid_capture(fname, body)
        return D0Efix(fname, param, body.accept(self))

    def visit_app(self, dexp: D0Eapp) -> D0E000:
        return D0Eapp(dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_if0(self, dexp: D0Eif0) -> D0E000:
        return D0Eif0(dexp.arg1.accept(self), dexp.arg2.accept(self),
                      dexp.arg3.accept(self))

    def visit_let(self, dexp: D0Elet) -> D0E000:
        name, init, body = dexp.arg1, dexp.arg2, dexp.arg3
        # The initializer is outside the let's scope, so it is always substituted.
        init = init.accept(self)
        if self._stops_at({name}, body):
            return D0Elet(name, init, body)
        name, body = self._avoid_capture(name, body)
        return D0Elet(name, init, body.accept(self))

    def visit_pair(self, dexp: D0Epair) -> D0E000:
        return D0Epair(dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_pfst(self, dexp: D0Epfst) -> D0E000:
        return D0Epfst(dexp.arg1.accept(self))

    def visit_psnd(self, dexp: D0Epsnd) -> D0E000:
        return D0Epsnd(dexp.arg1.accept(self))


def source_substitute(dexp: D0E000, target: str, replacement: D0E000) -> D0E000:
    """Return dexp[target := replacement] without capturing free names."""
    used = source_names(dexp) | source_names(replacement) | {target}
    return dexp.accept(SubstitutionVisitor(target, replacement, FreshNames(used)))


########################################################################
# Source values as Python data.

def source_data(value: D0E000) -> Data:
    """Python data for a source value: int, bool, or a tuple for a pair.

    Functions have no data form, so they raise TypeError.
    """
    match value:
        case D0Eint(n):
            return n
        case D0Ebtf(b):
            return b
        case D0Epair(first, second):
            return (source_data(first), source_data(second))
    raise TypeError(f"not a data value: {show_source(value)}")
