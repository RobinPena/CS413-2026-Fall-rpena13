"""Bounded observers: expected kinds, computed values, malformed and exhausted outcomes.

Step counts are checked against hand traces of small terms, for example:
observing NUM(2) runs NUM(2) STEP BASE in 4 steps (NUM(2) STEP, then BASE,
then STEP BASE, then STEP applied to that); observing TRUE takes 2 steps.
"""
import copy
import unittest
from unittest import mock

import MySolution.observers as observers_module
from MySolution.encodings import ADD, FALSE, MUL, PAIR, SUB, TRUE, I, numeral
from MySolution.evaluator import evaluate
from MySolution.observers import BASE, NO, STEP, YES, observe
from MySolution.results import (
    BOOL, NAT, Completed, Decoded, Malformed, ObservationExhausted, PairKind,
)
from MySolution.target import App, Lam, Var, alpha_equivalent, app, lam, show


def value_of(term, budget=10_000):
    result = evaluate(term, budget)
    assert isinstance(result, Completed)
    return result.value


class ContextTests(unittest.TestCase):
    def test_context_and_marker_shapes(self):
        self.assertEqual(show(STEP), "(lam tail. (lam c. (lam z. (c tail))))")
        self.assertEqual(show(BASE), "(lam c. (lam z. z))")
        self.assertEqual(show(YES), "(lam a. (lam b. (lam c. a)))")
        self.assertEqual(show(NO), "(lam a. (lam b. (lam c. c)))")
        for marker in (YES, NO):
            for other in (TRUE, FALSE, numeral(0), numeral(1)):
                self.assertFalse(alpha_equivalent(marker, other))
        self.assertFalse(alpha_equivalent(YES, NO))


class DecodingTests(unittest.TestCase):
    def test_alpha_renamed_literals(self):
        two = lam("succ", "zero", App(Var("succ"), App(Var("succ"), Var("zero"))))
        self.assertEqual(observe(two, NAT, 100).data, 2)
        self.assertIs(observe(lam("yes", "no", Var("yes")), BOOL, 100).data, True)
        self.assertIs(observe(lam("yes", "no", Var("no")), BOOL, 100).data, False)

    def test_computed_values_with_redexes_inside(self):
        five = value_of(app(ADD, numeral(2), numeral(3)))
        # The value still holds unreduced applications under its binders ...
        self.assertFalse(alpha_equivalent(five, numeral(5)))
        self.assertIn("((lam s. (lam z. (s (s z)))) s)", show(five))
        # ... and still observes as 5, without reducing under those binders.
        self.assertEqual(observe(five, NAT, 1_000), Decoded(5, 11, 1_000))
        self.assertEqual(observe(value_of(app(MUL, numeral(3), numeral(4))), NAT, 1_000).data, 12)

    def test_zero_and_false_decode_by_expected_kind(self):
        for term in (numeral(0), FALSE):
            with self.subTest(show(term)):
                self.assertEqual(observe(term, NAT, 100), Decoded(0, 2, 100))
                self.assertEqual(observe(term, BOOL, 100), Decoded(False, 2, 100))

    def test_nested_pair(self):
        p = value_of(app(PAIR, app(PAIR, numeral(2), TRUE), numeral(3)))
        result = observe(p, PairKind(PairKind(NAT, BOOL), NAT), 1_000)
        self.assertEqual(result.data, ((2, True), 3))
        self.assertIsInstance(result, Decoded)

    def test_value_is_not_changed(self):
        p = value_of(app(PAIR, numeral(2), TRUE))
        before = copy.deepcopy(p)
        observe(p, PairKind(NAT, BOOL), 1_000)
        self.assertEqual(p, before)

    def test_observation_runs_on_the_shared_evaluator(self):
        with mock.patch.object(observers_module, "evaluate", wraps=evaluate) as engine:
            observe(numeral(2), NAT, 100)
        self.assertEqual(engine.call_count, 1)


