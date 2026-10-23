"""Lambda Arcade — Three Pieces, Many Programs: the command-line demonstration.

Run from assigns/06/:

    python3 -m MySolution.demo                     all 14 required examples
    python3 -m MySolution.demo --only DEMO-08 DEMO-10
    python3 -m MySolution.demo --execution-budget 500 --observation-budget 50
    python3 -m MySolution.demo --show-terms        print each pure term in full

Each example is a source AST built in Python (see examples.py). For each one
the demo:

1. evaluates the source program with the shared evaluator, unless the
   example is known to diverge, in which case the source run is skipped
   rather than attempted;
2. compiles it to a pure term made only of Var, Lam and App, and saves the
   whole term, printed by target.show, to MySolution/demo_terms/<ID>.txt;
3. executes the term on the same evaluator under the execution budget;
4. if execution completed, observes the value as the expected kind under a
   separate observation budget;
5. checks the outcome. A terminating example passes only when the explicit
   expected answer, the source result and the observed target result are
   the same data of the expected kind, so 1 and true never match. A
   divergent example passes when its execution exhausts the budget, which
   is reported as exhaustion, never as proof of divergence.

The exit status is 0 when every selected example passes and 1 otherwise.

Budgets: by default each example gets 10,000 execution steps and 1,000
observation steps. With this implementation the largest measured needs
are 2,021 execution steps (fibonacci 5) and 218 observation steps
(factorial 4), so each default is more than four times the largest need.
These are measurements of this implementation only; another implementation
of the same rules may count differently. The source run uses the execution
budget as a safety bound, and its count is of source function applications,
not target steps. A budget given on the command line is used exactly as
given: if it is too small, the example reports exhaustion and fails.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .compiler import compile_expr
from .evaluator import evaluate
from .examples import (
    boolean, call, factorial, fibonacci, fst, fun, if_, let, loop, num, op,
    pair, snd, var,
)
from .observers import observe
from .results import (
    BOOL, NAT, Completed, Data, Decoded, Exhausted, Kind, Malformed,
    Observation, ObservationExhausted, format_data, has_kind, same_data,
)
from .source_support import D0E000, show_source, source_data
from .target import App, Lam, Term, Var, iter_nodes, show

EXECUTION_BUDGET = 10_000
OBSERVATION_BUDGET = 1_000
TERMS_DIR = Path(__file__).resolve().parent / "demo_terms"
PREVIEW_LENGTH = 72


@dataclass(frozen=True)
class DemoCase:
    """One example. `kind` is None when execution is expected to exhaust."""
    id: str
    title: str
    notation: str               # the example as the assignment writes it
    build: Callable[[], D0E000]
    kind: Kind | None
    expected: Data | None
    point: str                  # what the example shows

    @property
    def diverges(self) -> bool:
        return self.kind is None


CASES: tuple[DemoCase, ...] = (
    DemoCase("DEMO-01", "Scoreboard", "2 + 3 * 4",
             lambda: op("+", num(2), op("*", num(3), num(4))), NAT, 14,
             "strict arithmetic: closed ADD and MUL terms applied to numerals"),
    DemoCase("DEMO-02", "Floor", "2 - 5",
             lambda: op("-", num(2), num(5)), NAT, 0,
             "subtraction on naturals stops at zero: predecessor of 0 is 0"),
    DemoCase("DEMO-03", "Fork", "if 2 <= 3 then 7 else 9",
             lambda: if_(op("<=", num(2), num(3)), num(7), num(9)), NAT, 7,
             "a comparison yields a Church boolean, which picks one thunk"),
    DemoCase("DEMO-04", "Carry-Over", "let x = 3 in (lam y. x + y) 4",
             lambda: let("x", num(3),
                         call(fun("y", op("+", var("x"), var("y"))), num(4))),
             NAT, 7,
             "let becomes an application, so x is substituted into the body"),
    DemoCase("DEMO-05", "Left Pocket", "fst (pair 2 true)",
             lambda: fst(pair(num(2), boolean(True))), NAT, 2,
             "a pair holds both computed fields; FST selects the first"),
    DemoCase("DEMO-06", "Right Pocket", "snd (pair 2 true)",
             lambda: snd(pair(num(2), boolean(True))), BOOL, True,
             "the same pair through SND, observed as a boolean"),
    DemoCase("DEMO-07", "Pass It On", "(lam f. f 3) (lam x. x + 1)",
             lambda: call(fun("f", call(var("f"), num(3))),
                          fun("x", op("+", var("x"), num(1)))),
             NAT, 4,
             "a function is a value that can be passed to another function"),
    DemoCase("DEMO-08", "Trapdoor", "if true then 1 else LOOP",
             lambda: if_(boolean(True), num(1), loop()), NAT, 1,
             "LOOP sits in the thunk that is never forced, so it never runs"),
    DemoCase("DEMO-09", "Strict Gate", "(lam x. 0) LOOP",
             lambda: call(fun("x", num(0)), loop()), None, None,
             "call by value runs the argument first, though the body ignores it"),
    DemoCase("DEMO-10", "Recursion Round", "factorial 4, with fact(0) = 1",
             lambda: factorial(4), NAT, 24,
             "fix compiles through the call-by-value Z combinator"),
    DemoCase("DEMO-11", "Fibonacci Climb",
             "fibonacci 5, with fib(0) = 0 and fib(1) = 1",
             lambda: fibonacci(5), NAT, 5,
             "two recursive calls per level; only the chosen branch recurses"),
    DemoCase("DEMO-12", "Endless Hallway", "LOOP",
             loop, None, None,
             "a recursive function that only ever calls itself again"),
    DemoCase("DEMO-13", "Both Switches", "true and false",
             lambda: op("and", boolean(True), boolean(False)), BOOL, False,
             "and runs its right operand only when the left one is true"),
    DemoCase("DEMO-14", "Either Switch", "false or true",
             lambda: op("or", boolean(False), boolean(True)), BOOL, True,
             "or runs its right operand only when the left one is false"),
)


@dataclass(frozen=True)
class DemoResult:
    """What happened to one example; None marks a run that was not made."""
    case: DemoCase
    source: D0E000
    source_run: Completed | Exhausted | None
    term: Term
    term_file: Path
    execution: Completed | Exhausted
    observation: Observation | None
    passed: bool
    verdict: str


def run_case(case: DemoCase, execution_budget: int = EXECUTION_BUDGET,
             observation_budget: int = OBSERVATION_BUDGET,
             terms_dir: Path = TERMS_DIR) -> DemoResult:
    """Compile, execute and observe one example, and check the outcome."""
    source = case.build()
    # A known divergent example is never run on the source side.
    source_run = None if case.diverges else evaluate(source, execution_budget)
    term = compile_expr(source)
    term_file = save_term(case, term, terms_dir)
    execution = evaluate(term, execution_budget)
    observation = None
    if isinstance(execution, Completed) and not case.diverges:
        observation = observe(execution.value, case.kind, observation_budget)
    passed, verdict = _check(case, source_run, execution, observation)
    return DemoResult(case, source, source_run, term, term_file, execution,
                      observation, passed, verdict)


def save_term(case: DemoCase, term: Term, terms_dir: Path) -> Path:
    """Write the whole printed term, and nothing else, to <ID>.txt."""
    terms_dir.mkdir(parents=True, exist_ok=True)
    path = terms_dir / f"{case.id}.txt"
    path.write_text(show(term) + "\n", encoding="utf-8")
    return path


def _check(case: DemoCase, source_run: Completed | Exhausted | None,
           execution: Completed | Exhausted,
           observation: Observation | None) -> tuple[bool, str]:
    if case.diverges:
        if isinstance(execution, Exhausted):
            return True, "PASS: execution exhausted its budget, as expected"
        return False, ("FAIL: execution was expected to exhaust its budget "
                       f"but completed in {execution.steps:,} steps")
    expected = format_data(case.expected)
    problems = []
    answer = _source_answer(source_run, problems)
    if answer is not None and not same_data(answer, case.expected):
        problems.append(f"source gave {format_data(answer)}")
    match observation:
        case None:
            problems.append("execution exhausted its budget")
        case Decoded(data) if not same_data(data, case.expected):
            problems.append(f"observation gave {format_data(data)}")
        case ObservationExhausted(path=path):
            problems.append(f"observation exhausted its budget at {path}")
        case Malformed(path=path):
            problems.append(f"observation was malformed at {path}")
    if not has_kind(case.kind, case.expected):
        problems.append(f"expected answer {expected} is not a {case.kind}")
    if problems:
        return False, f"FAIL: expected {expected}, but " + "; ".join(problems)
    return True, (f"PASS: expected {expected}, source {expected} and "
                  f"observed {expected} agree")


def _source_answer(source_run: Completed | Exhausted | None,
                   problems: list[str]) -> Data | None:
    if not isinstance(source_run, Completed):
        problems.append("source run exhausted its budget")
        return None
    try:
        return source_data(source_run.value)
    except TypeError:
        problems.append("source result is a function, not data")
        return None


########################################################################
# Printing.

def format_result(result: DemoResult, show_terms: bool = False) -> str:
    case = result.case
    lines = [f"{case.id}  {case.title}"]

    def row(label: str, text: str) -> None:
        lines.append(f"  {label:<12} {text}")

    def more(text: str) -> None:
        lines.append(f"  {'':<12} {text}")

    row("example", case.notation)
    row("source AST", show_source(result.source))
    row("shows", case.point)
    row("expected", "execution-budget exhaustion" if case.diverges
        else f"{case.kind} {format_data(case.expected)}")
    row("source run", _describe_source_run(result.source_run))
    text = show(result.term)
    row("pure term", _describe_pieces(result.term))
    more(f"full term ({len(text):,} characters) saved to "
         f"{display_path(result.term_file)}")
    more(text if show_terms else show(result.term, PREVIEW_LENGTH))
    execution = result.execution
    if isinstance(execution, Completed):
        row("execution", f"completed in {execution.steps:,} of "
            f"{execution.budget:,} beta-value steps")
    else:
        row("execution", f"exhausted after {execution.steps:,} of "
            f"{execution.budget:,} beta-value steps; another step was needed")
        more("(running out of budget is not proof that it never finishes)")
    row("observation", _describe_observation(result))
    row("result", result.verdict)
    return "\n".join(lines)


def _describe_source_run(run: Completed | Exhausted | None) -> str:
    match run:
        case None:
            return "skipped: known divergent example, not run on the source side"
        case Exhausted(steps):
            return f"exhausted its budget after {_applications(steps)}"
    try:
        answer = format_data(source_data(run.value))
    except TypeError:
        answer = show_source(run.value)
    return f"{answer} (shared evaluator, source mode; {_applications(run.steps)})"


def _applications(count: int) -> str:
    noun = "application" if count == 1 else "applications"
    return f"{count:,} source function {noun}"


def _describe_pieces(term: Term) -> str:
    counts = {Var: 0, Lam: 0, App: 0}
    for node in iter_nodes(term):
        counts[type(node)] += 1
    return (f"{sum(counts.values()):,} nodes: {counts[Var]:,} Var, "
            f"{counts[Lam]:,} Lam, {counts[App]:,} App")


def _describe_observation(result: DemoResult) -> str:
    match result.observation:
        case None if isinstance(result.execution, Exhausted):
            return "not attempted: execution did not finish"
        case None:
            return "not attempted: no expected kind for this example"
        case Decoded(data, steps, budget):
            return (f"decoded {result.case.kind} {format_data(data)} in "
                    f"{steps:,} of {budget:,} steps")
        case ObservationExhausted(steps, budget, path):
            return (f"exhausted at {path} after {steps:,} of {budget:,} steps; "
                    "another step was needed")
        case Malformed(reason, steps, budget, path):
            return f"malformed at {path} after {steps:,} of {budget:,} steps: {reason}"


def display_path(path: Path) -> str:
    """The path relative to the working directory when it lies inside it."""
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path.resolve())


HEADER = """\
Lambda Arcade — Three Pieces, Many Programs

