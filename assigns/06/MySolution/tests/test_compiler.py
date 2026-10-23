"""The compiler: translation rules, purity, scope, freshness, and end-to-end meaning.

End-to-end cases compare three things: an explicit expected answer, the
shared evaluator's source result, and the observed result of the compiled
program run by the same evaluator.
"""
import ast
import copy
import dataclasses
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import MySolution.compiler as compiler_module
import MySolution.evaluator as evaluator_module
from MySolution.compiler import compile_expr
from MySolution.encodings import (
    ADD, EQ, FALSE, FST, GEQ, GT, LEQ, LIBRARY, LIBRARY_NAMES, LT, MUL, NEQ,
    NOT, PAIR, SND, SUB, TRUE, Z, numeral,
)
from MySolution.evaluator import evaluate
from MySolution.examples import (
    boolean, call, factorial, fibonacci, fix, fst, fun, if_, let, loop,
    loop_bool, not_, num, op, pair, snd, var,
)
from MySolution.observers import observe
from MySolution.results import (
    BOOL, NAT, Completed, Decoded, Exhausted, PairKind, UnsupportedSourceError,
    same_data,
)
from MySolution.source_support import (
    BINARY_OPERATORS, D0E000, D0Eop1, D0Eop2, show_source, source_data,
    source_fv, source_names,
)
from MySolution.target import (
    App, Lam, Var, all_names, app, free_vars, iter_nodes, show, substitute,
)

ASSIGN06 = Path(__file__).resolve().parents[2]
a, b, c = var("a"), var("b"), var("c")


def source_nodes(dexp):
    """Every node of a source tree (the supplied classes are dataclasses)."""
    todo = [dexp]
    while todo:
        node = todo.pop()
        yield node
        todo += [getattr(node, f.name) for f in dataclasses.fields(node)
                 if isinstance(getattr(node, f.name), D0E000)]


def run_compiled(program, kind, execution_budget=100_000, observation_budget=100_000):
    execution = evaluate(compile_expr(program), execution_budget)
    assert isinstance(execution, Completed), (show_source(program), execution)
    observation = observe(execution.value, kind, observation_budget)
    assert isinstance(observation, Decoded), (show_source(program), observation)
    return observation.data


class TranslationRuleTests(unittest.TestCase):
    def test_literals_and_variables(self):
        self.assertEqual(compile_expr(num(0)), numeral(0))
        self.assertEqual(compile_expr(num(3)), numeral(3))
        self.assertEqual(compile_expr(boolean(True)), TRUE)
        self.assertEqual(compile_expr(boolean(False)), FALSE)
        self.assertEqual(compile_expr(var("x")), Var("x"))

    def test_lambda_application_let(self):
        self.assertEqual(compile_expr(fun("x", var("y"))), Lam("x", Var("y")))
        self.assertEqual(compile_expr(call(var("f"), var("x"))), App(Var("f"), Var("x")))
        self.assertEqual(compile_expr(let("x", a, var("x"))),
                         App(Lam("x", Var("x")), Var("a")))

    def test_strict_operators(self):
        expected = {"+": ADD, "-": SUB, "*": MUL, "<": LT, "<=": LEQ, ">": GT,
                    ">=": GEQ, "==": EQ, "!=": NEQ}
        for name, combinator in expected.items():
            with self.subTest(name):
                self.assertEqual(compile_expr(op(name, a, b)),
                                 app(combinator, Var("a"), Var("b")))
        self.assertEqual(compile_expr(not_(a)), App(NOT, Var("a")))

    def test_conditional_and_short_circuit_thunks(self):
        self.assertEqual(show(compile_expr(if_(c, var("t"), var("f")))),
                         "(((c (lam u_1. t)) (lam v_1. f)) (lam w. w))")
        self.assertEqual(show(compile_expr(op("and", a, b))),
                         "(((a (lam u_1. b)) (lam v_1. (lam t. (lam f. f))))"
                         " (lam w. w))")
        self.assertEqual(show(compile_expr(op("or", a, b))),
                         "(((a (lam u_1. (lam t. (lam f. t)))) (lam v_1. b))"
                         " (lam w. w))")

    def test_pairs_and_projections(self):
        self.assertEqual(compile_expr(pair(a, b)), app(PAIR, Var("a"), Var("b")))
        self.assertEqual(compile_expr(fst(a)), App(FST, Var("a")))
        self.assertEqual(compile_expr(snd(a)), App(SND, Var("a")))

    def test_fix_including_coincident_binders(self):
        self.assertEqual(compile_expr(fix("f", "n", call(var("f"), var("n")))),
                         App(Z, Lam("f", Lam("n", App(Var("f"), Var("n"))))))
        # The inner lam f (the parameter) shadows the outer one (the function).
        self.assertEqual(compile_expr(fix("f", "f", var("f"))),
                         App(Z, Lam("f", Lam("f", Var("f")))))

    def test_translation_is_compositional(self):
        left = if_(c, num(1), num(2))
        right = op("*", var("x"), num(3))
        self.assertEqual(compile_expr(op("+", left, right)),
                         app(ADD, compile_expr(left), compile_expr(right)))


