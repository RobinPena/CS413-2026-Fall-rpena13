"""
Test type: BOUNDARY CASE

Rationale:
Two boundary conditions of `search`'s control flow are exercised:

  (a) j == N on the very first call (i = 0). This is the exact edge where
      the loop guard `if j < N` first turns false with no earlier row to
      backtrack into (i == 0). This is the *terminating* boundary of the
      whole recursion: search must stop immediately and report however
      many solutions were already tallied (0 here), instead of trying to
      backtrack to row i - 1 = -1 (which does not exist).

  (b) i == N - 1 (the last row) reached with a valid, ready-made 7-row
      prefix taken from a genuine solution. This exercises the other edge
      of the recursion: the `if i + 1 = N` branch that triggers
      solution-printing.

      Note: `search` does not stop at the first solution it finds in a
      row -- after printing one, it keeps incrementing j to look for
      further completions, and once j reaches N it backtracks upward
      through earlier rows the same way a fresh search would. So an
      arbitrary valid 7-row prefix is *not* safe to use here: it would
      make this "boundary" case silently re-run a large fraction of the
      full search (potentially tens of thousands of calls). To keep this
      a genuine, contained boundary probe, the prefix used below is taken
      from the *lexicographically last* solution the normal-case search
      finds (Solution #92): by construction nothing later in column/row
      order remains once that state is reached, so the backtracking
      unwinds in a handful of calls instead of cascading.
"""
import io
import sys
import contextlib
import eqp_solution as eqp

# Kept for parity/safety with the other test files even though case (b)
# below is designed to stay shallow -- see the note above.
sys.setrecursionlimit(20000)


def run():
    all_ok = True

    print("=== BOUNDARY CASE (a): j == N, i == 0 ===")
    bd0 = (-1,) * 8
    buf_a = io.StringIO()
    with contextlib.redirect_stdout(buf_a):
        nsol_a = eqp.search(bd0, 0, 8, 0)
    out_a = buf_a.getvalue()
    ok_a = (nsol_a == 0 and out_a == "")
    print("Input:    bd=(-1,)*8, i=0, j=8 (== N), nsol=0")
    print("Expected: nsol == 0, no output printed (immediate termination)")
    print(f"Actual:   nsol == {nsol_a}, output length == {len(out_a)}")
    print("Result:  ", "PASS" if ok_a else "FAIL")
    all_ok = all_ok and ok_a
    print()

    print("=== BOUNDARY CASE (b): i == N - 1 with the *last* valid prefix ===")
    # Rows 0..6 below are taken directly from "Solution #92" (the last
    # solution the normal case finds) -- columns 7,3,0,2,5,1,6; row 7 (the
    # last row) is left unset (-1). See the module docstring for why this
    # specific prefix (rather than an arbitrary one) is needed here.
    bd_prefix = (7, 3, 0, 2, 5, 1, 6, -1)
    buf_b = io.StringIO()
    with contextlib.redirect_stdout(buf_b):
        nsol_b = eqp.search(bd_prefix, 7, 0, 0)
    out_b = buf_b.getvalue()
    ok_b = (nsol_b == 1 and "Solution #1:" in out_b)
    print("Input:    bd=(7,3,0,2,5,1,6,-1), i=7 (== N-1), j=0, nsol=0")
    print("Expected: nsol == 1 (exactly one completion of the last row)")
    print(f"Actual:   nsol == {nsol_b}")
    print("Result:  ", "PASS" if ok_b else "FAIL")
    print("Board found:")
    print(out_b)
    all_ok = all_ok and ok_b

    return all_ok


if __name__ == "__main__":
    run()
