"""Pretty printing: exact output for every constructor, without evaluation."""
import unittest
from unittest import mock

from examples import PRETTY_CASES, PRETTY_NO_EVAL_CASES
from lambda1_visitors import D0E000, D0Eint, PrettyPrintVisitor, d0exp_pretty
import lambda1_vp  # importable once lambda1_visitors has set up sys.path


class PrettyPrintTests(unittest.TestCase):
    def test_exact_output(self):
        for name, dexp, expected in PRETTY_CASES:
            with self.subTest(name):
                self.assertEqual(d0exp_pretty(dexp), expected)

    def test_cases_cover_every_constructor(self):
        covered = {type(dexp) for _, dexp, _ in PRETTY_CASES}
        self.assertEqual(covered, set(D0E000.__subclasses__()))

    def test_visitor_dispatches_through_accept(self):
        self.assertEqual(D0Eint(5).accept(PrettyPrintVisitor()), "5")

    def test_no_eval_cases_fail_when_evaluated(self):
        for name, dexp, _ in PRETTY_NO_EVAL_CASES:
            with self.subTest(name):
                with self.assertRaises((TypeError, ZeroDivisionError,
                                        RecursionError)):
                    lambda1_vp.d0exp_evaluate(dexp)

    def test_prints_without_evaluating(self):
        refuse = AssertionError("expression was evaluated")
        with mock.patch.object(lambda1_vp.EvaluateVisitor, "__init__",
                               side_effect=refuse):
            for name, dexp, expected in PRETTY_NO_EVAL_CASES:
                with self.subTest(name):
                    self.assertEqual(d0exp_pretty(dexp), expected)


if __name__ == "__main__":
    unittest.main()
