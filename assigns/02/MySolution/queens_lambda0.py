import sys
from pathlib import Path

# This file sits in MySolution/ alongside the extended interpreter.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lambda0 import *

# substitution-based evaluation nests deeply 
# raise the limit before running.
sys.setrecursionlimit(100000)

# terminator for the board spine, never projected in correct operation,
# so its value is arbitrary, it only has to be *something*.
NIL = T0Mbtf(False)


########################################################################
# AST-building helpers 
########################################################################

def lam_multi(names, body):
    """Curried abstraction: lam_multi(["a","b"], M) is  λa. λb. M

    Built inside-out: the LAST name becomes the innermost binder.
    """
    for name in reversed(names):
        body = T0Mlam(name, body)
    return body


def app_multi(func, args):
    """Curried application: app_multi(f, [a, b]) is  ((f a) b)

    Left-associative, same as writing `f a b`: start with f, and each
    new argument becomes the right child of a new outer application.
    """
    for arg in args:
        func = T0Mapp(func, arg)
    return func


def let_bind(name, value_term, body):
    """let name = value_term in body  ==  (λname. body) value_term

    this avoids duplicating a subterm that would 
    otherwise appear in several places.
    """
    return T0Mapp(T0Mlam(name, body), value_term)


def andalso(left, right):
    """if left then right else false."""
    return T0Mif0(left, right, T0Mbtf(False))

########################################################################
# Board encoding: a list of column indices, one per row,
# as a right-nested spine of pairs ending in NIL.
#   [3, 1] becomes  (3, (1, NIL))
########################################################################

def encode_board(columns):
    """Python list of ints -> LAMBDA0 nested-pair board term."""
    term = NIL
    for col in reversed(columns):
        term = T0Mpair(T0Mint(col), term)
    return term


def decode_board(term, n):
    """LAMBDA0 board value -> Python list of n ints."""
    columns = []
    for _ in range(n):
        columns.append(term.arg1.arg1)   # T0Mpair -> T0Mint -> int
        term = term.arg2
    return columns


def print_board(columns):
    """Render one solution the way the ATS2 print_board does."""
    n = len(columns)
    for col in columns:
        print(" ".join("Q" if k == col else "." for k in range(n)))
    print()

########################################################################
# LAMBDA0 term builders -- the actual translation.
# Each returns a CLOSED term, so it can be dropped in wherever needed.
########################################################################

def make_board_get():
    """Term for board_get(bd, i): the column in row i. """

    # T0Mfix binds one param so the snd param is a plain T0Mlam, 
    # this means the recursive reference T0Mvar("g") 
    # stands for the fix term,  which still expects bd first thats 
    # why we used app_multi(g, [tail, i-1]) rather than a single application.

    return T0Mfix("g", "bd",                          
        T0Mlam("i",                                   
            T0Mif0(
                T0Mop2("==", T0Mvar("i"), T0Mint(0)),  
                T0Mpfst(T0Mvar("bd")),                 # base: head of this spine node
                app_multi(T0Mvar("g"), [               # step: recurse one node down
                    T0Mpsnd(T0Mvar("bd")),             # tail of the spine
                    T0Mop2("-", T0Mvar("i"), T0Mint(1)),  
                ]),
            )))

def make_board_set():
    """fix s(bd). λi. λj.
            if i == 0 then (j, snd bd)
            else (fst bd, s (snd bd) (i - 1) j)
        """
    return T0Mfix("s", "bd",                          
            T0Mlam("i", 
                T0Mlam("j",                         
                    T0Mif0(
                        T0Mop2("==", T0Mvar("i"), T0Mint(0)),

                        # base: replace this head, keep the rest of the spine as-is
                        T0Mpair(T0Mvar("j"), T0Mpsnd(T0Mvar("bd"))),

                        # step: keep this head, rebuild the tail recursively
                        T0Mpair(
                            T0Mpfst(T0Mvar("bd")), 
                            app_multi(T0Mvar("s"), [
                                T0Mpsnd(T0Mvar("bd")),
                                T0Mop2("-", T0Mvar("i"), T0Mint(1)),
                                T0Mvar("j"), 
                                ]),
                        )
                    )
            )))

def make_safety_test1():
    """λi0. λj0. λi1. λj1.
           j0 != j1  andalso  abs(i0 - i1) != abs(j0 - j1)

    True when queens at (i0, j0) and (i1, j1) do not attack each other.
    """
    # different columns
    diff_column = T0Mop2("!=", T0Mvar("j0"), T0Mvar("j1"))

    # different diagonals: the row gap and column gap must not match
    row_gap = T0Mop1("abs", T0Mop2("-", T0Mvar("i0"), T0Mvar("i1")))
    col_gap = T0Mop1("abs", T0Mop2("-", T0Mvar("j0"), T0Mvar("j1")))
    diff_diagonal = T0Mop2("!=", row_gap, col_gap)

    return lam_multi(["i0", "j0", "i1", "j1"],
                     andalso(diff_column, diff_diagonal))


