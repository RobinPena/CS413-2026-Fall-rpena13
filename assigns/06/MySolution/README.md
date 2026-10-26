# Assign06: Lambda Arcade — Three Pieces, Many Programs

A compiler from extended LAMBDA (numbers, booleans, `let`, `if`, pairs,
recursion) to the pure untyped lambda calculus. Every compiled program is
built from only three pieces: `Var` (a variable), `Lam` (a one-parameter
function) and `App` (an application). Numbers, booleans and pairs become
Church encodings, conditionals become selected thunks, and recursion goes
through the call-by-value `Z` combinator. One evaluator runs both the source
program and the compiled term, and bounded observers read the compiled
result back as data, so each example can be checked against both an
explicit expected answer and the source result.

See `DESIGN.md` for the translation rules and correctness argument, and
`AI-TRANSCRIPT.md` for how AI was used.

## Presentation

| File | Contents |
| --- | --- |
| [`MySolution/presentation/slides.pdf`](presentation/slides.pdf) | The slide deck, 12 slides |
| [`MySolution/presentation/Presentation.mp4`](presentation/Presentation.mp4) | The recorded presentation: the slides with a webcam inset, and live runs of the demo including factorial (DEMO-10). MP4 (H.264 video, AAC audio), 1280×720 |

## Requirements

- Python 3.12 or later, because the supplied `lambda1_vp.py` uses `type`
  statements. Developed and tested with Python 3.14.9 on macOS.
- No third-party packages; only the standard library (`unittest`,
  `argparse`, `dataclasses`).
- The supplied source AST at `assigns/05/lambda1_vp.py`, unchanged.

## Setup

No installation is needed. From the repository root:

```bash
cd assigns/06
python3 --version        # must be 3.12 or later
```

If `python3` is older, use a newer interpreter such as `python3.14` in
every command below. Importing the package with an older Python stops with
the message "MySolution needs Python 3.12 or later".

## Commands

Run all commands from `assigns/06/`.

```bash
python3 -m unittest discover -s MySolution/tests -t . -v    # all tests
python3 -m MySolution.demo                                  # all 14 examples
```

The test suite runs 171 tests in about 2 seconds. The demo finishes in well
under a second and exits with status 0 when every example passes, 1 when any
fails, and 2 for invalid arguments.

Demo options:

| Option | Effect |
| --- | --- |
| `--only ID [ID ...]` | Run only these examples, such as `DEMO-08` (table order is kept) |
| `--execution-budget N` | Beta-value steps allowed for each execution (default 10,000) |
| `--observation-budget N` | Steps allowed for each observation (default 1,000) |
| `--show-terms` | Print each pure term in full instead of its first 72 characters |
| `--terms-dir DIR` | Where to save the pure terms (default `MySolution/demo_terms`) |

A short route through four examples:

```bash
python3 -m MySolution.demo --only DEMO-01 DEMO-08 DEMO-09 DEMO-10
```

## Supplied AST import

`source_support.py` loads `assigns/05/lambda1_vp.py` by its path relative to
this package, not through `sys.path`, so no other `lambda1_vp.py` (for
example one from another assignment) can be picked up by mistake. It
refuses to run if a module named `lambda1_vp` from a different file was
already imported. The file is never modified. Its supplied interpreter is
not used: source programs run on this package's own evaluator.

## Modules

