"""Every Church combinator, tested on its own, through execution and observation.

These tests use no compiler: they apply library terms directly and decode the
results with the bounded observers.
"""
import ast
import unittest
from pathlib import Path

import MySolution.encodings as E
from MySolution.encodings import LIBRARY, LIBRARY_NAMES, numeral
from MySolution.evaluator import evaluate
from MySolution.observers import observe
from MySolution.results import BOOL, NAT, Completed, Decoded, Exhausted, PairKind
from MySolution.target import (
    App, Lam, Var, all_names, alpha_equivalent, app, free_vars, iter_nodes, lam, show,
)


def recomputed_fv(term) -> frozenset[str]:
    """Free variables from the definition, independent of the cached field."""
    match term:
        case Var(name):
            return frozenset({name})
        case Lam(name, body):
            return recomputed_fv(body) - {name}
        case App(fn, arg):
            return recomputed_fv(fn) | recomputed_fv(arg)


def run(term, kind, execution_budget=100_000, observation_budget=100_000):
    result = evaluate(term, execution_budget)
    assert isinstance(result, Completed), show(term, 80)
    observed = observe(result.value, kind, observation_budget)
    assert isinstance(observed, Decoded), observed
    return observed.data


class RepresentationTests(unittest.TestCase):
    def test_required_shapes_exactly(self):
        self.assertEqual(show(E.TRUE), "(lam t. (lam f. t))")
        self.assertEqual(show(E.FALSE), "(lam t. (lam f. f))")
        self.assertEqual(show(numeral(0)), "(lam s. (lam z. z))")
        self.assertEqual(show(numeral(2)), "(lam s. (lam z. (s (s z))))")
        self.assertEqual(show(E.PAIR), "(lam a. (lam b. (lam p. ((p a) b))))")
        self.assertEqual(show(E.Z), "(lam g. ((lam x. (g (lam v. ((x x) v)))) "
                                    "(lam x. (g (lam v. ((x x) v))))))")
        self.assertEqual(show(E.I), "(lam w. w)")

    def test_identity_returns_its_argument_in_one_step(self):
        for value in (E.TRUE, numeral(2), E.I):
            with self.subTest(show(value)):
                self.assertEqual(evaluate(App(E.I, value), 1), Completed(value, 1, 1))

    def test_zero_and_false_are_the_same_term(self):
        self.assertTrue(alpha_equivalent(numeral(0), E.FALSE))

    def test_numerals_need_naturals(self):
        for bad in (-1, True, 2.0):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    numeral(bad)

    def test_every_combinator_is_closed_and_pure(self):
        for name, term in LIBRARY.items():
            with self.subTest(name):
                self.assertEqual(free_vars(term), set())
                self.assertEqual(recomputed_fv(term), set())
                self.assertTrue(all(type(node) in (Var, Lam, App)
                                    for node in iter_nodes(term)))
        for n in range(4):
            self.assertEqual(free_vars(numeral(n)), set())

    def test_library_names_cover_every_bound_name(self):
        for term in LIBRARY.values():
            self.assertLessEqual(all_names(term), LIBRARY_NAMES)

    def test_encodings_use_only_the_target_module(self):
        source = Path(E.__file__).read_text(encoding="utf-8")
        imported = {node.module for node in ast.walk(ast.parse(source))
                    if isinstance(node, ast.ImportFrom)}
        self.assertEqual(imported, {"__future__", "target"})