def make_safety_test2():
    """fix t(i0). λj0. λbd. λi.
           if i >= 0 then
               safety_test1 i0 j0 i (board_get bd i)  andalso  t i0 j0 bd (i - 1)
           else true

    True when the queen at (i0, j0) clashes with no queen in rows 0..i.
    """
    # the column stored in row i of the board
    column_at_i = app_multi(make_board_get(), 
                    [T0Mvar("bd"), T0Mvar("i")])

    # does the candidate at (i0, j0) clash with the queen at (i, column_at_i)?
    no_clash = app_multi(make_safety_test1(), [
        T0Mvar("i0"), T0Mvar("j0"), T0Mvar("i"), column_at_i,
    ])

    # keep checking the row above - only i changes
    check_next_row = app_multi(T0Mvar("t"), [
        T0Mvar("i0"), T0Mvar("j0"), T0Mvar("bd"),
        T0Mop2("-", T0Mvar("i"), T0Mint(1)),
    ])

    return T0Mfix("t", "i0",
        lam_multi(["j0", "bd", "i"],
            T0Mif0(
                T0Mop2(">=", T0Mvar("i"), T0Mint(0)),
                andalso(no_clash, check_next_row),  # stops at the first clash
                T0Mbtf(True),                       # no rows left: safe
            )))

def make_search(n):
    """fix f(bd). λi. λj. λnsol. λbest.
            if j < N then
                if 
                    safety_test2 i j bd (i - 1) 
                then
                    let bd1 = board_set bd i j in
                        if i + 1 == N then f bd i (j+1) (nsol+1) bd1
                        else               
                            f bd1 (i+1) 0 nsol best
                else                    
                    f bd i (j+1) nsol best
            else
                if i > 0 
                then 
                    f bd (i-1) ((board_get bd (i-1)) + 1) nsol best
                else 
                    (nsol, best)

        Mirrors the ATS2 `search`, plus one parameter: `best` carries the most
        recently completed board out, since there is no I/O to print it with.
        The result is the pair (solution count, one solution board).
    """
    N = T0Mint(n)

    board_get = make_board_get()
    board_set = make_board_set()
    safety_test2 = make_safety_test2()

    # is the candidate at (i, j) safe against every queen in rows 0..i-1?
    is_safe = app_multi(safety_test2, [
        T0Mvar("i"), T0Mvar("j"), T0Mvar("bd"),
        T0Mop2("-", T0Mvar("i"), T0Mint(1)),
    ])

    # the board with row i set to column j
    placed = app_multi(board_set, [T0Mvar("bd"), 
                        T0Mvar("i"), T0Mvar("j")])

    # board complete: record it, then keep scanning this row from j+1.
    # note this passes bd, not bd1 -- the ATS2 original does the same.
    record_solution = app_multi(T0Mvar("f"), [
        T0Mvar("bd"),
        T0Mvar("i"),
        T0Mop2("+", T0Mvar("j"), T0Mint(1)),
        T0Mop2("+", T0Mvar("nsol"), T0Mint(1)),
        T0Mvar("bd1"),
    ])

    # board still partial: commit the placement, move to the next row
    descend = app_multi(T0Mvar("f"), [
        T0Mvar("bd1"),
        T0Mop2("+", T0Mvar("i"), T0Mint(1)),
        T0Mint(0),
        T0Mvar("nsol"),
        T0Mvar("best"),
    ])

    # placement rejected: try the next column in this row
    try_next_column = app_multi(T0Mvar("f"), [
        T0Mvar("bd"),
        T0Mvar("i"),
        T0Mop2("+", T0Mvar("j"), T0Mint(1)),
        T0Mvar("nsol"),
        T0Mvar("best"),
    ])

    # row exhausted: back up one row, resume after its current column
    backtrack = app_multi(T0Mvar("f"), [
        T0Mvar("bd"),
        T0Mop2("-", T0Mvar("i"), T0Mint(1)),
        T0Mop2("+",
               app_multi(board_get, [T0Mvar("bd"),
                        T0Mop2("-", T0Mvar("i"), T0Mint(1))]),
               T0Mint(1)),
        T0Mvar("nsol"),
        T0Mvar("best"),
    ])

    # bd1 is bound once and used by both branches below
    place_queen = let_bind("bd1", placed,
        T0Mif0(
            T0Mop2("==", T0Mop2("+", T0Mvar("i"), T0Mint(1)), N),
            record_solution,
            descend,
        ))

    body = T0Mif0(
        T0Mop2("<", T0Mvar("j"), N),
        T0Mif0(is_safe, place_queen, try_next_column),
        T0Mif0(
            T0Mop2(">", T0Mvar("i"), T0Mint(0)),
            backtrack,
            T0Mpair(T0Mvar("nsol"), T0Mvar("best")),   # done
        ),
    )

    return T0Mfix("f", "bd", lam_multi(["i", "j", "nsol", "best"], body))

def run_queens(n):
    """Build, evaluate, and decode the n-queens search.

    Returns (solution_count, board_columns), with board_columns None
    when there are no solutions.
    """
    start = encode_board([0] * n)
    term = app_multi(make_search(n), [
        start,        # bd:   working board
        T0Mint(0),    # i:    current row
        T0Mint(0),    # j:    current column
        T0Mint(0),    # nsol: solutions found so far
        start,        # best: placeholder until a solution is recorded
    ])
    result = t0erm_cbv_evaluate0(term)
    count = result.arg1.arg1                  # T0Mpair -> T0Mint -> int
    board = decode_board(result.arg2, n)
    return count, (board if count > 0 else None)

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    count, board = run_queens(n)
    print(f"N = {n}: {count} solution(s)")
    if count > 0:
        print_board(board)


if __name__ == "__main__":
    main()