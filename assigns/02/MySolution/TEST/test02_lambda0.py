import sys
import unittest
from pathlib import Path

# Allow this file to run directly from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lambda0 import (
    T0Mint, T0Mbtf, T0Mstr, T0Mvar, T0Mlam, T0Mfix, T0Mapp, 
    T0Mif0, T0Mop1, T0Mop2,T0Mpair, T0Mpfst, T0Mpsnd,
    t0erm_size, t0erm_fvset, t0erm_subst0, t0erm_cbv_evaluate0,
)


class TestPair(unittest.TestCase):
    # test that the size of a pair is 1 + size of its components
    def test_pair_size(self):
        pair_term = T0Mpair(T0Mint(5), T0Mint(2))
        pair_nested_terms = T0Mpair(T0Mpair(T0Mint(1), 
                            T0Mint(2)), T0Mpair(T0Mint(3), T0Mint(4)))
        self.assertEqual(t0erm_size(pair_term), 3)  # +1 for pair + 1 for each element
        self.assertEqual(t0erm_size(pair_nested_terms), 7)  # +1 for outer pair + 1 for each inner pair

    # test that the size of projections is 1 + size of the operand
    def test_projections_size(self):
        pair_term = T0Mpair(T0Mint(1), T0Mint(1))
        pfst_term = T0Mpfst(pair_term)
        psnd_term = T0Mpsnd(pair_term)
        self.assertEqual(t0erm_size(pfst_term), 4)  # 2 for pfst + 2 for pair
        self.assertEqual(t0erm_size(psnd_term), 4)  # 2 for psnd + 2 for pair

class TestPairFvset(unittest.TestCase):
    # the free variables of a pair is the union of free variables of its components
    def test_pair_fvset(self):
        pair_term = T0Mpair(T0Mvar("x"), T0Mvar("y"))
        self.assertEqual(t0erm_fvset(pair_term), {"x", "y"}) 

    # free variables of projections should be the same as the free variables of the operand    
    def test_projections_fvset(self):
        pair_term = T0Mpair(T0Mvar("x"), T0Mvar("y"))
        pfst_term = T0Mpfst(pair_term)
        psnd_term = T0Mpsnd(pair_term)
        self.assertEqual(t0erm_fvset(pfst_term), {"x", "y"})
        self.assertEqual(t0erm_fvset(psnd_term), {"x", "y"})

class TestPairSubstitution(unittest.TestCase):
    # substituting in a pair should substitute in both components
    def test_pair_substitution(self): 
        pair_term = T0Mpair(T0Mvar("x"), T0Mvar("y"))
        substituted_term = t0erm_subst0(pair_term, "x", T0Mint(42))
        expected_term = T0Mpair(T0Mint(42), T0Mvar("y"))
        self.assertEqual(substituted_term, expected_term)

    # substituting in projections substitutes the operand of the projection
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
        # test that substitution does not occur in the bound variable of a lambda
        lambda_term = T0Mlam("x", T0Mpair(T0Mvar("x"), T0Mvar("y")))
        substituted_term = t0erm_subst0(lambda_term, "x", T0Mint(55))
        expected_term = T0Mlam("x", T0Mpair(T0Mvar("x"), T0Mvar("y")))  # No substitution should occur
        self.assertEqual(substituted_term, expected_term)

class TestPairEvaluation(unittest.TestCase):
        # test that evaluating a pair returns the pair itself (since pairs are values)
    def test_pair_construction(self):
        pair_term = T0Mpair(T0Mint(3), T0Mint(1))
        evaluated_term = t0erm_cbv_evaluate0(pair_term)
        self.assertEqual(evaluated_term, pair_term)  # Pairs are values

    # test that evaluating pfst and psnd returns the first and second elements of the pair
    def test_projections_evaluation(self):
        pair_term = T0Mpair(T0Mint(3), T0Mint(1))
        pfst_term = T0Mpfst(pair_term)
        psnd_term = T0Mpsnd(pair_term)
        evaluated_pfst = t0erm_cbv_evaluate0(pfst_term)
        evaluated_psnd = t0erm_cbv_evaluate0(psnd_term)
        self.assertEqual(evaluated_pfst, T0Mint(3))
        self.assertEqual(evaluated_psnd, T0Mint(1))

    # Test that evaluating pfst and psnd on a non-pair raises a TypeError
    def test_projection_eval_type_error(self):
        non_pair_term = T0Mint(5)
        pfst_term = T0Mpfst(non_pair_term)
        psnd_term = T0Mpsnd(non_pair_term)
        with self.assertRaises(TypeError):
            t0erm_cbv_evaluate0(pfst_term)
        with self.assertRaises(TypeError):
            t0erm_cbv_evaluate0(psnd_term)
    
    # test that both components of a pair are 
    # evaluated even when only one is projected 
    def test_pair_evaluation_order(self):
        # This must raise a ZeroDivisionError when evaluated
        pair_term = T0Mpair(T0Mint(1), T0Mop2("/", T0Mint(1), T0Mint(0)))
        pfst_term = T0Mpfst(pair_term)
        with self.assertRaises(ZeroDivisionError):
            t0erm_cbv_evaluate0(pfst_term)  

    # test that nested pairs are evaluated correctly
    def test_nested_pair_evaluation(self):
        nested_pair_term = T0Mpair(T0Mpair(T0Mint(1), T0Mint(2)), T0Mpair(T0Mint(3), T0Mint(4)))
        pfst_term = T0Mpfst(nested_pair_term)
        psnd_term = T0Mpsnd(nested_pair_term)
        evaluated_pfst = t0erm_cbv_evaluate0(pfst_term)
        evaluated_psnd = t0erm_cbv_evaluate0(psnd_term)
        self.assertEqual(evaluated_pfst, T0Mpair(T0Mint(1), T0Mint(2)))
        self.assertEqual(evaluated_psnd, T0Mpair(T0Mint(3), T0Mint(4)))


    # test that nested pairs with operations are evaluated correctly
    def test_nested_pair_mixed_values(self):
        nested_pair_term = T0Mpair(T0Mpair(T0Mint(1), T0Mop2("+", T0Mint(2), T0Mint(3))), 
                                   T0Mpair(T0Mop2("*", T0Mint(4), T0Mint(5)), T0Mint(6)))
        pfst_term = T0Mpfst(nested_pair_term)
        psnd_term = T0Mpsnd(nested_pair_term)
        evaluated_pfst = t0erm_cbv_evaluate0(pfst_term)
        evaluated_psnd = t0erm_cbv_evaluate0(psnd_term)
        self.assertEqual(evaluated_pfst, T0Mpair(T0Mint(1), T0Mint(5)))  # 2 + 3 = 5
        self.assertEqual(evaluated_psnd, T0Mpair(T0Mint(20), T0Mint(6)))  # 4 * 5 = 20


    # test that functions can be applied to pairs and their projections
    def test_functions_over_pairs(self):
        pair_term = T0Mpair(T0Mint(10), T0Mint(20))
        pfst_term = T0Mpfst(pair_term)
        psnd_term = T0Mpsnd(pair_term)
        add_function = T0Mlam("x", T0Mlam("y", T0Mop2("+", T0Mvar("x"), T0Mvar("y"))))
        add_pfst_psnd = T0Mapp(T0Mapp(add_function, pfst_term), psnd_term)
        evaluated_result = t0erm_cbv_evaluate0(add_pfst_psnd)
        self.assertEqual(evaluated_result, T0Mint(30))  # 10 + 20 = 30

if __name__ == "__main__":
    unittest.main(verbosity=2)