"""A request id on every response but a CORS preflight, and every log line. A client's id is
reused only when it is a plain token; anything else is replaced, so a caller cannot write
arbitrary text into the logs or the response headers."""

import json
import uuid
from collections.abc import Callable

import httpx2
import pytest
from fastapi import FastAPI

from app.core.logging import log_event
from app.core.request_id import REQUEST_ID_HEADER, choose_request_id, current_request_id
from fakes import FakeSession

UseSession = Callable[[FakeSession], FakeSession]


@pytest.mark.parametrize(
    "incoming", ["abc-12345-test-correlation-id", "a", "trace.v1:part_2", "x" * 128]
)
def test_a_plain_token_is_kept(incoming: str) -> None:
    assert choose_request_id(incoming) == incoming


@pytest.mark.parametrize(
    "incoming", [None, "", "x" * 129, "has space", "line\nbreak", 'quote"', "<script>"]
)
def test_anything_else_is_replaced_with_a_fresh_uuid(incoming: str | None) -> None:
    replacement = choose_request_id(incoming)
    assert replacement != incoming
    assert uuid.UUID(replacement).version == 4


def test_outside_a_request_the_id_is_a_dash() -> None:
    assert current_request_id() == "-"


async def test_response_carries_a_generated_request_id(
    api: httpx2.AsyncClient, use_session: UseSession
) -> None:
    use_session(FakeSession([None]))
    response = await api.get("/api/v1/health")
    assert uuid.UUID(response.headers[REQUEST_ID_HEADER]).version == 4


async def test_request_id_is_echoed_when_supplied_by_client(
    api: httpx2.AsyncClient, use_session: UseSession
) -> None:
    use_session(FakeSession([None]))
    supplied = "abc-12345-test-correlation-id"
    response = await api.get("/api/v1/health", headers={REQUEST_ID_HEADER: supplied})
    assert response.headers[REQUEST_ID_HEADER] == supplied


async def test_a_log_line_written_during_a_request_carries_its_id(
    api_app: FastAPI, api: httpx2.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    def logs_an_event() -> dict[str, str]:
        log_event("probe.event", detail="seen")
        return {"status": "ok"}

    api_app.add_api_route("/logs-an-event", logs_an_event, methods=["GET"])
    await api.get("/logs-an-event", headers={REQUEST_ID_HEADER: "trace-7"})
    lines = [json.loads(text) for text in capsys.readouterr().out.splitlines()]
    [line] = [line for line in lines if "event" in line]
    assert line == {
        "event": "probe.event",
        "service": "holly",
        "request_id": "trace-7",
        "detail": "seen",
    }