# (program, expected kind, explicit expected answer)
END_TO_END = [
    (num(0), NAT, 0), (num(5), NAT, 5),
    (boolean(True), BOOL, True), (boolean(False), BOOL, False),
    # Arithmetic, including truncated subtraction.
    (op("+", num(2), op("*", num(3), num(4))), NAT, 14),
    (op("+", num(0), num(0)), NAT, 0), (op("*", num(0), num(4)), NAT, 0),
    (op("-", num(2), num(5)), NAT, 0), (op("-", num(3), num(3)), NAT, 0),
    (op("-", num(5), num(2)), NAT, 3),
    # Every comparison, true and false.
    *[(op(name, num(m), num(n)), BOOL, answer)
      for name, answers in {
          "<": (True, False, False), "<=": (True, True, False),
          ">": (False, False, True), ">=": (False, True, True),
          "==": (False, True, False), "!=": (True, False, True)}.items()
      for (m, n), answer in zip(((2, 3), (3, 3), (3, 2)), answers)],
    (op("==", num(0), num(0)), BOOL, True),
    # Boolean truth tables.
    (not_(boolean(True)), BOOL, False), (not_(boolean(False)), BOOL, True),
    *[(op("and", boolean(x), boolean(y)), BOOL, x and y)
      for x in (True, False) for y in (True, False)],
    *[(op("or", boolean(x), boolean(y)), BOOL, x or y)
      for x in (True, False) for y in (True, False)],
    # Conditionals, functions, lets and lexical scope.
    (if_(boolean(True), num(7), num(9)), NAT, 7),
    (if_(boolean(False), num(7), num(9)), NAT, 9),
    (if_(op("<=", num(2), num(3)), num(7), num(9)), NAT, 7),
    (let("x", num(3), call(fun("y", op("+", var("x"), var("y"))), num(4))), NAT, 7),
    (call(fun("f", call(var("f"), num(3))), fun("x", op("+", var("x"), num(1)))), NAT, 4),
    (let("x", num(7), let("x", op("+", var("x"), num(1)), var("x"))), NAT, 8),
    (let("x", num(2), let("x", op("*", var("x"), num(3)), var("x"))), NAT, 6),
    (let("x", num(10), let("f", fun("y", op("+", var("x"), var("y"))),
                           let("x", num(20), call(var("f"), num(1))))), NAT, 11),
    (call(fun("x", fun("x", var("x"))), num(1), num(2)), NAT, 2),
    # Pairs.
    (fst(pair(num(2), boolean(True))), NAT, 2),
    (snd(pair(num(2), boolean(True))), BOOL, True),
    (pair(pair(num(2), boolean(True)), num(3)), PairKind(PairKind(NAT, BOOL), NAT),
     ((2, True), 3)),
    (snd(fst(pair(pair(num(2), boolean(True)), num(3)))), BOOL, True),
    # Recursion, including coincident binders.
    (factorial(0), NAT, 1), (factorial(4), NAT, 24),
    (fibonacci(0), NAT, 0), (fibonacci(1), NAT, 1), (fibonacci(5), NAT, 5),
    (call(fix("f", "f", var("f")), num(3)), NAT, 3),
    # With coincident binders, f in the body is the parameter, here a function.
    (call(fix("f", "f", call(var("f"), num(1))), fun("y", op("+", var("y"), num(1)))),
     NAT, 2),
    # Each fix binder shadows an outer binding of the same name ...
    (let("f", num(9), call(fix("f", "n", if_(op("==", var("n"), num(0)), num(0),
                                              call(var("f"), op("-", var("n"), num(1))))),
                           num(2))), NAT, 0),
    (let("n", num(9), call(fix("f", "n", if_(op("==", var("n"), num(0)), num(5),
                                              call(var("f"), op("-", var("n"), num(1))))),
                           num(2))), NAT, 5),
    # ... and a later binding of the function's name does not reach inside it.
    (let("g", fix("f", "n", op("+", var("n"), num(1))),
         let("f", num(100), call(var("g"), num(2)))), NAT, 3),
    (let("y", num(1), call(fun("x", fun("y", op("+", var("x"), var("y")))),
                           var("y"), num(2))), NAT, 3),
    # Source names that coincide with encoding binders (s, z, t, f, x) and with
    # Z's own binders (g, x, v), including a free outer variable in a fix body.
    (let("s", num(1), let("z", num(2), let("t", boolean(True), let("f", boolean(False),
        let("x", num(3), if_(var("t"), op("+", op("+", var("s"), var("z")), var("x")),
                             num(0))))))), NAT, 6),
    (call(fix("s", "z", if_(op("==", var("z"), num(0)), num(0),
                            call(var("s"), op("-", var("z"), num(1))))), num(3)), NAT, 0),
    (let("x", num(4), call(fix("g", "v", if_(op("==", var("v"), num(0)), var("x"),
                                             call(var("g"), op("-", var("v"), num(1))))),
                           num(2))), NAT, 4),
    (let("n", num(5), call(fix("f", "x", if_(op("==", var("x"), num(0)), var("n"),
                                             call(var("f"), op("-", var("x"), num(1))))),
                           num(2))), NAT, 5),
]


