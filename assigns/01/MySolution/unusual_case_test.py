"""
Test type: UNUSUAL CASE

Rationale:
`search`'s fourth parameter, nsol, is meant to start at 0 (a running
solution counter) -- every call in the original source and in
eqp_solution.main() does this. Nothing in the code enforces that, though:
it is a syntactically valid, if unusual, call to start the counter
somewhere else. This test starts the count at 1000 on an otherwise
perfectly normal empty board -- an "unusual" but not "wrong" input: right
types, right shapes, a state a caller could genuinely be in (e.g. tallying
solutions across several boards), just not how the function is normally
invoked.

Expected result:
Since nsol is used purely additively (`nsol + 1` on each solution found,
returned unchanged otherwise), the search itself is unaffected by the
starting offset: it should still discover all 92 solutions, but report
them as "Solution #1001" through "Solution #1092", and return nsol == 1092.
"""
import io
import sys
import contextlib
import eqp_solution as eqp

# See normal_case_test.py: the recursion-limit raise in eqp_solution.py is
# gated behind `if __name__ == "__main__":`, which does not run on import,
# so it is repeated here for this direct call into `search`.
sys.setrecursionlimit(20000)


def run():
    bd0 = (-1,) * 8

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        nsol = eqp.search(bd0, 0, 0, 1000)
    output = buf.getvalue()

    has_1001 = "Solution #1001:" in output
    has_1092 = "Solution #1092:" in output
    has_stray_1 = "Solution #1:" in output

    ok = (nsol == 1092 and has_1001 and has_1092 and not has_stray_1)

    print("=== UNUSUAL CASE: nsol starting at a nonzero offset (1000) ===")
    print("Input:    bd=(-1,)*8, i=0, j=0, nsol=1000")
    print("Expected: nsol == 1092, labels run \"Solution #1001\" .. \"Solution #1092\"")
    print(f"Actual:   nsol == {nsol}, has 'Solution #1001:' == {has_1001}, "
          f"has 'Solution #1092:' == {has_1092}")
    print("Result:  ", "PASS" if ok else "FAIL")

    return ok


if __name__ == "__main__":
    run()
