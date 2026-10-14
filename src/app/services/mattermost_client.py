"""Thin async wrapper around Mattermost's REST API.

Holly uses Mattermost's `/api/v4` surface with a bot personal access token. The bot must be a
member of any channel Holly polls; channels it is not in answer 403, which the caller treats
as "skip silently". Mattermost's response bodies go to the server log, never to a browser.
"""

import logging
import re
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any, Self

import httpx2

from app.config import get_settings
from app.services.api_client import ApiClient

logger = logging.getLogger(__name__)

# The shape of a Mattermost id (26 lowercase letters and digits in practice). Every id that
# goes into a request path is checked against it, so a value taken from a post can never point
# the bot's token at a different API path.
PLAIN_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


class MattermostClientError(Exception):
    """Raised when a Mattermost request fails or returns an unexpected response."""


class MattermostAuthError(MattermostClientError):
    """Raised when Mattermost rejects the bot token or the bot lacks access."""


class MattermostClient(ApiClient):
    """Async client. Use as `async with MattermostClient() as mm: ...`."""

    service = "Mattermost"
    error = MattermostClientError
    logger = logger

    def __init__(
        self,
        base_url: str | None = None,
        bot_token: str | None = None,
        timeout: float = 30.0,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.mattermost_url).rstrip("/")
        self._bot_token = (
            bot_token if bot_token is not None else settings.mattermost_bot_token.get_secret_value()
        )
        self._timeout = timeout
        self._transport = transport
        self._client: httpx2.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        if not self._base_url or not self._bot_token:
            msg = "Mattermost is not configured (MATTERMOST_URL / MATTERMOST_BOT_TOKEN)."
            raise MattermostClientError(msg)
        client = httpx2.AsyncClient(
            base_url=f"{self._base_url}/api/v4",
            headers={"Authorization": f"Bearer {self._bot_token}"},
            timeout=self._timeout,
            transport=self._transport,
        )
        self._client = await client.__aenter__()
        return self

    def _check_auth(self, response: httpx2.Response) -> None:
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            msg = "Mattermost rejected the bot token (401)."
            raise MattermostAuthError(msg)
        if response.status_code == HTTPStatus.FORBIDDEN:
            msg = "Mattermost denied access (403): is the bot in the channel?"
            raise MattermostAuthError(msg)

    async def _get_object(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """The JSON object at `path`; anything else raises MattermostClientError."""
        data = await self._get_json(path, params)
        if not isinstance(data, dict):
            msg = f"Mattermost response was not a JSON object (got {type(data).__name__})."
            raise MattermostClientError(msg)
        return data

    async def get_channel(self, channel_id: str) -> dict[str, Any]:
        return await self._get_object(f"/channels/{_checked(channel_id)}")

    async def get_user(self, user_id: str) -> dict[str, Any]:
        return await self._get_object(f"/users/{_checked(user_id)}")

    async def get_channel_posts_since(
        self,
        channel_id: str,
        since_ms: int,
        per_page: int = 200,
    ) -> dict[str, Any]:
        """Posts in a channel created since `since_ms` (epoch milliseconds).

        Returns Mattermost's native shape: `{posts: {id: {...}}, order: [id, ...]}`, with
        `order` newest first.
        """
        return await self._get_object(
            f"/channels/{_checked(channel_id)}/posts",
            params={"since": since_ms, "per_page": per_page},
        )


def _checked(identifier: str) -> str:
    if not PLAIN_ID.fullmatch(identifier):
        msg = "A Mattermost id was malformed."
        raise MattermostClientError(msg)
    return identifier


def datetime_to_ms(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


def ms_to_datetime(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=UTC)
