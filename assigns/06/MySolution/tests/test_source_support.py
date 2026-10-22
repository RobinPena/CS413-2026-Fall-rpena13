"""The supplied AST is the unchanged assigns/05 file; source printing and names."""
import sys
import types
import unittest
from pathlib import Path

import MySolution
from MySolution import source_support as S

ASSIGN06 = Path(__file__).resolve().parents[2]


class EnvironmentTests(unittest.TestCase):
    def test_python_is_at_least_3_12(self):
        self.assertGreaterEqual(sys.version_info[:2], (3, 12))

    def test_package_is_the_assign06_solution(self):
        self.assertEqual(Path(MySolution.__file__).resolve().parent,
                         ASSIGN06 / "MySolution")


class SuppliedAstTests(unittest.TestCase):
    def test_classes_come_from_the_assign05_file(self):
        supplied = sys.modules["lambda1_vp"]
        self.assertEqual(Path(supplied.__file__).resolve(),
                         ASSIGN06.parent / "05" / "lambda1_vp.py")
        self.assertIs(S.D0Eint, supplied.D0Eint)
        self.assertIs(S.D0ExpVisitor, supplied.D0ExpVisitor)
        self.assertIs(S.source_fv, supplied.d0exp_fvset)

    def test_loading_again_reuses_the_same_module(self):
        self.assertIs(S.load_supplied_ast(), sys.modules["lambda1_vp"])

    def test_refuses_a_lambda1_vp_from_elsewhere(self):
        real = sys.modules["lambda1_vp"]
        impostor = types.ModuleType("lambda1_vp")
        impostor.__file__ = str(ASSIGN06 / "lambda1_vp.py")
        sys.modules["lambda1_vp"] = impostor
        try:
            with self.assertRaises(ImportError):
                S.load_supplied_ast()
        finally:
            sys.modules["lambda1_vp"] = real


# One example of every constructor, with its expected printed form and names.
EVERY_FORM = [
    (S.D0Eint(7), "7", set()),
    (S.D0Ebtf(True), "true", set()),
    (S.D0Ebtf(False), "false", set()),
    (S.D0Evar("x"), "x", {"x"}),
    (S.D0Elam("x", S.D0Evar("y")), "(lam x. y)", {"x", "y"}),
    (S.D0Eapp(S.D0Evar("f"), S.D0Eint(3)), "(f 3)", {"f"}),
    (S.D0Eop1("not", S.D0Evar("b")), "(not b)", {"b"}),
    (S.D0Eop2("+", S.D0Eint(2), S.D0Evar("n")), "(2 + n)", {"n"}),
    (S.D0Eif0(S.D0Evar("c"), S.D0Eint(1), S.D0Eint(2)),
     "(if c then 1 else 2)", {"c"}),
    (S.D0Elet("x", S.D0Evar("x"), S.D0Evar("x")), "(let x = x in x)", {"x"}),
    (S.D0Epair(S.D0Eint(2), S.D0Ebtf(True)), "(pair 2 true)", set()),
    (S.D0Epfst(S.D0Evar("p")), "(fst p)", {"p"}),
    (S.D0Epsnd(S.D0Evar("p")), "(snd p)", {"p"}),
    (S.D0Efix("f", "n", S.D0Eapp(S.D0Evar("f"), S.D0Evar("m"))),
     "(fix f(n). (f m))", {"f", "n", "m"}),
]


class SourcePrintingAndNamesTests(unittest.TestCase):
    def test_examples_cover_every_constructor(self):
        self.assertEqual({type(e) for e, _, _ in EVERY_FORM},
                         set(S.D0E000.__subclasses__()))

    def test_printed_forms(self):
        for dexp, text, _ in EVERY_FORM:
            with self.subTest(text):
                self.assertEqual(S.show_source(dexp), text)

    def test_all_names_include_unused_binders(self):
        for dexp, text, names in EVERY_FORM:
            with self.subTest(text):
                self.assertEqual(S.source_names(dexp), names)

    def test_nested_printing(self):
        dexp = S.D0Elet("x", S.D0Eint(3),
                        S.D0Eapp(S.D0Elam("y", S.D0Eop2("+", S.D0Evar("x"),
                                                        S.D0Evar("y"))),
                                 S.D0Eint(4)))
        self.assertEqual(S.show_source(dexp),
                         "(let x = 3 in ((lam y. (x + y)) 4))")


if __name__ == "__main__":
    unittest.main()
