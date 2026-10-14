"""The one place Holly calls Claude (llm-integration).

Every assistant feature (notification evaluations, event narratives, shift-note polish and the
end-of-shift summary) goes through call_claude, which:

● reads the API key server-side at call time and fails closed without it;
● holds each call's largest possible cost against the day's token cap before it is sent, and
  refuses a call the cap cannot cover, across every caller (LLM_DAILY_TOKEN_CAP);
● marks the fixed system prompt for prompt caching;
● classifies a failure by exception type, so the background loops can tell a persistent fault
  (a bad key, no permission, rate limiting, no credit) from a transient one, and reports it
  in a fixed message: the API's own text stays in the server log;
● writes one structured log line per call with its token usage.

The calls are short and use no tools, so they are not streamed and never pause mid-turn.
Model output is untrusted: each caller validates what it keeps before storing it.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import anthropic

from app.config import get_settings
from app.core.logging import log_event

logger = logging.getLogger(__name__)

# Failures that will recur on every call until someone changes the key, the model setting,
# the plan or the account, so a background loop should stop its cycle rather than retry. Each
# is reported to analysts in a fixed message.
_PERSISTENT_ERRORS: dict[type[anthropic.APIStatusError], str] = {
    anthropic.AuthenticationError: "The assistant rejected Holly's API key.",
    anthropic.PermissionDeniedError: "The assistant refused this request for Holly's API key.",
    anthropic.NotFoundError: "The assistant does not offer the model Holly is set to use.",
    anthropic.RateLimitError: "The assistant is limiting Holly's requests; try again later.",
}
_NO_CREDIT = "The assistant account has no credit left."
_BAD_REQUEST = "The assistant rejected the request."
_UNAVAILABLE = "The assistant could not be reached or failed; try again."
# A rough count of characters per token, low so that a call's hold is never too small.
_CHARS_PER_TOKEN = 3
# A reply is one JSON object, perhaps after a little prose, so the decoder tries only this many
# opening braces: a crafted reply full of them cannot hold the event loop.
_MAX_JSON_STARTS = 20


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

    def _roll(self) -> date:
        """Start a new count when the day (UTC) has turned; returns the day counted."""
        today = datetime.now(UTC).date()
        if self.day != today:
            self.day = today
            self.spent = 0
        return today

    def reserve(self, cap: int, tokens: int) -> date:
        """Hold `tokens` of today's cap for a call about to be sent, or refuse when the cap
        cannot cover them. Nothing awaits between the check and the hold, so calls made at the
        same moment cannot all pass the same check. Returns the day the hold counts against."""
        day = self._roll()
        if self.spent + tokens > cap:
            msg = "The daily assistant token cap is spent; assistant calls resume tomorrow (UTC)."
            raise AssistantError(msg, persistent=True)
        self.spent += tokens
        return day

    def settle(self, day: date, held: int, used: int) -> None:
        """Replace a call's hold with what it used. A hold from an earlier day was cleared when
        the day turned, so only the use counts then."""
        today = self._roll()
        self.spent += used - (held if day == today else 0)


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
    except anthropic.APIError as exc:
        logger.warning("Anthropic API error (%s): %s", type(exc).__name__, exc)
        raise _failure(exc) from exc


def _failure(exc: anthropic.APIError) -> AssistantError:
    for error_type, message in _PERSISTENT_ERRORS.items():
        if isinstance(exc, error_type):
            return AssistantError(message, persistent=True)
    if isinstance(exc, anthropic.BadRequestError):
        if _is_credit_error(exc):
            return AssistantError(_NO_CREDIT, persistent=True)
        return AssistantError(_BAD_REQUEST)
    return AssistantError(_UNAVAILABLE)


async def call_claude(
    system_prompt: str, user_message: str, *, max_tokens: int, purpose: str
) -> ClaudeReply:
    """Send one request and return the reply's text. Raises AssistantError on any failure."""
    settings = get_settings()
    api_key = settings.anthropic_api_key.get_secret_value()
    if not api_key:
        raise AssistantError("ANTHROPIC_API_KEY is not configured", persistent=True)
    # The most this call can cost: its whole output allowance and a generous input estimate.
    held = max_tokens + (len(system_prompt) + len(user_message)) // _CHARS_PER_TOKEN
    day = BUDGET.reserve(settings.llm_daily_token_cap, held)
    try:
        response = await _create_message(
            api_key, settings.anthropic_model, system_prompt, user_message, max_tokens
        )
    except BaseException:
        BUDGET.settle(day, held, 0)
        raise
    tokens = _tokens_used(response.usage)
    BUDGET.settle(day, held, tokens)
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

    The standard JSON decoder reads from each opening brace in turn, up to _MAX_JSON_STARTS of
    them, so braces inside strings never confuse it. Raises AssistantError when no JSON object
    starts at any of them.
    """
    decoder = json.JSONDecoder()
    start = text.find("{")
    for _attempt in range(_MAX_JSON_STARTS):
        if start == -1:
            break
        try:
            value, _end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            value = None
        except RecursionError:
            # Nesting deeper than Python can decode is no evaluation; retrying from each inner
            # brace would only repeat the work.
            msg = "Model response nested too deeply to read"
            raise AssistantError(msg) from None
        if isinstance(value, dict):
            return value
        start = text.find("{", start + 1)
    raise AssistantError("Model response contained no JSON object")
