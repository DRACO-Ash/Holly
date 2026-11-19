"""A request id on every response but a CORS preflight, and every log line, so one request can
be traced end to end; and one log line per request.

An id the client sends (the App Store's gateway sends X-Request-Id) is reused only when it is a
plain token of at most 128 characters; anything else is replaced with a fresh UUID, so a caller
cannot write arbitrary text into the logs or the response headers. While a request is handled,
every log line carries the id in its attributes as http.request.header.x-request-id, and the
signed-in email the gateway sends in X-Auth-Request-Email as user.email, when it is a plain
address. The request line gives the method, the path without its query string, the status and
the duration; no header value but those two is ever logged.
"""

import logging
import re
import time
import uuid
from collections.abc import Mapping
from contextvars import ContextVar
from types import MappingProxyType

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

REQUEST_ID_HEADER = "X-Request-ID"
EMAIL_HEADER = "X-Auth-Request-Email"
REQUEST_ID_ATTRIBUTE = "http.request.header.x-request-id"
EMAIL_ATTRIBUTE = "user.email"
_ACCEPTABLE_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_PLAIN_EMAIL = re.compile(r"[A-Za-z0-9._%+'-]{1,64}@[A-Za-z0-9.-]{1,189}\.[A-Za-z]{2,63}")

_NONE: Mapping[str, str] = MappingProxyType({})
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
request_attributes_var: ContextVar[Mapping[str, str]] = ContextVar(
    "request_attributes", default=_NONE
)

request_log = logging.getLogger("app.request")


def current_request_id() -> str:
    return request_id_var.get()


def current_request_attributes() -> Mapping[str, str]:
    return request_attributes_var.get()


def choose_request_id(incoming: str | None) -> str:
    """The client's id when it is a plain token, otherwise a fresh UUID."""
    if incoming and _ACCEPTABLE_ID.fullmatch(incoming):
        return incoming
    return str(uuid.uuid4())


def request_attributes(request_id: str, email: str | None) -> Mapping[str, str]:
    """The attributes every line written for this request carries. An email that is not a
    plain address is left out rather than written."""
    attributes = {REQUEST_ID_ATTRIBUTE: request_id}
    if email and _PLAIN_EMAIL.fullmatch(email):
        attributes[EMAIL_ATTRIBUTE] = email
    return MappingProxyType(attributes)


def _log_request(request: Request, status: int, started: float) -> None:
    request_log.info(
        "%s %s %d",
        request.method,
        request.url.path,
        status,
        extra={
            "attributes": {
                "http.request.method": request.method,
                "url.path": request.url.path,
                "http.response.status_code": status,
                "http.server.request.duration_ms": round((time.perf_counter() - started) * 1000),
            }
        },
    )


class RequestIDMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, header_name: str = REQUEST_ID_HEADER) -> None:
        super().__init__(app)
        self._header_name = header_name

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        request_id = choose_request_id(request.headers.get(self._header_name))
        # Kept on the request too, for the 500 response Starlette builds outside this layer.
        request.state.request_id = request_id
        attributes = request_attributes(request_id, request.headers.get(EMAIL_HEADER))
        request.state.log_attributes = attributes
        token = request_id_var.set(request_id)
        attributes_token = request_attributes_var.set(attributes)
        try:
            response = await call_next(request)
        except Exception:
            _log_request(request, 500, started)
            raise
        else:
            response.headers[self._header_name] = request_id
            _log_request(request, response.status_code, started)
            return response
        finally:
            request_attributes_var.reset(attributes_token)
            request_id_var.reset(token)
