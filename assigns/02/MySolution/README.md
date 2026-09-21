# Assignment 2 — Pairs, Projections, and an ATS2 → LAMBDA0 Translation

Extends the LAMBDA0 interpreter with pairs and projections, then
translates the eight-queens program written in ATS2 for Assignment 1
into a LAMBDA0 term that the extended interpreter evaluates.

## Files

| File | Contents |
| --- | --- |
| `lambda0.py` | The extended interpreter |
| `queens_lambda0.py` | The translated eight-queens term and its driver |
| `eqp_source.dats` | The ATS2 original being translated (from Assignment 1) |
| `TEST/test01_lambda0.py` | The provided tests, copied here so they import this interpreter |
| `TEST/test02_lambda0.py` | Tests for pairs and projections |
| `TEST/test03_queens.py` | Tests for the translation |

## Interpreter changes (`lambda0.py`)

The provided `assigns/02/lambda0.py` is left untouched; every change
below is in this copy only.

- `T0Mpair`, `T0Mpfst`, and `T0Mpsnd` are handled in `t0erm_size`,
  `t0erm_fvset`, `t0erm_subst0`, and `t0erm_cbv_evaluate0`.
- Pair construction evaluates both components before returning the pair,
  so a projection cannot hide a failure in the component it discards.
- Projections raise `TypeError` when applied to a non-pair value.
- Integer comparisons (`<`, `>`, `<=`, `>=`, `==`, `!=`) were added to
  `T0Mop2`. They produce `T0Mbtf` values, so they can be used directly as
  `T0Mif0` conditions.
- `abs` was added to `T0Mop1`, required by the diagonal check in
  `safety_test1`. Because the operator is a string field rather than a
  subterm, `t0erm_size`, `t0erm_fvset`, and `t0erm_subst0` needed no new
  cases — only the evaluator changed. `TEST/test03_queens.py` covers this
  in `TestAbsPrimitive`, including that the structural functions still
  treat it as an ordinary `T0Mop1`.

## How the ATS2 maps to LAMBDA0

| ATS2 | LAMBDA0 |
| --- | --- |
| `int8` board tuple | right-nested pairs ending in an inert `NIL`, built by `encode_board` |
| `board_get (bd, i)` | `make_board_get`: `T0Mfix` walking the spine by index |
| `board_set (bd, i, j)` | `make_board_set`: `T0Mfix` rebuilding the spine with one slot replaced |
| `safety_test1` | `make_safety_test1`: four curried binders, no recursion |
| `safety_test2` | `make_safety_test2`: `T0Mfix` recursing downward on the row index |
| `search` | `make_search`: `T0Mfix` over `bd, i, j, nsol, best` |
| `andalso` | `T0Mif0(a, b, false)`, via the `andalso` helper |
| `abs` | new `T0Mop1` case |
| `print_board` | Python-side decoder over the returned pair structure |

### Board representation

The ATS2 `int8` is a flat 8-tuple where index `i` is a row and the value
is that row's queen column. Here the board is a cons-list of pairs:
`[3, 1]` becomes `(3, (1, NIL))`. `NIL` is `T0Mbtf(False)` and is never
projected in correct operation — it exists only to terminate the spine.

A cons-list was chosen over a fixed eight-slot nesting for two reasons.
Recursive `board_get`/`board_set` are far smaller terms than the sixteen
`if0` branches a flat tuple would need, and the same code works for any
board size, which made it possible to debug at N=4 and report results
across N=1..8.

### Multiple arguments

`T0Mfix(f, x, body)` binds exactly one parameter, but `search` needs
five and `safety_test2` needs four. Every multi-argument function is
therefore curried: the fix binds the first parameter and the rest are
nested `T0Mlam`s. The Python helpers `lam_multi` and `app_multi` build
and apply these chains, with `app_multi` producing the left-associative
nesting that `f a b c` denotes.

Packing the arguments into a pair and projecting them back out was the
alternative. Currying was chosen because the body then refers to plain
named variables rather than projection chains, which mattered a great
deal while debugging.

## Changes needed for call-by-value

Three places where CBV shaped the translation rather than the ATS2
source doing so.

`andalso` must short-circuit. It expands to `T0Mif0(a, b, false)`, and
`T0Mif0` evaluates only the branch it selects. In `safety_test2` the
second operand *is* the recursive call, so an eager conjunction would
evaluate it unconditionally and the recursion would never terminate.

