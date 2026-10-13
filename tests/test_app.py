"""Route contract: / and the health paths answer 200, unauthenticated, touching nothing."""

import json

import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.factory import HEALTH_PATHS, SECURITY_HEADERS, create_app


def test_root_returns_200_and_never_a_redirect(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert response.json() == {"service": "holly", "status": "ok"}


@pytest.mark.parametrize("path", HEALTH_PATHS)
def test_health_paths_answer_ok(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert response.text == "ok"


@pytest.mark.parametrize("path", ["/", *HEALTH_PATHS])
def test_probe_paths_answer_head(client: TestClient, path: str) -> None:
    assert client.head(path).status_code == 200


@pytest.mark.parametrize("path", HEALTH_PATHS)
def test_health_paths_refuse_writes(client: TestClient, path: str) -> None:
    assert client.post(path).status_code == 405


@pytest.mark.parametrize("path", ["/", "/healthz", "/status", "/not-a-route"])
def test_every_response_carries_the_security_headers(client: TestClient, path: str) -> None:
    response = client.get(path)
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_interactive_docs_are_not_exposed(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


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
