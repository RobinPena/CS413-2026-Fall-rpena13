import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lambda0 import T0Mint, t0erm_cbv_evaluate0
from queens_lambda0 import (
    app_multi, encode_board, make_board_get,
)

class TestBoard(unittest.TestCase):

    def test_board_get(self):
        columns = [3, 1, 4, 1]
        bd = encode_board(columns)
        board_get = make_board_get()          # build the term once
        for i in range(len(columns)):
            term = app_multi(board_get, [bd, T0Mint(i)])
            self.assertEqual(t0erm_cbv_evaluate0(term), T0Mint(columns[i]))

if __name__ == "__main__":
    unittest.main(verbosity=2)