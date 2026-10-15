"""Capture-avoiding substitution: every constructor, shadowing and renaming."""
import copy
import unittest
from unittest import mock

from examples import SUBST_AST_CASES, SUBST_CASES, SUBST_NO_EVAL_CASES
from lambda1_visitors import (
    D0E000, D0Eint, D0Evar, FreshNames, SubstitutionVisitor,
    d0exp_fvset, d0exp_pretty, d0exp_substitute,
)
import lambda1_vp  # importable once lambda1_visitors has set up sys.path


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


class SubstitutionPropertyTests(unittest.TestCase):
    def test_free_variables_when_target_is_free(self):
        for name, dexp, target, replacement, _ in SUBST_CASES:
            if target not in d0exp_fvset(dexp):
                continue
            with self.subTest(name):
                result = d0exp_substitute(dexp, target, replacement)
                self.assertEqual(d0exp_fvset(result),
                                 (d0exp_fvset(dexp) - {target})
                                 | d0exp_fvset(replacement))

    def test_unchanged_when_target_is_not_free(self):
        for name, dexp, target, replacement, _ in SUBST_CASES:
            if target in d0exp_fvset(dexp):
                continue
            with self.subTest(name):
                result = d0exp_substitute(dexp, target, replacement)
                self.assertEqual(result, dexp)
                self.assertEqual(d0exp_fvset(result), d0exp_fvset(dexp))

    def test_inputs_unchanged(self):
        for name, dexp, target, replacement, _ in SUBST_CASES:
            with self.subTest(name):
                before = copy.deepcopy((dexp, replacement))
                d0exp_substitute(dexp, target, replacement)
                self.assertEqual((dexp, replacement), before)

    def test_repeated_calls_agree(self):
        for name, dexp, target, replacement, _ in SUBST_CASES:
            with self.subTest(name):
                self.assertEqual(d0exp_substitute(dexp, target, replacement),
                                 d0exp_substitute(dexp, target, replacement))


class NoEvaluationTests(unittest.TestCase):
    def test_no_eval_results_fail_when_evaluated(self):
        for name, dexp, target, replacement, _ in SUBST_NO_EVAL_CASES:
            with self.subTest(name):
                result = d0exp_substitute(dexp, target, replacement)
                with self.assertRaises((TypeError, ZeroDivisionError,
                                        RecursionError)):
                    lambda1_vp.d0exp_evaluate(result)

    def test_substitutes_without_evaluating(self):
        refuse = AssertionError("expression was evaluated")
        with mock.patch.object(lambda1_vp.EvaluateVisitor, "__init__",
                               side_effect=refuse):
            with self.assertRaises(AssertionError):
                lambda1_vp.d0exp_evaluate(D0Eint(1))
            for name, dexp, target, replacement, expected in (
                    SUBST_CASES + SUBST_NO_EVAL_CASES):
                with self.subTest(name):
                    result = d0exp_substitute(dexp, target, replacement)
                    self.assertEqual(d0exp_pretty(result), expected)


if __name__ == "__main__":
    unittest.main()
