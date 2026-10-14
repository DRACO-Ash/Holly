"""The one place Holly calls Claude (llm-integration).

Every assistant feature (notification evaluations, event narratives, shift-note polish and the
end-of-shift summary) goes through call_claude, which:

● reads the API key server-side at call time and fails closed without it;
● refuses once the day's token cap is spent, across every caller (LLM_DAILY_TOKEN_CAP);
● marks the fixed system prompt for prompt caching;
● classifies a failure by exception type, so the background loops can tell a persistent fault
  (a bad key, no permission, rate limiting, no credit) from a transient one;
● writes one structured log line per call with its token usage.

The calls are short and use no tools, so they are not streamed and never pause mid-turn.
Model output is untrusted: each caller validates what it keeps before storing it.
"""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import anthropic

from app.config import get_settings
from app.core.logging import log_event

# Failures that will recur on every call until someone changes the key, the model setting,
# the plan or the account, so a background loop should stop its cycle rather than retry.
_PERSISTENT_ERRORS = (
    anthropic.AuthenticationError,
    anthropic.PermissionDeniedError,
    anthropic.NotFoundError,
    anthropic.RateLimitError,
)


class AssistantError(Exception):
    """An assistant call that produced no usable answer.

    `persistent` is true when the cause will not clear within a polling cycle.
    """

    def __init__(self, message: str, *, persistent: bool = False) -> None:
        super().__init__(message)
        self.persistent = persistent


@dataclass(frozen=True)
class ClaudeReply:
    text: str
    model: str
    truncated: bool


@dataclass
class DailyTokenBudget:
    """Tokens spent today (UTC), in this process. A restart starts the count again."""

    day: date | None = None
    spent: int = 0

    def _roll(self) -> None:
        today = datetime.now(UTC).date()
        if self.day != today:
            self.day = today
            self.spent = 0

    def ensure_available(self, cap: int) -> None:
        self._roll()
        if self.spent >= cap:
            msg = "The daily assistant token cap is spent; assistant calls resume tomorrow (UTC)."
            raise AssistantError(msg, persistent=True)

    def charge(self, tokens: int) -> None:
        self._roll()
        self.spent += tokens


BUDGET = DailyTokenBudget()


def _is_credit_error(exc: anthropic.BadRequestError) -> bool:
    # The API reports an exhausted credit balance as an invalid request; the message is the
    # only signal that tells it apart from a malformed request.
    return "credit balance" in str(exc).lower()


def _tokens_used(usage: anthropic.types.Usage) -> int:
    cached = (usage.cache_creation_input_tokens or 0) + (usage.cache_read_input_tokens or 0)
    return usage.input_tokens + usage.output_tokens + cached


async def _create_message(
    api_key: str, model: str, system_prompt: str, user_message: str, max_tokens: int
) -> anthropic.types.Message:
    try:
        async with anthropic.AsyncAnthropic(api_key=api_key) as client:
            return await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=[
                    {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
                ],
                messages=[{"role": "user", "content": user_message}],
            )
    except _PERSISTENT_ERRORS as exc:
        raise AssistantError(f"Anthropic API error: {exc}", persistent=True) from exc
    except anthropic.BadRequestError as exc:
        raise AssistantError(
            f"Anthropic API error: {exc}", persistent=_is_credit_error(exc)
        ) from exc
    except anthropic.APIError as exc:
        raise AssistantError(f"Anthropic API error: {exc}") from exc


async def call_claude(
    system_prompt: str, user_message: str, *, max_tokens: int, purpose: str
) -> ClaudeReply:
    """Send one request and return the reply's text. Raises AssistantError on any failure."""
    settings = get_settings()
    api_key = settings.anthropic_api_key.get_secret_value()
    if not api_key:
        raise AssistantError("ANTHROPIC_API_KEY is not configured", persistent=True)
    BUDGET.ensure_available(settings.llm_daily_token_cap)
    response = await _create_message(
        api_key, settings.anthropic_model, system_prompt, user_message, max_tokens
    )
    tokens = _tokens_used(response.usage)
    BUDGET.charge(tokens)
    log_event(
        "llm.call",
        purpose=purpose,
        model=settings.anthropic_model,
        tokens=tokens,
        stop_reason=response.stop_reason,
    )
    if response.stop_reason == "refusal":
        raise AssistantError("The model declined to answer this request.")
    text = "\n".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise AssistantError("Model response contained no text")
    return ClaudeReply(
        text=text, model=settings.anthropic_model, truncated=response.stop_reason == "max_tokens"
    )


def extract_json_object(text: str) -> dict[str, Any]:
    """The first JSON object in a reply, ignoring any prose or code fence around it.

    The standard JSON decoder reads from each opening brace in turn, so braces inside strings
    never confuse it. Raises AssistantError when the reply holds no JSON object.
    """
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            value, _end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            value = None
        if isinstance(value, dict):
            return value
        start = text.find("{", start + 1)
    raise AssistantError("Model response contained no JSON object")
