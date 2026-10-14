"""The one place Holly calls Claude: the request it sends, the reply it accepts, the daily
token cap, and how each failure is classified. The real SDK runs against a mock transport, so
the error classes and the reply parsing are the SDK's own, and nothing leaves the process."""

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import anthropic
import httpx2
import pytest

from app.services import claude
from app.services.claude import AssistantError, DailyTokenBudget, call_claude, extract_json_object

Handler = Callable[[httpx2.Request], httpx2.Response]


def reply(
    text: str | None = "All quiet.",
    *,
    stop_reason: str = "end_turn",
    usage: dict[str, int] | None = None,
) -> dict[str, Any]:
    content = [{"type": "text", "text": text}] if text is not None else []
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-4-6",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": usage or {"input_tokens": 10, "output_tokens": 5},
    }


def error_body(kind: str, message: str) -> dict[str, Any]:
    return {"type": "error", "error": {"type": kind, "message": message}}


class AnthropicRecorder:
    """The Anthropic API as the SDK sees it: each request is recorded and answered in turn."""

    def __init__(self) -> None:
        self.requests: list[httpx2.Request] = []
        self.answers: list[Handler] = []

    def answer(self, status: int, body: dict[str, Any]) -> None:
        self.answers.append(lambda _request: httpx2.Response(status, json=body))

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return self.answers.pop(0)(request)


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch, settings_env: Callable[..., None]) -> AnthropicRecorder:
    """Configure a key and a 1,000-token day, and route the real SDK to a recorder."""
    monkeypatch.setenv("LLM_DAILY_TOKEN_CAP", "1000")
    settings_env(ANTHROPIC_API_KEY="k-1")
    recorder = AnthropicRecorder()
    real_client = anthropic.AsyncAnthropic

    def client_factory(**kwargs: Any) -> anthropic.AsyncAnthropic:
        http_client = httpx2.AsyncClient(transport=httpx2.MockTransport(recorder.handle))
        return real_client(**kwargs, http_client=http_client, max_retries=0)

    monkeypatch.setattr(anthropic, "AsyncAnthropic", client_factory)
    return recorder


async def test_without_a_key_it_fails_closed_and_persistently() -> None:
    with pytest.raises(AssistantError, match="ANTHROPIC_API_KEY") as raised:
        await call_claude("system", "user", max_tokens=256, purpose="test")
    assert raised.value.persistent is True


async def test_a_reply_is_returned_with_the_request_it_answered(api: AnthropicRecorder) -> None:
    api.answer(200, reply("  Line one.\n"))
    result = await call_claude("You are terse.", "Status?", max_tokens=300, purpose="test")
    assert result.text == "Line one."
    assert result.model == "claude-sonnet-4-6"
    assert result.truncated is False
    [request] = api.requests
    assert request.url == "https://api.anthropic.com/v1/messages"
    assert request.headers["x-api-key"] == "k-1"
    assert json.loads(request.content) == {
        "model": "claude-sonnet-4-6",
        "max_tokens": 300,
        "system": [
            {"type": "text", "text": "You are terse.", "cache_control": {"type": "ephemeral"}}
        ],
        "messages": [{"role": "user", "content": "Status?"}],
    }


async def test_a_reply_cut_short_by_the_token_limit_is_marked_truncated(
    api: AnthropicRecorder,
) -> None:
    api.answer(200, reply("Partial", stop_reason="max_tokens"))
    result = await call_claude("s", "u", max_tokens=256, purpose="test")
    assert result.truncated is True


async def test_every_token_counts_against_the_day_and_is_logged(
    api: AnthropicRecorder, capsys: pytest.CaptureFixture[str]
) -> None:
    usage = {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_creation_input_tokens": 7,
        "cache_read_input_tokens": 3,
    }
    api.answer(200, reply(usage=usage))
    await call_claude("s", "u", max_tokens=256, purpose="shift.polish")
    assert claude.BUDGET.spent == 160
    lines = [json.loads(text) for text in capsys.readouterr().out.splitlines()]
    [line] = [line for line in lines if "event" in line]
    assert line["event"] == "llm.call"
    assert line["purpose"] == "shift.polish"
    assert line["tokens"] == 160
    assert line["stop_reason"] == "end_turn"
    assert "k-1" not in json.dumps(line)


async def test_once_the_cap_is_spent_calls_stop_until_the_next_day(
    api: AnthropicRecorder,
) -> None:
    api.answer(200, reply())
    claude.BUDGET.reserve(1000, 1000)
    with pytest.raises(AssistantError, match="daily assistant token cap") as raised:
        await call_claude("s", "u", max_tokens=256, purpose="test")
    assert raised.value.persistent is True
    assert api.requests == [], "no request is sent once the cap is spent"
    claude.BUDGET.day = date(2000, 1, 1)
    await call_claude("s", "u", max_tokens=256, purpose="test")
    assert claude.BUDGET.spent == 15


async def test_a_refusal_is_an_error(api: AnthropicRecorder) -> None:
    api.answer(200, reply("I can't help with that.", stop_reason="refusal"))
    with pytest.raises(AssistantError, match="declined") as raised:
        await call_claude("s", "u", max_tokens=256, purpose="test")
    assert raised.value.persistent is False


@pytest.mark.parametrize("text", [None, "   "])
async def test_a_reply_without_text_is_an_error(api: AnthropicRecorder, text: str | None) -> None:
    api.answer(200, reply(text))
    with pytest.raises(AssistantError, match="no text"):
        await call_claude("s", "u", max_tokens=256, purpose="test")


