"""
Test type: WRONG INPUT CASE

Rationale:
ATS is statically typed: `int8` is fixed at exactly 8 ints, so a call to
`search` with a 3-element tuple, or a tuple holding non-integers, could
never even compile. Python enforces none of that at call time, so this
file feeds `search` three kinds of malformed input to show how -- and
where -- the untyped translation actually fails at runtime instead of at
compile time (and one case where it doesn't fail at all).

  (a) Board tuple with the wrong number of elements (3 instead of 8).
  (b) Board tuple whose elements are not integers (strings instead).
  (c) A negative starting row index (i = -2).

Expected result:
  (a) A crash: board_set tries to unpack the tuple into 8 names
      (x0..x7) and fails with ValueError.
  (b) No crash, surprisingly: `search` always overwrites row i with a
      real integer (via board_set) *before* that row is ever read back
      (by a later row's safety_test2 check, or by the backtracking
      branch's board_get(bd, i - 1)) -- every board_get call only ever
      targets a row index strictly less than the current row, which by
      that point has always already been set. So the original string
      placeholders are dead data that get clobbered before use, and the
      search runs exactly as if it had started from a normal (-1,)*8
      board: all 92 solutions are still found. This is a genuine,
      non-obvious finding about the translated code, not a mistaken
      expectation -- it is verified below.
  (c) No crash at all: board_set's final `else: bd` fallback (for any i
      outside 0..7) silently leaves the board unchanged instead of
      raising an error, and i is incremented every call regardless, so
      the negative index just "counts up" to 0 over a couple of wasted
      calls and the search then proceeds exactly like the normal case --
      silently swallowing the invalid input rather than reporting it.
"""
import io
import sys
import contextlib
import eqp_solution as eqp

# Sub-case (c) below falls through to a full, normal N=8 search once the
# negative row index "heals" back to 0. See normal_case_test.py: the
# recursion-limit raise in eqp_solution.py only runs under its own
# `if __name__ == "__main__":` guard, so it is repeated here.
sys.setrecursionlimit(20000)


def run():
    all_ok = True

    print("=== WRONG INPUT CASE (a): board tuple too short (3 elements) ===")
    bd_short = (-1, -1, -1)
    try:
        eqp.search(bd_short, 0, 0, 0)
        print("Expected: ValueError (not enough values to unpack)")
        print("Actual:   no exception raised")
        print("Result:   FAIL")
        all_ok = False
    except ValueError as e:
        print("Expected: ValueError (not enough values to unpack)")
        print(f"Actual:   ValueError: {e}")
        print("Result:   PASS")
    except Exception as e:  # noqa: BLE001 - intentionally broad, for reporting
        print(f"Actual:   unexpected {type(e).__name__}: {e}")
        print("Result:   FAIL")
        all_ok = False
    print()

    print("=== WRONG INPUT CASE (b): board holding non-integers (strings) ===")
    bd_strs = ("a", "b", "c", "d", "e", "f", "g", "h")
    try:
        buf_b = io.StringIO()
        with contextlib.redirect_stdout(buf_b):
            nsol_b = eqp.search(bd_strs, 0, 0, 0)
        out_b = buf_b.getvalue()
        ok_b = (nsol_b == 92 and out_b.count("Solution #") == 92)
        print("Expected: no crash -- every string placeholder is overwritten")
        print("          by board_set before it is ever read back, so this")
        print("          runs identically to the normal case (nsol == 92)")
        print(f"Actual:   nsol == {nsol_b}, "
              f"{out_b.count('Solution #')} \"Solution #\" labels printed")
        print("Result:  ", "PASS" if ok_b else "FAIL")
        all_ok = all_ok and ok_b
    except Exception as e:  # noqa: BLE001
        print(f"Actual:   unexpected {type(e).__name__}: {e}")
        print("Result:   FAIL")
        all_ok = False
    print()

    print("=== WRONG INPUT CASE (c): negative starting row index (i = -2) ===")
    bd0 = (-1,) * 8
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            nsol_c = eqp.search(bd0, -2, 0, 0)
        ok_c = (nsol_c == 92)
        print("Expected: no crash; the invalid negative row is silently")
        print("          absorbed by board_set's fallback, and the search")
        print("          still completes normally once i reaches 0 (nsol == 92)")
        print(f"Actual:   nsol == {nsol_c}")
        print("Result:  ", "PASS" if ok_c else "FAIL")
        all_ok = all_ok and ok_c
    except Exception as e:  # noqa: BLE001
        print(f"Actual:   unexpected {type(e).__name__}: {e}")
        print("Result:   FAIL")
        all_ok = False

    return all_ok


if __name__ == "__main__":
    run()
