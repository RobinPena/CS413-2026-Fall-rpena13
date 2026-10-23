"""The shared evaluator: exact budgets, weak left-to-right CBV, source semantics.

Divergent source programs are only ever run with a budget.
"""
import ast
import copy
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import MySolution.evaluator as evaluator_module
from MySolution.evaluator import evaluate
from MySolution.examples import (
    boolean, call, factorial, fibonacci, fix, fst, fun, if_, let, loop,
    loop_bool, not_, num, op, pair, snd, var,
)
from MySolution.results import (
    Completed, Exhausted, OpenTermError, SourceEvaluationError,
    UnsupportedSourceError,
)
from MySolution.source_support import show_source, source_data
from MySolution.target import App, Lam, Var, alpha_equivalent, show

ASSIGN06 = Path(__file__).resolve().parents[2]


def ident(name: str) -> Lam:
    return Lam(name, Var(name))


I = ident("x")
W = Lam("x", App(Var("x"), Var("x")))
OMEGA = App(W, W)


def nested_identity_calls(depth: int):
    """I (I (... (I I))): `depth` redexes nested in argument position."""
    term = I
    for _ in range(depth):
        term = App(I, term)
    return term


class TargetBudgetTests(unittest.TestCase):
    def test_value_completes_with_zero_steps_at_budget_zero(self):
        result = evaluate(I, 0)
        self.assertEqual(result, Completed(I, 0, 0))
        self.assertIs(result.value, I)

    def test_one_redex_exhausts_at_zero_and_completes_at_one(self):
        self.assertEqual(evaluate(App(I, I), 0), Exhausted(0, 0))
        self.assertEqual(evaluate(App(I, I), 1), Completed(I, 1, 1))

    def test_three_redexes_complete_exactly_on_the_last_step(self):
        term = App(App(I, I), App(I, I))
        self.assertEqual(evaluate(term, 2), Exhausted(2, 2))
        self.assertEqual(evaluate(term, 3), Completed(I, 3, 3))
        self.assertEqual(evaluate(term, 1000), Completed(I, 3, 1000))

    def test_omega_exhausts_every_budget_exactly(self):
        for budget in (0, 1, 2, 3, 10, 1000):
            with self.subTest(budget=budget):
                self.assertEqual(evaluate(OMEGA, budget), Exhausted(budget, budget))

    def test_long_runs_do_not_hit_python_recursion(self):
        self.assertEqual(evaluate(OMEGA, 20_000), Exhausted(20_000, 20_000))
        result = evaluate(nested_identity_calls(5_000), 10_000)
        self.assertEqual((type(result), result.steps), (Completed, 5_000))

    def test_budget_must_be_a_nonnegative_integer(self):
        for bad in (-1, True, 1.5, "3"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    evaluate(I, bad)
        with self.assertRaises(ValueError):
            evaluate(I)  # target execution is always bounded

    def test_open_terms_are_rejected_not_exhausted(self):
        for term in (Var("y"), App(I, Var("y")), Lam("x", Var("y"))):
            with self.subTest(show(term)):
                with self.assertRaises(OpenTermError) as caught:
                    evaluate(term, 0)
                self.assertEqual(caught.exception.names, {"y"})


class TargetStrategyTests(unittest.TestCase):
    def trace(self, term, budget):
        steps = []
        hook = lambda step, fn, arg: steps.append((step, show(fn), show(arg)))
        return evaluate(term, budget, on_step=hook), steps

    def test_function_then_argument_then_outer_contraction(self):
        term = App(App(ident("a"), ident("b")), App(ident("c"), ident("d")))
        result, steps = self.trace(term, 10)
        self.assertEqual(steps, [
            (1, "(lam a. a)", "(lam b. b)"),  # left child first
            (2, "(lam c. c)", "(lam d. d)"),  # then the right child
            (3, "(lam b. b)", "(lam d. d)"),  # then the outer application
        ])
        self.assertEqual(result, Completed(ident("d"), 3, 10))

    def test_function_position_is_evaluated_before_the_argument(self):
        # Omega in function position loops before (I I) is ever reached.
        result, steps = self.trace(App(OMEGA, App(ident("a"), ident("b"))), 5)
        self.assertEqual(result, Exhausted(5, 5))
        self.assertTrue(all(fn == show(W) for _, fn, _ in steps))

    def test_no_reduction_beneath_a_lambda(self):
        term = Lam("x", App(ident("y"), Var("x")))
        for budget in (0, 10):
            with self.subTest(budget=budget):
                result = evaluate(term, budget)
                self.assertEqual(result, Completed(term, 0, budget))
                self.assertIs(result.value, term)

    def test_no_eta_reduction(self):
        # (lam f. lam x. f x) I stops at lam x. I x; it is not turned into I.
        term = App(Lam("f", Lam("x", App(Var("f"), Var("x")))), ident("y"))
        result = evaluate(term, 10)
        self.assertEqual(show(result.value), "(lam x. ((lam y. y) x))")
        self.assertEqual(result.steps, 1)
        self.assertFalse(alpha_equivalent(result.value, ident("y")))

    def test_arguments_are_values_before_substitution(self):
        # A diverging argument is evaluated even though the body ignores it ...
        self.assertEqual(evaluate(App(Lam("x", I), OMEGA), 50), Exhausted(50, 50))
        # ... but a lambda argument is already a value, so its body never runs.
        delayed = App(Lam("x", I), Lam("y", OMEGA))
        self.assertEqual(evaluate(delayed, 50), Completed(I, 1, 50))

    def test_repeated_runs_agree_and_inputs_are_unchanged(self):
        for term, budget in ((App(App(I, I), App(I, I)), 3), (OMEGA, 7),
                             (App(Lam("x", I), Lam("y", OMEGA)), 5)):
            with self.subTest(show(term)):
                before = copy.deepcopy(term)
                first, second = evaluate(term, budget), evaluate(term, budget)
                self.assertEqual(first, second)
                self.assertEqual(term, before)


class SourceSemanticsTests(unittest.TestCase):
    def value(self, program, budget=1_000):
        result = evaluate(program, budget)
        self.assertIsInstance(result, Completed, show_source(program))
        return source_data(result.value)

    def check(self, cases):
        for program, expected in cases:
            with self.subTest(show_source(program)):
                actual = self.value(program)
                self.assertEqual((type(actual), actual), (type(expected), expected))

    def test_literals(self):
        self.check([(num(0), 0), (num(7), 7),
                    (boolean(True), True), (boolean(False), False)])

    def test_arithmetic_with_truncated_subtraction(self):
        self.check([
            (op("+", num(2), op("*", num(3), num(4))), 14),
            (op("+", num(0), num(0)), 0),
            (op("*", num(0), num(9)), 0),
            (op("*", num(6), num(7)), 42),
            (op("-", num(2), num(5)), 0),  # below zero truncates
            (op("-", num(3), num(3)), 0),
            (op("-", num(5), num(2)), 3),
            (op("-", num(0), num(0)), 0),
        ])

    def test_all_comparisons_both_ways(self):
        expected = {  # results for (2, 3), (3, 3), (3, 2)
            "<": (True, False, False), "<=": (True, True, False),
            ">": (False, False, True), ">=": (False, True, True),
            "==": (False, True, False), "!=": (True, False, True),
        }
        operands = ((2, 3), (3, 3), (3, 2))
        self.check([(op(name, num(m), num(n)), answer)
                    for name, answers in expected.items()
                    for (m, n), answer in zip(operands, answers)])
        self.check([(op("==", num(0), num(0)), True), (op("<", num(0), num(0)), False)])

    def test_boolean_truth_tables(self):
        T, F = True, False
        self.check([(not_(boolean(T)), F), (not_(boolean(F)), T)])
        self.check([(op("and", boolean(a), boolean(b)), r) for a, b, r in
                    ((T, T, T), (T, F, F), (F, T, F), (F, F, F))])
        self.check([(op("or", boolean(a), boolean(b)), r) for a, b, r in
                    ((T, T, T), (T, F, T), (F, T, T), (F, F, F))])

    def test_conditionals_test_a_boolean(self):
        self.check([
            (if_(boolean(True), num(7), num(9)), 7),
            (if_(boolean(False), num(7), num(9)), 9),
            (if_(op("<=", num(2), num(3)), num(7), num(9)), 7),
        ])

    def test_functions_and_lexical_scope(self):
        self.check([
            (call(fun("f", call(var("f"), num(3))),
                  fun("x", op("+", var("x"), num(1)))), 4),
            (let("x", num(3), call(fun("y", op("+", var("x"), var("y"))), num(4))), 7),
            # Nested lets shadow; the inner initializer sees the outer x.
            (let("x", num(7), let("x", op("+", var("x"), num(1)), var("x"))), 8),
            (let("x", num(2), let("x", op("*", var("x"), num(10)), var("x"))), 20),
            # f keeps the x it was defined with, not the later one.
            (let("x", num(10),
                 let("f", fun("y", op("+", var("x"), var("y"))),
                     let("x", num(20), call(var("f"), num(1))))), 11),
            # Nested lambdas with a shadowed parameter.
            (call(fun("x", fun("x", var("x"))), num(1), num(2)), 2),
        ])

    def test_a_function_result_has_no_data_form(self):
        result = evaluate(fun("x", var("x")))
        self.assertEqual(show_source(result.value), "(lam x. x)")
        with self.assertRaises(TypeError):
            source_data(result.value)

    def test_pairs_and_projections(self):
        self.check([
            (fst(pair(num(2), boolean(True))), 2),
            (snd(pair(num(2), boolean(True))), True),
            (pair(op("+", num(1), num(1)), not_(boolean(False))), (2, True)),
            (pair(pair(num(2), boolean(True)), num(3)), ((2, True), 3)),
            (snd(fst(pair(pair(num(2), boolean(True)), num(3)))), True),
        ])

    def test_recursion(self):
        self.check([(factorial(0), 1), (factorial(1), 1), (factorial(4), 24)])
        self.check([(fibonacci(n), f) for n, f in
                    ((0, 0), (1, 1), (2, 1), (3, 2), (4, 3), (5, 5), (6, 8))])
        # The parameter shadows the function name when the two coincide.
        self.check([(call(fix("f", "f", var("f")), num(3)), 3)])
        # Distinct binders: f is the function, n the parameter.
        countdown = fix("f", "n", if_(op("==", var("n"), num(0)), num(0),
                                      call(var("f"), op("-", var("n"), num(1)))))
        self.check([(call(countdown, num(3)), 0)])

    def test_unselected_branches_and_operands_are_skipped(self):
        self.check([
            (if_(boolean(True), num(1), loop()), 1),
            (if_(boolean(False), loop(), num(2)), 2),
            (op("and", boolean(False), loop_bool()), False),
            (op("or", boolean(True), loop_bool()), True),
        ])

    def test_selected_divergence_and_strict_positions_exhaust(self):
        for program in (
            if_(boolean(True), loop(), num(2)),      # selected branches
            if_(boolean(False), num(1), loop()),
            if_(loop_bool(), num(1), num(2)),        # the condition itself
            op("and", boolean(True), loop_bool()),
            op("or", boolean(False), loop_bool()),
            op("and", loop_bool(), boolean(False)),
            not_(loop_bool()),
            call(fun("x", num(0)), loop()),          # unused argument
            call(loop(), num(1)),
            let("x", loop(), num(2)),                # unused initializer
            pair(num(2), loop()),
            fst(pair(num(2), loop())),               # either pair field
            snd(pair(loop(), boolean(True))),
            op("+", loop(), num(1)),
            op("*", num(1), loop()),
            loop(),
        ):
            with self.subTest(show_source(program)):
                self.assertEqual(evaluate(program, 200), Exhausted(200, 200))

    def test_evaluation_order_is_left_to_right(self):
        tag = lambda e: call(fun("t", var("t")), e)  # an identity call we can see
        cases = [
            (op("+", tag(num(1)), tag(num(2))), ["1", "2"]),
            (op("<", tag(num(1)), tag(num(2))), ["1", "2"]),
            (pair(tag(num(1)), tag(num(2))), ["1", "2"]),
            (let("a", tag(num(1)), tag(num(2))), ["1", "2"]),
            (op("and", tag(boolean(True)), tag(boolean(False))), ["true", "false"]),
            (op("or", tag(boolean(False)), tag(boolean(True))), ["false", "true"]),
            (if_(tag(boolean(True)), tag(num(1)), tag(num(2))), ["true", "1"]),
            # Function position, then argument, then the call itself.
            (call(tag(fun("y", var("y"))), tag(num(5))), ["(lam y. y)", "5", "5"]),
        ]
        for program, expected in cases:
            with self.subTest(show_source(program)):
                seen = []
                evaluate(program, 100, on_step=lambda _, fn, arg: seen.append(show_source(arg)))
                self.assertEqual(seen, expected)

    def test_type_errors_are_reported(self):
        for program in (op("+", num(1), boolean(True)), call(num(3), num(4)),
                        fst(num(3)), if_(num(1), num(2), num(3)), not_(num(0))):
            with self.subTest(show_source(program)):
                with self.assertRaises(SourceEvaluationError):
                    evaluate(program, 100)

    def test_unsupported_forms_are_rejected_before_running(self):
        steps = []
        program = call(fun("x", var("x")), if_(boolean(True), num(1),
                                               op("/", num(1), num(0))))
        with self.assertRaises(UnsupportedSourceError):
            evaluate(program, 100, on_step=lambda *step: steps.append(step))
        self.assertEqual(steps, [])

    def test_open_programs_are_rejected(self):
        with self.assertRaises(OpenTermError) as caught:
            evaluate(let("x", var("x"), var("x")))
        self.assertEqual(caught.exception.names, {"x"})

    def test_inputs_unchanged_and_repeated_runs_agree(self):
        for program in (factorial(3), let("x", num(3), op("+", var("x"), var("x"))),
                        snd(pair(num(1), boolean(False)))):
            with self.subTest(show_source(program)):
                before = copy.deepcopy(program)
                first, second = evaluate(program), evaluate(program)
                self.assertEqual(first, second)
                self.assertEqual(program, before)


class SingleEvaluatorTests(unittest.TestCase):
    def test_both_languages_run_on_the_same_machine(self):
        with mock.patch.object(evaluator_module, "_run",
                               wraps=evaluator_module._run) as machine:
            evaluate(App(I, I), 5)
            evaluate(factorial(2))
        languages = [c.args[1] for c in machine.call_args_list]
        self.assertEqual(languages, [evaluator_module.TARGET, evaluator_module.SOURCE])

    def test_target_runs_never_use_source_operations(self):
        fail = mock.Mock(side_effect=AssertionError("source operation used"))
        with mock.patch.object(evaluator_module, "source_substitute", fail), \
             mock.patch.object(evaluator_module.SOURCE, "start", fail):
            self.assertEqual(evaluate(App(App(I, I), App(I, I)), 3).steps, 3)

    def test_source_runs_never_use_target_substitution(self):
        fail = mock.Mock(side_effect=AssertionError("target substitution used"))
        with mock.patch.object(evaluator_module, "substitute", fail):
            self.assertEqual(source_data(evaluate(factorial(3)).value), 6)

    def test_supplied_interpreter_is_not_used(self):
        supplied = sys.modules["lambda1_vp"]
        fail = mock.Mock(side_effect=AssertionError("supplied evaluator used"))
        with mock.patch.object(supplied.EvaluateVisitor, "__init__", fail), \
             mock.patch.object(supplied, "d0exp_evaluate", fail):
            with self.assertRaises(AssertionError):
                supplied.d0exp_evaluate(num(1))  # the patch is in force
            self.assertEqual(source_data(evaluate(factorial(4)).value), 24)

    def test_evaluator_imports_no_compiler_or_encodings(self):
        source = Path(evaluator_module.__file__).read_text(encoding="utf-8")
        imported = {node.module for node in ast.walk(ast.parse(source))
                    if isinstance(node, ast.ImportFrom)}
        self.assertEqual(imported, {"__future__", "collections.abc", "dataclasses",
                                    "results", "source_support", "target"})
        for name in ("EvaluateVisitor", "d0exp_evaluate", "compile_expr"):
            self.assertNotIn(name, source)

    def test_importing_the_evaluator_loads_no_compiler(self):
        code = ("import sys, MySolution.evaluator; "
                "print(sorted(m for m in sys.modules if m.startswith('MySolution')))")
        loaded = subprocess.run([sys.executable, "-c", code], cwd=ASSIGN06,
                                capture_output=True, text=True, check=True).stdout
        self.assertEqual(loaded.strip(), str(sorted([
            "MySolution", "MySolution.evaluator", "MySolution.names",
            "MySolution.results", "MySolution.source_support", "MySolution.target"])))


if __name__ == "__main__":
    unittest.main()
