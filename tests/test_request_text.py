"""Text PostgreSQL cannot store, above all a NUL, is refused at the request boundary with a 422,
before any query, assistant call or write. JSON carries a NUL as the six-character escape
\\u0000, a query string as %00 and a multipart form as the raw byte."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

import httpx2
import pytest
from pydantic import BaseModel, ValidationError

from app.api.v1.routes import procedures
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest
from app.schemas.event_timer import EventTimerCreate
from app.schemas.notification import NotificationIngestRequest
from app.schemas.shift import ShiftNoteCreate, ShiftNoteUpdate
from fakes import FakeSession, make_user

UseSession = Callable[[FakeSession], FakeSession]
SignIn = Callable[[User], User]

NUL = "\x00"
TARGET = "2030-01-01T00:00:00Z"
UNSTORABLE = "holds a character Holly cannot store"


@pytest.mark.parametrize(
    ("model", "body"),
    [
        (LoginRequest, {"username": f"ali{NUL}ce", "password": "unused-in-tests"}),
        (LoginRequest, {"username": "alice", "password": f"unused-in-tests{NUL}"}),
        (NotificationIngestRequest, {"msg_type": f"TACREP_NOTSO{NUL}"}),
        (NotificationIngestRequest, {"data_mode": f"REAL{NUL}"}),
        (NotificationIngestRequest, {"source": f"JCO{NUL}"}),
        (EventTimerCreate, {"label": f"Window{NUL}", "target_time": TARGET}),
        (EventTimerCreate, {"label": "Window", "target_time": TARGET, "event_key": f"k{NUL}"}),
        (ShiftNoteCreate, {"raw_text": f"Handover done{NUL}"}),
        (ShiftNoteUpdate, {"polished_text": f"Handover done{NUL}"}),
        (procedures._UploadFields, {"name": f"Handover checklist{NUL}"}),
        (procedures._UploadFields, {"name": "Handover checklist", "description": f"d{NUL}"}),
    ],
    ids=[
        "username",
        "password",
        "ingest-msg-type",
        "ingest-data-mode",
        "ingest-source",
        "timer-label",
        "timer-event-key",
        "note",
        "polished-note",
        "procedure-name",
        "procedure-description",
    ],
)
def test_every_request_text_field_refuses_what_holly_cannot_store(
    model: type[BaseModel], body: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError, match=UNSTORABLE):
        model.model_validate(body)


async def test_a_sign_in_holding_a_nul_is_refused_before_any_query(
    api: httpx2.AsyncClient, use_session: UseSession
) -> None:
    session = use_session(FakeSession())
    body = {"username": f"ali{NUL}ce", "password": "unused-in-tests"}
    assert (await api.post("/api/v1/auth/login", json=body)).status_code == 422
    session.execute.assert_not_awaited()


async def test_a_note_holding_a_nul_never_reaches_the_assistant(
    api: httpx2.AsyncClient,
    use_session: UseSession,
    sign_in: SignIn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sign_in(make_user())
    session = use_session(FakeSession())
    assistant = AsyncMock()
    monkeypatch.setattr("app.services.shift_log.call_claude", assistant)
    response = await api.post("/api/v1/shift-log/notes", json={"raw_text": f"Handover {NUL}"})
    assert response.status_code == 422
    assistant.assert_not_awaited()
    assert session.added == []


@pytest.mark.parametrize(
    ("path", "role"),
    [
        ("/api/v1/notifications?msg_type=%00", UserRole.ANALYST),
        ("/api/v1/notifications?event_type=%00", UserRole.ANALYST),
        ("/api/v1/notifications?status=%00", UserRole.ANALYST),
        ("/api/v1/maneuvers?mnvr_type=%00", UserRole.ANALYST),
        ("/api/v1/mattermost/messages?channel_id=%00", UserRole.ANALYST),
        ("/api/v1/mattermost/messages?user_id=%00", UserRole.ANALYST),
        ("/api/v1/audit?action_type=%00", UserRole.ADMIN),
    ],
)
async def test_a_query_holding_a_nul_is_refused_before_any_query(
    api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, path: str, role: UserRole
) -> None:
    sign_in(make_user(role=role))
    session = use_session(FakeSession())
    assert (await api.get(path)).status_code == 422
    session.execute.assert_not_awaited()


def multipart(name: str, filename: str, content_type: str) -> tuple[bytes, dict[str, str]]:
    """An upload whose form name and file part headers are written byte for byte."""
    boundary = "holly-test-boundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="name"\r\n\r\n'
        f"{name}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
        "Step 1: confirm the feed is live.\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    return body, {"Content-Type": f"multipart/form-data; boundary={boundary}"}


@pytest.mark.parametrize(
    ("name", "filename", "content_type"),
    [
        (f"Handover{NUL}", "handover.txt", "text/plain"),
        ("Handover", f"hand{NUL}over.txt", "text/plain"),
        ("Handover", "handover.txt", f"text/plain{NUL}"),
    ],
    ids=["name", "filename", "content-type"],
)
async def test_an_upload_holding_a_nul_is_refused_and_never_stored(
    api: httpx2.AsyncClient,
    use_session: UseSession,
    sign_in: SignIn,
    name: str,
    filename: str,
    content_type: str,
) -> None:
    sign_in(make_user())
    session = use_session(FakeSession())
    body, headers = multipart(name, filename, content_type)
    response = await api.post("/api/v1/procedures", content=body, headers=headers)
    assert response.status_code == 422
    assert session.added == []