class EndToEndTests(unittest.TestCase):
    def test_cases_cover_every_constructor_and_operator(self):
        forms, operators = set(), set()
        for program, _, _ in END_TO_END:
            for node in source_nodes(program):
                forms.add(type(node))
                if isinstance(node, (D0Eop1, D0Eop2)):
                    operators.add(node.name)
        self.assertEqual(forms, set(D0E000.__subclasses__()))
        self.assertEqual(operators, BINARY_OPERATORS | {"not"})

    def test_source_and_compiled_results_match_the_expected_answers(self):
        for program, kind, expected in END_TO_END:
            with self.subTest(show_source(program)):
                source_result = source_data(evaluate(program, 10_000).value)
                compiled_result = run_compiled(program, kind)
                self.assertTrue(same_data(source_result, expected), source_result)
                self.assertTrue(same_data(compiled_result, expected), compiled_result)

    def test_arithmetic_and_comparison_sweep(self):
        expected = {
            "+": lambda m, n: m + n, "-": lambda m, n: max(m - n, 0),
            "*": lambda m, n: m * n, "<": lambda m, n: m < n,
            "<=": lambda m, n: m <= n, ">": lambda m, n: m > n,
            ">=": lambda m, n: m >= n, "==": lambda m, n: m == n,
            "!=": lambda m, n: m != n,
        }
        for name, answer in expected.items():
            for m in range(4):
                for n in range(4):
                    program = op(name, num(m), num(n))
                    want = answer(m, n)
                    kind = BOOL if type(want) is bool else NAT
                    with self.subTest(f"{m} {name} {n}"):
                        self.assertTrue(same_data(
                            source_data(evaluate(program, 1_000).value), want))
                        self.assertTrue(same_data(run_compiled(program, kind), want))

    def test_exact_steps_for_small_compiled_programs(self):
        # true and false = ((TRUE (lam u_1. FALSE)) (lam v_1. FALSE)) I:
        # TRUE takes the then-thunk (1), drops the else-thunk (2), and the
        # then-thunk is forced with I (3), giving FALSE.
        # if true then 1 else LOOP has the same shape: the LOOP thunk is
        # dropped at step 2 and never applied.
        # fst (pair 2 true): PAIR takes 2 (1) and TRUE (2), giving the pair
        # value q; FST q (3), q TRUE (4), TRUE takes 2 (5) and drops true (6).
        # let x = 3 in x = (lam x. x) NUM(3): one step.
        cases = [
            (op("and", boolean(True), boolean(False)), 3, FALSE),
            (if_(boolean(True), num(1), loop()), 3, numeral(1)),
            (fst(pair(num(2), boolean(True))), 6, numeral(2)),
            (let("x", num(3), var("x")), 1, numeral(3)),
        ]
        for program, steps, value in cases:
            with self.subTest(show_source(program)):
                term = compile_expr(program)
                self.assertEqual(evaluate(term, steps - 1), Exhausted(steps - 1, steps - 1))
                self.assertEqual(evaluate(term, steps), Completed(value, steps, steps))

    def test_unselected_code_is_skipped(self):
        for program, kind, expected in (
            (op("and", boolean(False), loop_bool()), BOOL, False),
            (op("or", boolean(True), loop_bool()), BOOL, True),
            (if_(boolean(True), num(1), loop()), NAT, 1),
            (if_(boolean(False), loop(), num(2)), NAT, 2),
        ):
            with self.subTest(show_source(program)):
                self.assertTrue(same_data(run_compiled(program, kind), expected))

    def test_selected_or_strict_divergence_exhausts(self):
        for program in (
            op("and", boolean(True), loop_bool()),
            op("or", boolean(False), loop_bool()),
            if_(boolean(True), loop(), num(2)),
            if_(boolean(False), num(1), loop()),
            if_(loop_bool(), num(1), num(2)),
            not_(loop_bool()),
            call(fun("x", num(0)), loop()),
            call(loop(), num(1)),
            let("x", loop(), num(2)),
            pair(num(2), loop()),
            fst(pair(num(2), loop())),
            snd(pair(loop(), boolean(True))),
            op("+", loop(), num(1)),
            op("*", num(1), loop()),
            op("<", num(1), loop()),
            op("and", loop_bool(), boolean(False)),
            loop(),
        ):
            with self.subTest(show_source(program)):
                self.assertEqual(evaluate(compile_expr(program), 5_000),
                                 Exhausted(5_000, 5_000))

    def test_skipped_operands_are_still_compiled(self):
        self.assertEqual(free_vars(compile_expr(op("and", boolean(False), var("q")))), {"q"})
        self.assertEqual(free_vars(compile_expr(op("or", boolean(True), var("q")))), {"q"})


