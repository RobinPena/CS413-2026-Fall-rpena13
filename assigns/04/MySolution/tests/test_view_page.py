"""View structure: the page served at / has the required controls, in
order, with labels. Parsed with Python's html.parser; no browser."""
from html.parser import HTMLParser

import pytest

from lambda_web import create_app
from lambda_web.controller import examples
from tests.fakes import FakeBackend

VOID = {"input", "meta", "link", "br", "img"}


class Page(HTMLParser):
    """Collects every element with its attributes and text content."""

    def __init__(self, html: str):
        super().__init__()
        self.elements: list[dict] = []
        self._open: list[dict] = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        element = {"tag": tag, "attrs": dict(attrs), "text": ""}
        self.elements.append(element)
        if tag not in VOID:
            self._open.append(element)

    def handle_endtag(self, tag):
        for i in range(len(self._open) - 1, -1, -1):
            if self._open[i]["tag"] == tag:
                del self._open[i:]
                break

    def handle_data(self, data):
        for element in self._open:
            element["text"] += data

    def by_id(self, id_: str) -> dict:
        return next(e for e in self.elements if e["attrs"].get("id") == id_)

    def with_attr(self, name: str) -> list[dict]:
        return [e for e in self.elements if name in e["attrs"]]


def text(element: dict) -> str:
    return " ".join(element["text"].split())


@pytest.fixture
def page() -> Page:
    resp = create_app(backend=FakeBackend()).test_client().get("/")
    assert resp.status_code == 200 and resp.mimetype == "text/html"
    return Page(resp.get_data(as_text=True))


def test_load_source_menu_has_required_options(page):
    labels = [text(e) for e in page.with_attr("data-load")]
    assert labels == ["Choose File…", "Manual input",
                      "Factorial (canned)", "Fibonacci (canned)"]
    assert page.by_id("file-input")["attrs"]["type"] == "file"


def test_action_buttons_in_required_order(page):
    buttons = page.with_attr("data-action")
    assert [text(b) for b in buttons] == \
        ["Lint", "Interpret", "Type-check", "Compile", "Execute"]
    for b in buttons:
        assert "disabled" in b["attrs"]
        page.by_id(b["attrs"]["aria-describedby"])


def test_editor_and_apply_discard_controls(page):
    assert page.by_id("editor")["tag"] == "textarea"
    assert any(e["tag"] == "label" and e["attrs"].get("for") == "editor"
               for e in page.elements)
    assert text(page.by_id("apply")) == "Apply changes"
    assert text(page.by_id("discard")) == "Discard changes"


def test_status_and_error_are_announced(page):
    status = page.by_id("status")["attrs"]
    assert status["role"] == "status" and status["aria-live"] == "polite"
    assert page.by_id("error")["attrs"]["role"] == "alert"
    page.by_id("results")


def test_every_control_is_labelled(page):
    labelled = {e["attrs"]["for"] for e in page.elements
                if e["tag"] == "label" and "for" in e["attrs"]}
    for e in page.elements:
        if e["tag"] in ("input", "textarea", "select"):
            assert e["attrs"]["id"] in labelled or "aria-label" in e["attrs"]
        if e["tag"] == "button":
            assert e["attrs"].get("type") == "button" and text(e)


def test_ids_are_unique(page):
    ids = [e["attrs"]["id"] for e in page.with_attr("id")]
    assert len(ids) == len(set(ids))


def test_page_loads_only_local_resources(page):
    for e in page.elements:
        url = e["attrs"].get("src") or (
            e["attrs"].get("href") if e["tag"] == "link" else None)
        if url:
            assert url.startswith("/static/"), url


def test_template_escapes_text(monkeypatch):
    monkeypatch.setattr(examples, "catalog",
                        lambda: [("evil", '<b onclick="x()">Evil</b>')])
    html = create_app(backend=FakeBackend()).test_client() \
        .get("/").get_data(as_text=True)
    assert "&lt;b onclick=" in html and "<b onclick=" not in html
