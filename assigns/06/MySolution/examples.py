"""Source programs built directly as ASTs, and short constructors for them.

No parser is needed: programs are written with the helpers below, so
`op("+", num(2), num(3))` is the source program 2 + 3. Every example is a
function returning a fresh tree, because the supplied AST classes are mutable
dataclasses, so no test can affect another through a shared tree.
"""
from __future__ import annotations

from .source_support import (
    D0E000, D0Eapp, D0Ebtf, D0Efix, D0Eif0, D0Eint, D0Elam, D0Elet, D0Eop1,
    D0Eop2, D0Epair, D0Epfst, D0Epsnd, D0Evar,
)


########################################################################
# Constructors.

def num(n: int) -> D0E000:
    return D0Eint(n)


def boolean(b: bool) -> D0E000:
    return D0Ebtf(b)


def var(name: str) -> D0E000:
    return D0Evar(name)


def fun(param: str, body: D0E000) -> D0E000:
    return D0Elam(param, body)


def call(fn: D0E000, *args: D0E000) -> D0E000:
    """Left-nested application: call(f, a, b) is ((f a) b)."""
    for arg in args:
        fn = D0Eapp(fn, arg)
    return fn


def op(name: str, left: D0E000, right: D0E000) -> D0E000:
    return D0Eop2(name, left, right)


def not_(operand: D0E000) -> D0E000:
    return D0Eop1("not", operand)


def if_(cond: D0E000, then: D0E000, else_: D0E000) -> D0E000:
    return D0Eif0(cond, then, else_)


def let(name: str, init: D0E000, body: D0E000) -> D0E000:
    return D0Elet(name, init, body)


def pair(first: D0E000, second: D0E000) -> D0E000:
    return D0Epair(first, second)


def fst(operand: D0E000) -> D0E000:
    return D0Epfst(operand)


def snd(operand: D0E000) -> D0E000:
    return D0Epsnd(operand)


def fix(fname: str, param: str, body: D0E000) -> D0E000:
    return D0Efix(fname, param, body)


########################################################################
# Divergent and recursive programs.

def loop() -> D0E000:
    """LOOP = (fix loop(x). loop x) 0, a computation that never returns."""
    return call(fix("loop", "x", call(var("loop"), var("x"))), num(0))


def loop_bool() -> D0E000:
    """(fix spin(b). spin b) true: a diverging boolean-to-boolean function.

    Used where a test needs a divergent boolean operand, so the program
    stays well-typed.
    """
    return call(fix("spin", "b", call(var("spin"), var("b"))), boolean(True))


def factorial_fn() -> D0E000:
    """fix fact(n). if n == 0 then 1 else n * fact (n - 1)"""
    return fix("fact", "n",
               if_(op("==", var("n"), num(0)),
                   num(1),
                   op("*", var("n"),
                      call(var("fact"), op("-", var("n"), num(1))))))


def fibonacci_fn() -> D0E000:
    """fix fib(n). if n < 2 then n else fib (n - 1) + fib (n - 2)

    So fib(0) = 0 and fib(1) = 1.
    """
    return fix("fib", "n",
               if_(op("<", var("n"), num(2)),
                   var("n"),
                   op("+",
                      call(var("fib"), op("-", var("n"), num(1))),
                      call(var("fib"), op("-", var("n"), num(2))))))


def factorial(n: int) -> D0E000:
    return call(factorial_fn(), num(n))


def fibonacci(n: int) -> D0E000:
    return call(fibonacci_fn(), num(n))
