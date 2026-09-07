"""
Test type: NORMAL INPUT CASE

Rationale:
The most ordinary, expected way to use the eight-queens `search` function:
start from a completely empty 8x8 board (no queen placed in any row, encoded
as -1 in every slot) and begin the search at row 0, column 0, with a
solution counter of 0. This is exactly the call eqp_solution.main() makes,
and is the "typical" input a user of this function would provide.

Expected result:
The classic, well-known answer for the Eight Queens Puzzle: exactly 92
distinct solutions, with the program printing each one labeled
"Solution #1" through "Solution #92".
"""
import io
import sys
import contextlib
import eqp_solution as eqp

# eqp_solution.py only raises the recursion limit inside its own
# `if __name__ == "__main__":` guard (see eqp_solution.py note 2). Since
# this test imports and calls `search` directly, that guard never runs, so
# the limit is raised here too -- otherwise the ~17,700-deep tail-recursive
# call chain for the full N=8 search would hit Python's default limit
# (1000) and raise RecursionError.
sys.setrecursionlimit(20000)


def run():
    bd0 = (-1, -1, -1, -1, -1, -1, -1, -1)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        nsol = eqp.search(bd0, 0, 0, 0)
    output = buf.getvalue()
    n_labels = output.count("Solution #")

    ok = (nsol == 92 and n_labels == 92)

    print("=== NORMAL CASE ===")
    print("Input:    bd=(-1,-1,-1,-1,-1,-1,-1,-1), i=0, j=0, nsol=0")
    print("Expected: nsol == 92, and 92 \"Solution #\" labels printed")
    print(f"Actual:   nsol == {nsol}, and {n_labels} \"Solution #\" labels printed")
    print("Result:  ", "PASS" if ok else "FAIL")
    print()
    print("First solution block printed (excerpt):")
    print(output.split("Solution #2:")[0])

    return ok


if __name__ == "__main__":
    run()
