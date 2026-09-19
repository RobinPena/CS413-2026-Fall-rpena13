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
    #the free variables of a pair is the union of free variables of its components
    def test_pair_fvset(self):
        pair_term = T0Mpair(T0Mvar("x"), T0Mvar("y"))
        self.assertEqual(t0erm_fvset(pair_term), {"x", "y"}) 

    #free variables of projections should be the same as the free variables of the operand    
    def test_projections_fvset(self):
        pair_term = T0Mpair(T0Mvar("x"), T0Mvar("y"))
        pfst_term = T0Mpfst(pair_term)
        psnd_term = T0Mpsnd(pair_term)
        self.assertEqual(t0erm_fvset(pfst_term), {"x", "y"})
        self.assertEqual(t0erm_fvset(psnd_term), {"x", "y"})

class TestPairSubstitution(unittest.TestCase):
    #substituting in a pair should substitute in both components
    def test_pair_substitution(self): 
        pair_term = T0Mpair(T0Mvar("x"), T0Mvar("y"))
        substituted_term = t0erm_subst0(pair_term, "x", T0Mint(42))
        expected_term = T0Mpair(T0Mint(42), T0Mvar("y"))
        self.assertEqual(substituted_term, expected_term)

#substituting in projections substitutes the operand of the projection
    def test_projections_substitution(self):
        pair_term = T0Mpair(T0Mvar("x"), T0Mvar("y"))
        pfst_term = T0Mpfst(pair_term)
        psnd_term = T0Mpsnd(pair_term)
        substituted_pfst = t0erm_subst0(pfst_term, "x", T0Mint(55))
        substituted_psnd = t0erm_subst0(psnd_term, "y", T0Mint(12))
        expected_pfst = T0Mpfst(T0Mpair(T0Mint(55), T0Mvar("y")))
        expected_psnd = T0Mpsnd(T0Mpair(T0Mvar("x"), T0Mint(12)))
        self.assertEqual(substituted_pfst, expected_pfst)
        self.assertEqual(substituted_psnd, expected_psnd)

    def test_binder_substitution(self):
        # Test that substitution does not occur in the bound variable of a lambda
        lambda_term = T0Mlam("x", T0Mpair(T0Mvar("x"), T0Mvar("y")))
        substituted_term = t0erm_subst0(lambda_term, "x", T0Mint(55))
        expected_term = T0Mlam("x", T0Mpair(T0Mvar("x"), T0Mvar("y")))  # No substitution should occur
        self.assertEqual(substituted_term, expected_term)
if __name__ == "__main__":
    unittest.main()