"""Method parameter rules and the source limit (RPC.md sections 3 and 5)."""
from MySolution.tests.support import ABSENT, RpcTestCase


class ParamsTests(RpcTestCase):
    def assert_invalid_params(self, params: object, data: dict) -> None:
        error = self.assert_error(self.call("service.health", params, "p"), "p", -32602)
        self.assertEqual(error["message"], "Invalid params")
        self.assertEqual(error["data"], data)

    def test_params_are_required(self):
        self.assert_invalid_params(ABSENT, {"param": None, "reason": "params_required"})

    def test_positional_params_are_rejected(self):
        for params in ([], ["x"]):
            with self.subTest(params=params):
                self.assert_invalid_params(params, {"param": None, "reason": "params_not_object"})

    def test_health_takes_no_members(self):
        self.assert_invalid_params({"verbose": True},
                                   {"param": None, "reason": "unexpected_param", "allowed": []})

    def test_health_accepts_empty_object(self):
        self.assert_result(self.call("service.health", {}, "p"), "p")


SOURCE_METHODS = ("lambda.typecheck", "lambda.interpret", "lambda.compile")


def with_target(method: str, params: dict) -> dict:
    """params plus a valid target for lambda.compile, so only source is at fault."""
    return {**params, "target": "python"} if method == "lambda.compile" else params


class SourceParamsTests(RpcTestCase):
    def assert_invalid(self, method: str, params: object, data: dict) -> None:
        error = self.assert_error(self.call(method, params, "s"), "s", -32602)
        self.assertEqual(error["data"], data)

    def test_params_rules_apply_to_source_methods(self):
        for method in SOURCE_METHODS:
            with self.subTest(method=method):
                self.assert_invalid(method, ABSENT, {"param": None, "reason": "params_required"})
                self.assert_invalid(method, ["1 + 2"], {"param": None, "reason": "params_not_object"})

    def test_unexpected_members_are_rejected(self):
        for method, allowed in (("lambda.typecheck", ["source"]), ("lambda.interpret", ["source"]),
                                ("lambda.compile", ["source", "target"])):
            with self.subTest(method=method):
                params = with_target(method, {"source": "1", "Source": "1"})
                self.assert_invalid(method, params,
                                    {"param": None, "reason": "unexpected_param", "allowed": allowed})

    def test_missing_source(self):
        for method in SOURCE_METHODS:
            with self.subTest(method=method):
                self.assert_invalid(method, with_target(method, {}), {"param": "source", "reason": "missing"})

    def test_source_must_be_a_string(self):
        for method in SOURCE_METHODS:
            for source in (42, None, True, ["1"], {"text": "1"}):
                with self.subTest(method=method, source=source):
                    self.assert_invalid(method, with_target(method, {"source": source}),
                                        {"param": "source", "reason": "wrong_type"})

    def test_unpaired_surrogate_is_invalid_text(self):
        answer = self.post_bytes(
            b'{"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "1 + \\ud800"}, "id": "s"}')
        error = self.assert_error(answer, "s", -32602)
        self.assertEqual(error["data"], {"param": "source", "reason": "invalid_text"})

    def test_blank_source(self):
        for method in SOURCE_METHODS:
            for source in ("", " ", "\n\t \r\n"):
                with self.subTest(method=method, source=source):
                    self.assert_invalid(method, with_target(method, {"source": source}),
                                        {"param": "source", "reason": "blank"})

    def test_source_is_checked_before_target(self):
        self.assert_invalid("lambda.compile", {"target": "cobol"}, {"param": "source", "reason": "missing"})
        self.assert_invalid("lambda.compile", {"source": " ", "target": 3},
                            {"param": "source", "reason": "blank"})


class TargetParamsTests(RpcTestCase):
    def assert_invalid_target(self, params: dict, data: dict) -> None:
        error = self.assert_error(self.call("lambda.compile", params, "t"), "t", -32602)
        self.assertEqual(error["data"], data)

    def test_missing_target(self):
        self.assert_invalid_target({"source": "1"}, {"param": "target", "reason": "missing"})

    def test_target_must_be_a_string(self):
        for target in (None, 1, ["python"]):
            with self.subTest(target=target):
                self.assert_invalid_target({"source": "1", "target": target},
                                           {"param": "target", "reason": "wrong_type"})

    def test_unsupported_targets(self):
        for target in ("Python", "js", "JavaScript", "", "python "):
            with self.subTest(target=target):
                self.assert_invalid_target({"source": "1", "target": target}, {
                    "param": "target", "reason": "unsupported_target", "allowed": ["python", "javascript"]})


class SourceLimitTests(RpcTestCase):
    LIMIT = 65_536

    def typecheck(self, source: str) -> tuple[int, object]:
        return self.call("lambda.typecheck", {"source": source}, "limit")

    def assert_too_large(self, source: str, limit: int) -> None:
        error = self.assert_error(self.typecheck(source), "limit", -32602)
        self.assertEqual(error["data"], {"param": "source", "reason": "too_large",
                                         "limit_bytes": limit, "size_bytes": len(source.encode("utf-8"))})

    def test_exactly_the_limit_is_accepted(self):
        source = "1" + " " * (self.LIMIT - 1)
        self.assertEqual(self.assert_result(self.typecheck(source), "limit"), {"type": "sint"})

    def test_one_byte_over_the_limit_is_rejected(self):
        self.assert_too_large("1" + " " * self.LIMIT, self.LIMIT)

    def test_bytes_are_counted_not_characters(self):
        # "é" is one character but two UTF-8 bytes.
        at_limit = "1 #" + "é" * ((self.LIMIT - 4) // 2) + " "
        self.assertEqual(len(at_limit.encode("utf-8")), self.LIMIT)
        self.assertEqual(self.assert_result(self.typecheck(at_limit), "limit"), {"type": "sint"})
        over = at_limit[:-1] + "é"
        self.assertLess(len(over), self.LIMIT)  # within the limit if characters were counted
        self.assert_too_large(over, self.LIMIT)

    def test_size_is_checked_before_blankness(self):
        self.assert_too_large(" " * (self.LIMIT + 1), self.LIMIT)


class ConfiguredSourceLimitTests(RpcTestCase):
    app_config = {"MAX_SOURCE_BYTES": 10}

    def test_limit_comes_from_the_app_config(self):
        self.assert_result(self.call("lambda.typecheck", {"source": "1234567890"}, 1), 1)
        error = self.assert_error(self.call("lambda.typecheck", {"source": "12345678901"}, 2), 2, -32602)
        self.assertEqual(error["data"], {"param": "source", "reason": "too_large",
                                         "limit_bytes": 10, "size_bytes": 11})
