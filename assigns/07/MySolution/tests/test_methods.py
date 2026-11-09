"""Successful results of the service's methods (RPC.md section 3)."""
from MySolution.tests.support import RpcTestCase


class HealthTests(RpcTestCase):
    def test_health_result_and_id(self):
        for request_id in ("health-1", 0, ""):
            with self.subTest(request_id=request_id):
                result = self.assert_result(self.call("service.health", {}, request_id), request_id)
                self.assertEqual(result, {"status": "ok", "version": "1.0"})
