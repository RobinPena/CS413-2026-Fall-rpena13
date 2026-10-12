"""Expressions and expected results shared by the unittest and pytest suites.

Each case is a (name, expression, expected) tuple.
"""
from lambda1_visitors import (
    D0Eapp, D0Ebtf, D0Efix, D0Eif0, D0Eint, D0Elam, D0Elet, D0Eop1, D0Eop2,
    D0Epair, D0Epfst, D0Epsnd, D0Evar,
)

PRETTY_CASES = [
    # literals and variables
    ("int zero", D0Eint(0), "0"),
    ("int positive", D0Eint(42), "42"),
    ("int negative", D0Eint(-7), "-7"),
    ("int large", D0Eint(2**100), "1267650600228229401496703205376"),
    ("int large negative", D0Eint(-(10**30)), "-1000000000000000000000000000000"),
    ("true", D0Ebtf(True), "true"),
    ("false", D0Ebtf(False), "false"),
    ("var", D0Evar("x_1"), "x_1"),
    # every other constructor
    ("op1 +1", D0Eop1("+1", D0Evar("n")), "(+1 n)"),
    ("op1 -1", D0Eop1("-1", D0Eint(5)), "(-1 5)"),
    ("op2 +", D0Eop2("+", D0Evar("x"), D0Eint(1)), "(x + 1)"),
    ("op2 <=", D0Eop2("<=", D0Evar("n"), D0Eint(0)), "(n <= 0)"),
    ("op2 !=", D0Eop2("!=", D0Eint(1), D0Eint(2)), "(1 != 2)"),
    ("lam", D0Elam("x", D0Evar("x")), "(lam x. x)"),
    ("fix", D0Efix("f", "n", D0Eapp(D0Evar("f"), D0Evar("n"))),
     "(fix f(n). (f n))"),
    ("app", D0Eapp(D0Evar("f"), D0Eint(1)), "(f 1)"),
    ("if0", D0Eif0(D0Ebtf(True), D0Eint(1), D0Eint(2)),
     "(if true then 1 else 2)"),
    ("let", D0Elet("x", D0Eint(1), D0Evar("x")), "(let x = 1 in x)"),
    ("pair", D0Epair(D0Eint(1), D0Ebtf(False)), "(pair 1 false)"),
    ("fst", D0Epfst(D0Evar("p")), "(fst p)"),
    ("snd", D0Epsnd(D0Evar("p")), "(snd p)"),
    # nesting
    ("spec example",
     D0Eapp(D0Elam("x", D0Eop2("+", D0Evar("x"), D0Eint(1))), D0Eint(4)),
     "((lam x. (x + 1)) 4)"),
    ("negative operands", D0Eop2("-", D0Eint(-3), D0Eint(-4)), "(-3 - -4)"),
    ("left-nested app",
     D0Eapp(D0Eapp(D0Evar("f"), D0Evar("x")), D0Evar("y")),
     "((f x) y)"),
    ("right-nested app",
     D0Eapp(D0Evar("f"), D0Eapp(D0Evar("g"), D0Evar("x"))),
     "(f (g x))"),
    ("lam returning pair",
     D0Elam("x", D0Epair(D0Evar("x"), D0Elam("y", D0Evar("x")))),
     "(lam x. (pair x (lam y. x)))"),
    ("let with projections",
     D0Elet("p", D0Epair(D0Eint(1), D0Eint(2)),
            D0Eop2("+", D0Epfst(D0Evar("p")), D0Epsnd(D0Evar("p")))),
     "(let p = (pair 1 2) in ((fst p) + (snd p)))"),
    ("factorial",
     D0Efix("fact", "n",
            D0Eif0(D0Eop2("<=", D0Evar("n"), D0Eint(0)),
                   D0Eint(1),
                   D0Eop2("*", D0Evar("n"),
                          D0Eapp(D0Evar("fact"), D0Eop1("-1", D0Evar("n")))))),
     "(fix fact(n). (if (n <= 0) then 1 else (n * (fact (-1 n)))))"),
]

_SELF_APPLY = D0Elam("x", D0Eapp(D0Evar("x"), D0Evar("x")))

# Each of these raises or never finishes when evaluated.
PRETTY_NO_EVAL_CASES = [
    ("division by zero", D0Eop2("/", D0Eint(1), D0Eint(0)), "(1 / 0)"),
    ("applying a non-function", D0Eapp(D0Eint(1), D0Eint(2)), "(1 2)"),
    ("non-boolean condition", D0Eif0(D0Eint(0), D0Eint(1), D0Eint(2)),
     "(if 0 then 1 else 2)"),
    ("projection of a non-pair", D0Epfst(D0Eint(5)), "(fst 5)"),
    ("unsupported operator", D0Eop1("neg", D0Eint(1)), "(neg 1)"),
    ("boolean arithmetic", D0Eop2("+", D0Ebtf(True), D0Eint(1)), "(true + 1)"),
    ("nonterminating", D0Eapp(_SELF_APPLY, _SELF_APPLY),
     "((lam x. (x x)) (lam x. (x x)))"),
]

# Expected sets hold every name, bound or free.
NAMES_CASES = [
    ("int", D0Eint(1), frozenset()),
    ("btf", D0Ebtf(True), frozenset()),
    ("var", D0Evar("x"), frozenset({"x"})),
    ("op1", D0Eop1("+1", D0Evar("n")), frozenset({"n"})),
    ("op2", D0Eop2("+", D0Evar("x"), D0Evar("y")), frozenset({"x", "y"})),
    ("lam binder unused in body", D0Elam("y", D0Eint(1)), frozenset({"y"})),
    ("lam with bound and free names",
     D0Elam("x", D0Eop2("+", D0Evar("x"), D0Evar("y"))), frozenset({"x", "y"})),
    ("fix binders unused in body", D0Efix("f", "n", D0Eint(1)),
     frozenset({"f", "n"})),
    ("app", D0Eapp(D0Evar("f"), D0Evar("a")), frozenset({"f", "a"})),
    ("if0", D0Eif0(D0Evar("b"), D0Evar("t"), D0Evar("e")),
     frozenset({"b", "t", "e"})),
    ("let binder unused in body", D0Elet("z", D0Evar("w"), D0Eint(1)),
     frozenset({"z", "w"})),
    ("pair", D0Epair(D0Evar("a"), D0Evar("b")), frozenset({"a", "b"})),
    ("fst", D0Epfst(D0Evar("p")), frozenset({"p"})),
    ("snd", D0Epsnd(D0Evar("q")), frozenset({"q"})),
    ("nested shadowing", D0Elam("x", D0Elam("x", D0Evar("x"))), frozenset({"x"})),
    ("binders inside initializer and body",
     D0Elet("a", D0Elam("b", D0Evar("c")), D0Efix("d", "e", D0Evar("a"))),
     frozenset({"a", "b", "c", "d", "e"})),
]
