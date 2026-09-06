#!/usr/bin/env python3
"""
Python3 translation of eqp_source.dats (Eight Queens Puzzle).

This mirrors the original ATS program function-for-function, keeping the
same names, parameter order, and control flow (including the somewhat
unusual "no explicit stack" backtracking trick, where `search` re-derives
the column to resume from at row i-1 by reading it back out of `bd` via
board_get instead of maintaining a separate history/stack).

Deliberate changes / notes on language-mechanics differences (also noted
inline near the relevant code):

1. ATS's `print` does not append a trailing newline; Python's builtin
   `print()` does by default. An `aprint` helper (print with end="")
   is used everywhere the original calls `print`, so newlines only
   appear exactly where the original source writes an explicit "\n".

2. ATS's `search` (and `print_dots`) are self tail-recursive, and ATS
   guarantees proper tail-call optimization, so the call chain never
   grows the stack. CPython has no TCO, and for N=8 the tail-recursive
   `search` chain is ~17,000+ calls deep. `sys.setrecursionlimit` is
   raised before running purely as a runtime accommodation for this;
   it does not change the algorithm's behavior or output.

3. ATS's `typedef int8 = (int,...,int)` (8-tuple) is a static type
   alias needed by ATS's type checker. Python has no static tuple-arity
   types, so the board is just a plain 8-tuple of ints, used directly
   wherever `int8` appears in the original.

4. `board_get`/`board_set` keep the original's explicit if/elif chain
   over indices 0..7 (rather than idiomatic `bd[i]` / tuple slicing)
   so the control flow matches the source as closely as possible.

5. The provided .dats excerpt defines only helper functions and
   `search`, with no `implement main0` entry point. A minimal `main()`
   was added (initial board of eight -1's = "no queen placed", then
   `search(bd0, 0, 0, 0)` followed by a solution-count report) mirroring
   the conventional ATS eight-queens example, so the translated program
   is actually runnable end-to-end. This is an addition, not a
   translation of existing source code.

6. ATS's `~1` (negative one) becomes Python's `-1`; ATS's `andalso`
   becomes Python's `and`; `!=` is spelled the same in both languages.
"""

import sys

N = 8

# typedef int8 = (int, int, int, int, int, int, int, int)
# -> represented directly as a plain Python tuple of 8 ints.


def aprint(s):
    """Mimics ATS's `print`, which (unlike Python's print()) does not
    append a trailing newline of its own."""
    print(s, end="")


def print_dots(i):
    if i > 0:
        aprint(". ")
        print_dots(i - 1)
    else:
        pass


def print_row(i):
    print_dots(i)
    aprint("Q ")
    print_dots(N - i - 1)
    aprint("\n")


def print_board(bd):
    print_row(bd[0])
    print_row(bd[1])
    print_row(bd[2])
    print_row(bd[3])
    print_row(bd[4])
    print_row(bd[5])
    print_row(bd[6])
    print_row(bd[7])
    print_newline()


def print_newline():
    aprint("\n")


def board_get(bd, i):
    if i == 0:
        return bd[0]
    elif i == 1:
        return bd[1]
    elif i == 2:
        return bd[2]
    elif i == 3:
        return bd[3]
    elif i == 4:
        return bd[4]
    elif i == 5:
        return bd[5]
    elif i == 6:
        return bd[6]
    elif i == 7:
        return bd[7]
    else:
        return -1


def board_set(bd, i, j):
    x0, x1, x2, x3, x4, x5, x6, x7 = bd

    if i == 0:
        x0 = j
        return (x0, x1, x2, x3, x4, x5, x6, x7)
    elif i == 1:
        x1 = j
        return (x0, x1, x2, x3, x4, x5, x6, x7)
    elif i == 2:
        x2 = j
        return (x0, x1, x2, x3, x4, x5, x6, x7)
    elif i == 3:
        x3 = j
        return (x0, x1, x2, x3, x4, x5, x6, x7)
    elif i == 4:
        x4 = j
        return (x0, x1, x2, x3, x4, x5, x6, x7)
    elif i == 5:
        x5 = j
        return (x0, x1, x2, x3, x4, x5, x6, x7)
    elif i == 6:
        x6 = j
        return (x0, x1, x2, x3, x4, x5, x6, x7)
    elif i == 7:
        x7 = j
        return (x0, x1, x2, x3, x4, x5, x6, x7)
    else:
        return bd


def safety_test1(i0, j0, i1, j1):
    return j0 != j1 and abs(i0 - i1) != abs(j0 - j1)


def safety_test2(i0, j0, bd, i):
    if i >= 0:
        if safety_test1(i0, j0, i, board_get(bd, i)):
            return safety_test2(i0, j0, bd, i - 1)
        else:
            return False
    else:
        return True


def search(bd, i, j, nsol):
    if j < N:
        test = safety_test2(i, j, bd, i - 1)
        if test:
            bd1 = board_set(bd, i, j)
            if i + 1 == N:
                aprint("Solution #" + str(nsol + 1) + ":\n\n")
                print_board(bd1)
                return search(bd, i, j + 1, nsol + 1)
            else:
                return search(bd1, i + 1, 0, nsol)
        else:
            return search(bd, i, j + 1, nsol)
    else:
        if i > 0:
            return search(bd, i - 1, board_get(bd, i - 1) + 1, nsol)
        else:
            return nsol


def main():
    # Not part of the original excerpt (see note 5 above): a minimal
    # driver so the program can actually be run.
    bd0 = (-1, -1, -1, -1, -1, -1, -1, -1)
    nsol = search(bd0, 0, 0, 0)
    aprint("There are " + str(nsol) + " solutions.\n")


if __name__ == "__main__":
    # See note 2 above: accommodates the deep tail-recursive call chain
    # that ATS would otherwise optimize away.
    sys.setrecursionlimit(20000)
    main()
