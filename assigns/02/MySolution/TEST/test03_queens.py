import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lambda0 import *
from queens_lambda0 import *

class TestBoard(unittest.TestCase):

    def test_board_get(self):
        columns = [3, 1, 4, 1]
        bd = encode_board(columns)
        board_get = make_board_get()          # build the term once
        for i in range(len(columns)):
            term = app_multi(board_get, [bd, T0Mint(i)])
            self.assertEqual(t0erm_cbv_evaluate0(term), T0Mint(columns[i]))


class TestBoardSet(unittest.TestCase):

    def setUp(self):
        # both builders return closed terms, so they can be reused across calls
        self.columns = [3, 1, 4, 1]
        self.bd = encode_board(self.columns)
        self.board_set = make_board_set()
        self.board_get = make_board_get()

    def set_board(self, bd, i, j):
        """Evaluate board_set(bd, i, j) and decode the result to a Python list."""
        term = app_multi(self.board_set, [bd, T0Mint(i), T0Mint(j)])
        return decode_board(t0erm_cbv_evaluate0(term), len(self.columns))

    def test_set_first_row(self):
        # index 0 fires the base case immediately, no recursion
        self.assertEqual(self.set_board(self.bd, 0, 7), [7, 1, 4, 1])

    def test_set_middle_row(self):
        self.assertEqual(self.set_board(self.bd, 2, 7), [3, 1, 7, 1])

    def test_set_last_row(self):
        # deepest walk down the spine before the base case fires
        self.assertEqual(self.set_board(self.bd, 3, 7), [3, 1, 4, 7])

    def test_original_board_unchanged(self):
        # board_set is a functional update, like the ATS2 original: it
        # builds a fresh spine and leaves the input board alone
        self.set_board(self.bd, 2, 7)
        self.assertEqual(decode_board(self.bd, len(self.columns)), self.columns)

    def test_set_then_get_round_trip(self):
        # setting row i to j, then reading row i back, must give j
        for i in range(len(self.columns)):
            with self.subTest(i=i):
                set_term = app_multi(self.board_set, [self.bd, T0Mint(i), T0Mint(6)])
                updated = t0erm_cbv_evaluate0(set_term)
                get_term = app_multi(self.board_get, [updated, T0Mint(i)])
                self.assertEqual(t0erm_cbv_evaluate0(get_term), T0Mint(6))

    def test_result_matches_encoded_board(self):
        # structural check: the evaluated spine should be identical to what
        # encode_board produces for the same list, NIL terminator included
        term = app_multi(self.board_set, [self.bd, T0Mint(1), T0Mint(9)])
        self.assertEqual(t0erm_cbv_evaluate0(term), encode_board([3, 9, 4, 1]))


class TestAbsPrimitive(unittest.TestCase):
    """abs was added to T0Mop1 for the queens translation's diagonal check."""

    def test_abs_of_values(self):
        for operand, expected in [(7, 7), (-7, 7), (0, 0), (-1, 1)]:
            with self.subTest(operand=operand):
                term = T0Mop1("abs", T0Mint(operand))
                self.assertEqual(t0erm_cbv_evaluate0(term), T0Mint(expected))

    def test_abs_evaluates_its_operand_first(self):
        # the operand is reduced before abs is applied, like every other
        # call-by-value operator: abs(3 - 10) = 7
        term = T0Mop1("abs", T0Mop2("-", T0Mint(3), T0Mint(10)))
        self.assertEqual(t0erm_cbv_evaluate0(term), T0Mint(7))

    def test_abs_rejects_non_integers(self):
        term = T0Mop1("abs", T0Mbtf(True))
        with self.assertRaises(TypeError):
            t0erm_cbv_evaluate0(term)

    def test_unknown_unary_operator_still_rejected(self):
        # the guard must not have been loosened by adding a third operator
        term = T0Mop1("!", T0Mint(1))
        with self.assertRaises(TypeError):
            t0erm_cbv_evaluate0(term)

    def test_abs_in_structural_functions(self):
        # "abs" lives in arg1 as a string, so size/fvset/subst need no
        # new cases -- this confirms they handle it as an ordinary T0Mop1
        term = T0Mop1("abs", T0Mvar("x"))
        self.assertEqual(t0erm_size(term), 2)                    # op1 + var
        self.assertEqual(t0erm_fvset(term), frozenset({"x"}))
        self.assertEqual(t0erm_subst0(term, "x", T0Mint(-4)),
                         T0Mop1("abs", T0Mint(-4)))