ALL_PROGRAMS = [program for program, _, _ in END_TO_END] + [
    loop(), loop_bool(), call(fun("x", num(0)), loop()),
    if_(var("s"), var("z"), var("t")), op("and", var("f"), var("x")),
    let("x", var("x"), var("x")), fix("f", "n", op("+", var("m"), var("n"))),
]


class PurityAndScopeTests(unittest.TestCase):
    def test_output_has_only_the_three_target_forms(self):
        for program in ALL_PROGRAMS:
            with self.subTest(show_source(program)):
                term = compile_expr(program)
                self.assertTrue(all(type(node) in (Var, Lam, App)
                                    for node in iter_nodes(term)))
                self.assertFalse(all_names(term) & set(LIBRARY))  # no "ADD" etc.

    def test_every_reachable_object_is_target_syntax(self):
        # Walks every dataclass field, so it does not rely on iter_nodes.
        terms = [compile_expr(program) for program in ALL_PROGRAMS]
        for term in terms + list(LIBRARY.values()):
            todo = [term]
            while todo:
                node = todo.pop()
                self.assertIn(type(node), (Var, Lam, App))
                for field in dataclasses.fields(node):
                    value = getattr(node, field.name)
                    if isinstance(value, (Var, Lam, App)):
                        todo.append(value)
                    elif field.name == "fv":
                        self.assertTrue(all(type(n) is str for n in value))
                    else:
                        self.assertIs(type(value), str)

    def test_library_and_generated_looking_names_stay_free(self):
        names = sorted(LIBRARY_NAMES | {"u", "u_1", "v_1", "w_1", "I", "Z", "ADD"})
        program = var(names[0])
        for name in names[1:]:
            program = if_(var(name), program, pair(var(name), num(0)))
        self.assertEqual(free_vars(compile_expr(program)), set(names))

    def test_open_programs_mean_the_same_once_closed(self):
        # Compile an open program, then substitute compiled closed values for
        # its free variables; encoding-style names must not have been captured.
        cases = [
            (op("+", var("s"), var("z")), {"s": num(2), "z": num(3)}, NAT, 5),
            (if_(var("t"), var("x"), var("f")),
             {"t": boolean(False), "x": num(1), "f": num(0)}, NAT, 0),
            (op("and", var("f"), var("x")),
             {"f": boolean(True), "x": boolean(False)}, BOOL, False),
            (call(fix("s", "z", if_(op("==", var("z"), num(0)), var("x"),
                                    call(var("s"), op("-", var("z"), num(1))))),
                  var("n")), {"x": num(7), "n": num(2)}, NAT, 7),
            (if_(var("u_1"), var("v_1"), var("u_2")),
             {"u_1": boolean(True), "v_1": num(4), "u_2": num(5)}, NAT, 4),
        ]
        for program, values, kind, expected in cases:
            with self.subTest(show_source(program)):
                term = compile_expr(program)
                self.assertEqual(free_vars(term), set(values))
                for name, value in values.items():
                    term = substitute(term, name, compile_expr(value))
                execution = evaluate(term, 10_000)
                self.assertTrue(same_data(observe(execution.value, kind, 10_000).data,
                                          expected))

    def test_moderately_deep_source_programs(self):
        # The source visitors recurse once per level; 250 levels is well
        # within Python's default limit (the mandatory examples nest far less).
        program = num(1)
        for _ in range(250):
            program = op("+", program, num(1))
        self.assertTrue(same_data(source_data(evaluate(program).value), 251))
        self.assertEqual(run_compiled(program, NAT), 251)

    def test_free_variables_are_preserved(self):
        cases = [
            (let("x", var("x"), var("x")), {"x"}),
            (fun("x", op("+", var("x"), var("y"))), {"y"}),
            (let("y", op("+", var("y"), num(1)), fun("y", var("y"))), {"y"}),
            (fix("f", "n", call(var("f"), op("+", var("n"), var("m")))), {"m"}),
            (fix("f", "f", call(var("f"), var("g"))), {"g"}),
            (if_(var("s"), var("z"), var("t")), {"s", "z", "t"}),
            (op("or", op("and", var("f"), var("x")), not_(var("t"))), {"f", "x", "t"}),
            (fun("s", fun("z", op("+", call(var("s"), var("z")), var("x")))), {"x"}),
            (pair(fst(var("p")), snd(var("q"))), {"p", "q"}),
            (if_(var("u_1"), var("v_1"), var("u_2")), {"u_1", "v_1", "u_2"}),
        ] + [(program, set()) for program in ALL_PROGRAMS
             if not source_fv(program)]
        for program, expected in cases:
            with self.subTest(show_source(program)):
                self.assertEqual(source_fv(program), expected)
                self.assertEqual(free_vars(compile_expr(program)), expected)

    def test_thunk_names_avoid_names_that_look_generated(self):
        program = if_(var("u_1"), var("v_1"), var("u_2"))
        self.assertEqual(show(compile_expr(program)),
                         "(((u_1 (lam u_3. v_1)) (lam v_2. u_2)) (lam w. w))")

    def test_generated_binders_are_new_distinct_and_unused(self):
        for program in ALL_PROGRAMS:
            with self.subTest(show_source(program)):
                known = source_names(program) | LIBRARY_NAMES
                generated = [node for node in iter_nodes(compile_expr(program))
                             if isinstance(node, Lam) and node.name not in known]
                names = [node.name for node in generated]
                self.assertEqual(len(names), len(set(names)))
                for node in generated:
                    self.assertNotIn(node.name, free_vars(node.body))

    def test_deterministic_and_source_unchanged(self):
        for program in ALL_PROGRAMS:
            with self.subTest(show_source(program)):
                before = copy.deepcopy(program)
                first = compile_expr(program)
                compile_expr(if_(var("other"), num(1), num(2)))  # no shared state
                second = compile_expr(program)
                self.assertEqual(first, second)
                self.assertEqual(show(first), show(second))
                self.assertEqual(program, before)


