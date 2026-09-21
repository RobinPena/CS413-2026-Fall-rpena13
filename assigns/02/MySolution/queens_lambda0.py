import sys
from pathlib import Path

# This file sits in MySolution/ alongside the extended interpreter.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lambda0 import (
    T0Mint, T0Mbtf, T0Mvar, T0Mlam, T0Mfix, T0Mapp, T0Mif0, T0Mop1, T0Mop2,
    T0Mpair, T0Mpfst, T0Mpsnd,
    t0erm_cbv_evaluate0,
)

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



def main():
    print("make_board_get() done ")

if __name__ == "__main__":
    main()
    