Each example is compiled to a pure program built from only three pieces:
Var (a variable), Lam (a one-parameter function) and App (an application).
The pure program runs on the same evaluator as the source program, and its
value is then observed as the expected natural or boolean.

LOOP stands for (fix loop(x). loop x) 0."""


########################################################################
# Command line.

def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python3 -m MySolution.demo",
        description="Compile, run and observe the Lambda Arcade examples.")
    parser.add_argument(
        "--only", nargs="+", metavar="ID", type=str.upper,
        choices=[case.id for case in CASES],
        help="run only these examples, such as DEMO-08 (default: all)")
    parser.add_argument(
        "--execution-budget", type=_budget, default=EXECUTION_BUDGET,
        metavar="N", help="beta-value steps allowed for each execution "
        f"(default: {EXECUTION_BUDGET:,})")
    parser.add_argument(
        "--observation-budget", type=_budget, default=OBSERVATION_BUDGET,
        metavar="N", help="steps allowed for each observation "
        f"(default: {OBSERVATION_BUDGET:,})")
    parser.add_argument(
        "--show-terms", action="store_true",
        help="print each pure term in full instead of its first characters")
    parser.add_argument(
        "--terms-dir", type=Path, default=TERMS_DIR, metavar="DIR",
        help="where to save the pure terms (default: MySolution/demo_terms)")
    return parser.parse_args(argv)


def _budget(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from None
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be nonnegative: {value}")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    selected = [case for case in CASES if not args.only or case.id in args.only]
    print(HEADER)
    print(f"Budgets for each example: execution {args.execution_budget:,} "
          f"beta-value steps; observation {args.observation_budget:,} steps.")
    print(f"Pure terms are saved in {display_path(args.terms_dir)}")
    results = []
    for case in selected:
        result = run_case(case, args.execution_budget,
                          args.observation_budget, args.terms_dir)
        results.append(result)
        print()
        print(format_result(result, args.show_terms))
    print()
    print("Summary")
    for result in results:
        print(f"  {result.case.id}  {'PASS' if result.passed else 'FAIL'}  "
              f"{result.case.title:<16} {_summary_outcome(result)}")
    failed = [result.case.id for result in results if not result.passed]
    passed = len(results) - len(failed)
    if failed:
        print(f"{passed} of {len(results)} examples passed; "
              f"failed: {', '.join(failed)}")
        return 1
    print(f"{passed} of {len(results)} examples passed.")
    return 0


def _summary_outcome(result: DemoResult) -> str:
    if not result.passed:
        return result.verdict.removeprefix("FAIL: ")
    if result.case.diverges:
        return "execution budget exhausted, as expected"
    return f"{result.case.kind} {format_data(result.observation.data)}"


if __name__ == "__main__":
    raise SystemExit(main())