`search` has one parameter the ATS2 version does not. The original
prints each completed board and returns only the solution count. There
is no I/O inside the interpreter, so a fifth parameter `best` carries the
most recently completed board out, and the term's final value is the
pair `(nsol, best)`. This also gives `TEST/test03_queens.py` a real
board to check for legality.

`bd1` is bound with `let_bind`, which is `(λbd1. body) value`. Under CBV
the argument is evaluated once and the resulting value substituted, so
`board_set` runs a single time even though two branches refer to `bd1` —
matching the ATS2, which computes `bd1` before its `if`.

## Running

From this directory:

    python3 queens_lambda0.py        # defaults to N = 8
    python3 queens_lambda0.py 6      # any board size

    python3 TEST/test01_lambda0.py
    python3 TEST/test02_lambda0.py
    python3 TEST/test03_queens.py

Python 3.12 or later is required, as with the starter code.

## Results

Solution counts from the LAMBDA0 term, with one sample board each.
Counts match the ATS2 original at every size.

| N | Solutions | Sample board | Time |
| --- | --- | --- | --- |
| 1 | 1 | `[0]` | <1s |
| 2 | 0 | — | <1s |
| 3 | 0 | — | <1s |
| 4 | 2 | `[2, 0, 3, 1]` | <1s |
| 5 | 10 | `[4, 2, 0, 3, 1]` | <1s |
| 6 | 4 | `[4, 2, 0, 5, 3, 1]` | ~3s |
| 7 | 40 | `[6, 4, 2, 0, 5, 3, 1]` | ~13s |
| 8 | 92 | `[7, 3, 0, 2, 5, 1, 6, 4]` | ~50s |

The board notation is one column index per row: `[2, 0, 3, 1]` places
queens at (0,2), (1,0), (2,3), (3,1).

### Comparison with the ATS2 original

Solution counts agree at every board size tested, including 92 for the
full eight-queens problem. The ATS2 program is substantially faster —
a couple of seconds where the LAMBDA0 term takes almost a minute at N=8.

That gap is expected and comes from the interpreter, not the
translation. `t0erm_cbv_evaluate0` is substitution-based: every
beta-reduction rebuilds the term it substitutes into, so the cost of a
step grows with the size of the surrounding term. The compiled ATS2
program mutates a stack frame instead. A closure-and-environment
evaluator would close most of the gap without changing the translated
term at all.

## Limitations

- Runtime grows sharply with N. N=8 completes, but the margin is not
  large; a substantially bigger board would not be practical under a
  substitution-based evaluator.
- Each term builder returns a fresh closed term, so helpers such as
  `board_get` are inlined at every use rather than shared. Binding them
  once with `let_bind` and referring to them by name would produce a
  smaller term and fewer substitutions. It was not necessary to reach
  N=8, so it was left alone.
- The term reports one solution board rather than enumerating all of
  them. Accumulating every solution would need a list of boards threaded
  through the search, at a cost in both term size and memory.
- `safety_test1` never checks whether two queens share a *row*. This
  mirrors the ATS2 original and is safe: the board stores exactly one
  column per row, so a shared row cannot be represented.

## Testing

`TEST/test01_lambda0.py` is the provided suite, copied into this
directory so that its import path resolves to this interpreter rather
than the starter one. It passes unchanged, confirming the additions
above did not alter any existing behavior.

`TEST/test02_lambda0.py` covers pairs and projections across all four
extended functions: sizes and free-variable sets including nested and
embedded pairs, substitution into both components and under `T0Mlam` and
`T0Mfix` binders, left-to-right evaluation order, projections of
non-pairs raising `TypeError`, and functions that accept and return
pairs.

`TEST/test03_queens.py` covers the translation bottom-up — `board_get`,
`board_set` (including that it leaves its input board untouched), the
`abs` primitive, both safety tests against a known-good 4-queens board,
and the full search at N=1..4 against known counts. `board_is_legal`
independently verifies that a returned board shares no column or
diagonal.

## AI assistance

An AI assistant was used during this assignment. It drafted the Python
AST helper functions, and many of the test cases. The interpreter changes for pairs and projections, the `abs` primitive, and the representation decisions documented were written by hand.

No drafted code was committed without being read and run first. Review
caught defects in both directions. In hand-written code the assistant
flagged a `.` typed for a `,` in an `isinstance` call, a `T0Mpair` case
nested one level too deep inside the `T0Mop2` branch so that pairs never
reached it, a collapsed argument list that left `T0Mif0` without an
else-branch, and a test asserting a row index against a `T0Mint` instead
of the expected column. Working through those is also what surfaced the
left-associativity rule for application chains that `app_multi` encodes.