class MalformedTests(unittest.TestCase):
    def test_wrong_shapes_are_reported_not_guessed(self):
        cases = [
            (TRUE, NAT),                                  # STEP left unapplied
            (numeral(2), BOOL),                           # neither marker
            (numeral(1), BOOL),
            (value_of(app(PAIR, numeral(1), numeral(2))), NAT),
            (lam("s", "z", app(Var("s"), Var("s"))), NAT),  # tail is not a spine
            # The tail's base refers to the outer level's z, not its own.
            (lam("s", "z", lam("c", "w", App(Var("c"), lam("c2", "w2", Var("w"))))), NAT),
            # Head and base binders coincide, so c is the inner (z) binder.
            (lam("s", "z", lam("c", "c", App(Var("c"), BASE))), NAT),
        ]
        for value, kind in cases:
            with self.subTest(f"{show(value, 50)} as {kind}"):
                result = observe(value, kind, 1_000)
                self.assertIsInstance(result, Malformed)
                self.assertEqual(result.path, "result")

    def test_malformed_component_names_its_path(self):
        p = value_of(app(PAIR, numeral(2), TRUE))
        result = observe(p, PairKind(NAT, NAT), 1_000)
        self.assertIsInstance(result, Malformed)
        self.assertEqual(result.path, "result.second")
        self.assertIn("neither a spine node", result.reason)

    def test_bad_requests_are_errors(self):
        with self.assertRaises(TypeError):
            observe(numeral(1), "natural", 10)
        with self.assertRaises(TypeError):
            observe(numeral(1), PairKind(NAT, "boolean"), 10)
        with self.assertRaises(ValueError):
            observe(App(I, I), NAT, 10)  # not a value yet
        with self.assertRaises(ValueError):
            observe(numeral(1), NAT, -1)


class ObservationBudgetTests(unittest.TestCase):
    def test_exact_boundaries(self):
        self.assertEqual(observe(numeral(2), NAT, 4), Decoded(2, 4, 4))
        self.assertEqual(observe(numeral(2), NAT, 3),
                         ObservationExhausted(3, 3, "result"))
        self.assertEqual(observe(TRUE, BOOL, 2), Decoded(True, 2, 2))
        self.assertEqual(observe(TRUE, BOOL, 1), ObservationExhausted(1, 1, "result"))
        self.assertEqual(observe(numeral(0), NAT, 2), Decoded(0, 2, 2))

    def test_pair_steps_are_totalled_across_components(self):
        p = value_of(app(PAIR, numeral(2), TRUE))
        kind = PairKind(NAT, BOOL)
        # FST p takes 4 steps, observing 2 takes 4, SND p 4, observing true 2.
        self.assertEqual(observe(p, kind, 14), Decoded((2, True), 14, 14))
        self.assertEqual(observe(p, kind, 13),
                         ObservationExhausted(13, 13, "result.second"))
        self.assertEqual(observe(p, kind, 5),
                         ObservationExhausted(5, 5, "result.first"))

    def test_budget_is_not_reset_for_each_component(self):
        # Each component needs 8 steps, which fits in 10; both together do not.
        p = value_of(app(PAIR, numeral(2), numeral(2)))
        self.assertEqual(observe(p, PairKind(NAT, NAT), 16).steps, 16)
        self.assertEqual(observe(p, PairKind(NAT, NAT), 10),
                         ObservationExhausted(10, 10, "result.second"))

    def test_execution_can_finish_before_observation_can(self):
        execution = evaluate(app(SUB, numeral(5), numeral(2)), 1_000)
        self.assertIsInstance(execution, Completed)
        self.assertEqual(observe(execution.value, NAT, 3),
                         ObservationExhausted(3, 3, "result"))
        self.assertEqual(observe(execution.value, NAT, 1_000).data, 3)


if __name__ == "__main__":
    unittest.main()
