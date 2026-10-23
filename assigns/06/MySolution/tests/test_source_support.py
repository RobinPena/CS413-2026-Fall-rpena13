"""Supplied AST import, source printing, names, validation, substitution and data."""
import copy
import subprocess
import sys
import types
import unittest
from pathlib import Path

import MySolution
from MySolution import source_support as S
from MySolution.results import UnsupportedSourceError

ASSIGN06 = Path(__file__).resolve().parents[2]


class EnvironmentTests(unittest.TestCase):
    def test_python_is_at_least_3_12(self):
        self.assertGreaterEqual(sys.version_info[:2], (3, 12))

    def test_package_is_the_assign06_solution(self):
        self.assertEqual(Path(MySolution.__file__).resolve().parent,
                         ASSIGN06 / "MySolution")

    def test_documented_test_command_works_from_assigns_06(self):
        # The README command, limited to one small file so it cannot recurse.
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "MySolution/tests",
             "-t", ".", "-p", "test_names.py"],
            cwd=ASSIGN06, capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertRegex(completed.stderr, r"Ran [1-9]\d* tests? in .*\n\nOK")


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


def bad(op="/"):
    return S.D0Eop2(op, S.D0Eint(1), S.D0Eint(1))


class ValidationTests(unittest.TestCase):
    def test_every_supported_form_and_operator_is_accepted(self):
        for dexp, text, _ in EVERY_FORM:
            with self.subTest(text):
                S.validate_source(dexp)
        for name in sorted(S.BINARY_OPERATORS):
            with self.subTest(name):
                S.validate_source(S.D0Eop2(name, S.D0Eint(1), S.D0Eint(2)))
        self.assertEqual(S.BINARY_OPERATORS, {"+", "-", "*", "<", "<=", ">", ">=",
                                              "==", "!=", "and", "or"})

    def test_rejected_forms_and_where_they_were_found(self):
        T = S.D0Ebtf(True)
        cases = [
            (S.D0Eint(-1), "negative literal -1 (at the root)"),
            (bad("/"), "unsupported binary operator '/' (division is not in the "
                       "language) (at the root)"),
            (bad("%"), "unsupported binary operator '%' (at the root)"),
            (bad("&&"), "unsupported binary operator '&&' (at the root)"),
            (S.D0Eop1("+1", S.D0Eint(1)), "unsupported unary operator '+1' (at the root)"),
            (S.D0Eop1("-1", S.D0Eint(1)), "unsupported unary operator '-1' (at the root)"),
            # Never-selected branch.
            (S.D0Eif0(T, S.D0Eint(1), S.D0Eint(-3)),
             "negative literal -3 (at if: else branch)"),
            # Function body that is never applied.
            (S.D0Elam("x", bad()), "unsupported binary operator '/' (division is not "
                                   "in the language) (at lam x: body)"),
            (S.D0Efix("f", "n", S.D0Eif0(T, S.D0Eint(0), S.D0Eint(-2))),
             "negative literal -2 (at fix f(n): body > if: else branch)"),
            # Short-circuited right operand.
            (S.D0Eop2("or", T, S.D0Eop2("==", bad("%"), S.D0Eint(0))),
             "unsupported binary operator '%' (at 'or': right operand > "
             "'==': left operand)"),
            (S.D0Elet("x", S.D0Eint(1), S.D0Epair(S.D0Eint(0), S.D0Eint(-5))),
             "negative literal -5 (at let x: body > pair: second)"),
        ]
        for dexp, message in cases:
            with self.subTest(message):
                with self.assertRaises(UnsupportedSourceError) as caught:
                    S.validate_source(dexp)
                self.assertEqual(str(caught.exception), message)


class SourceSubstitutionTests(unittest.TestCase):
    def test_capture_scope_and_fix_binders(self):
        x, y = S.D0Evar("x"), S.D0Evar("y")
        cases = [
            (S.D0Elam("y", S.D0Eop2("+", x, y)), "x", y, "(lam y_1. (y + y_1))"),
            (S.D0Elet("x", x, S.D0Eop2("+", x, y)), "x", S.D0Eint(3),
             "(let x = 3 in (x + y))"),
            (S.D0Efix("f", "f", S.D0Eop2("+", x, S.D0Evar("f"))), "x", S.D0Evar("f"),
             "(fix f_2(f_1). (f + f_1))"),
            (S.D0Efix("f", "n", x), "f", S.D0Eint(1), "(fix f(n). x)"),
        ]
        for dexp, name, replacement, expected in cases:
            with self.subTest(expected):
                before = copy.deepcopy(dexp)
                result = S.source_substitute(dexp, name, replacement)
                self.assertEqual(S.show_source(result), expected)
                self.assertEqual(dexp, before)


class SourceDataTests(unittest.TestCase):
    def test_data_values(self):
        self.assertEqual(S.source_data(S.D0Eint(3)), 3)
        self.assertIs(S.source_data(S.D0Ebtf(False)), False)
        nested = S.D0Epair(S.D0Epair(S.D0Eint(2), S.D0Ebtf(True)), S.D0Eint(3))
        self.assertEqual(S.source_data(nested), ((2, True), 3))
        with self.assertRaises(TypeError):
            S.source_data(S.D0Elam("x", S.D0Evar("x")))


if __name__ == "__main__":
    unittest.main()
