"""Controller source routes through HTTP, with a fake backend.

No browser or real interpreter is involved.
"""
import ast
import io
from pathlib import Path

import pytest

from lambda_web import MAX_REQUEST_BYTES, create_app
from lambda_web.controller import examples
from lambda_web.model import MAX_SOURCE_BYTES
from tests.fakes import FakeBackend
from tests.programs import ADD_42


@pytest.fixture
def client():
    return create_app(backend=FakeBackend()).test_client()


def body(resp):
    data = resp.get_json()
    return data["state"], data["error"]


def upload(client, data: bytes, name: str = "prog.txt"):
    return client.post("/api/source/upload",
                       data={"file": (io.BytesIO(data), name)},
                       content_type="multipart/form-data")


# --- initial state ----------------------------------------------------

def test_initial_state_has_no_source_and_disabled_actions(client):
    resp = client.get("/api/state")
    state, error = body(resp)
    assert resp.status_code == 200 and error is None
    assert state["source"] is None and state["draft"] is None
    assert [a["id"] for a in state["actions"]] == \
        ["lint", "interpret", "typecheck", "compile", "execute"]
    assert not any(a["enabled"] for a in state["actions"])


# --- canned examples (F1) ----------------------------------------------

@pytest.mark.parametrize("key, title", [("factorial", "Factorial"),
                                        ("fibonacci", "Fibonacci")])
def test_canned_example_loads_as_revision(client, key, title):
    state, _ = body(client.post(f"/api/source/canned/{key}"))
    assert (state["source"]["name"], state["source"]["origin"],
            state["source"]["revision"]) == (title, "canned", 1)
    assert state["source"]["text"] == examples.get(key).text


def test_unknown_example_is_404_and_state_unchanged(client):
    client.post("/api/source/canned/factorial")
    resp = client.post("/api/source/canned/..%2F..%2Fetc%2Fpasswd")
    state, error = body(resp)
    assert resp.status_code == 404 and error["kind"] == "request"
    assert state["source"]["name"] == "Factorial"


@pytest.mark.parametrize("method, url, status", [
    ("post", "/api/nosuch", 404),
    ("get", "/api/source/apply", 405),
])
def test_unknown_api_route_answers_in_json(client, method, url, status):
    resp = getattr(client, method)(url)
    assert resp.status_code == status and body(resp)[1]["kind"] == "request"


# --- upload (F1, F3) ----------------------------------------------------

def test_upload_loads_file(client):
    state, _ = body(upload(client, ADD_42.encode(), "add.txt"))
    assert (state["source"]["name"], state["source"]["origin"],
            state["source"]["text"]) == ("add.txt", "upload", ADD_42)


def test_upload_without_file_is_400(client):
    resp = client.post("/api/source/upload", data={},
                       content_type="multipart/form-data")
    assert resp.status_code == 400


@pytest.mark.parametrize("data, status", [
    (b"\xff\xfe bad", 422),
    (b"   \n", 422),
    (b"x" * (MAX_SOURCE_BYTES + 1), 422),
    (b"x" * (MAX_REQUEST_BYTES + 1), 413),
], ids=["invalid-utf8", "whitespace", "over-64KiB", "over-request-cap"])
def test_rejected_upload_keeps_previous_source(client, data, status):
    client.post("/api/source/canned/factorial")
    resp = upload(client, data)
    state, error = body(resp)
    assert resp.status_code == status and error["kind"] == "validation"
    assert (state["source"]["name"], state["source"]["revision"]) == \
        ("Factorial", 1)


# --- manual input and editing (F1, F2, Test 4) -------------------------

def test_manual_input_without_upload(client):
    state, _ = body(client.post("/api/source/manual"))
    assert state["draft"] == "" and state["source"] is None
    client.post("/api/source/edit", json={"text": ADD_42})
    state, _ = body(client.post("/api/source/apply", json={"text": ADD_42}))
    assert (state["source"]["name"], state["source"]["text"],
            state["source"]["revision"]) == ("Manual input", ADD_42, 1)
    assert state["draft"] is None


def test_draft_blocks_source_replacement_with_409(client):
    client.post("/api/source/canned/factorial")
    client.post("/api/source/edit", json={"text": ADD_42})
    resp = client.post("/api/source/canned/fibonacci")
    state, error = body(resp)
    assert resp.status_code == 409 and error["kind"] == "state"
    assert "Apply or discard" in error["message"]
    assert (state["source"]["name"], state["draft"]) == ("Factorial", ADD_42)


def test_invalid_apply_keeps_draft_and_source(client):
    client.post("/api/source/canned/factorial")
    resp = client.post("/api/source/apply", json={"text": "  "})
    state, error = body(resp)
    assert resp.status_code == 422 and error["kind"] == "validation"
    assert state["draft"] == "  " and state["source"]["revision"] == 1


@pytest.mark.parametrize("route, payload", [
    ("/api/source/edit", None),
    ("/api/source/apply", {"text": 5}),
], ids=["edit-no-body", "apply-non-string"])
def test_text_routes_require_text_field(client, route, payload):
    resp = client.post(route, json=payload) if payload is not None \
        else client.post(route)
    assert resp.status_code == 400 and body(resp)[1]["kind"] == "request"


def test_html_like_source_passes_through_unchanged(client):
    text = '# <script>alert("x")</script> & <b>\nD0Eint(1)'
    state, _ = body(client.post("/api/source/apply", json={"text": text}))
    assert state["source"]["text"] == text


# --- architectural boundary --------------------------------------------

def test_controller_does_not_import_backend_implementation():
    forbidden = {"lambda_web.backend.lambda1", "lambda_web.backend.reader",
                 "lambda_web.backend.lambda_backend"}
    controller_dir = Path(__file__).parent.parent / "lambda_web" / "controller"
    for path in controller_dir.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert node.module not in forbidden, \
                    f"{path.name} imports {node.module}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in forbidden, \
                        f"{path.name} imports {alias.name}"