class TestSafetyTests(unittest.TestCase):

    def setUp(self):
        self.safety1 = make_safety_test1()
        self.safety2 = make_safety_test2()
        # a known-good 4-queens solution: row i holds a queen in column bd[i]
        self.solution = [1, 3, 0, 2]
        self.bd = encode_board(self.solution)

    def safe1(self, i0, j0, i1, j1):
        term = app_multi(self.safety1,
                         [T0Mint(i0), T0Mint(j0), T0Mint(i1), T0Mint(j1)])
        return t0erm_cbv_evaluate0(term)

    def safe2(self, i0, j0, bd, i):
        term = app_multi(self.safety2,
                         [T0Mint(i0), T0Mint(j0), bd, T0Mint(i)])
        return t0erm_cbv_evaluate0(term)

    # --- safety_test1 ---------------------------------------------------

    def test_same_column_conflicts(self):
        self.assertEqual(self.safe1(0, 2, 3, 2), T0Mbtf(False))

    def test_down_right_diagonal_conflicts(self):
        # (0,0) and (2,2) share a diagonal
        self.assertEqual(self.safe1(0, 0, 2, 2), T0Mbtf(False))

    def test_down_left_diagonal_conflicts(self):
        # (0,2) and (2,0) share the other diagonal -- this is the case
        # the abs primitive exists for
        self.assertEqual(self.safe1(0, 2, 2, 0), T0Mbtf(False))

    def test_non_attacking_pair(self):
        # a knight's move apart: different column, different diagonal
        self.assertEqual(self.safe1(0, 0, 1, 2), T0Mbtf(True))

    def test_same_row_reported_safe(self):
        # the board stores one column per row, so two queens cannot share
        # a row; the ATS2 original never checks for it, and neither do we
        self.assertEqual(self.safe1(1, 0, 1, 3), T0Mbtf(True))

    # --- safety_test2 ---------------------------------------------------

    def test_no_rows_to_check_is_safe(self):
        # i < 0 means there are no earlier rows to conflict with
        self.assertEqual(self.safe2(0, 0, self.bd, -1), T0Mbtf(True))

    def test_safe_against_all_earlier_rows(self):
        # row 2 column 0 is this solution's own placement, so it must
        # clear both queens already standing in rows 0 and 1
        self.assertEqual(self.safe2(2, 0, self.bd, 1), T0Mbtf(True))

    def test_column_clash_with_earlier_row(self):
        # row 0 already holds column 1
        self.assertEqual(self.safe2(2, 1, self.bd, 1), T0Mbtf(False))

    def test_diagonal_clash_with_earlier_row(self):
        # (2,2) and the queen at (1,3) share a diagonal
        self.assertEqual(self.safe2(2, 2, self.bd, 1), T0Mbtf(False))

    def test_whole_solution_is_internally_consistent(self):
        # every queen in the known solution must clear all queens
        # standing in rows before it
        for i in range(1, len(self.solution)):
            with self.subTest(row=i):
                self.assertEqual(
                    self.safe2(i, self.solution[i], self.bd, i - 1),
                    T0Mbtf(True))
def board_is_legal(columns):
    """True when no two queens share a column or a diagonal.

    Rows are distinct by construction: the board stores one column per row.
    """
    n = len(columns)
    for a in range(n):
        for b in range(a + 1, n):
            if columns[a] == columns[b]:
                return False
            if abs(a - b) == abs(columns[a] - columns[b]):
                return False
    return True


class TestSearch(unittest.TestCase):

    def test_known_solution_counts(self):
        # the classic sequence for N = 1..4
        for n, expected in [(1, 1), (2, 0), (3, 0), (4, 2)]:
            with self.subTest(n=n):
                count, _ = run_queens(n)
                self.assertEqual(count, expected)

    def test_returned_board_is_legal(self):
        count, board = run_queens(4)
        self.assertEqual(count, 2)
        self.assertIsNotNone(board)
        self.assertTrue(board_is_legal(board))
        self.assertEqual(len(board), 4)

    def test_no_board_when_no_solution(self):
        count, board = run_queens(3)
        self.assertEqual(count, 0)
        self.assertIsNone(board)


if __name__ == "__main__":
    unittest.main(verbosity=2)