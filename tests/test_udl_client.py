"""The read-only UDL client: the queries it sends, and that every failure becomes a short
error of Holly's own while UDL's response body stays in the server log."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import httpx2
import pytest

from app.services.udl_client import (
    UDLAuthError,
    UDLClient,
    UDLClientError,
    _format_epoch,
)

Captured = dict[str, Any]


def recording_transport(captured: Captured, response: httpx2.Response) -> httpx2.MockTransport:
    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        captured["auth_header"] = request.headers.get("authorization")
        return response

    return httpx2.MockTransport(handler)


# Test-only credentials, never sent anywhere: every request goes to a mock transport.
USER, KEY = "user", "pw"
UDL_ENV = {"UDL_USERNAME": "analyst", "UDL_PASSWORD": KEY, "UDL_BASE_URL": "https://u.test/"}


def client_for(transport: httpx2.MockTransport) -> UDLClient:
    return UDLClient(
        base_url="https://udl.test/udl/", username=USER, password=KEY, transport=transport
    )


def test_format_epoch_naive_datetime() -> None:
    dt = datetime(2025, 1, 15, 12, 30, 45, 123456)  # noqa: DTZ001  UDL's naive-UTC form
    assert _format_epoch(dt) == "2025-01-15T12:30:45.123456Z"


def test_format_epoch_aware_datetime_converts_to_utc() -> None:
    dt = datetime(2025, 1, 15, 14, 30, 45, 0, tzinfo=timezone(timedelta(hours=2)))
    assert _format_epoch(dt) == "2025-01-15T12:30:45.000000Z"


async def test_get_elsets_sends_correct_request_and_returns_records() -> None:
    expected_records = [{"id": "abc-123", "satNo": 25544, "epoch": "2025-01-15T00:00:00.000000Z"}]
    captured: Captured = {}
    transport = recording_transport(captured, httpx2.Response(200, json=expected_records))
    async with client_for(transport) as client:
        records = await client.get_elsets(
            epoch_gte=datetime(2025, 1, 1, tzinfo=UTC), sat_no=25544, max_results=100
        )
    assert records == expected_records
    assert captured["path"] == "/udl/elset"
    assert captured["params"] == {
        "epoch": ">2025-01-01T00:00:00.000000Z",
        "satNo": "25544",
        "maxResults": "100",
    }
    assert captured["auth_header"].startswith("Basic ")


async def test_get_maneuvers_queries_by_event_start_time() -> None:
    captured: Captured = {}
    transport = recording_transport(captured, httpx2.Response(200, json=[]))
    async with client_for(transport) as client:
        await client.get_maneuvers(
            event_start_time_gte=datetime(2026, 6, 1, tzinfo=UTC), data_mode="REAL"
        )
    assert captured["path"] == "/udl/maneuver"
    assert captured["params"] == {
        "eventStartTime": ">2026-06-01T00:00:00.000000Z",
        "dataMode": "REAL",
    }


async def test_get_notifications_sends_only_the_filters_given() -> None:
    captured: Captured = {}
    transport = recording_transport(captured, httpx2.Response(200, json=[]))
    async with client_for(transport) as client:
        await client.get_notifications(
            msg_type="TACREP_NOTSO",
            created_at_gte=datetime(2026, 6, 1, tzinfo=UTC),
            source="erudition",
            max_results=5,
        )
        first = dict(captured["params"])
        await client.get_notifications()
    assert captured["path"] == "/udl/notification"
    assert first == {
        "msgType": "TACREP_NOTSO",
        "createdAt": ">2026-06-01T00:00:00.000000Z",
        "source": "erudition",
        "maxResults": "5",
    }
    assert captured["params"] == {}


async def test_get_elsets_raises_auth_error_on_401() -> None:
    transport = httpx2.MockTransport(lambda _request: httpx2.Response(401, text="Unauthorized"))
    with pytest.raises(UDLAuthError):
        async with client_for(transport) as client:
            await client.get_elsets(epoch_gte=datetime(2025, 1, 1, tzinfo=UTC))


async def test_an_upstream_error_body_is_logged_not_returned(
    caplog: pytest.LogCaptureFixture,
) -> None:
    transport = httpx2.MockTransport(
        lambda _request: httpx2.Response(500, text="server boom: internal detail")
    )
    with pytest.raises(UDLClientError) as raised:
        async with client_for(transport) as client:
            await client.get_elsets(epoch_gte=datetime(2025, 1, 1, tzinfo=UTC))
    assert str(raised.value) == "UDL returned HTTP 500."
    assert "internal detail" in caplog.text


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx2.Response(200, json={"unexpected": "object"}), "not a list"),
        (httpx2.Response(200, text="<html>maintenance</html>"), "not valid JSON"),
    ],
)
async def test_an_unexpected_body_is_a_client_error(
    response: httpx2.Response, message: str
) -> None:
    transport = httpx2.MockTransport(lambda _request: response)
    with pytest.raises(UDLClientError, match=message):
        async with client_for(transport) as client:
            await client.get_elsets(epoch_gte=datetime(2025, 1, 1, tzinfo=UTC))


async def test_a_transport_failure_is_a_client_error_naming_only_its_type() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        msg = "connect failed to 10.1.2.3"
        raise httpx2.ConnectError(msg, request=request)

    with pytest.raises(UDLClientError, match=r"^UDL request failed: ConnectError$"):
        async with client_for(httpx2.MockTransport(handler)) as client:
            await client.get_elsets(epoch_gte=datetime(2025, 1, 1, tzinfo=UTC))


async def test_missing_credentials_raises_on_enter() -> None:
    with pytest.raises(UDLClientError, match="credentials"):
        async with UDLClient(username="", password=""):
            pass


async def test_a_query_outside_the_context_manager_is_refused() -> None:
    client = UDLClient(username=USER, password=KEY)
    with pytest.raises(UDLClientError, match="async context manager"):
        await client.get_elsets(epoch_gte=datetime(2025, 1, 1, tzinfo=UTC))


def test_unset_arguments_come_from_the_settings(settings_env: Any) -> None:
    settings_env(**UDL_ENV)
    client = UDLClient()
    assert client._base_url == "https://u.test"
    assert (client._username, client._password) == ("analyst", KEY)
    assert client._verify_ssl is True
