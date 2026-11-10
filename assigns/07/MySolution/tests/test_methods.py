"""Successful results of the service's methods (RPC.md section 3).

Every lambda.* test here goes through the real spawned worker and the real
LAMBDA3; nothing is replaced by a test double.
"""
import json
import os
import subprocess
import sys
import tempfile

from MySolution.tests.support import FACTORIAL, FIB_26, SOLUTION_DIR, RpcTestCase

LAMBDA3_DIR = SOLUTION_DIR.parent / "LAMBDA3"


def library_program(name: str, body: str) -> str:
    """A source that declares a supplied library from mylib/ and then runs body."""
    declarations = (LAMBDA3_DIR / "mylib" / f"{name}.lam").read_text(encoding="utf-8")
    return f"let\n{declarations}\nin {body} end"


def direct_compile(sources: list[str]) -> list[dict[str, str]]:
    """{target: code} for each source, from LAMBDA3 called directly in a separate process."""
    script = (
        "import json, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import lambda3\n"
        "expressions = [lambda3.d0exp_parse_and_typecheck(s)[0] for s in json.load(sys.stdin)]\n"
        "json.dump([{'python': lambda3.d0exp_compile(e), 'javascript': lambda3.d0exp_compile_js(e)}\n"
        "           for e in expressions], sys.stdout)\n"
    )
    # -B: write no __pycache__ into LAMBDA3; -I: ignore the environment and this directory.
    completed = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(LAMBDA3_DIR)],
                               input=json.dumps(sources), capture_output=True, encoding="utf-8", check=True)
    return json.loads(completed.stdout)


class HealthTests(RpcTestCase):
    def test_health_result_and_id(self):
        for request_id in ("health-1", 0, ""):
            with self.subTest(request_id=request_id):
                result = self.assert_result(self.call("service.health", {}, request_id), request_id)
                self.assertEqual(result, {"status": "ok", "version": "1.0"})


class TypecheckTests(RpcTestCase):
    def test_formatted_types(self):
        cases = {
            "20 + 22": "sint",
            "1 < 2": "bool",
            "(1, true)": "(sint, bool)",
            "list_cons(1, list_cons(2, list_nil()))": "List[sint]",
            "lam (x: sint) => x * 2": "sint -> sint",
            "lam (x) => x": "?t0 -> ?t0",
            FACTORIAL: "sint",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                result = self.assert_result(self.call("lambda.typecheck", {"source": source}, "t"), "t")
                self.assertEqual(result, {"type": expected})

    def test_typecheck_does_not_evaluate(self):
        # Evaluating either program would fail (division by zero) or time out.
        for source in ("1 / 0", FIB_26):
            with self.subTest(source=source[:20]):
                result = self.assert_result(self.call("lambda.typecheck", {"source": source}, 7), 7)
                self.assertEqual(result, {"type": "sint"})


class InterpretTests(RpcTestCase):
    def interpret(self, source: str) -> dict:
        return self.assert_result(self.call("lambda.interpret", {"source": source}, "i"), "i")

    def test_arithmetic(self):
        self.assertEqual(self.interpret("20 + 22"), {"type": "sint", "value": "42"})
        self.assertEqual(self.interpret("(7 - 10) * 4 / 2"), {"type": "sint", "value": "-6"})

    def test_factorial(self):
        self.assertEqual(self.interpret(FACTORIAL), {"type": "sint", "value": "720"})

    def test_tuple(self):
        self.assertEqual(self.interpret("(1, true)"), {"type": "(sint, bool)", "value": "(1, true)"})

    def test_list(self):
        self.assertEqual(self.interpret("list_cons(1, list_cons(2, list_nil()))"),
                         {"type": "List[sint]", "value": "[1, 2]"})

    def test_array_and_option(self):
        self.assertEqual(self.interpret("a1sz_make_ncpy(3, 7)"), {"type": "A1sz[sint]", "value": "[7, 7, 7]"})
        self.assertEqual(self.interpret("optn_cons(5)"), {"type": "Optn[sint]", "value": "optn_cons(5)"})

    def test_function_values_are_formatted_without_internals(self):
        cases = {
            "let f : sint -> sint = lam (x: sint) => x in f end": "<lam>",
            "fix g(n: sint): sint => n": "<fix>",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(self.interpret(source), {"type": "sint -> sint", "value": expected})

    def test_print_output_is_discarded(self):
        # The worker inherits the server's file descriptor 1, so capture it.
        with tempfile.TemporaryFile() as captured:
            saved = os.dup(1)
            os.dup2(captured.fileno(), 1)
            try:
                result = self.interpret("print(424242)")
            finally:
                os.dup2(saved, 1)
                os.close(saved)
            captured.seek(0)
            self.assertNotIn(b"424242", captured.read())
        self.assertEqual(result, {"type": "unit", "value": "()"})

    def test_source_is_used_unchanged(self):
        self.assertEqual(self.interpret("\n  20 + 22  # comment\n"), {"type": "sint", "value": "42"})

    def test_supplied_list_library(self):
        source = library_program("list", "list_length(list_range(0, 3))")
        self.assertEqual(self.interpret(source), {"type": "sint", "value": "3"})


class CompileTests(RpcTestCase):
    def compile(self, source: str, target: str, request_id: object = "c") -> dict:
        params = {"source": source, "target": target}
        return self.assert_result(self.call("lambda.compile", params, request_id), request_id)

    def test_code_is_the_unchanged_compiler_output(self):
        sources = ["1 + 2", FACTORIAL, "(1, list_cons(true, list_nil()))",
                   library_program("list", "list_length(list_range(0, 3))")]
        for source, direct in zip(sources, direct_compile(sources), strict=True):
            for target in ("python", "javascript"):
                with self.subTest(source=source[:30], target=target):
                    self.assertEqual(self.compile(source, target), {"target": target, "code": direct[target]})

    def test_both_targets_return_nonempty_programs(self):
        for target, entry in (("python", "def _lambda_main():"), ("javascript", "function _lambda_main() {")):
            with self.subTest(target=target):
                result = self.compile(FACTORIAL, target)
                self.assertEqual(result["target"], target)
                self.assertIn(entry, result["code"])

    def test_compile_does_not_evaluate(self):
        # 1 / 0 would fail and fib(26) would time out if the service ran them.
        for source in ("1 / 0", FIB_26):
            with self.subTest(source=source[:20]):
                self.assertTrue(self.compile(source, "python")["code"])

    def test_output_larger_than_a_pipe_buffer(self):
        source = "let\n" + "".join(f"x{i} = {i}\n" for i in range(3000)) + "in x0 end"
        code = self.compile(source, "javascript")["code"]
        self.assertGreater(len(code.encode("utf-8")), 65_536)
        self.assertTrue(code.endswith("const _lambda_result = _lambda_main();\n"))
