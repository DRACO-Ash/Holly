"""A read-only client for the Unified Data Library (UDL), over HTTPS with Basic auth.

Errors carry a short message of Holly's own: UDL's response body goes to the server log,
never back to a browser.
"""

import logging
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any, Self

import httpx2

from app.config import get_settings
from app.services.api_client import ApiClient

logger = logging.getLogger(__name__)

UDLRecord = dict[str, Any]
QueryValue = str | int | float | bool


class UDLClientError(Exception):
    """Raised when a UDL request fails or returns an unexpected response."""


class UDLAuthError(UDLClientError):
    """Raised when UDL rejects the supplied credentials."""


def _format_epoch(dt: datetime) -> str:
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _after(dt: datetime) -> str:
    # UDL accepts only `>` as the interval operator on these endpoints (`>=` is rejected).
    # The microsecond between the two never matters in practice.
    return f">{_format_epoch(dt)}"


def _present(**params: QueryValue | None) -> dict[str, QueryValue]:
    """The query parameters that were supplied, under their UDL names."""
    return {name: value for name, value in params.items() if value is not None}


class UDLClient(ApiClient):
    service = "UDL"
    error = UDLClientError
    logger = logger

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float | None = None,
        verify_ssl: bool | None = None,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.udl_base_url).rstrip("/")
        self._username = username if username is not None else settings.udl_username
        self._password = (
            password if password is not None else settings.udl_password.get_secret_value()
        )
        self._timeout = timeout if timeout is not None else settings.udl_request_timeout_seconds
        self._verify_ssl = verify_ssl if verify_ssl is not None else settings.udl_verify_ssl
        self._transport = transport
        self._client: httpx2.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        if not self._username or not self._password:
            msg = "UDL credentials are not configured (UDL_USERNAME / UDL_PASSWORD)."
            raise UDLClientError(msg)
        client = httpx2.AsyncClient(
            base_url=self._base_url,
            auth=httpx2.BasicAuth(self._username, self._password),
            timeout=self._timeout,
            verify=self._verify_ssl,
            transport=self._transport,
        )
        self._client = await client.__aenter__()
        return self

    def _check_auth(self, response: httpx2.Response) -> None:
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            msg = "UDL rejected credentials (401)."
            raise UDLAuthError(msg)

    async def get_elsets(
        self,
        epoch_gte: datetime,
        sat_no: int | None = None,
        data_mode: str | None = None,
        max_results: int | None = None,
    ) -> list[UDLRecord]:
        params = _present(satNo=sat_no, dataMode=data_mode, maxResults=max_results)
        return await self._get_list("/elset", {"epoch": _after(epoch_gte), **params})

    async def get_maneuvers(
        self,
        event_start_time_gte: datetime,
        sat_no: int | None = None,
        data_mode: str | None = None,
        max_results: int | None = None,
    ) -> list[UDLRecord]:
        params = _present(satNo=sat_no, dataMode=data_mode, maxResults=max_results)
        return await self._get_list(
            "/maneuver", {"eventStartTime": _after(event_start_time_gte), **params}
        )

    async def get_notifications(
        self,
        msg_type: str | None = None,
        created_at_gte: datetime | None = None,
        data_mode: str | None = None,
        source: str | None = None,
        max_results: int | None = None,
    ) -> list[UDLRecord]:
        params = _present(
            msgType=msg_type,
            createdAt=_after(created_at_gte) if created_at_gte is not None else None,
            dataMode=data_mode,
            source=source,
            maxResults=max_results,
        )
        return await self._get_list("/notification", params)

    async def _get_list(self, path: str, params: dict[str, QueryValue]) -> list[UDLRecord]:
        data = await self._get_json(path, params)
        if not isinstance(data, list):
            msg = f"UDL response was not a list (got {type(data).__name__})."
            raise UDLClientError(msg)
        return data
