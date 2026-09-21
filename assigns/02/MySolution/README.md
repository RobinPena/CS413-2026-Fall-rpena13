# Assignment 2 — Pairs, Projections, and an ATS2 → LAMBDA0 Translation

Work in progress. Tasks 1–3 are complete; Task 4 (the eight-queens
translation) is partially built.

## Interpreter changes (`lambda0.py`)

The provided `assigns/02/lambda0.py` is left untouched; every change
below lives in this copy only.

- `T0Mpair`, `T0Mpfst`, and `T0Mpsnd` are handled in `t0erm_size`,
  `t0erm_fvset`, `t0erm_subst0`, and `t0erm_cbv_evaluate0`.
- Pair construction evaluates both components before returning, so a
  projection never hides a failure in the component it discards.
- Projections raise `TypeError` when applied to a non-pair value.
- Integer comparisons (`<`, `>`, `<=`, `>=`, `==`, `!=`) were added to
  `T0Mop2`; they produce `T0Mbtf` values, so they can be used directly
  as `T0Mif0` conditions.
- `abs` was added to `T0Mop1`, needed by the queens diagonal check.
  Since the operator is a string field rather than a subterm, `size`,
  `fvset`, and `subst0` needed no new cases.

## Translation (`queens_lambda0.py`) — in progress

Translating `eqp_source.dats` (included here), the eight-queens solution
written for Assignment 1.

| ATS2 | LAMBDA0 |
| --- | --- |
| `int8` board tuple | right-nested pairs ending in an inert `NIL` |
| `board_get` | `T0Mfix` walking the spine by index |
| `board_set` | `T0Mfix` rebuilding the spine with one slot replaced |
| multi-argument functions | curried `T0Mlam` chains, since `T0Mfix` binds one parameter |
| `andalso` | `T0Mif0(a, b, false)` |
| `abs` | new `T0Mop1` case |

Built so far: the Python AST helpers (`lam_multi`, `app_multi`,
`let_bind`, `andalso`, `encode_board`, `decode_board`, `print_board`),
plus the `make_board_get` and `make_board_set` term builders.

Still to build: `make_safety_test1`, `make_safety_test2`, `make_search`,
and the `run_queens` driver.

## Running the tests

From this directory:

    python3 TEST/test02_lambda0.py
    python3 TEST/test03_queens.py

`test02` covers pairs and projections in all four extended functions.
`test03` covers the translation's board operations and the `abs`
primitive.

Of note: `../TEST/test01_lambda0.py` resolves its import path to the
assignment directory, so as written it exercises the starter interpreter
rather than this one. It needs to be copied into `TEST/` before it can
serve as a regression check against these changes.

## AI assistance

An AI assistant was used to draft the Python AST helper functions and a number of test cases. 
All AI-drafted code was read and run before being committed rather than
taken as-is. Review caught real defects on both sides: in drafted code,
and in hand-written code where the assistant flagged a mis-nested
`T0Mpair` branch in the evaluator, a `.`-for-`,` typo in an `isinstance`
call, and an assertion that compared a row index against a `T0Mint`
instead of the expected column value.
