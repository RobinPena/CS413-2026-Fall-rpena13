"""LAMBDA constructor-expression sources shared by the tests."""

ADD_42 = 'D0Eop2("+", D0Eint(20), D0Eint(22))'
DIV_ZERO = 'D0Eop2("/", D0Eint(1), D0Eint(0))'


def fact(n: int) -> str:
    return f'''
# factorial: fix f(n). if n <= 0 then 1 else n * f(n - 1)
D0Eapp(
  D0Efix("f", "n",
    D0Eif0(D0Eop2("<=", D0Evar("n"), D0Eint(0)),
      D0Eint(1),
      D0Eop2("*", D0Evar("n"),
        D0Eapp(D0Evar("f"), D0Eop2("-", D0Evar("n"), D0Eint(1)))))),
  D0Eint({n}))
'''


def fib(n: int) -> str:
    return f'''
# fibonacci: fix fib(n). if n < 2 then n else fib(n - 1) + fib(n - 2)
D0Eapp(
  D0Efix("fib", "n",
    D0Eif0(D0Eop2("<", D0Evar("n"), D0Eint(2)),
      D0Evar("n"),
      D0Eop2("+",
        D0Eapp(D0Evar("fib"), D0Eop2("-", D0Evar("n"), D0Eint(1))),
        D0Eapp(D0Evar("fib"), D0Eop2("-", D0Evar("n"), D0Eint(2)))))),
  D0Eint({n}))
'''