class NoEvaluationTests(unittest.TestCase):
    def test_compiles_with_the_evaluator_disabled(self):
        fail = mock.Mock(side_effect=AssertionError("compiler called the evaluator"))
        with mock.patch.object(evaluator_module, "evaluate", fail), \
             mock.patch.object(evaluator_module, "_run", fail):
            with self.assertRaises(AssertionError):
                evaluator_module.evaluate(num(1))  # the double does intercept
            fail.reset_mock()
            for program in (op("+", num(2), op("*", num(3), num(4))), loop(),
                            factorial(4), if_(boolean(True), num(1), loop())):
                with self.subTest(show_source(program)):
                    before = copy.deepcopy(program)
                    term = compile_expr(program)
                    self.assertTrue(all(type(n) in (Var, Lam, App) for n in iter_nodes(term)))
                    self.assertEqual(program, before)
            fail.assert_not_called()

    def test_compiler_does_not_import_the_evaluator(self):
        source = Path(compiler_module.__file__).read_text(encoding="utf-8")
        imported = {node.module for node in ast.walk(ast.parse(source))
                    if isinstance(node, ast.ImportFrom)}
        self.assertEqual(imported, {"__future__", "encodings", "names",
                                    "source_support", "target"})
        code = ("import sys, MySolution.compiler; "
                "print(sorted(m for m in sys.modules if m.startswith('MySolution')))")
        loaded = subprocess.run([sys.executable, "-c", code], cwd=ASSIGN06,
                                capture_output=True, text=True, check=True).stdout
        self.assertNotIn("MySolution.evaluator", loaded)
        self.assertNotIn("MySolution.observers", loaded)

    def test_visitor_dispatch(self):
        visitor = compiler_module.CompileVisitor(compiler_module.FreshNames(set()))
        self.assertEqual(num(2).accept(visitor), numeral(2))


