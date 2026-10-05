"""View script: static safety and boundary checks on app.js.

There is no JavaScript runtime in the test environment, so behavior is
verified by the browser smoke test recorded in TESTING.md.
"""
import re
from pathlib import Path

import pytest

from lambda_web import create_app
from tests.fakes import FakeBackend
from tests.test_view_page import Page

SCRIPT = (Path(__file__).parent.parent / "lambda_web" / "view" / "static"
          / "app.js").read_text(encoding="utf-8")


@pytest.fixture
def client():
    return create_app(backend=FakeBackend()).test_client()


def test_script_is_served(client):
    resp = client.get("/static/app.js")
    assert resp.status_code == 200 and "javascript" in resp.mimetype


@pytest.mark.parametrize("sink", ["innerHTML", "outerHTML",
                                  "insertAdjacentHTML", "document.write",
                                  "eval(", "new Function"])
def test_script_never_inserts_markup_or_runs_strings(sink):
    assert sink not in SCRIPT


def test_script_only_talks_to_the_local_api():
    urls = re.findall(r'[`"\'](/[^`"\'\s]*)', SCRIPT)
    assert urls and all(u.startswith("/api/") for u in urls), urls
    assert "http://" not in SCRIPT and "https://" not in SCRIPT


@pytest.mark.parametrize("word", ["D0E", "D0V", "fvset", "lambda1",
                                  "free variable"])
def test_script_has_no_language_logic(word):
    assert word.lower() not in SCRIPT.lower()


def test_every_element_the_script_uses_exists_on_the_page(client):
    page = Page(client.get("/").get_data(as_text=True))
    ids = {e["attrs"]["id"] for e in page.with_attr("id")}
    used = set(re.findall(r'byId\("([^"]+)"\)', SCRIPT))
    assert used and used <= ids
    for action in ["lint", "interpret", "typecheck", "compile", "execute"]:
        assert {f"action-{action}", f"reason-{action}"} <= ids
    assert page.with_attr("data-load") and page.with_attr("data-action")
