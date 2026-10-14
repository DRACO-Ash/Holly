"""The core guards driven directly: the sliding-window limiter's expiry and memory bound, the
body cap's edges as raw ASGI, and the stdout log handler's refusal to raise."""

import io
import logging
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.types import Message, Receive, Scope, Send

from app.core import rate_limit
from app.core.body_limit import BodySizeLimitMiddleware
from app.core.logging import JsonFormatter, StdoutHandler
from app.core.rate_limit import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class TestRateLimiter:
    def test_a_key_is_refused_at_its_limit_and_told_how_long_to_wait(self) -> None:
        clock = FakeClock()
        limiter = RateLimiter(limit=2, window_seconds=60, clock=clock)
        assert limiter.retry_after("analyst") == 0
        clock.now += 10
        assert limiter.retry_after("analyst") == 0
        clock.now += 0.5
        assert limiter.wait_time("analyst") == 50

    def test_hits_older_than_the_window_stop_counting(self) -> None:
        clock = FakeClock()
        limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
        limiter.record("analyst")
        assert limiter.wait_time("analyst") == 60
        clock.now += 60
        assert limiter.wait_time("analyst") == 0

    def test_check_raises_429_with_retry_after(self) -> None:
        limiter = RateLimiter(limit=1, window_seconds=60, clock=FakeClock())
        limiter.check("analyst")
        with pytest.raises(HTTPException) as raised:
            limiter.check("analyst")
        assert raised.value.status_code == 429
        assert raised.value.headers == {"Retry-After": "60"}

    def test_the_stalest_key_is_forgotten_once_the_bound_is_reached(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(rate_limit, "MAX_TRACKED_KEYS", 2)
        limiter = RateLimiter(limit=1, window_seconds=60, clock=FakeClock())
        for key in ("first", "second", "third"):
            limiter.record(key)
        assert limiter.wait_time("first") == 0, "the stalest key was dropped"
        assert limiter.wait_time("third") == 60

    @pytest.mark.parametrize(
        ("limiter", "limit", "window_seconds"),
        [
            (rate_limit.GLOBAL_LIMIT, 600, 60),
            (rate_limit.LOGIN_LIMIT, 10, 900),
            (rate_limit.LOGIN_ADDRESS_LIMIT, 30, 60),
            (rate_limit.ASSISTANT_LIMIT, 30, 600),
        ],
        ids=["every request", "sign-ins per username", "sign-ins per address", "assistant calls"],
    )
    def test_each_limit_is_the_documented_one(
        self, limiter: RateLimiter, limit: int, window_seconds: int
    ) -> None:
        # Literals, so a loosened limit fails here; the documentation states the same values.
        assert (limiter.limit, limiter.window_seconds) == (limit, window_seconds)

    def test_a_limiter_remembers_at_most_10000_keys(self) -> None:
        assert rate_limit.MAX_TRACKED_KEYS == 10_000

    def test_forget_and_reset_clear_the_counts(self) -> None:
        limiter = RateLimiter(limit=1, window_seconds=60, clock=FakeClock())
        limiter.record("a")
        limiter.record("b")
        limiter.forget("a")
        assert limiter.wait_time("a") == 0
        assert limiter.wait_time("b") == 60
        limiter.reset()
        assert limiter.wait_time("b") == 0


async def _run(
    middleware: BodySizeLimitMiddleware, scope: Scope, chunks: list[bytes]
) -> list[Message]:
    sent: list[Message] = []
    pending = [
        {"type": "http.request", "body": chunk, "more_body": i < len(chunks) - 1}
        for i, chunk in enumerate(chunks)
    ]
    receive = AsyncMock(side_effect=lambda: pending.pop(0))
    send = AsyncMock(side_effect=sent.append)
    await middleware(scope, receive, send)
    return sent


def _scope(headers: list[tuple[bytes, bytes]]) -> Scope:
    return {"type": "http", "method": "POST", "path": "/", "headers": headers}


async def _read_everything(_scope: Scope, receive: Receive, send: Send) -> None:
    """A bare ASGI app that reads the whole body, handles no error, and answers 200."""
    more = True
    while more:
        message = await receive()
        more = message.get("more_body", False)
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


class TestBodyCap:
    async def test_an_unreadable_content_length_is_counted_as_it_arrives(self) -> None:
        middleware = BodySizeLimitMiddleware(_read_everything, max_bytes=10)
        sent = await _run(middleware, _scope([(b"content-length", b"abc")]), [b"12345"])
        assert sent[0]["status"] == 200

    async def test_a_body_that_passes_the_cap_is_answered_413_by_the_cap_itself(self) -> None:
        # An app with no error handling of its own: the cap answers for it.
        middleware = BodySizeLimitMiddleware(_read_everything, max_bytes=10)
        sent = await _run(middleware, _scope([]), [b"123456", b"789012"])
        assert sent[0]["status"] == 413
        headers = dict(sent[0]["headers"])
        assert headers[b"content-security-policy"] == b"default-src 'none'; frame-ancestors 'none'"
        assert sent[1]["body"] == b'{"detail": "Request body too large"}'

    async def test_once_a_response_has_started_nothing_more_is_sent(self) -> None:
        async def answers_then_reads(_scope: Scope, receive: Receive, send: Send) -> None:
            await send({"type": "http.response.start", "status": 202, "headers": []})
            await receive()
            await receive()

        middleware = BodySizeLimitMiddleware(answers_then_reads, max_bytes=10)
        sent = await _run(middleware, _scope([]), [b"123456", b"789012"])
        assert [message["type"] for message in sent] == ["http.response.start"]

    async def test_anything_but_http_passes_through(self) -> None:
        lifespan_app = AsyncMock()
        receive, send = AsyncMock(), AsyncMock()
        await BodySizeLimitMiddleware(lifespan_app)({"type": "lifespan"}, receive, send)
        lifespan_app.assert_awaited_once_with({"type": "lifespan"}, receive, send)


class _BrokenStream(io.StringIO):
    def write(self, _text: str) -> int:
        msg = "stdout is closed"
        raise OSError(msg)


def test_a_log_line_that_cannot_be_written_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = StdoutHandler()
    handler.setFormatter(JsonFormatter())
    handled: list[Any] = []
    monkeypatch.setattr(handler, "handleError", handled.append)
    monkeypatch.setattr("sys.stdout", _BrokenStream())
    record = logging.LogRecord("holly", logging.INFO, __file__, 1, "message", None, None)
    handler.emit(record)
    assert handled == [record]
