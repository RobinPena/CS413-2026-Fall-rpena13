"""Target AST: the three forms, exact printing, names, substitution, alpha-equivalence.

Substitution is tested here on open terms directly, independent of evaluation.
"""
import copy
import dataclasses
import unittest

from MySolution.source_support import D0Eint
from MySolution.target import (
    App, Lam, Var, all_names, alpha_equivalent, app, free_vars, is_term, lam,
    show, size, substitute,
)

x, y, z, f = Var("x"), Var("y"), Var("z"), Var("f")
I = Lam("a", Var("a"))


def deep_lambda(depth: int) -> Lam:
    """lam v. lam v. ... lam v. x, nested `depth` times, built without recursion."""
    term = x
    for _ in range(depth):
        term = Lam("v", term)
    return term


def recomputed_fv(term) -> frozenset[str]:
    """Free variables straight from the definition, to check the node caches."""
    match term:
        case Var(name):
            return frozenset({name})
        case Lam(name, body):
            return recomputed_fv(body) - {name}
        case App(fn, arg):
            return recomputed_fv(fn) | recomputed_fv(arg)


class FormTests(unittest.TestCase):
    def test_terms_are_immutable(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            x.name = "y"
        with self.assertRaises(dataclasses.FrozenInstanceError):
            Lam("x", x).body = y

    def test_names_must_be_identifiers(self):
        for bad in ("", "1x", "x y", 3):
            with self.subTest(bad):
                with self.assertRaises(ValueError):
                    Var(bad)
                with self.assertRaises(ValueError):
                    Lam(bad, x)

    def test_children_must_be_target_terms(self):
        # A source literal can never end up inside a target term.
        with self.assertRaises(TypeError):
            App(x, D0Eint(3))
        with self.assertRaises(TypeError):
            Lam("x", "x")
        self.assertFalse(is_term(D0Eint(3)))

    def test_builders_only_nest_the_three_forms(self):
        self.assertEqual(app(f, x, y), App(App(f, x), y))
        self.assertEqual(lam("a", "b", x), Lam("a", Lam("b", x)))
        with self.assertRaises(ValueError):
            app(f)
        with self.assertRaises(ValueError):
            lam(x)

    def test_cached_fv_is_not_part_of_equality_or_repr(self):
        self.assertEqual(Lam("x", x), Lam("x", x))
        self.assertEqual(repr(Lam("x", y)), "Lam(name='x', body=Var(name='y'))")


class PrintTests(unittest.TestCase):
    def test_exact_formats(self):
        cases = [
            (x, "x"),
            (Lam("x", x), "(lam x. x)"),
            (App(f, x), "(f x)"),
            (app(f, x, y), "((f x) y)"),
            (App(f, App(x, y)), "(f (x y))"),
            (lam("t", "f", Var("t")), "(lam t. (lam f. t))"),
            (App(Lam("x", App(x, x)), Lam("x", App(x, x))),
             "((lam x. (x x)) (lam x. (x x)))"),
            (Lam("g", App(Lam("x", App(Var("g"), Lam("v", app(x, x, Var("v"))))),
                          Lam("x", App(Var("g"), Lam("v", app(x, x, Var("v"))))))),
             "(lam g. ((lam x. (g (lam v. ((x x) v)))) "
             "(lam x. (g (lam v. ((x x) v))))))"),
        ]
        for term, text in cases:
            with self.subTest(text):
                self.assertEqual(show(term), text)
                self.assertEqual(str(term), text)

    def test_deep_terms_print_without_recursion(self):
        text = show(deep_lambda(20_000))
        self.assertTrue(text.startswith("(lam v. (lam v. "))
        self.assertEqual(text.count("("), 20_000)

    def test_size_counts_printed_nodes(self):
        self.assertEqual(size(app(f, x, y)), 5)
        self.assertEqual(size(App(I, I)), 5)  # a shared subtree counts twice


class NameTests(unittest.TestCase):
    def test_free_and_all_names(self):
        cases = [
            (x, {"x"}, {"x"}),
            (Lam("x", App(x, y)), {"y"}, {"x", "y"}),
            (Lam("z", y), {"y"}, {"y", "z"}),  # unused binder
            (App(Lam("x", x), x), {"x"}, {"x"}),  # bound and free x
            (Lam("x", Lam("x", x)), set(), {"x"}),
            (App(Lam("x", App(x, z)), Lam("y", App(f, y))), {"z", "f"},
             {"x", "y", "z", "f"}),
        ]
        for term, fv, names in cases:
            with self.subTest(show(term)):
                self.assertEqual(free_vars(term), fv)
                self.assertEqual(recomputed_fv(term), fv)
                self.assertEqual(all_names(term), names)


class SubstitutionTests(unittest.TestCase):
    # (term, name, replacement, exact expected result under the fresh-name policy)
    CASES = [
        # The assignment's capture hazard: y must stay free.
        (Lam("y", x), "x", y, "(lam y_1. y)"),
        # Variables, hit and miss.
        (x, "x", Lam("q", Var("q")), "(lam q. q)"),
        (z, "x", y, "z"),
        (App(x, App(f, x)), "x", y, "(y (f y))"),
        # Shadowing: the binder for x stops substitution.
        (Lam("x", x), "x", y, "(lam x. x)"),
        (App(x, Lam("x", x)), "x", y, "(y (lam x. x))"),
        (Lam("z", Lam("x", App(x, z))), "x", y, "(lam z. (lam x. (x z)))"),
        # No renaming when the binder is not free in the replacement.
        (Lam("z", App(x, z)), "x", y, "(lam z. (y z))"),
        # No renaming when x is not free under the binder.
        (App(x, Lam("y", y)), "x", y, "(y (lam y. y))"),
        # Renaming respects an inner binder with the same name.
        (Lam("y", App(Lam("y", y), App(x, y))), "x", y,
         "(lam y_1. ((lam y. y) (y y_1)))"),
        # Fresh names avoid names already in the term ...
        (Lam("y", App(x, Var("y_1"))), "x", y, "(lam y_2. (y y_1))"),
        (Lam("y", App(Lam("y_1", x), y)), "x", y, "(lam y_2. ((lam y_1. y) y_2))"),
        # ... in the replacement ...
        (Lam("y", App(x, y)), "x", App(y, Var("y_1")), "(lam y_2. ((y y_1) y_2))"),
        # ... and names generated earlier in the same call.
        (Lam("y", Lam("y", x)), "x", y, "(lam y_1. (lam y_2. y))"),
        (App(Lam("y", x), Lam("y", x)), "x", y, "((lam y_1. y) (lam y_2. y))"),
        # A replacement containing the substituted name.
        (App(x, x), "x", App(x, x), "((x x) (x x))"),
        (Lam("z", x), "x", Lam("z", x), "(lam z. (lam z. x))"),
        # Encoding-style binder names are not reserved.
        (lam("s", "z", App(Var("s"), x)), "x", App(Var("s"), z),
         "(lam s_1. (lam z_1. (s_1 (s z))))"),
    ]

    def test_exact_results(self):
        for term, name, replacement, expected in self.CASES:
            with self.subTest(f"{show(term)}[{name} := {show(replacement)}]"):
                self.assertEqual(show(substitute(term, name, replacement)), expected)

    def test_capture_hazard_is_alpha_equivalent_to_lam_fresh_y(self):
        result = substitute(Lam("y", x), "x", y)
        self.assertTrue(alpha_equivalent(result, Lam("w", y)))
        self.assertNotEqual(result.name, "y")
        self.assertEqual(free_vars(result), {"y"})

    def test_free_variable_law(self):
        for term, name, replacement, _ in self.CASES:
            with self.subTest(f"{show(term)}[{name} := {show(replacement)}]"):
                result = substitute(term, name, replacement)
                if name in free_vars(term):
                    expected = (free_vars(term) - {name}) | free_vars(replacement)
                else:
                    expected = free_vars(term)
                self.assertEqual(free_vars(result), expected)
                self.assertEqual(recomputed_fv(result), expected)

    def test_absent_name_returns_the_input(self):
        for term in (z, Lam("x", x), Lam("y", y), App(Lam("x", x), z)):
            with self.subTest(show(term)):
                self.assertIs(substitute(term, "x", y), term)

    def test_inputs_unchanged_and_repeated_calls_agree(self):
        for term, name, replacement, _ in self.CASES:
            with self.subTest(f"{show(term)}[{name} := {show(replacement)}]"):
                term_before = copy.deepcopy(term)
                replacement_before = copy.deepcopy(replacement)
                first = substitute(term, name, replacement)
                second = substitute(term, name, replacement)
                self.assertEqual(first, second)
                self.assertEqual(show(first), show(second))
                self.assertEqual(term, term_before)
                self.assertEqual(replacement, replacement_before)

    def test_deep_terms_substitute_without_recursion(self):
        term = deep_lambda(20_000)
        result = substitute(term, "x", Lam("q", Var("q")))
        self.assertEqual(free_vars(result), set())
        self.assertTrue(show(result).endswith("(lam q. q)" + ")" * 20_000))

    def test_rejects_invalid_arguments(self):
        with self.assertRaises(ValueError):
            substitute(x, "not a name", y)
        with self.assertRaises(TypeError):
            substitute(x, "x", D0Eint(1))


class AlphaEquivalenceTests(unittest.TestCase):
    def test_equivalent_pairs(self):
        cases = [
            (Lam("x", x), Lam("y", y)),
            (lam("t", "f", Var("t")), lam("a", "b", Var("a"))),
            (Lam("x", Lam("x", x)), lam("a", "b", Var("b"))),
            (Lam("x", App(x, z)), Lam("y", App(y, z))),
            (App(Lam("x", x), Lam("y", y)), App(Lam("p", Var("p")), Lam("q", Var("q")))),
        ]
        for left, right in cases:
            with self.subTest(f"{show(left)} ~ {show(right)}"):
                self.assertTrue(alpha_equivalent(left, right))
                self.assertTrue(alpha_equivalent(right, left))

    def test_inequivalent_pairs(self):
        cases = [
            (lam("t", "f", Var("t")), lam("t", "f", Var("f"))),  # TRUE vs FALSE
            (Lam("x", Lam("x", x)), lam("a", "b", Var("a"))),    # shadowing matters
            (Lam("x", y), Lam("x", z)),                          # free names exact
            (Lam("x", y), Lam("y", y)),                          # free vs bound
            (App(Lam("x", x), y), y),                            # no beta
            (Lam("x", App(f, x)), f),                            # no eta
            (Lam("x", x), App(x, x)),                            # different forms
        ]
        for left, right in cases:
            with self.subTest(f"{show(left)} vs {show(right)}"):
                self.assertFalse(alpha_equivalent(left, right))
                self.assertFalse(alpha_equivalent(right, left))


if __name__ == "__main__":
    unittest.main()
