"""Route contract: / and the health paths answer 200, unauthenticated, touching nothing; every
other route is in a reviewed inventory; every response but a CORS preflight carries the
security headers.

Every expected value here is a literal on purpose. The contract comes from CLAUDE.md, the
platform and security-hardening, not from the code under test, so loosening a policy or
dropping a path fails here first and can only pass through a deliberate, reviewed test edit.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import httpx2 as httpx
import pytest
from fastapi.dependencies.models import Dependant
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from app import __version__, factory
from app.config import get_settings
from app.core.body_limit import LARGE_BODY_ROUTES
from app.core.rate_limit import GLOBAL_LIMIT
from app.dependencies import get_current_user
from app.factory import create_app

PROBE_PATHS = ["/healthz", "/health", "/readyz", "/livez", "/ping"]

API_CSP = "default-src 'none'; frame-ancestors 'none'"
DASHBOARD_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)
COMMON_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "cache-control": "no-store",
}

DASHBOARD_PAGE = "<!doctype html><title>Holly</title><div id=root></div>"


def assert_security_headers(response: httpx.Response, csp: str = API_CSP) -> None:
    for name, value in {**COMMON_HEADERS, "content-security-policy": csp}.items():
        assert response.headers.get(name) == value, name


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """Holly as a plain source checkout runs it: no dashboard has been built."""
    with TestClient(create_app(static_dir=tmp_path / "not-built")) as test_client:
        yield test_client


@pytest.fixture
def dashboard_client(tmp_path: Path) -> Iterator[TestClient]:
    """Holly as the container runs it: the built dashboard sits in the static directory."""
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text(DASHBOARD_PAGE, encoding="utf-8")
    (static / "assets" / "app.js").write_text("export const ready = true;\n", encoding="utf-8")
    with TestClient(create_app(static_dir=static)) as test_client:
        yield test_client


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
        ("GET", "/api/v1/notifications", 401),
        ("GET", "/not-a-route", 404),
        ("POST", "/healthz", 405),
        ("POST", "/api/v1/auth/login", 422),
    ],
)
def test_security_headers_on_every_status(
    client: TestClient, method: str, path: str, status: int
) -> None:
    response = client.request(method, path)
    assert response.status_code == status
    assert_security_headers(response)


def test_every_response_carries_a_request_id(client: TestClient) -> None:
    assert client.get("/healthz").headers["x-request-id"]
    assert client.get("/healthz", headers={"X-Request-ID": "trace-42"}).headers["x-request-id"] == (
        "trace-42"
    )


PREFLIGHT = {"Origin": "https://ops.example", "Access-Control-Request-Method": "POST"}


def test_a_preflight_is_refused_while_no_origin_is_allowed(client: TestClient) -> None:
    headers = {**PREFLIGHT, "Access-Control-Request-Headers": "X-Probe-<b>"}
    response = client.options("/api/v1/auth/login", headers=headers)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
    assert "content-security-policy" not in response.headers
    # A fixed answer: nothing the client sent comes back.
    assert response.content.startswith(b"Disallowed CORS ")
    assert b"X-Probe" not in response.content
    assert all("x-probe" not in value.lower() for value in response.headers.values())


def test_cors_sits_outermost_for_an_allowed_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ALLOWED_ORIGINS", '["https://ops.example"]')
    get_settings.cache_clear()
    with TestClient(create_app(static_dir=tmp_path / "not-built")) as cors_client:
        preflight = cors_client.options("/api/v1/auth/login", headers=PREFLIGHT)
        refused = cors_client.get(
            "/api/v1/notifications", headers={"Origin": "https://ops.example"}
        )
    # The preflight is answered before the inner layers; a refusal from inside carries both
    # the CORS headers and the security headers.
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "https://ops.example"
    assert "x-request-id" not in preflight.headers
    assert "content-security-policy" not in preflight.headers
    assert preflight.content == b"OK"
    assert refused.status_code == 401
    assert refused.headers["access-control-allow-origin"] == "https://ops.example"
    assert refused.headers["x-request-id"]
    assert_security_headers(refused)


def test_an_allowed_origin_may_send_holly_s_token_header_and_never_authorization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The dashboard sends its token in X-Holly-Token and never Authorization (ADR-013); the
    # preflight allows what it sends and nothing in place of it.
    monkeypatch.setenv("APP_ALLOWED_ORIGINS", '["https://ops.example"]')
    get_settings.cache_clear()
    with TestClient(create_app(static_dir=tmp_path / "not-built")) as cors_client:
        allowed, refused = (
            cors_client.options(
                "/api/v1/auth/me",
                headers={**PREFLIGHT, "Access-Control-Request-Headers": requested},
            )
            for requested in ("x-holly-token", "authorization")
        )
    assert allowed.status_code == 200
    listed = allowed.headers["access-control-allow-headers"].lower()
    assert "x-holly-token" in listed
    assert "authorization" not in listed
    # No credentials mode: Holly reads no cookie, and the platform's own would only ride along.
    assert "access-control-allow-credentials" not in allowed.headers
    assert refused.status_code == 400
    assert refused.content == b"Disallowed CORS headers"


def test_a_server_error_is_generic_and_keeps_the_security_headers(tmp_path: Path) -> None:
    app = create_app(static_dir=tmp_path / "not-built")

    def probe_only_failure() -> None:
        msg = "probe-only failure detail"
        raise RuntimeError(msg)

    app.add_api_route("/fail", probe_only_failure, methods=["GET"])
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/fail", headers={"X-Request-ID": "trace-500"})
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert_security_headers(response)
    assert response.headers["x-request-id"] == "trace-500"


def test_a_server_error_before_the_request_id_is_set_still_answers_generically(
    tmp_path: Path,
) -> None:
    # A failure outside the request-id middleware reaches the handler with no id to echo.
    handler = create_app(static_dir=tmp_path / "not-built").exception_handlers[500]
    response = handler(Request({"type": "http", "headers": []}), RuntimeError("detail"))
    assert isinstance(response, Response)
    assert (response.status_code, response.body) == (500, b"Internal Server Error")
    assert "x-request-id" not in response.headers
    for name, value in {**COMMON_HEADERS, "content-security-policy": API_CSP}.items():
        assert response.headers.get(name) == value, name


def test_a_trailing_slash_is_not_redirected(client: TestClient) -> None:
    response = client.get("/healthz/", follow_redirects=False, headers={"host": "evil.example"})
    assert response.status_code == 404
    assert "location" not in response.headers


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_interactive_docs_are_not_exposed(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


class TestTheDashboard:
    def test_the_root_serves_the_built_page_under_the_dashboard_policy(
        self, dashboard_client: TestClient
    ) -> None:
        response = dashboard_client.get("/", follow_redirects=False)
        assert response.status_code == 200
        assert response.text == DASHBOARD_PAGE
        assert_security_headers(response, DASHBOARD_CSP)

    def test_the_root_still_answers_head_for_the_platform(
        self, dashboard_client: TestClient
    ) -> None:
        assert dashboard_client.head("/").status_code == 200

    def test_a_bookmarked_page_loads_the_app(self, dashboard_client: TestClient) -> None:
        response = dashboard_client.get("/notifications", headers={"Accept": "text/html"})
        assert response.status_code == 200
        assert response.text == DASHBOARD_PAGE

    def test_an_asset_is_served_under_the_strict_policy(self, dashboard_client: TestClient) -> None:
        response = dashboard_client.get("/assets/app.js")
        assert response.status_code == 200
        assert "export const ready" in response.text
        assert_security_headers(response)

    @pytest.mark.parametrize("path", ["/api/v1/not-a-route", "/assets/missing.js"])
    def test_an_unknown_path_is_a_404_not_the_page(
        self, dashboard_client: TestClient, path: str
    ) -> None:
        response = dashboard_client.get(path)
        assert response.status_code == 404
        assert DASHBOARD_PAGE not in response.text

    @pytest.mark.parametrize("path", PROBE_PATHS)
    def test_the_probes_are_unchanged(self, dashboard_client: TestClient, path: str) -> None:
        assert dashboard_client.get(path).text == "ok"


def _route_table() -> dict[str, list[str]]:
    table: dict[str, list[str]] = {}
    for context in iter_route_contexts(create_app(static_dir=Path("/nonexistent")).routes):
        assert context.path is not None
        table.setdefault(context.path, []).extend(sorted(context.methods or ()))
    return {path: sorted(methods) for path, methods in table.items()}


def test_route_inventory_is_exactly_the_reviewed_set() -> None:
    """Trip-wire: a new route fails here until it is reviewed (SECURITY.md)."""
    assert _route_table() == {
        "/": ["GET", "HEAD"],
        "/healthz": ["GET", "HEAD"],
        "/health": ["GET", "HEAD"],
        "/readyz": ["GET", "HEAD"],
        "/livez": ["GET", "HEAD"],
        "/ping": ["GET", "HEAD"],
        "/status": ["GET"],
        "/api/v1/health": ["GET"],
        "/api/v1/health/detailed": ["GET"],
        "/api/v1/auth/login": ["POST"],
        "/api/v1/auth/refresh": ["POST"],
        "/api/v1/auth/logout": ["POST"],
        "/api/v1/auth/me": ["GET"],
        "/api/v1/elsets": ["GET"],
        "/api/v1/elsets/{elset_id}": ["GET"],
        "/api/v1/elsets/ingest": ["POST"],
        "/api/v1/notifications": ["GET"],
        "/api/v1/notifications/{notification_id}": ["GET"],
        "/api/v1/notifications/ingest": ["POST"],
        "/api/v1/notifications/refresh": ["POST"],
        "/api/v1/maneuvers": ["GET"],
        "/api/v1/maneuvers/{maneuver_id}": ["GET"],
        "/api/v1/mattermost/messages": ["GET"],
        "/api/v1/procedures": ["GET", "POST"],
        "/api/v1/procedures/{procedure_id}": ["DELETE", "GET"],
        "/api/v1/procedures/{procedure_id}/download": ["GET"],
        "/api/v1/shift-log/dates": ["GET"],
        "/api/v1/shift-log/notes": ["GET", "POST"],
        "/api/v1/shift-log/notes/{note_id}": ["DELETE", "PATCH"],
        "/api/v1/shift-log/notes/{note_id}/repolish": ["POST"],
        "/api/v1/shift-log/summary": ["GET", "POST"],
        "/api/v1/shift-log/export": ["GET"],
        "/api/v1/event-timers": ["GET", "POST"],
        "/api/v1/event-timers/{timer_id}/acknowledge-pre-alert": ["POST"],
        "/api/v1/event-timers/{timer_id}/dismiss": ["POST"],
        "/api/v1/event-timers/{timer_id}": ["DELETE"],
        "/api/v1/assistant/feed": ["GET"],
        "/api/v1/assistant/evaluation/{notification_id}": ["GET"],
        "/api/v1/assistant/evaluate/{notification_id}": ["POST"],
        "/api/v1/audit": ["GET"],
    }


def _requires_sign_in(dependant: Dependant) -> bool:
    pending = [dependant]
    while pending:
        current = pending.pop()
        if current.call is get_current_user:
            return True
        pending.extend(current.dependencies)
    return False


def test_only_the_reviewed_routes_are_open_without_sign_in() -> None:
    """Trip-wire: every route outside this list must demand a valid access token."""
    public = set()
    for context in iter_route_contexts(create_app(static_dir=Path("/nonexistent")).routes):
        dependant: Any = context.dependant
        if not _requires_sign_in(dependant):
            public.add(context.path)
    assert public == {
        "/",
        "/healthz",
        "/health",
        "/readyz",
        "/livez",
        "/ping",
        "/status",
        "/api/v1/health",
        "/api/v1/health/detailed",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
    }


def test_status_reports_presence_and_length_never_the_value(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PORT", "9090")
    response = client.get("/status")
    assert response.json() == {
        "service": "holly",
        "version": __version__,
        "config": {
            "PORT": {"set": True, "length": 4},
            "APP_ENV": {"set": True, "length": 10},
            "STORAGE_MOUNT_PATH": {"set": False, "length": 0},
            "PROCEDURE_STORAGE_PATH": {
                "set": True,
                "length": len(str(tmp_path / "procedures")),
            },
        },
        "storage": {"procedures": "ready"},
    }
    assert "9090" not in response.text
    assert str(tmp_path) not in response.text


def test_status_reports_an_unset_input(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PORT", raising=False)
    assert client.get("/status").json()["config"]["PORT"] == {"set": False, "length": 0}


def _events(captured: str) -> list[dict[str, Any]]:
    lines = [json.loads(line) for line in captured.splitlines() if line.startswith("{")]
    return [line for line in lines if "event" in line]


def test_boot_and_shutdown_each_log_one_json_line(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    with TestClient(create_app(static_dir=tmp_path / "not-built")):
        pass
    assert _events(capsys.readouterr().out) == [
        {
            "event": "boot",
            "service": "holly",
            "request_id": "-",
            "version": __version__,
            "storage": str(tmp_path / "procedures"),
            "storage_writable": True,
            "background_refresh": False,
        },
        {"event": "shutdown", "service": "holly", "request_id": "-", "version": __version__},
    ]


def test_a_store_that_refuses_writes_stops_the_boot_with_the_errno(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, settings_env: Any
) -> None:
    blocker = tmp_path / "a-file"
    blocker.write_text("not a directory", encoding="utf-8")
    settings_env(PROCEDURE_STORAGE_PATH=str(blocker / "procedures"))
    with (
        pytest.raises(OSError, match="Not a directory"),
        TestClient(create_app(static_dir=tmp_path / "not-built")),
    ):
        pass
    [boot] = _events(capsys.readouterr().out)
    assert boot["event"] == "boot"
    assert boot["storage"] == str(blocker / "procedures")
    assert boot["storage_writable"] is False
    assert boot["errno"] == 20
    assert boot["error"] == "Not a directory"


def test_the_background_loops_start_with_the_app_and_stop_with_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, settings_env: Any
) -> None:
    settings_env(BACKGROUND_REFRESH_ENABLED="true")
    calls: list[Any] = []
    sentinel_tasks = ["loop"]

    def fake_start() -> list[str]:
        calls.append("start")
        return sentinel_tasks

    def fake_stop(tasks: list[str]) -> None:
        calls.append(("stop", tasks))

    monkeypatch.setattr(factory, "start_background_loops", fake_start)
    monkeypatch.setattr(factory, "stop_background_loops", AsyncMock(side_effect=fake_stop))
    with TestClient(create_app(static_dir=tmp_path / "not-built")):
        assert calls == ["start"]
    assert calls == ["start", ("stop", sentinel_tasks)]


class TestTheBodyCap:
    def test_a_declared_oversized_body_is_refused_before_it_is_read(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/v1/auth/login",
            content=b"{}",
            headers={"Content-Length": str(11 * 1024 * 1024 + 1)},
        )
        assert response.status_code == 413
        assert response.json() == {"detail": "Request body too large"}
        assert_security_headers(response)
        assert response.headers["x-request-id"]

    def test_a_streamed_oversized_body_is_cut_off(self, client: TestClient) -> None:
        chunk = b"x" * (1024 * 1024)

        def body() -> Iterator[bytes]:
            for _ in range(12):
                yield chunk

        response = client.post("/api/v1/auth/login", content=body())
        assert response.status_code == 413
        assert response.json() == {"detail": "Request body too large"}
        assert_security_headers(response)

    def test_a_body_under_the_cap_reaches_the_route(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/login", json={"username": "a"})
        assert response.status_code == 422

    def test_a_json_route_takes_no_more_than_256_kib(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/login", json={"username": "a", "password": "p" * 256 * 1024}
        )
        assert response.status_code == 413
        assert response.json() == {"detail": "Request body too large"}

    def test_only_the_procedure_upload_takes_a_large_body(self) -> None:
        assert LARGE_BODY_ROUTES == {("POST", "/api/v1/procedures"): 11 * 1024 * 1024}


class TestTheCoarseRateLimit:
    def test_the_api_answers_429_with_retry_after_once_the_budget_is_spent(
        self, client: TestClient
    ) -> None:
        for _ in range(GLOBAL_LIMIT.limit):
            GLOBAL_LIMIT.record("testclient")
        response = client.get("/status")
        assert response.status_code == 429
        assert int(response.headers["retry-after"]) >= 1
        assert_security_headers(response)

    def test_a_429_to_an_allowed_origin_carries_the_cors_headers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_ALLOWED_ORIGINS", '["https://ops.example"]')
        get_settings.cache_clear()
        with TestClient(create_app(static_dir=tmp_path / "not-built")) as cors_client:
            for _ in range(GLOBAL_LIMIT.limit):
                GLOBAL_LIMIT.record("testclient")
            response = cors_client.get("/status", headers={"Origin": "https://ops.example"})
        assert response.status_code == 429
        assert response.headers["access-control-allow-origin"] == "https://ops.example"
        assert_security_headers(response)

    @pytest.mark.parametrize("path", ["/", *PROBE_PATHS])
    def test_the_probes_are_never_throttled(self, client: TestClient, path: str) -> None:
        for _ in range(GLOBAL_LIMIT.limit):
            GLOBAL_LIMIT.record("testclient")
        assert client.get(path).status_code == 200
