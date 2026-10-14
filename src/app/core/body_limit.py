"""A cap on every request body, enforced before the body is parsed or buffered.

A declared Content-Length over the cap is refused at once; a body without one (chunked) is
counted as it arrives and refused the moment it passes the cap. Either way the answer is 413,
and an oversized upload never fills memory or disk. Most routes take small JSON, whose largest
field is a 10,000-character shift note; only the procedure upload takes a 10 MB file plus its
multipart framing, and it reads that only once the caller is signed in.
"""

import json
from collections.abc import Mapping

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_BODY_BYTES = 256 * 1024
MAX_UPLOAD_BODY_BYTES = 11 * 1024 * 1024
# The routes allowed a larger body than the default, by method and path.
LARGE_BODY_ROUTES: Mapping[tuple[str, str], int] = {
    ("POST", "/api/v1/procedures"): MAX_UPLOAD_BODY_BYTES,
}
_TOO_LARGE = "Request body too large"


class _BodyTooLargeError(HTTPException):
    """Raised from the body stream itself. An HTTPException, because FastAPI turns any other
    error raised while reading a body into a 400 but re-raises this one, so the route's normal
    error handling answers 413 with the usual headers."""

    def __init__(self) -> None:
        super().__init__(status_code=413, detail=_TOO_LARGE)


def _declared_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


class BodySizeLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        max_bytes: int = MAX_BODY_BYTES,
        large_bodies: Mapping[tuple[str, str], int] = LARGE_BODY_ROUTES,
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.large_bodies = large_bodies

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.large_bodies.get((scope["method"], scope["path"]), self.max_bytes)
        declared = _declared_length(scope)
        if declared is not None and declared > limit:
            await _send_413(send)
            return

        received = 0
        response_started = False

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLargeError
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _BodyTooLargeError:
            if not response_started:
                await _send_413(send)


async def _send_413(send: Send) -> None:
    body = json.dumps({"detail": _TOO_LARGE}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
                (b"x-content-type-options", b"nosniff"),
                (b"cache-control", b"no-store"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
