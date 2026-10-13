"""The HTTP application factory. It builds the app and never listens (code-architecture)."""

import json
import os
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

from app import __version__

SERVICE_NAME = "holly"

# Liveness and readiness paths: public, unauthenticated, and touching nothing.
HEALTH_PATHS = ("/healthz", "/health", "/readyz", "/livez", "/ping")

# Inputs the diagnostics read-out reports, by name only. Add every new input here.
CONFIG_INPUTS = ("PORT",)

# Sent on every response. The CSP is the strictest policy; loosen it deliberately, and only
# when the dashboard first serves a page.
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def log_event(event: str, **fields: object) -> None:
    """Write one structured JSON log line to stdout. Never pass a secret value."""
    sys.stdout.write(json.dumps({"event": event, "service": SERVICE_NAME, **fields}) + "\n")
    sys.stdout.flush()


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # One decisive boot line. Holly has no storage yet; when a volume or database add-on
    # arrives, this line records whether it accepted a real write.
    log_event("boot", version=__version__, storage="none")
    yield
    log_event("shutdown", version=__version__)


async def _root() -> dict[str, str]:
    return {"service": SERVICE_NAME, "status": "ok"}


async def _health() -> PlainTextResponse:
    return PlainTextResponse("ok")


async def _status() -> dict[str, Any]:
    """Secret-free diagnostics: each input as set or not and its length, never its value."""
    config = {}
    for name in CONFIG_INPUTS:
        value = os.environ.get(name)
        config[name] = {"set": value is not None, "length": len(value or "")}
    return {
        "service": SERVICE_NAME,
        "version": __version__,
        "config": config,
        "storage": {"configured": False},
    }


async def _security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    return response


def create_app() -> FastAPI:
    """Build the Holly application. The interactive API docs are off, so nothing extra is public."""
    app = FastAPI(
        title="Holly",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=_lifespan,
    )
    app.middleware("http")(_security_headers)
    app.add_api_route("/", _root, methods=["GET", "HEAD"])
    for path in HEALTH_PATHS:
        app.add_api_route(path, _health, methods=["GET", "HEAD"])
    app.add_api_route("/status", _status, methods=["GET"])
    return app
