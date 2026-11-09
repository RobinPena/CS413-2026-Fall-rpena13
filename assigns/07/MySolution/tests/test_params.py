"""Method parameter rules that apply to every method (RPC.md section 3)."""
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