| Module | Contents |
| --- | --- |
| `source_support.py` | Supplied AST classes and `D0ExpVisitor`; `validate_source`, `show_source`, `source_names`, `source_fv`, `source_substitute`, `source_data` |
| `target.py` | `Var`, `Lam`, `App`; `show` (exact printer), `free_vars`, `all_names`, `substitute`, `alpha_equivalent`, `size`, `iter_nodes` |
| `names.py` | Identifier rule and the deterministic `FreshNames` supply |
| `results.py` | Expected kinds `NAT`, `BOOL`, `PairKind`; outcome types; error types |
| `evaluator.py` | `evaluate(program, budget=None, on_step=None)` for source ASTs and target terms |
| `encodings.py` | Closed Church combinators (`TRUE`, `numeral`, `PAIR`, `Z`, `ADD`, `PRED`, `SUB`, comparisons, ...) and `LIBRARY` |
| `observers.py` | `observe(value, kind, budget)` and its contexts `STEP`, `BASE`, `YES`, `NO` |
| `compiler.py` | `compile_expr(source)`, a `D0ExpVisitor`; never imports the evaluator |
| `examples.py` | Source-AST builders, `loop()` (LOOP), factorial and Fibonacci |
| `demo.py` | The command-line demonstration |
| `tests/` | The unittest suite, one file per module |

Principal contracts:

- `compile_expr(source) -> Term` accepts open or closed source ASTs. It
  raises `UnsupportedSourceError` (with the path to the offending node) for
  negative literals, division or any other unsupported operator, wherever
  they occur. It never evaluates anything.
- `evaluate(program, budget)` returns `Completed(value, steps, budget)` or
  `Exhausted(steps, budget)`. A target run must be given a budget. Both
  languages accept only closed programs and raise `OpenTermError`
  otherwise; compilation and substitution still handle open terms.
- `observe(value, kind, budget)` returns `Decoded(data, steps, budget)`,
  `ObservationExhausted(steps, budget, path)` or
  `Malformed(reason, steps, budget, path)`. Data are `int`, `bool` or
  tuples.

## Budgets, counts and outcomes

- **Execution** runs the compiled term. Its count is beta-value steps,
  `(lam x. body) v` with `v` a lambda; nothing else is counted. A value
  reached on the last allowed step is `Completed`. `Exhausted` means another
  step was needed. It is not proof that the program never finishes.
- **Observation** runs the value inside a pure context on the same
  evaluator, with its own budget and count. For a pair, one budget covers
  both projections and all nested components, and the outcome names the
  component where observation stopped, such as `result.second`.
- **Source runs** use the same evaluator. Their count is source function
  applications, which is not comparable to target steps. The demo bounds
  them with the execution budget.
- **Expected kinds** are always given by the caller: `NUM(0)` and `FALSE`
  are the same term, decoded as `0` or `false` by the requested kind. The
  demo compares results with a check that keeps `1` and `true` apart.
- **Demo budgets** are 10,000 execution steps and 1,000 observation steps
  per example. The largest measured needs are 2,021 execution steps
  (Fibonacci 5) and 218 observation steps (factorial 4), so each default is
  more than four times the largest need. These counts describe this
  implementation, not a property of the encodings in general. A budget
  given on the command line is used exactly; if it is too small, the
  example reports exhaustion and fails.

## Demonstration results

Measured with `python3 -m MySolution.demo` (all 14 passed):

| ID | Example | Expected | Execution steps | Observation steps |
| --- | --- | --- | --- | --- |
| DEMO-01 | `2 + 3 * 4` | natural 14 | 4 | 25 |
| DEMO-02 | `2 - 5` | natural 0 | 87 | 2 |
| DEMO-03 | `if 2 <= 3 then 7 else 9` | natural 7 | 77 | 9 |
| DEMO-04 | `let x = 3 in (lam y. x + y) 4` | natural 7 | 4 | 13 |
| DEMO-05 | `fst (pair 2 true)` | natural 2 | 6 | 4 |
| DEMO-06 | `snd (pair 2 true)` | boolean true | 6 | 2 |
| DEMO-07 | `(lam f. f 3) (lam x. x + 1)` | natural 4 | 4 | 10 |
| DEMO-08 | `if true then 1 else LOOP` | natural 1 | 3 | 3 |
| DEMO-09 | `(lam x. 0) LOOP` | exhaustion | exhausted at 10,000 | not attempted |
| DEMO-10 | factorial 4 | natural 24 | 471 | 218 |
| DEMO-11 | Fibonacci 5 | natural 5 | 2,021 | 45 |
| DEMO-12 | `LOOP` | exhaustion | exhausted at 10,000 | not attempted |
| DEMO-13 | `true and false` | boolean false | 3 | 2 |
| DEMO-14 | `false or true` | boolean true | 3 | 2 |

