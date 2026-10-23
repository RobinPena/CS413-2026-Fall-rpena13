"""The Lambda Arcade demonstration: the 14 required examples, saved terms, exit status.

The case table is checked against an independent copy of the requirements
table, and every saved term is checked against a fresh compilation.
"""
import contextlib
import io
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import MySolution.demo as demo
from MySolution.compiler import compile_expr
from MySolution.evaluator import evaluate
from MySolution.examples import boolean, num
from MySolution.results import (
    BOOL, NAT, Completed, Decoded, Exhausted, Malformed, ObservationExhausted,
    has_kind, same_data,
)
from MySolution.source_support import D0E000, show_source
from MySolution.target import show

ASSIGN06 = Path(__file__).resolve().parents[2]

# The requirements table, restated: ID -> (expected kind, answer), where
# None means execution-budget exhaustion.
REQUIRED = {
    "DEMO-01": (NAT, 14), "DEMO-02": (NAT, 0), "DEMO-03": (NAT, 7),
    "DEMO-04": (NAT, 7), "DEMO-05": (NAT, 2), "DEMO-06": (BOOL, True),
    "DEMO-07": (NAT, 4), "DEMO-08": (NAT, 1), "DEMO-09": None,
    "DEMO-10": (NAT, 24), "DEMO-11": (NAT, 5), "DEMO-12": None,
    "DEMO-13": (BOOL, False), "DEMO-14": (BOOL, True),
}

LOOP = "((fix loop(x). (loop x)) 0)"
SOURCES = {
    "DEMO-01": "(2 + (3 * 4))",
    "DEMO-02": "(2 - 5)",
    "DEMO-03": "(if (2 <= 3) then 7 else 9)",
    "DEMO-04": "(let x = 3 in ((lam y. (x + y)) 4))",
    "DEMO-05": "(fst (pair 2 true))",
    "DEMO-06": "(snd (pair 2 true))",
    "DEMO-07": "((lam f. (f 3)) (lam x. (x + 1)))",
    "DEMO-08": f"(if true then 1 else {LOOP})",
    "DEMO-09": f"((lam x. 0) {LOOP})",
    "DEMO-10": "((fix fact(n). (if (n == 0) then 1 else (n * (fact (n - 1))))) 4)",
    "DEMO-11": "((fix fib(n). (if (n < 2) then n else "
               "((fib (n - 1)) + (fib (n - 2))))) 5)",
    "DEMO-12": LOOP,
    "DEMO-13": "(true and false)",
    "DEMO-14": "(false or true)",
}

# A printed target term has only these tokens.
PURE_TOKEN = re.compile(r"\(|\)|\.|lam\b|[A-Za-z_][A-Za-z0-9_]*")


