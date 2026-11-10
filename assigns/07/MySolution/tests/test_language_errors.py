"""LAMBDA syntax, type and runtime errors from the real LAMBDA3 (RPC.md section 4)."""
from MySolution.tests.support import RpcTestCase

SOURCE_METHODS = ("lambda.typecheck", "lambda.interpret", "lambda.compile")


def params_for(method: str, source: str) -> dict:
    return {"source": source, "target": "python"} if method == "lambda.compile" else {"source": source}


def recursion(depth: int) -> str:
    """A well-typed program that recurses depth LAMBDA calls deep."""
    return ("let f : sint -> sint = fix f(n: sint): sint => "
            f"if n == 0 then 0 else 1 + f(n - 1) in f({depth}) end")


class LanguageErrorTests(RpcTestCase):
    def assert_language_error(self, method: str, source: str, code: int) -> dict:
        error = self.assert_error(self.call(method, params_for(method, source), "e"), "e", code)
        return error["data"]

    def test_syntax_error_has_diagnostic_and_location(self):
        for method in SOURCE_METHODS:
            with self.subTest(method=method):
                data = self.assert_language_error(method, "if then", -32010)
                self.assertEqual(data, {"diagnostic": "Expected an expression", "line": 1, "column": 4})

    def test_syntax_error_location_counts_the_unchanged_source(self):
        data = self.assert_language_error("lambda.typecheck", "\n\n  if then", -32010)
        self.assertEqual((data["line"], data["column"]), (3, 6))

    def test_type_error(self):
        for method in SOURCE_METHODS:
            with self.subTest(method=method):
                data = self.assert_language_error(method, "(lam (x: sint) => x)(true)", -32011)
                self.assertEqual(data, {"diagnostic": "function application: expected sint, got bool"})

    def test_unbound_variable_is_a_type_error(self):
        for method in SOURCE_METHODS:
            with self.subTest(method=method):
                data = self.assert_language_error(method, "missing_name + 1", -32011)
                self.assertEqual(data, {"diagnostic": "unbound variable 'missing_name'"})

    def test_syntax_and_type_errors_have_distinct_codes(self):
        syntax = self.call("lambda.interpret", {"source": "1 +"}, 1)
        typing = self.call("lambda.interpret", {"source": "1 + true"}, 2)
        self.assertNotEqual(self.assert_error(syntax, 1, -32010)["code"],
                            self.assert_error(typing, 2, -32011)["code"])

    def test_runtime_errors(self):
        cases = {
            "1 / 0": "division by zero",
            "list_head(list_nil())": "list_head: nonempty list expected",
            "optn_get(optn_nil())": "optn_get: nonempty option expected",
            "a1sz_getat(a1sz_make_ncpy(2, 0), 5)": "a1sz_getat: index out of range",
            "a1sz_make_ncpy(0 - 1, 0)": "a1sz_make_ncpy: negative size",
        }
        for source, diagnostic in cases.items():
            with self.subTest(source=source):
                data = self.assert_language_error("lambda.interpret", source, -32013)
                self.assertEqual(data, {"diagnostic": diagnostic})

    def test_integer_too_long_to_format_is_a_runtime_error(self):
        # 2 squared 14 times is 2 ** 16384, which has 4,933 digits.
        source = "let sq : sint -> sint = lam (x: sint) => x * x in " + "sq(" * 14 + "2" + ")" * 14 + " end"
        data = self.assert_language_error("lambda.interpret", source, -32013)
        self.assertEqual(data, {"diagnostic": "an integer has more than 4,300 digits and cannot be formatted"})

    def test_recursion_limit_is_a_runtime_error(self):
        self.assert_result(self.call("lambda.interpret", {"source": recursion(100)}, 1), 1)
        data = self.assert_language_error("lambda.interpret", recursion(5000), -32013)
        self.assertEqual(data, {"diagnostic": "recursion too deep: Python's recursion limit was reached"})

    def test_too_deeply_nested_source_is_a_syntax_error(self):
        data = self.assert_language_error("lambda.typecheck", "(" * 3000 + "1" + ")" * 3000, -32010)
        self.assertEqual(data, {"diagnostic": "the program is nested too deeply to parse"})

    def test_too_deeply_nested_for_the_type_checker_is_a_type_error(self):
        # The parser reads a chain of + in a loop, but the type checker recurses.
        data = self.assert_language_error("lambda.typecheck", "1" + " + 1" * 2000, -32011)
        self.assertEqual(data, {"diagnostic": "the program is nested too deeply to type-check"})

    def test_overlong_integer_literal_is_a_syntax_error(self):
        data = self.assert_language_error("lambda.typecheck", "9" * 5000, -32010)
        self.assertEqual(data, {"diagnostic": "an integer literal has more than 4,300 digits"})

    def test_long_diagnostic_is_cut_to_1000_characters(self):
        name = "v" * 2000
        data = self.assert_language_error("lambda.typecheck", f"{name} + 1", -32011)
        self.assertEqual(len(data["diagnostic"]), 1000)
        self.assertEqual(data["diagnostic"], f"unbound variable '{name}"[:997] + "...")
