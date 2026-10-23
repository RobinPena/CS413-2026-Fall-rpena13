"""Compile extended LAMBDA source ASTs into pure lambda terms.

    compile_expr(source) -> Term

Compilation is a D0ExpVisitor: each visit method combines the translations
of its children according to the rules below, so the translation is
compositional and never runs anything. This module does not import the
evaluator. Before translating, the whole tree is checked for negative
literals and unsupported operators (UnsupportedSourceError), including code
that would never run.

Translation rules, where C[e] is the translation of e, I = lam w. w, and u
and v stand for fresh thunk parameters (see below):

    C[n]                 = NUM(n)
    C[true]              = TRUE
    C[false]             = FALSE
    C[x]                 = x
    C[lam x. e]          = lam x. C[e]
    C[e1 e2]             = C[e1] C[e2]
    C[not e]             = NOT C[e]
    C[e1 + e2]           = ADD C[e1] C[e2]       likewise - SUB, * MUL,
                                                 < LT, <= LEQ, > GT, >= GEQ,
                                                 == EQ, != NEQ
    C[e1 and e2]         = (C[e1] (lam u. C[e2]) (lam v. FALSE)) I
    C[e1 or e2]          = (C[e1] (lam u. TRUE) (lam v. C[e2])) I
    C[if c then t else f]= (C[c] (lam u. C[t]) (lam v. C[f])) I
    C[let x = e1 in e2]  = (lam x. C[e2]) C[e1]
    C[pair e1 e2]        = PAIR C[e1] C[e2]
    C[fst e]             = FST C[e]
    C[snd e]             = SND C[e]
    C[fix f(x). e]       = Z (lam f. lam x. C[e])

Call by value evaluates the arguments of ADD, PAIR and the let's lambda
before they run, left to right, so operands, pair fields and let
initializers stay strict. The only delayed code is inside the thunks: a
Church boolean selects one thunk, and applying the result to I runs only
that one. `and` and `or` compile their right operand even when the left
operand is a literal; whether it runs is decided at run time.

When f and x of a fix coincide, the inner lam x shadows lam f, so the
parameter wins throughout the body, as the source language requires.

Fresh names: every thunk parameter is new. A supply is seeded, once per
compile_expr call, with every name in the source program (free, bound or
unused binders) and every name bound inside the library combinators. Then
thunk parameters are u_1, u_2, ... and v_1, v_2, ... in translation order,
skipping any name already used. No source name is reserved, and a parameter
can never capture or shadow a source variable. Identical calls produce
identical terms. Combinators are closed, so their own bound names cannot
capture anything either; FV(C[e]) = FV(e).
"""
from __future__ import annotations

from .encodings import (
    ADD, AND, EQ, FALSE, FST, GEQ, GT, LEQ, LIBRARY_NAMES, LT, MUL, NEQ, NOT,
    PAIR, SND, SUB, TRUE, Z, I, numeral,
)
from .names import FreshNames
from .source_support import (
    D0E000, D0Eapp, D0Ebtf, D0Efix, D0Eif0, D0Eint, D0Elam, D0Elet, D0Eop1,
    D0Eop2, D0Epair, D0Epfst, D0Epsnd, D0Evar, D0ExpVisitor, source_names,
    validate_source,
)
from .target import App, Lam, Term, Var, app

# Strict binary operators: both operands are computed, left to right.
STRICT_OPERATORS: dict[str, Term] = {
    "+": ADD, "-": SUB, "*": MUL,
    "<": LT, "<=": LEQ, ">": GT, ">=": GEQ, "==": EQ, "!=": NEQ,
}


def compile_expr(source: D0E000) -> Term:
    """Translate a source AST, open or closed, into a pure target term."""
    if not isinstance(source, D0E000):
        raise TypeError(f"not a source AST: {source!r}")
    validate_source(source)
    fresh = FreshNames(source_names(source) | LIBRARY_NAMES)
    return source.accept(CompileVisitor(fresh))


class CompileVisitor(D0ExpVisitor[Term]):
    """C[e] for each source form, built from the translations of its parts."""

    def __init__(self, fresh: FreshNames) -> None:
        self.fresh = fresh

    def _select(self, cond: Term, if_true: Term, if_false: Term) -> Term:
        """(cond (lam u. if_true) (lam v. if_false)) I: run only one branch."""
        then_thunk = Lam(self.fresh.fresh("u"), if_true)
        else_thunk = Lam(self.fresh.fresh("v"), if_false)
        return App(app(cond, then_thunk, else_thunk), I)

    def visit_int(self, dexp: D0Eint) -> Term:
        return numeral(dexp.arg1)

    def visit_btf(self, dexp: D0Ebtf) -> Term:
        return TRUE if dexp.arg1 else FALSE

    def visit_var(self, dexp: D0Evar) -> Term:
        return Var(dexp.arg1)

    def visit_lam(self, dexp: D0Elam) -> Term:
        return Lam(dexp.arg1, dexp.arg2.accept(self))

    def visit_app(self, dexp: D0Eapp) -> Term:
        return App(dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_op1(self, dexp: D0Eop1) -> Term:
        # validate_source has already accepted only "not".
        return App(NOT, dexp.arg1.accept(self))

    def visit_op2(self, dexp: D0Eop2) -> Term:
        left, right = dexp.arg1.accept(self), dexp.arg2.accept(self)
        if dexp.name == "and":
            return self._select(left, right, FALSE)
        if dexp.name == "or":
            return self._select(left, TRUE, right)
        return app(STRICT_OPERATORS[dexp.name], left, right)

    def visit_if0(self, dexp: D0Eif0) -> Term:
        cond = dexp.arg1.accept(self)
        then, else_ = dexp.arg2.accept(self), dexp.arg3.accept(self)
        return self._select(cond, then, else_)

    def visit_let(self, dexp: D0Elet) -> Term:
        init, body = dexp.arg2.accept(self), dexp.arg3.accept(self)
        return App(Lam(dexp.arg1, body), init)

    def visit_pair(self, dexp: D0Epair) -> Term:
        return app(PAIR, dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_pfst(self, dexp: D0Epfst) -> Term:
        return App(FST, dexp.arg1.accept(self))

    def visit_psnd(self, dexp: D0Epsnd) -> Term:
        return App(SND, dexp.arg1.accept(self))

    def visit_fix(self, dexp: D0Efix) -> Term:
        return App(Z, Lam(dexp.arg1, Lam(dexp.arg2, dexp.arg3.accept(self))))
