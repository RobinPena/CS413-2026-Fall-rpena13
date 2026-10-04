"""Smoke tests: the app builds and the supplied interpreter imports."""
from lambda_web import create_app


def test_app_serves_index():
    client = create_app().test_client()
    resp = client.get("/")
    assert resp.status_code == 200


def test_lambda1_importable():
    from lambda_web.backend import lambda1
    assert callable(lambda1.d0exp_evaluate)
    assert callable(lambda1.d0exp_fvset)
