"""Name collection and the fresh-name policy used by substitution."""
import unittest

from examples import NAMES_CASES, PRETTY_CASES, PRETTY_NO_EVAL_CASES
from lambda1_visitors import (
    D0E000, AllNamesVisitor, D0Evar, FreshNames, d0exp_allnames, d0exp_fvset,
)


class AllNamesTests(unittest.TestCase):
    def test_exact_names(self):
        for name, dexp, expected in NAMES_CASES:
            with self.subTest(name):
                self.assertEqual(d0exp_allnames(dexp), expected)

    def test_cases_cover_every_constructor(self):
        covered = {type(dexp) for _, dexp, _ in NAMES_CASES}
        self.assertEqual(covered, set(D0E000.__subclasses__()))

    def test_includes_every_free_variable(self):
        for name, dexp, _ in PRETTY_CASES + PRETTY_NO_EVAL_CASES:
            with self.subTest(name):
                self.assertLessEqual(d0exp_fvset(dexp), d0exp_allnames(dexp))

    def test_visitor_dispatches_through_accept(self):
        self.assertEqual(D0Evar("x").accept(AllNamesVisitor()), {"x"})


class FreshNamesTests(unittest.TestCase):
    def test_first_suffix_when_unused(self):
        self.assertEqual(FreshNames(set()).fresh("y"), "y_1")

    def test_skips_names_already_used(self):
        self.assertEqual(FreshNames({"y", "y_1", "y_2"}).fresh("y"), "y_3")

    def test_never_repeats_a_generated_name(self):
        supply = FreshNames({"y"})
        self.assertEqual([supply.fresh("y") for _ in range(3)],
                         ["y_1", "y_2", "y_3"])

    def test_bases_are_independent(self):
        supply = FreshNames(set())
        self.assertEqual((supply.fresh("y"), supply.fresh("f")), ("y_1", "f_1"))

    def test_suffix_is_appended_not_replaced(self):
        self.assertEqual(FreshNames({"y_1"}).fresh("y_1"), "y_1_1")

    def test_same_used_set_gives_same_sequence(self):
        used = {"x", "y", "y_1"}
        first, second = FreshNames(used), FreshNames(used)
        self.assertEqual([first.fresh("y"), first.fresh("x")],
                         [second.fresh("y"), second.fresh("x")])

    def test_does_not_modify_the_given_set(self):
        used = {"y"}
        FreshNames(used).fresh("y")
        self.assertEqual(used, {"y"})


if __name__ == "__main__":
    unittest.main()