class NumeralArithmeticTests(unittest.TestCase):
    def check(self, combinator, cases):
        for args, expected in cases:
            with self.subTest(args=args):
                term = app(combinator, *(numeral(n) for n in args))
                self.assertEqual(run(term, NAT), expected)

    def test_numerals(self):
        for n in range(6):
            with self.subTest(n=n):
                self.assertEqual(run(numeral(n), NAT), n)

    def test_successor(self):
        self.check(E.SUCC, [((0,), 1), ((1,), 2), ((4,), 5)])

    def test_predecessor_stops_at_zero(self):
        self.check(E.PRED, [((0,), 0), ((1,), 0), ((2,), 1), ((5,), 4)])

    def test_addition(self):
        self.check(E.ADD, [((0, 0), 0), ((0, 3), 3), ((3, 0), 3), ((2, 3), 5)])

    def test_multiplication(self):
        self.check(E.MUL, [((0, 4), 0), ((4, 0), 0), ((1, 5), 5), ((3, 4), 12)])

    def test_truncated_subtraction(self):
        self.check(E.SUB, [((0, 0), 0), ((2, 5), 0), ((5, 5), 0), ((5, 2), 3),
                           ((4, 0), 4), ((0, 3), 0)])

    def test_shift_advances_previous_current(self):
        # (previous, current) = (0, 2) becomes (2, 3).
        start = app(E.PAIR, numeral(0), numeral(2))
        self.assertEqual(run(App(E.SHIFT, start), PairKind(NAT, NAT)), (2, 3))


class BooleanAndComparisonTests(unittest.TestCase):
    def test_zero_test(self):
        for n, expected in ((0, True), (1, False), (3, False)):
            with self.subTest(n=n):
                self.assertIs(run(App(E.ISZERO, numeral(n)), BOOL), expected)

    def test_all_comparisons_both_ways(self):
        expected = {  # results for (2, 3), (3, 3), (3, 2), (0, 0)
            "LT": (True, False, False, False), "LEQ": (True, True, False, True),
            "GT": (False, False, True, False), "GEQ": (False, True, True, True),
            "EQ": (False, True, False, True), "NEQ": (True, False, True, False),
        }
        for name, answers in expected.items():
            for (m, n), answer in zip(((2, 3), (3, 3), (3, 2), (0, 0)), answers):
                with self.subTest(f"{name} {m} {n}"):
                    term = app(LIBRARY[name], numeral(m), numeral(n))
                    self.assertIs(run(term, BOOL), answer)

    def test_boolean_truth_tables(self):
        b = {True: E.TRUE, False: E.FALSE}
        for x in (True, False):
            self.assertIs(run(App(E.NOT, b[x]), BOOL), not x)
            for y in (True, False):
                with self.subTest(x=x, y=y):
                    self.assertIs(run(app(E.AND, b[x], b[y]), BOOL), x and y)
                    self.assertIs(run(app(E.OR, b[x], b[y]), BOOL), x or y)


class PairTests(unittest.TestCase):
    def test_projections(self):
        p = app(E.PAIR, numeral(2), E.TRUE)
        self.assertEqual(run(App(E.FST, p), NAT), 2)
        self.assertIs(run(App(E.SND, p), BOOL), True)

    def test_nested_pair(self):
        p = app(E.PAIR, app(E.PAIR, numeral(2), E.TRUE), numeral(3))
        self.assertEqual(run(p, PairKind(PairKind(NAT, BOOL), NAT)), ((2, True), 3))


class FixedPointTests(unittest.TestCase):
    # fact = Z (lam f. lam n. (ISZERO n (lam u. 1) (lam u. n * f (PRED n))) I),
    # with the branches delayed in thunks as the compiler will do.
    FACT = App(E.Z, lam("f", "n", App(
        app(App(E.ISZERO, Var("n")),
            Lam("u", numeral(1)),
            Lam("u", app(E.MUL, Var("n"), App(Var("f"), App(E.PRED, Var("n")))))),
        E.I)))

    def test_z_gives_working_recursion(self):
        for n, expected in ((0, 1), (1, 1), (3, 6)):
            with self.subTest(n=n):
                self.assertEqual(run(App(self.FACT, numeral(n)), NAT), expected)

    def test_z_applied_to_a_function_is_a_value(self):
        result = evaluate(App(E.Z, lam("f", "n", Var("n"))), 100)
        self.assertIsInstance(result, Completed)
        self.assertIsInstance(result.value, Lam)

    def test_ordinary_y_never_produces_a_value_under_call_by_value(self):
        half = Lam("x", App(Var("f"), App(Var("x"), Var("x"))))
        Y = Lam("f", App(half, half))
        self.assertEqual(evaluate(App(Y, lam("f", "n", Var("n"))), 1_000),
                         Exhausted(1_000, 1_000))


if __name__ == "__main__":
    unittest.main()
