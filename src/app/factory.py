"""The HTTP application factory. It builds the app and never listens (code-architecture).

One process serves three things:
● the platform probes and the secret-free status read-out, public and touching nothing;
● the JSON API under /api/v1, behind sign-in;
● the dashboard itself: the React app built into app/static by the container build.
"""

import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app import __version__
from app.api.v1.routes import (
    assistant,
    audit,
    auth,
    elsets,
    event_timers,
    health,
    maneuvers,
    mattermost,
    notifications,
    procedures,
    shift_log,
)
from app.config import get_settings
from app.core.body_limit import BodySizeLimitMiddleware
from app.core.logging import SERVICE_NAME, log_event
from app.core.net import client_ip
from app.core.rate_limit import GLOBAL_LIMIT
from app.core.request_id import REQUEST_ID_HEADER, RequestIDMiddleware
from app.db.session import dispose_engine
from app.services.background_refresh import start_background_loops, stop_background_loops
from app.services.procedure_storage import prepare_storage

# Liveness and readiness paths: public, unauthenticated, and touching nothing.
HEALTH_PATHS = ("/healthz", "/health", "/readyz", "/livez", "/ping")

# Inputs the diagnostics read-out reports, by name only. Never list a secret here.
CONFIG_INPUTS = ("PORT", "APP_ENV", "STORAGE_MOUNT_PATH", "PROCEDURE_STORAGE_PATH")

# The built dashboard. Present in the container image; absent in a plain source checkout,
# where Holly serves the API alone.
STATIC_DIR = Path(__file__).resolve().parent / "static"

# The strictest policy, on every response that is not an HTML page.
API_CSP = "default-src 'none'; frame-ancestors 'none'"
# HTML pages (the dashboard): its own scripts, styles and API only. No inline script, no eval,
# nothing from another origin.
DASHBOARD_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}

# The coarse rate-limit tier covers the API and the status read-out; probes and the
# dashboard's static files are never throttled.
_RATE_LIMITED_PREFIXES = ("/api/", "/status")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    procedure_dir = settings.procedure_dir()
    try:
        prepare_storage(settings)
    except OSError as exc:
        # One decisive boot line with the errno, then stop: a store that refuses writes must
        # not look healthy (appstore-gate-compliance).
        log_event(
            "boot",
            version=__version__,
            storage=str(procedure_dir),
            storage_writable=False,
            errno=exc.errno,
            error=exc.strerror,
        )
        raise
    app.state.storage = "ready"
    log_event(
        "boot",
        version=__version__,
        storage=str(procedure_dir),
        storage_writable=True,
        background_refresh=settings.background_refresh_enabled,
    )
    tasks = start_background_loops() if settings.background_refresh_enabled else []
    try:
        yield
    finally:
        await stop_background_loops(tasks)
        await dispose_engine()
        log_event("shutdown", version=__version__)


# Plain functions, not coroutines: none of these awaits anything (SonarQube python:S7503).
def _root() -> dict[str, str]:
    return {"service": SERVICE_NAME, "status": "ok"}


def _health() -> PlainTextResponse:
    return PlainTextResponse("ok")


def _status(request: Request) -> dict[str, Any]:
    """Secret-free diagnostics: each input as set or not and its length, never its value."""
    config = {}
    for name in CONFIG_INPUTS:
        value = os.environ.get(name)
        config[name] = {"set": value is not None, "length": len(value or "")}
    return {
        "service": SERVICE_NAME,
        "version": __version__,
        "config": config,
        "storage": {"procedures": getattr(request.app.state, "storage", "unknown")},
    }


async def _security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    is_page = response.headers.get("content-type", "").startswith("text/html")
    response.headers["Content-Security-Policy"] = DASHBOARD_CSP if is_page else API_CSP
    return response


async def _coarse_rate_limit(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.url.path.startswith(_RATE_LIMITED_PREFIXES):
        wait = GLOBAL_LIMIT.retry_after(client_ip(request) or "unknown")
        if wait:
            return JSONResponse(
                {"detail": f"Too many requests. Try again in {wait} seconds."},
                status_code=429,
                headers={"Retry-After": str(wait)},
            )
    return await call_next(request)


def _mount_dashboard(app: FastAPI, static_dir: Path) -> None:
    """Serve the built dashboard, or the JSON service descriptor when it was not built.

    FastAPI's frontend routes are checked only after every API route, and fall back to
    index.html only for a browser's page navigation, so an unknown API path still answers 404
    and a bookmarked dashboard page still loads.
    """
    if (static_dir / "index.html").is_file():
        app.frontend("/", directory=static_dir)
    else:
        app.add_api_route("/", _root, methods=["GET", "HEAD"])


def create_app(static_dir: Path = STATIC_DIR) -> FastAPI:
    """Build the Holly application.

    The interactive API docs are off, so nothing extra is public. Trailing slashes are not
    redirected, because the redirect would echo the request's Host header in its Location.
    """
    settings = get_settings()
    app = FastAPI(
        title="Holly",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
        lifespan=_lifespan,
    )
    # Starlette runs the middleware added last first, so a request passes the security
    # headers, the request id, the coarse limit, CORS and the body-size cap, in that order, and
    # every response, a 413 or a 429 included, leaves with the security headers and the
    # request id. The body cap sits innermost so the route reads the body straight from it:
    # its 413 error then reaches FastAPI as itself, not wrapped by the layers above.
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.middleware("http")(_coarse_rate_limit)
    app.add_middleware(RequestIDMiddleware)
    app.middleware("http")(_security_headers)

    @app.exception_handler(500)
    def _server_error(_request: Request, _exc: Exception) -> PlainTextResponse:
        # A generic body; the traceback stays in the server log. Starlette builds this response
        # outside the header middleware, so the security headers are added here too.
        return PlainTextResponse(
            "Internal Server Error",
            status_code=500,
            headers={**SECURITY_HEADERS, "Content-Security-Policy": API_CSP},
        )

    for path in HEALTH_PATHS:
        app.add_api_route(path, _health, methods=["GET", "HEAD"])
    app.add_api_route("/status", _status, methods=["GET"])
    for module in (
        health,
        auth,
        elsets,
        notifications,
        maneuvers,
        mattermost,
        procedures,
        shift_log,
        event_timers,
        assistant,
        audit,
    ):
        app.include_router(module.router, prefix="/api/v1")
    _mount_dashboard(app, static_dir)
    return app
