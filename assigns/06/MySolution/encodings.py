"""Closed Church encodings, built as pure target terms.

Names such as TRUE, PAIR and Z are Python names for building and
documentation, not target primitives: each is an ordinary Var/Lam/App term,
and using one inside a larger term simply inlines it. Every combinator in
LIBRARY is closed, so inserting one can never capture or free a variable.
Their bound names (s, z, t, f, ...) are local to each combinator and do not
restrict the names a source program may use.

Representations required by the assignment:

    TRUE   = lam t. lam f. t
    FALSE  = lam t. lam f. f
    NUM(n) = lam s. lam z. s (s ... (s z))        with n applications of s
    PAIR   = lam a. lam b. lam p. p a b
    Z      = lam g. (lam x. g (lam v. x x v)) (lam x. g (lam v. x x v))

Derived combinators (application associates to the left):

    I      = lam w. w
    FST    = lam p. p TRUE                SND = lam p. p FALSE
    SUCC   = lam n. lam s. lam z. s (n s z)
    ADD    = lam m. lam n. lam s. lam z. m s (n s z)
    MUL    = lam m. lam n. lam s. m (n s)
    ISZERO = lam n. n (lam x. FALSE) TRUE
    SHIFT  = lam q. PAIR (SND q) (SUCC (SND q))
    PRED   = lam n. FST (n SHIFT (PAIR NUM(0) NUM(0)))
    SUB    = lam m. lam n. n PRED m
    NOT    = lam b. b FALSE TRUE
    AND    = lam a. lam b. a b FALSE      OR = lam a. lam b. a TRUE b
    LEQ    = lam m. lam n. ISZERO (SUB m n)          m <= n  iff  m - n = 0
    GEQ    = lam m. lam n. ISZERO (SUB n m)          m >= n  iff  n - m = 0
    LT     = lam m. lam n. NOT (GEQ m n)
    GT     = lam m. lam n. NOT (LEQ m n)
    EQ     = lam m. lam n. AND (LEQ m n) (GEQ m n)
    NEQ    = lam m. lam n. NOT (EQ m n)

Predecessor: SHIFT turns a pair (previous, current) into (current,
current + 1). Starting from (0, 0), n shifts give (n - 1, n) for n >= 1, and
PRED takes the first component. For n = 0 there are no shifts, so the first
component of (0, 0) is returned: PRED 0 = 0, as truncated subtraction needs.
SUB m n applies PRED to m, n times, so it stops at zero.

Under call by value, the arguments of a combinator are values before it
runs. NOT, AND and OR therefore combine booleans that are already computed;
they cannot skip work. Source-level `and`, `or` and `if` must skip their
unselected operand, so the compiler wraps those operands in thunks instead
of passing them to these combinators.

Python arithmetic appears only in `numeral`, to build a literal. All
arithmetic of a running program happens by beta reduction of these terms.
"""
from __future__ import annotations

from .target import App, Lam, Term, Var, all_names, app, lam

V = Var

I = lam("w", V("w"))
TRUE = lam("t", "f", V("t"))
FALSE = lam("t", "f", V("f"))


def numeral(n: int) -> Lam:
    """NUM(n) = lam s. lam z. s (s ... (s z)), with n applications of s."""
    if type(n) is not int or n < 0:
        raise ValueError(f"a Church numeral needs a natural number, not {n!r}")
    body: Term = V("z")
    for _ in range(n):
        body = App(V("s"), body)
    return lam("s", "z", body)


PAIR = lam("a", "b", "p", app(V("p"), V("a"), V("b")))
FST = lam("p", App(V("p"), TRUE))
SND = lam("p", App(V("p"), FALSE))

# Each half applies g to a delayed self-application. The extra lam v is what
# makes Z work under call by value: x x is only evaluated when v arrives.
_HALF = lam("x", App(V("g"), lam("v", app(V("x"), V("x"), V("v")))))
Z = lam("g", App(_HALF, _HALF))

SUCC = lam("n", "s", "z", App(V("s"), app(V("n"), V("s"), V("z"))))
ADD = lam("m", "n", "s", "z",
          app(V("m"), V("s"), app(V("n"), V("s"), V("z"))))
MUL = lam("m", "n", "s", App(V("m"), App(V("n"), V("s"))))
ISZERO = lam("n", app(V("n"), lam("x", FALSE), TRUE))

SHIFT = lam("q", app(PAIR, App(SND, V("q")), App(SUCC, App(SND, V("q")))))
PRED = lam("n", App(FST, app(V("n"), SHIFT, app(PAIR, numeral(0), numeral(0)))))
SUB = lam("m", "n", app(V("n"), PRED, V("m")))

NOT = lam("b", app(V("b"), FALSE, TRUE))
AND = lam("a", "b", app(V("a"), V("b"), FALSE))
OR = lam("a", "b", app(V("a"), TRUE, V("b")))

LEQ = lam("m", "n", App(ISZERO, app(SUB, V("m"), V("n"))))
GEQ = lam("m", "n", App(ISZERO, app(SUB, V("n"), V("m"))))
LT = lam("m", "n", App(NOT, app(GEQ, V("m"), V("n"))))
GT = lam("m", "n", App(NOT, app(LEQ, V("m"), V("n"))))
EQ = lam("m", "n", app(AND, app(LEQ, V("m"), V("n")), app(GEQ, V("m"), V("n"))))
NEQ = lam("m", "n", App(NOT, app(EQ, V("m"), V("n"))))

LIBRARY: dict[str, Term] = {
    "I": I, "TRUE": TRUE, "FALSE": FALSE, "PAIR": PAIR, "FST": FST, "SND": SND,
    "Z": Z, "SUCC": SUCC, "ADD": ADD, "MUL": MUL, "ISZERO": ISZERO,
    "SHIFT": SHIFT, "PRED": PRED, "SUB": SUB, "NOT": NOT, "AND": AND, "OR": OR,
    "LEQ": LEQ, "GEQ": GEQ, "LT": LT, "GT": GT, "EQ": EQ, "NEQ": NEQ,
}

# Every name bound inside the library, so the compiler can choose binders
# that differ from all of them as well as from the source program's names.
LIBRARY_NAMES: frozenset[str] = frozenset().union(
    *(all_names(term) for term in LIBRARY.values()), all_names(numeral(1)))