@pytest.mark.parametrize(
    ("status", "kind", "message", "persistent", "shown"),
    [
        (401, "authentication_error", "invalid x-api-key", True, "rejected Holly's API key"),
        (403, "permission_error", "no access to model", True, "refused this request for Holly"),
        (404, "not_found_error", "model not found", True, "does not offer the model"),
        (429, "rate_limit_error", "rate limited", True, "limiting Holly's requests"),
        (400, "invalid_request_error", "Your credit balance is too low", True, "no credit left"),
        (400, "invalid_request_error", "messages: field required", False, "rejected the request"),
        (500, "api_error", "internal error", False, "could not be reached or failed"),
        (529, "overloaded_error", "overloaded", False, "could not be reached or failed"),
    ],
)
async def test_each_failure_is_classified_and_reported_in_a_fixed_message(
    api: AnthropicRecorder,
    caplog: pytest.LogCaptureFixture,
    status: int,
    kind: str,
    message: str,
    persistent: bool,
    shown: str,
) -> None:
    api.answer(status, error_body(kind, message))
    with pytest.raises(AssistantError) as raised:
        await call_claude("s", "u", max_tokens=256, purpose="test")
    assert raised.value.persistent is persistent
    # Analysts see the fixed message; the API's own text stays in the server log.
    assert shown in str(raised.value)
    assert message not in str(raised.value)
    assert any(message in record.getMessage() for record in caplog.records)
    assert claude.BUDGET.spent == 0, "a failed call gives its hold back"


async def test_calls_made_together_cannot_overrun_the_cap(api: AnthropicRecorder) -> None:
    # Each call holds its whole output allowance before it is sent, so with a 1,000-token day
    # only two 400-token calls fit, however many start at once.
    for _ in range(2):
        api.answer(200, reply())
    results = await asyncio.gather(
        *(call_claude("s", "u", max_tokens=400, purpose="test") for _ in range(3)),
        return_exceptions=True,
    )
    assert [type(result).__name__ for result in results] == [
        "ClaudeReply",
        "ClaudeReply",
        "AssistantError",
    ]
    assert len(api.requests) == 2
    assert claude.BUDGET.spent == 30


async def test_the_hold_counts_the_prompt_at_three_characters_a_token(
    api: AnthropicRecorder,
) -> None:
    # 400 output tokens held on a 1,000-token day leave 600 for the prompt: 1,800 characters
    # at three a token. A 2,100-character prompt is refused before it is sent.
    with pytest.raises(AssistantError, match="daily assistant token cap"):
        await call_claude("s", "u" * 2099, max_tokens=400, purpose="test")
    assert api.requests == []
    api.answer(200, reply())
    await call_claude("s", "u" * 1799, max_tokens=400, purpose="test")
    assert len(api.requests) == 1


class _Clock:
    """Stands in for datetime in the claude module: each now() is the next of `times`."""

    def __init__(self, *times: datetime) -> None:
        self._times = iter(times)

    def now(self, _tz: object = None) -> datetime:
        return next(self._times)


def test_a_call_that_crosses_midnight_counts_only_its_use_on_the_new_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = datetime(2026, 6, 1, 23, 59, 59, 999_999, tzinfo=UTC)
    after = datetime(2026, 6, 2, tzinfo=UTC)
    monkeypatch.setattr(claude, "datetime", _Clock(before, after, after))
    budget = DailyTokenBudget()
    day = budget.reserve(1000, 400)
    assert day == date(2026, 6, 1)
    budget.settle(day, held=400, used=10)
    assert (budget.day, budget.spent) == (date(2026, 6, 2), 10)


def test_a_hold_from_an_earlier_day_does_not_reduce_todays_count() -> None:
    budget = DailyTokenBudget()
    budget.reserve(1000, 40)
    budget.settle(date(2000, 1, 1), held=400, used=10)
    assert budget.spent == 50


async def test_a_connection_failure_is_transient(api: AnthropicRecorder) -> None:
    def refuse(request: httpx2.Request) -> httpx2.Response:
        msg = "connection refused"
        raise httpx2.ConnectError(msg, request=request)

    api.answers.append(refuse)
    with pytest.raises(AssistantError) as raised:
        await call_claude("s", "u", max_tokens=256, purpose="test")
    assert raised.value.persistent is False


class TestExtractJsonObject:
    def test_a_bare_object(self) -> None:
        assert extract_json_object('{"a": 1}') == {"a": 1}

    def test_an_object_inside_prose_and_a_code_fence(self) -> None:
        text = 'Here it is:\n```json\n{"urgency": "high", "note": "a {brace} inside"}\n```'
        assert extract_json_object(text) == {"urgency": "high", "note": "a {brace} inside"}

    def test_a_stray_brace_before_the_object_is_skipped(self) -> None:
        assert extract_json_object('Use {curly} braces: {"ok": true}') == {"ok": True}

    def test_a_json_array_is_not_an_object(self) -> None:
        with pytest.raises(AssistantError, match="no JSON object"):
            extract_json_object("[1, 2, 3]")

    @pytest.mark.parametrize("text", ["", "no json here", "{not json}", '{"open": '])
    def test_no_object_is_an_error(self, text: str) -> None:
        with pytest.raises(AssistantError, match="no JSON object"):
            extract_json_object(text)

    @pytest.mark.parametrize(("stray", "found"), [(19, True), (20, False)])
    def test_only_the_first_20_opening_braces_are_tried(self, stray: int, found: bool) -> None:
        text = "{x} " * stray + '{"ok": true}'
        if found:
            assert extract_json_object(text) == {"ok": True}
        else:
            with pytest.raises(AssistantError, match="no JSON object"):
                extract_json_object(text)

    def test_nesting_too_deep_to_decode_is_an_error_not_a_crash(self) -> None:
        text = '{"a":' * 20_000 + "1" + "}" * 20_000
        with pytest.raises(AssistantError, match="nested too deeply"):
            extract_json_object(text)
