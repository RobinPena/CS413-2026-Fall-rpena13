import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lambda0 import T0Mint, t0erm_cbv_evaluate0
from queens_lambda0 import (
    app_multi, decode_board, encode_board, make_board_get,make_board_set
)

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

if __name__ == "__main__":
    unittest.main(verbosity=2)