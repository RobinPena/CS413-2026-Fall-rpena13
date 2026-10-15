"""Capture-avoiding substitution: every constructor, shadowing and renaming."""
import unittest

from examples import SUBST_AST_CASES, SUBST_CASES
from lambda1_visitors import (
    D0E000, D0Eint, D0Evar, FreshNames, SubstitutionVisitor,
    d0exp_pretty, d0exp_substitute,
)


class SubstitutionTests(unittest.TestCase):
    def test_exact_output(self):
        for name, dexp, target, replacement, expected in SUBST_CASES:
            with self.subTest(name):
                result = d0exp_substitute(dexp, target, replacement)
                self.assertEqual(d0exp_pretty(result), expected)

    def test_exact_structure(self):
        for name, dexp, target, replacement, expected in SUBST_AST_CASES:
            with self.subTest(name):
                self.assertEqual(d0exp_substitute(dexp, target, replacement),
                                 expected)

    def test_cases_cover_every_constructor(self):
        covered = {type(case[1]) for case in SUBST_CASES}
        self.assertEqual(covered, set(D0E000.__subclasses__()))

    def test_visitor_dispatches_through_accept(self):
        visitor = SubstitutionVisitor("x", D0Eint(3), FreshNames({"x"}))
        self.assertEqual(D0Evar("x").accept(visitor), D0Eint(3))


if __name__ == "__main__":
    unittest.main()
