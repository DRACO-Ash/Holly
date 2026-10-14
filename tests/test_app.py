"""Route contract: / and the health paths answer 200, unauthenticated, touching nothing.

Every expected value here is a literal on purpose. The contract comes from CLAUDE.md, the
platform and security-hardening, not from the code under test, so loosening a policy or
dropping a path fails here first and can only pass through a deliberate, reviewed test edit.
"""

import json

import httpx2 as httpx
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app import __version__
from app.factory import create_app

PROBE_PATHS = ["/healthz", "/health", "/readyz", "/livez", "/ping"]

EXPECTED_HEADERS = {
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "cache-control": "no-store",
}


def assert_security_headers(response: httpx.Response) -> None:
    for name, value in EXPECTED_HEADERS.items():
        assert response.headers.get(name) == value, name


def test_root_returns_200_and_never_a_redirect(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert response.json() == {"service": "holly", "status": "ok"}


@pytest.mark.parametrize("path", PROBE_PATHS)
def test_health_paths_answer_ok(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert response.text == "ok"


@pytest.mark.parametrize("path", ["/", *PROBE_PATHS])
def test_probe_paths_answer_head(client: TestClient, path: str) -> None:
    assert client.head(path).status_code == 200


@pytest.mark.parametrize("path", PROBE_PATHS)
def test_health_paths_refuse_writes(client: TestClient, path: str) -> None:
    assert client.post(path).status_code == 405


@pytest.mark.parametrize(
    ("method", "path", "status"),
    [
        ("GET", "/", 200),
        ("GET", "/healthz", 200),
        ("GET", "/status", 200),
        ("GET", "/not-a-route", 404),
        ("POST", "/healthz", 405),
    ],
)
def test_security_headers_on_every_status(
    client: TestClient, method: str, path: str, status: int
) -> None:
    response = client.request(method, path)
    assert response.status_code == status
    assert_security_headers(response)


def test_a_server_error_is_generic_and_keeps_the_security_headers() -> None:
    app = create_app()

    def probe_only_failure() -> None:
        msg = "probe-only failure detail"
        raise RuntimeError(msg)

    app.add_api_route("/fail", probe_only_failure, methods=["GET"])
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/fail")
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert_security_headers(response)


def test_a_trailing_slash_is_not_redirected(client: TestClient) -> None:
    response = client.get("/healthz/", follow_redirects=False, headers={"host": "evil.example"})
    assert response.status_code == 404
    assert "location" not in response.headers


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_interactive_docs_are_not_exposed(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_route_inventory_is_exactly_the_reviewed_public_set() -> None:
    """Trip-wire: a new route fails here until it is reviewed. A route that costs money or
    changes state lands with the constant-time token gate in the same change (SECURITY.md)."""
    routes = create_app().routes
    assert all(isinstance(route, APIRoute) for route in routes)
    inventory = {
        route.path: sorted(route.methods or ()) for route in routes if isinstance(route, APIRoute)
    }
    assert inventory == {
        "/": ["GET", "HEAD"],
        "/healthz": ["GET", "HEAD"],
        "/health": ["GET", "HEAD"],
        "/readyz": ["GET", "HEAD"],
        "/livez": ["GET", "HEAD"],
        "/ping": ["GET", "HEAD"],
        "/status": ["GET"],
    }


def test_status_reports_presence_and_length_never_the_value(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORT", "9090")
    response = client.get("/status")
    assert response.json() == {
        "service": "holly",
        "version": __version__,
        "config": {"PORT": {"set": True, "length": 4}},
        "storage": {"configured": False},
    }
    assert "9090" not in response.text


def test_status_reports_an_unset_input(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PORT", raising=False)
    assert client.get("/status").json()["config"]["PORT"] == {"set": False, "length": 0}


def test_boot_and_shutdown_each_log_one_json_line(capsys: pytest.CaptureFixture[str]) -> None:
    with TestClient(create_app()):
        pass
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines == [
        {"event": "boot", "service": "holly", "version": __version__, "storage": "none"},
        {"event": "shutdown", "service": "holly", "version": __version__},
    ]
