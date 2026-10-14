"""What Holly's two outbound clients (UDL and Mattermost) share.

A subclass opens the httpx2 client in its own __aenter__, because each authenticates its own
way; this base closes it, sends each GET, and turns every failure into the subclass's own error
with a short message of Holly's. An upstream response body goes to the server log, cut to 200
characters, and never into an error a browser could see.
"""

import logging
from collections.abc import Mapping
from typing import Any, ClassVar

import httpx2

_LOGGED_BODY_LENGTH = 200


class ApiClient:
    # Set by each subclass: the service's name in messages, its error class, and its logger.
    service: ClassVar[str]
    error: ClassVar[type[Exception]]
    logger: ClassVar[logging.Logger]

    _client: httpx2.AsyncClient | None = None

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._client is not None:
            await self._client.__aexit__(*exc_info)
            self._client = None

    def _check_auth(self, response: httpx2.Response) -> None:
        """Raise the subclass's own error for an authentication or access refusal."""

    async def _get_json(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        """The decoded JSON body of a successful GET of `path`."""
        if self._client is None:
            msg = f"{type(self).__name__} must be used as an async context manager."
            raise self.error(msg)
        try:
            response = await self._client.get(path, params=params)
        except httpx2.HTTPError as exc:
            msg = f"{self.service} request failed: {type(exc).__name__}"
            raise self.error(msg) from exc
        self._check_auth(response)
        if not response.is_success:
            self.logger.warning(
                "%s %s returned HTTP %s: %s",
                self.service,
                path,
                response.status_code,
                response.text[:_LOGGED_BODY_LENGTH],
            )
            msg = f"{self.service} returned HTTP {response.status_code}."
            raise self.error(msg)
        try:
            return response.json()
        except ValueError as exc:
            msg = f"{self.service} response was not valid JSON."
            raise self.error(msg) from exc
