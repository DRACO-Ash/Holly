"""A request id on every response but a CORS preflight, and every log line, so one request can
be traced end to end.

An id the client sends is reused only when it is a plain token of at most 128 characters;
anything else is replaced with a fresh UUID, so a caller cannot write arbitrary text into the
logs or the response headers.
"""

import re
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

REQUEST_ID_HEADER = "X-Request-ID"
_ACCEPTABLE_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def current_request_id() -> str:
    return request_id_var.get()


def choose_request_id(incoming: str | None) -> str:
    """The client's id when it is a plain token, otherwise a fresh UUID."""
    if incoming and _ACCEPTABLE_ID.fullmatch(incoming):
        return incoming
    return str(uuid.uuid4())


class RequestIDMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, header_name: str = REQUEST_ID_HEADER) -> None:
        super().__init__(app)
        self._header_name = header_name

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = choose_request_id(request.headers.get(self._header_name))
        # Kept on the request too, for the 500 response Starlette builds outside this layer.
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers[self._header_name] = request_id
            return response
        finally:
            request_id_var.reset(token)
