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
        self.assertEqual(t0erm_size(pfst_term), 4)  # 1 for pfst + 3 for pair
        self.assertEqual(t0erm_size(psnd_term), 4)  # 1 for psnd + 3 for pair

    # pairs and projections must also count correctly when they sit
    # inside other constructs, not just on their own
    def test_size_pair_inside_other_constructs(self):
        # lam(x). if0 (x < 1) then fst(x, 2) else snd(3, x)
        term = T0Mlam("x",
            T0Mif0(
                T0Mop2("<", T0Mvar("x"), T0Mint(1)),        # 1 op2 + 1 var + 1 int = 3
                T0Mpfst(T0Mpair(T0Mvar("x"), T0Mint(2))),   # 1 pfst + 3 pair = 4
                T0Mpsnd(T0Mpair(T0Mint(3), T0Mvar("x"))),   # 1 psnd + 3 pair = 4
            ))
        # 1 lam + 1 if0 + 3 + 4 + 4 = 13
        self.assertEqual(t0erm_size(term), 13)


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

    # a binder outside the pair still removes its own name from the result
    def test_fvset_pair_inside_other_constructs(self):
        # lam(x). (x, (y, z)) -- x is bound here, y and z stay free
        term = T0Mlam("x", T0Mpair(T0Mvar("x"), T0Mpair(T0Mvar("y"), T0Mvar("z"))))
        self.assertEqual(t0erm_fvset(term), frozenset({"y", "z"}))

        # a projection nested in an application contributes its operand's names
        app_term = T0Mapp(T0Mvar("f"), T0Mpfst(T0Mpair(T0Mvar("a"), T0Mvar("b"))))
        self.assertEqual(t0erm_fvset(app_term), frozenset({"f", "a", "b"}))


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

    # a binder whose name differs does not block substitution:
    # the replacement still reaches the pair inside the body
    def test_subst_under_nonmatching_binder(self):
        term = T0Mlam("y", T0Mpair(T0Mvar("x"), T0Mvar("y")))
        substituted = t0erm_subst0(term, "x", T0Mint(42))
        expected = T0Mlam("y", T0Mpair(T0Mint(42), T0Mvar("y")))
        self.assertEqual(substituted, expected)

    # same rule inside a recursive function: neither the function name
    # nor the parameter shadows "x", so substitution reaches the pair
    def test_subst_under_fix_binder(self):
        term = T0Mfix("f", "n", T0Mpair(T0Mvar("x"), T0Mvar("n")))
        substituted = t0erm_subst0(term, "x", T0Mint(7))
        expected = T0Mfix("f", "n", T0Mpair(T0Mint(7), T0Mvar("n")))
        self.assertEqual(substituted, expected)

        # but a T0Mfix whose parameter IS "x" blocks it entirely
        blocked = T0Mfix("f", "x", T0Mpfst(T0Mpair(T0Mvar("x"), T0Mint(0))))
        self.assertEqual(t0erm_subst0(blocked, "x", T0Mint(7)), blocked)


class TestPairEvaluation(unittest.TestCase):
    # components are already values, so the result matches the input
    def test_pair_construction(self):
        pair_term = T0Mpair(T0Mint(3), T0Mint(1))
        evaluated_term = t0erm_cbv_evaluate0(pair_term)
        self.assertEqual(evaluated_term, pair_term)

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

    # both components get reduced before the pair is returned,
    # with no projection involved to force it
    def test_pair_components_evaluated_in_place(self):
        term = T0Mpair(
            T0Mop2("+", T0Mint(2), T0Mint(3)),
            T0Mop2("*", T0Mint(2), T0Mint(4)),
        )
        self.assertEqual(t0erm_cbv_evaluate0(term), T0Mpair(T0Mint(5), T0Mint(8)))

    # a pair may hold values of different kinds, including a function
    def test_pair_mixed_kinds(self):
        identity = T0Mlam("z", T0Mvar("z"))
        pair_term = T0Mpair(T0Mint(7), identity)
        self.assertEqual(t0erm_cbv_evaluate0(pair_term),
                         T0Mpair(T0Mint(7), identity))
        # the function survives projection and is still applicable
        applied = t0erm_cbv_evaluate0(T0Mapp(T0Mpsnd(pair_term), T0Mint(9)))
        self.assertEqual(applied, T0Mint(9))

    # a function that accepts a pair: the pair value is substituted into
    # a body whose projections then pull it apart
    def test_function_accepting_pair(self):
        sum_pair = T0Mlam("p",
            T0Mop2("+", T0Mpfst(T0Mvar("p")), T0Mpsnd(T0Mvar("p"))))
        term = T0Mapp(sum_pair, T0Mpair(T0Mint(10), T0Mint(20)))
        self.assertEqual(t0erm_cbv_evaluate0(term), T0Mint(30))

    # a function that returns a pair: the bound variable is substituted
    # into both components before the pair is built
    def test_function_returning_pair(self):
        make_pair = T0Mlam("x",
            T0Mpair(T0Mvar("x"), T0Mop2("+", T0Mvar("x"), T0Mint(1))))
        term = T0Mapp(make_pair, T0Mint(4))
        self.assertEqual(t0erm_cbv_evaluate0(term),
                         T0Mpair(T0Mint(4), T0Mint(5)))


if __name__ == "__main__":
    unittest.main(verbosity=2)