class RejectionTests(unittest.TestCase):
    def test_unsupported_forms_are_rejected_wherever_they_are(self):
        division = op("/", num(4), num(2))
        cases = [
            (num(-1), "negative literal -1"),
            (division, "'/'"),
            (D0Eop1("+1", num(1)), "'+1'"),
            (D0Eop1("-1", num(1)), "'-1'"),
            (op("%", num(1), num(2)), "'%'"),
            (if_(boolean(True), num(1), num(-2)), "if: else branch"),
            (fun("x", division), "lam x: body"),
            (fix("f", "n", op("+", var("n"), num(-1))), "fix f(n): body"),
            (op("and", boolean(False), op("==", division, num(2))),
             "'and': right operand"),
            (op("or", boolean(True), not_(D0Eop1("neg", boolean(True)))),
             "'or': right operand"),
            (if_(boolean(False), num(-1), num(2)), "if: then branch"),
            (let("x", division, num(1)), "let x: initializer"),
            (pair(num(1), D0Eop1("!", boolean(True))), "pair: second"),
            (call(fun("x", var("x")), division), "application: argument"),
            (call(division, num(1)), "application: function"),
            (op("&&", boolean(True), boolean(True)), "'&&'"),
            (op("||", boolean(True), boolean(True)), "'||'"),
            (op("=", num(1), num(1)), "'='"),
            (op("AND", boolean(True), boolean(True)), "'AND'"),
        ]
        for program, fragment in cases:
            with self.subTest(fragment):
                with self.assertRaises(UnsupportedSourceError) as caught:
                    compile_expr(program)
                self.assertIn(fragment, str(caught.exception))

    def test_rejects_non_source_input(self):
        with self.assertRaises(TypeError):
            compile_expr(Var("x"))


if __name__ == "__main__":
    unittest.main()