def run_main(*argv):
    """Run the command line in-process; return (exit status, output)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        status = demo.main(list(argv))
    return status, out.getvalue()


class TemporaryTermsDir(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.terms_dir = Path(temp.name)


class CaseTableTests(unittest.TestCase):
    def test_the_fourteen_required_examples_in_order(self):
        self.assertEqual([case.id for case in demo.CASES], list(REQUIRED))

    def test_expected_results_match_the_requirements(self):
        for case in demo.CASES:
            with self.subTest(case.id):
                if REQUIRED[case.id] is None:
                    self.assertTrue(case.diverges)
                    self.assertIsNone(case.expected)
                else:
                    kind, answer = REQUIRED[case.id]
                    self.assertEqual(case.kind, kind)
                    self.assertTrue(same_data(case.expected, answer))
                    self.assertTrue(has_kind(case.kind, case.expected))

    def test_sources_are_the_required_programs(self):
        for case in demo.CASES:
            with self.subTest(case.id):
                self.assertEqual(show_source(case.build()), SOURCES[case.id])

    def test_each_build_returns_a_fresh_tree(self):
        for case in demo.CASES:
            with self.subTest(case.id):
                first, second = case.build(), case.build()
                self.assertIsInstance(first, D0E000)
                self.assertIsNot(first, second)


class FullRunTests(unittest.TestCase):
    """The default command, run once; every check reads its output or records."""

    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.terms_dir = Path(temp.name)
        recorded = []
        real_run_case = demo.run_case

        def recording_run_case(*args, **kwargs):
            recorded.append(real_run_case(*args, **kwargs))
            return recorded[-1]

        with mock.patch.object(demo, "run_case", recording_run_case):
            cls.status, cls.output = run_main("--terms-dir", str(cls.terms_dir))
        cls.results = {result.case.id: result for result in recorded}

    def test_all_fourteen_run_and_pass(self):
        self.assertEqual(self.status, 0)
        self.assertEqual(list(self.results), list(REQUIRED))
        self.assertTrue(all(result.passed for result in self.results.values()))
        self.assertIn("14 of 14 examples passed.", self.output)
        for case_id in REQUIRED:
            self.assertRegex(self.output, rf"(?m)^  {case_id}  PASS  ")

    def test_terminating_examples_agree_three_ways(self):
        for case_id, required in REQUIRED.items():
            if required is None:
                continue
            kind, answer = required
            result = self.results[case_id]
            with self.subTest(case_id):
                self.assertIsInstance(result.source_run, Completed)
                self.assertIsInstance(result.execution, Completed)
                self.assertEqual(result.execution.budget, demo.EXECUTION_BUDGET)
                self.assertIsInstance(result.observation, Decoded)
                self.assertEqual(result.observation.budget, demo.OBSERVATION_BUDGET)
                self.assertTrue(same_data(result.observation.data, answer))

    def test_divergent_examples_exhaust_without_source_or_observation(self):
        for case_id in ("DEMO-09", "DEMO-12"):
            result = self.results[case_id]
            with self.subTest(case_id):
                self.assertIsNone(result.source_run)
                self.assertEqual(result.execution,
                                 Exhausted(demo.EXECUTION_BUDGET, demo.EXECUTION_BUDGET))
                self.assertIsNone(result.observation)
        block = self.output.split("DEMO-12  Endless Hallway")[1]
        self.assertIn("skipped: known divergent example", block)
        self.assertIn("another step was needed", block)
        self.assertIn("not proof that it never finishes", block)
        self.assertIn("not attempted: execution did not finish", block)
        self.assertNotRegex(self.output, r"(?i)proven|diverges forever")

    def test_saved_terms_are_the_whole_pure_programs(self):
        for case in demo.CASES:
            path = self.terms_dir / f"{case.id}.txt"
            with self.subTest(case.id):
                self.assertEqual(self.results[case.id].term_file, path)
                text = path.read_text(encoding="utf-8")
                self.assertEqual(text, show(compile_expr(case.build())) + "\n")
                tokens = PURE_TOKEN.findall(text)
                self.assertEqual("".join(tokens), re.sub(r"\s", "", text))
                for name in ("ADD", "MUL", "Z", "PAIR", "TRUE", "NUM"):
                    self.assertNotIn(name, tokens)
                self.assertIn(demo.display_path(path), self.output)

    def test_each_example_reports_every_required_field(self):
        blocks = self.output.split("\n\n")
        for case in demo.CASES:
            block = next(b for b in blocks if b.startswith(case.id + "  "))
            with self.subTest(case.id):
                for label in ("example", "source AST", "expected", "source run",
                              "pure term", "execution", "observation", "result"):
                    self.assertRegex(block, rf"(?m)^  {label} +\S")
                self.assertIn(SOURCES[case.id], block)
                self.assertIn(f"of {demo.EXECUTION_BUDGET:,} beta-value steps", block)
                if not case.diverges:
                    self.assertIn(f"of {demo.OBSERVATION_BUDGET:,} steps", block)

    def test_default_budgets_leave_a_margin_over_measured_needs(self):
        for case_id, result in self.results.items():
            with self.subTest(case_id):
                if result.case.diverges:
                    continue
                self.assertLessEqual(4 * result.execution.steps, demo.EXECUTION_BUDGET)
                self.assertLessEqual(4 * result.observation.steps, demo.OBSERVATION_BUDGET)

    def test_the_numbers_in_the_docstring_are_the_measured_ones(self):
        fib, fact = self.results["DEMO-11"], self.results["DEMO-10"]
        largest_execution = max(r.execution.steps for r in self.results.values()
                                if not r.case.diverges)
        largest_observation = max(r.observation.steps for r in self.results.values()
                                  if not r.case.diverges)
        self.assertEqual(largest_execution, fib.execution.steps)
        self.assertEqual(largest_observation, fact.observation.steps)
        doc = " ".join(demo.__doc__.split())
        self.assertIn(f"{fib.execution.steps:,} execution steps (fibonacci 5)", doc)
        self.assertIn(f"{fact.observation.steps:,} observation steps (factorial 4)", doc)


class SourceSideTests(TemporaryTermsDir):
    def test_divergent_examples_never_reach_source_evaluation(self):
        calls = []

        def watching_evaluate(program, *args, **kwargs):
            calls.append(program)
            return evaluate(program, *args, **kwargs)

        with mock.patch.object(demo, "evaluate", watching_evaluate):
            for case in demo.CASES:
                calls.clear()
                demo.run_case(case, terms_dir=self.terms_dir)
                sources = [p for p in calls if isinstance(p, D0E000)]
                with self.subTest(case.id):
                    self.assertEqual(len(sources), 0 if case.diverges else 1)
                    self.assertEqual(len(calls) - len(sources), 1)


class BudgetOverrideTests(TemporaryTermsDir):
    def test_small_execution_budget_is_used_exactly_and_fails(self):
        status, output = run_main("--only", "DEMO-10", "--execution-budget", "100",
                                  "--terms-dir", str(self.terms_dir))
        self.assertEqual(status, 1)
        self.assertIn("exhausted after 100 of 100 beta-value steps", output)
        self.assertIn("not attempted: execution did not finish", output)
        self.assertIn("FAIL: expected 24, but execution exhausted its budget", output)
        self.assertIn("0 of 1 examples passed; failed: DEMO-10", output)

    def test_small_observation_budget_is_reported_separately(self):
        status, output = run_main("--only", "DEMO-10", "--observation-budget", "10",
                                  "--terms-dir", str(self.terms_dir))
        self.assertEqual(status, 1)
        self.assertRegex(output, r"execution +completed in [\d,]+ of 10,000 beta-value steps")
        self.assertIn("exhausted at result after 10 of 10 steps", output)

    def test_divergent_example_passes_at_any_budget(self):
        result = demo.run_case(demo.CASES[11], 0, 0, self.terms_dir)
        self.assertEqual(result.execution, Exhausted(0, 0))
        self.assertTrue(result.passed)

    def test_selection_follows_table_order(self):
        status, output = run_main("--only", "demo-14", "DEMO-01", "DEMO-14",
                                  "--terms-dir", str(self.terms_dir))
        self.assertEqual(status, 0)
        self.assertLess(output.index("DEMO-01  Scoreboard"),
                        output.index("DEMO-14  Either Switch"))
        self.assertIn("2 of 2 examples passed.", output)
        self.assertEqual(sorted(p.name for p in self.terms_dir.iterdir()),
                         ["DEMO-01.txt", "DEMO-14.txt"])

    def test_show_terms_prints_the_whole_term(self):
        _, output = run_main("--only", "DEMO-10", "--show-terms",
                             "--terms-dir", str(self.terms_dir))
        self.assertIn(show(compile_expr(demo.CASES[9].build())), output)
        _, output = run_main("--only", "DEMO-10", "--terms-dir", str(self.terms_dir))
        self.assertNotIn(show(compile_expr(demo.CASES[9].build())), output)

    def test_bad_arguments_are_usage_errors(self):
        for argv in (["--only", "DEMO-15"], ["--execution-budget", "-1"],
                     ["--observation-budget", "lots"]):
            with self.subTest(argv):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as stop:
                        demo.main(argv)
                self.assertEqual(stop.exception.code, 2)


class FailureDetectionTests(TemporaryTermsDir):
    def case(self, build, kind, expected):
        return demo.DemoCase("DEMO-XX", "Test", "test", build, kind, expected, "test")

    def test_wrong_expected_answer_fails_with_exit_status_1(self):
        wrong = self.case(lambda: num(3), NAT, 4)
        with mock.patch.object(demo, "CASES", (wrong,)):
            status, output = run_main("--terms-dir", str(self.terms_dir))
        self.assertEqual(status, 1)
        self.assertIn("FAIL: expected 4, but source gave 3; observation gave 3", output)

    def test_one_and_true_never_match(self):
        for build, kind, expected in [(lambda: boolean(True), BOOL, 1),
                                      (lambda: num(1), NAT, True),
                                      (lambda: boolean(True), NAT, 1)]:
            with self.subTest(f"{show_source(build())} as {kind}, expecting {expected!r}"):
                result = demo.run_case(self.case(build, kind, expected),
                                       terms_dir=self.terms_dir)
                self.assertFalse(result.passed)
                self.assertTrue(result.verdict.startswith("FAIL"))

    def test_a_wrongly_typed_observation_is_never_accepted(self):
        # The observers always return data of the requested kind, so this
        # cannot come from them; the check still must not rely on 1 == True.
        case = self.case(lambda: num(1), NAT, 1)
        passed, verdict = demo._check(case, Completed(num(1), 0, None),
                                      Completed(compile_expr(num(1)), 0, 10),
                                      Decoded(True, 2, 10))
        self.assertFalse(passed)
        self.assertIn("observation gave true", verdict)

    def test_boolean_observed_as_natural_is_malformed(self):
        result = demo.run_case(self.case(lambda: boolean(True), NAT, 1),
                               terms_dir=self.terms_dir)
        self.assertIsInstance(result.observation, Malformed)
        self.assertIn("source gave true", result.verdict)
        self.assertIn("observation was malformed at result", result.verdict)

    def test_unexpected_completion_of_a_divergent_example_fails(self):
        result = demo.run_case(self.case(lambda: num(0), None, None),
                               terms_dir=self.terms_dir)
        self.assertFalse(result.passed)
        self.assertIn("expected to exhaust its budget but completed", result.verdict)

    def test_observation_exhaustion_fails(self):
        result = demo.run_case(demo.CASES[0], observation_budget=3,
                               terms_dir=self.terms_dir)
        self.assertIsInstance(result.observation, ObservationExhausted)
        self.assertFalse(result.passed)


class CommandTests(TemporaryTermsDir):
    def test_default_terms_dir_is_under_my_solution(self):
        self.assertEqual(demo.TERMS_DIR, ASSIGN06 / "MySolution" / "demo_terms")

    def test_documented_command_runs_from_assigns_06(self):
        completed = subprocess.run(
            [sys.executable, "-m", "MySolution.demo", "--only", "DEMO-13",
             "--terms-dir", str(self.terms_dir)],
            cwd=ASSIGN06, capture_output=True, text=True, encoding="utf-8",
            timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Lambda Arcade — Three Pieces, Many Programs", completed.stdout)
        self.assertIn("1 of 1 examples passed.", completed.stdout)

    def test_paths_inside_the_working_directory_print_relative(self):
        inside = Path.cwd() / "MySolution" / "demo_terms" / "DEMO-01.txt"
        self.assertEqual(demo.display_path(inside),
                         str(Path("MySolution", "demo_terms", "DEMO-01.txt")))
        self.assertEqual(demo.display_path(self.terms_dir),
                         str(self.terms_dir.resolve()))


if __name__ == "__main__":
    unittest.main()