`LOOP` is `(fix loop(x). loop x) 0`. For DEMO-09 and DEMO-12 the source run
is skipped rather than attempted. Each terminating example's source result
also matched its expected answer.

Every example's full pure term is saved as `MySolution/demo_terms/DEMO-NN.txt`
(UTF-8, the term printed by `target.show` and nothing else). The demo
rewrites these files on each run, and the output is identical every time.

## Test coverage

The suite uses `unittest` with explicit expected answers. Each assignment
obligation maps to these tests:

| Obligation | Tests |
| --- | --- |
| Substitution, shadowing, capture (`lam y. x`, `x := y`) | `test_target.SubstitutionTests` |
| Left-to-right weak CBV, zero-step values, budgets, divergence | `test_evaluator.TargetBudgetTests`, `TargetStrategyTests` |
| Every constructor and operator, comparisons both ways, truth tables | `test_compiler.EndToEndTests`, `test_evaluator.SourceSemanticsTests`, `test_encodings` |
| Nested lets and lambdas, initializer scope, fix binders, open programs, colliding names, free variables, immutability | `test_compiler.EndToEndTests`, `PurityAndScopeTests` |
| Skipped unselected code; exhaustion of strict positions | `test_compiler.EndToEndTests` (`test_unselected_code_is_skipped`, `test_selected_or_strict_divergence_exhausts`); `test_evaluator.SourceSemanticsTests` (`test_unselected_branches_and_operands_are_skipped`, `test_selected_divergence_and_strict_positions_exhaust`) |
| All demonstrations, nested pairs, rejection anywhere in the tree | `test_demo`, `test_observers`, `test_compiler.RejectionTests`, `test_source_support.ValidationTests` |
| Pure output, closed combinators, no evaluator calls during compilation | `PurityAndScopeTests`, `test_encodings.RepresentationTests`, `NoEvaluationTests` |
| One evaluator for both languages; no compiler import | `test_evaluator.SingleEvaluatorTests` |

During development, deliberately broken copies of each module (for
example, swapped `and` branches, non-fresh thunk names, an off-by-one
budget) were run against the suite in a scratch directory to confirm that
the tests reject them.

## Limitations

- Execution accepts closed programs only. Open programs compile, and their
  free variables are preserved.
- Source trees nested more than about 330 levels deep exceed Python's
  default recursion limit in the recursive source visitors. Target terms
  are processed without recursion.
- Costs grow quickly with the operands because numerals are unary and
  predecessor rebuilds the number: factorial 6 needs 859 execution and
  6,590 observation steps, and Fibonacci 10 needs 27,560 execution steps.
- Observers reject malformed shapes they meet but do not recognize every
  invalid untyped term (`I` observes as the natural 1).
- Exhaustion is not a proof of divergence, and function results cannot be
  decoded as data.
- No parser: example programs are built in Python (`examples.py`).

## Attribution

- `lambda1_vp.py` (the source AST and `D0ExpVisitor`) is supplied by the
  course and used unchanged.
- `PrettyPrintVisitor`, `AllNamesVisitor` and `SubstitutionVisitor` in
  `source_support.py`, and `FreshNames` in `names.py`, are adapted from my
  Assignment 5 solution, `assigns/05/MySolution/lambda1_visitors.py`.
- The Church encodings, the pair-based predecessor and the call-by-value
  fixed-point combinator `Z` are standard constructions; the
  representations of booleans, numerals, pairs and `Z` are the ones given in
  the assignment. No external source was consulted while writing this code.
  The same constructions are covered in B. C. Pierce, *Types and
  Programming Languages* (MIT Press, 2002), Chapter 5.
- The code and documents were written with Claude Code; see
  `AI-TRANSCRIPT.md`.
