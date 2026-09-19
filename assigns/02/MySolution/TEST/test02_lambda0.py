import sys
import unittest
from pathlib import Path

# Allow this file to run directly from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lambda0 import (
    T0Mint, T0Mbtf, T0Mstr, T0Mvar, T0Mlam, T0Mfix, T0Mapp, T0Mif0, T0Mop1, T0Mop2,
    T0Mpair, T0Mpfst, T0Mpsnd,
    t0erm_size, t0erm_fvset, t0erm_subst0, t0erm_cbv_evaluate0,
)


class TestPair(unittest.TestCase):

    def test_pair_size(self):
        pair_term = T0Mpair(T0Mint(5), T0Mint(2))
        pair_nested_terms = T0Mpair(T0Mpair(T0Mint(1), T0Mint(2)), T0Mpair(T0Mint(3), T0Mint(4)))
        self.assertEqual(t0erm_size(pair_term), 3)  # 1 for pair + 1 for each element
        self.assertEqual(t0erm_size(pair_nested_terms), 7)  # 1 for outer pair + 1 for each inner pair

    def test_projections_size(self):
        pair_term = T0Mpair(T0Mint(1), T0Mint(1))
        pfst_term = T0Mpfst(pair_term)
        psnd_term = T0Mpsnd(pair_term)
        self.assertEqual(t0erm_size(pfst_term), 4)  # 2 for pfst + 2 for pair
        self.assertEqual(t0erm_size(psnd_term), 4)  # 2 for psnd + 2 for pair

class TestPairFvset(unittest.TestCase):
    
    def test_pair_fvset(self):
        pair_term = T0Mpair(T0Mvar("x"), T0Mvar("y"))
        self.assertEqual(t0erm_fvset(pair_term), {"x", "y"})

    def test_projections_fvset(self):
        pair_term = T0Mpair(T0Mvar("x"), T0Mvar("y"))
        pfst_term = T0Mpfst(pair_term)
        psnd_term = T0Mpsnd(pair_term)
        self.assertEqual(t0erm_fvset(pfst_term), {"x", "y"})
        self.assertEqual(t0erm_fvset(psnd_term), {"x", "y"})


if __name__ == "__main__":
    unittest.main()