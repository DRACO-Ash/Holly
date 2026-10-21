"""Claude's evaluation of a notification: the prompt built from the notification, its related
maneuvers, recent team chat and the uploaded procedures; the queries behind it; how a reply is
validated, retried once and stored; and that concurrent requests for one notification share a
single run. Claude is replaced by a recorder that answers from a queue, so nothing leaves the
process, and each query is compiled for PostgreSQL to read the SQL the service would send.

Every value here is synthetic: sequential ids, satellite 99999 (and 99998 where two are
needed) or TEST-SAT, Example names and hosts under the reserved .example domain."""

import asyncio
import itertools
import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, NoReturn

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.models.assistant_evaluation import AssistantEvaluation
from app.models.maneuver import Maneuver
from app.models.mattermost_message import MattermostMessage
from app.models.notification import Notification
from app.models.procedure import Procedure
from app.schemas.assistant import AssistantEvaluationRead
from app.services import assistant, claude
from app.services.assistant import (
    EvaluationOutcome,
    NotificationNotFoundError,
    display_value,
    evaluate_once,
    get_latest_evaluation,
    parse_evaluation,
)
from app.services.claude import AssistantError, ClaudeReply
from app.services.disclosure import NOT_CLEARED
from app.services.procedure_storage import write_file
from fakes import NOW, FakeSession, rows_result, scalar_result

SettingsEnv = Callable[..., None]

CONFIGURED_MODEL = "claude-configured-model"
REPLY_MODEL = "claude-reply-model"
SUMMARY = "A close approach involving TEST-SAT is predicted."
EMPTY_EVALUATION = {
    "summary": "Assistant evaluation could not be generated.",
    "applicable_procedures": [],
    "next_actions": [],
    "open_questions": [],
}
NO_MANEUVERS = "RELATED MANEUVERS: (none for the satellite(s) in this notification)"
CLOSING_LINE = "Return the JSON object as specified. No text before or after the JSON."
NO_PREVIEW = "  Content: <binary or unsupported preview type; operator should view file>"

POSTGRESQL = postgresql.dialect()  # type: ignore[no-untyped-call]

_SERIALS = itertools.count(1)


def synthetic_id() -> uuid.UUID:
    """The next obviously synthetic id: 00000000-0000-4000-8000-000000000001, then 2, and so on."""
    return uuid.UUID(f"00000000-0000-4000-8000-{next(_SERIALS):012d}")


@pytest.fixture(autouse=True)
def assistant_settings(settings_env: SettingsEnv) -> None:
    """Pin every setting the service reads, whatever a local .env file holds."""
    settings_env(
        ANTHROPIC_MODEL=CONFIGURED_MODEL,
        ANTHROPIC_MAX_TOKENS="4096",
        MATTERMOST_PROMPT_WINDOW_HOURS="6",
        MATTERMOST_MAX_MESSAGES_IN_PROMPT="30",
    )


def make_notification(**fields: Any) -> Notification:
    """A notification row as the database returns it, with only the given fields set and a
    marking cleared for the assistant unless one is given."""
    fields.setdefault("classification_marking", "U")
    return Notification(id=synthetic_id(), raw={}, created_at=NOW, updated_at=NOW, **fields)


def make_maneuver(**fields: Any) -> Maneuver:
    return Maneuver(id=synthetic_id(), raw={}, **fields)


def chat_message(posted_at: datetime, text: str, **fields: Any) -> MattermostMessage:
    values: dict[str, Any] = {
        "id": synthetic_id(),
        "mm_post_id": "test-post",
        "channel_id": "test-channel-1",
        "channel_name": "example-ops",
        "user_id": "test-user-1",
        "user_display_name": "Example Analyst",
        "posted_at": posted_at,
        "message": text,
        "raw": {},
    }
    return MattermostMessage(**(values | fields))


def make_procedure(
    name: str,
    *,
    filename: str = "procedure.md",
    content_type: str = "text/markdown",
    description: str | None = None,
) -> Procedure:
    return Procedure(
        id=synthetic_id(),
        name=name,
        description=description,
        filename=filename,
        content_type=content_type,
        size_bytes=0,
        file_hash="0" * 64,
        created_at=NOW,
        updated_at=NOW,
    )


def reply_body(**fields: Any) -> dict[str, Any]:
    """An evaluation that validates, with any field replaced."""
    body: dict[str, Any] = {
        "summary": SUMMARY,
        "applicable_procedures": [],
        "next_actions": [
            {
                "action": "Notify the duty officer",
                "urgency": "high",
                "deadline": None,
                "rationale": "Step 1 of the example procedure.",
            }
        ],
        "open_questions": [],
    }
    return body | fields


def reply(text: str, *, truncated: bool = False) -> ClaudeReply:
    return ClaudeReply(text=text, model=REPLY_MODEL, truncated=truncated)


def valid_reply() -> ClaudeReply:
    return reply(json.dumps(reply_body()))


class FakeClaude:
    """Stands in for call_claude: records each request, then gives the next queued answer (a
    reply, or an AssistantError to raise). A request with nothing queued fails the test."""

    def __init__(self, *answers: ClaudeReply | AssistantError) -> None:
        self.answers = list(answers)
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self, system_prompt: str, user_message: str, *, max_tokens: int, purpose: str
    ) -> ClaudeReply:
        self.calls.append(
            {
                "system": system_prompt,
                "user": user_message,
                "max_tokens": max_tokens,
                "purpose": purpose,
            }
        )
        answer = self.answers.pop(0)
        if isinstance(answer, AssistantError):
            raise answer
        return answer


class HeldClaude(FakeClaude):
    """A FakeClaude that holds every request until the test releases it, so runs overlap."""

    def __init__(self, *answers: ClaudeReply | AssistantError) -> None:
        super().__init__(*answers)
        self.release = asyncio.Event()
        self._arrived: asyncio.Queue[None] = asyncio.Queue()

    async def __call__(
        self, system_prompt: str, user_message: str, *, max_tokens: int, purpose: str
    ) -> ClaudeReply:
        self._arrived.put_nowait(None)
        await self.release.wait()
        return await super().__call__(
            system_prompt, user_message, max_tokens=max_tokens, purpose=purpose
        )

    async def arrivals(self, count: int) -> None:
        """Wait, briefly, until `count` requests are being held."""
        for _ in range(count):
            await asyncio.wait_for(self._arrived.get(), timeout=1)


def use_claude[C: FakeClaude](monkeypatch: pytest.MonkeyPatch, fake: C) -> C:
    monkeypatch.setattr(assistant, "call_claude", fake)
    return fake


def _fill_generated_columns(row: AssistantEvaluation) -> None:
    """What refresh reads back for a new row: the id and evaluated_at the database assigned."""
    row.id = synthetic_id()
    row.evaluated_at = NOW


def evaluation_session(
    notification: Notification | None,
    *,
    procedures: Sequence[Procedure] = (),
    maneuvers: Sequence[Maneuver] | None = None,
    chat: Sequence[MattermostMessage] | None = (),
) -> FakeSession:
    """A session answering evaluate_notification's queries in the order it asks them: the
    notification, the procedures, the maneuvers and the team chat. None for the maneuvers or
    the chat means the service must not ask for them."""
    results: list[Any] = [scalar_result(notification), rows_result(list(procedures))]
    if maneuvers is not None:
        results.append(rows_result(list(maneuvers)))
    if chat is not None:
        results.append(rows_result(list(chat)))
    session = FakeSession(results)
    session.refresh.side_effect = _fill_generated_columns
    return session


def sent(session: FakeSession, index: int) -> tuple[str, dict[str, Any]]:
    """The session's `index`th query as PostgreSQL would receive it: the SQL on one line, and
    the bound values."""
    query = session.execute.await_args_list[index].args[0].compile(dialect=POSTGRESQL)
    return " ".join(str(query).split()), dict(query.params)


def open_sessions(monkeypatch: pytest.MonkeyPatch, *sessions: FakeSession) -> list[FakeSession]:
    """Have the service open `sessions` in turn as its own; returns those it opened, in order.
    Opening one more than was given fails the test."""
    waiting = list(sessions)
    opened: list[FakeSession] = []

    @asynccontextmanager
    async def open_session() -> AsyncIterator[FakeSession]:
        opened.append(waiting.pop(0))
        yield opened[-1]

    monkeypatch.setattr(assistant, "get_session_factory", lambda: open_session)
    return opened


async def evaluate(session: FakeSession, notification_id: uuid.UUID) -> EvaluationOutcome:
    return await assistant.evaluate_notification(session, notification_id)  # type: ignore[arg-type]


async def prompt_for(
    monkeypatch: pytest.MonkeyPatch, session: FakeSession, notification: Notification
) -> str:
    """The user message evaluate_notification sends Claude for the rows `session` holds."""
    fake = use_claude(monkeypatch, FakeClaude(valid_reply()))
    await evaluate(session, notification.id)
    [call] = fake.calls
    return str(call["user"])


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (datetime(2026, 6, 5, 10, 30, tzinfo=UTC), "2026-06-05T10:30:00+00:00"),
        (99999, "99999"),
        (0.0, "0.0"),
        ("TEST-SAT", "TEST-SAT"),
    ],
)
def test_display_value_gives_datetimes_in_iso_8601_and_anything_else_as_text(
    value: object, shown: str
) -> None:
    assert display_value(value) == shown


class TestParseEvaluation:
    def test_the_first_json_object_in_the_reply_is_validated_and_normalised(self) -> None:
        body = reply_body(
            next_actions=[
                {"action": "Notify the duty officer", "urgency": " HIGH ", "rationale": "Step 1."}
            ]
        )
        text = f"Here is my assessment:\n```json\n{json.dumps(body)}\n```\nAnything else?"
        evaluation = parse_evaluation(text, set())
        assert evaluation.summary == SUMMARY
        [action] = evaluation.next_actions
        assert (action.urgency, action.deadline) == ("high", None)

    @pytest.mark.parametrize(
        ("deadline", "kept"),
        [
            ("2026-01-02T06:00:00Z", "2026-01-02T06:00:00Z"),
            (" 2026-01-02T06:00:00+00:00 ", "2026-01-02T06:00:00+00:00"),
            ("by end of shift", None),
            ("2026-01-02", "2026-01-02"),
            # A time of day with no offset would read as the browser's own zone.
            ("2026-07-02T06:00", None),
            ("2026-07-02T06:00+01:00", "2026-07-02T06:00+01:00"),
            ("tomorrow", None),
            ("", None),
        ],
    )
    def test_a_deadline_is_kept_only_as_a_timestamp(self, deadline: str, kept: str | None) -> None:
        body = reply_body(
            next_actions=[
                {
                    "action": "Notify the duty officer",
                    "urgency": "high",
                    "deadline": deadline,
                    "rationale": "Step 1.",
                }
            ]
        )
        [action] = parse_evaluation(json.dumps(body), set()).next_actions
        assert action.deadline == kept

    def test_a_procedure_the_prompt_did_not_supply_is_dropped(self) -> None:
        known = str(synthetic_id())
        body = reply_body(
            applicable_procedures=[
                {"procedure_id": known, "name": "Example procedure", "reason": "Predicted."},
                {"procedure_id": "test-invented-id", "name": "Example drill", "reason": "Guess."},
            ]
        )
        evaluation = parse_evaluation(json.dumps(body), {known})
        assert [(p.procedure_id, p.name) for p in evaluation.applicable_procedures] == [
            (known, "Example procedure"),
            (None, "Example drill"),
        ]

    @pytest.mark.parametrize(
        ("body", "errors"),
        [
            pytest.param(
                {k: v for k, v in reply_body().items() if k != "summary"}, 1, id="no-summary"
            ),
            pytest.param(reply_body(summary="s" * 4001), 1, id="summary-too-long"),
            pytest.param(
                reply_body(
                    next_actions=[{"action": "Panic", "urgency": "critical", "rationale": ""}]
                ),
                1,
                id="unknown-urgency",
            ),
            pytest.param(
                reply_body(next_actions=[{"action": "Panic", "urgency": 3, "rationale": ""}]),
                1,
                id="urgency-not-text",
            ),
            pytest.param(
                reply_body(next_actions=[{"urgency": "low"}]), 2, id="action-missing-fields"
            ),
            pytest.param(reply_body(open_questions=["Why?"] * 21), 1, id="too-many-open-questions"),
        ],
    )
    def test_a_reply_of_the_wrong_shape_is_refused_as_retryable(
        self, body: dict[str, Any], errors: int
    ) -> None:
        with pytest.raises(AssistantError) as raised:
            parse_evaluation(json.dumps(body), set())
        assert str(raised.value) == (
            f"Model response did not match the evaluation schema ({errors} errors)"
        )
        assert raised.value.persistent is False
        assert isinstance(raised.value.__cause__, ValidationError)

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param(reply_body(summary="nul \u0000 inside"), id="summary"),
            pytest.param(
                reply_body(
                    next_actions=[{"action": "Hold \u0000", "urgency": "low", "rationale": ""}]
                ),
                id="an-action",
            ),
            pytest.param(reply_body(open_questions=["Why \u0000?"]), id="an-open-question"),
        ],
    )
    def test_a_reply_holding_a_character_postgresql_cannot_store_is_refused_as_retryable(
        self, body: dict[str, Any]
    ) -> None:
        text = json.dumps(body)
        assert "\\u0000" in text, "the model writes the NUL as an escape of six plain characters"
        with pytest.raises(AssistantError) as raised:
            parse_evaluation(text, set())
        assert str(raised.value) == "Model response held a character Holly cannot store"
        assert raised.value.persistent is False

    def test_a_reply_without_a_json_object_is_refused(self) -> None:
        with pytest.raises(AssistantError, match=r"^Model response contained no JSON object$"):
            parse_evaluation("Notify the duty officer, then release a NOTSO.", set())


class TestThePrompt:
    async def test_a_bare_notification_gets_the_skeleton_prompt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        session = evaluation_session(notification)
        prompt = await prompt_for(monkeypatch, session, notification)
        assert prompt == "\n\n".join(
            [
                "NOTIFICATION:\n  Notice: TEST-NOTSO-1",
                "",
                NO_MANEUVERS,
                "AVAILABLE PROCEDURES: (none uploaded)",
                "",
                CLOSING_LINE,
            ]
        )
        assert session.execute.await_count == 3

    async def test_the_notification_shows_each_field_that_is_set_in_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notification = make_notification(
            notso_identifier="TEST-NOTSO-1",
            msg_type="TEST_MSG",
            event_type="TEST_EVENT",
            event_class="Example close approach",
            status="ACTIVE",
            subject="Example subject",
            description="",
            region=None,
            company_name="Example Operator",
            publish_date=datetime(2026, 6, 5, 10, 0, tzinfo=UTC),
            effective_until=datetime(2026, 6, 6, 10, 0, tzinfo=UTC),
            udl_created_at=datetime(2026, 6, 5, 10, 5, tzinfo=UTC),
            sat_no=99999,
            sat_ids=["99999", "99998"],
            notso_link="https://notso.example/test-1",
        )
        session = evaluation_session(notification, maneuvers=[])
        prompt = await prompt_for(monkeypatch, session, notification)
        assert prompt.startswith(
            "NOTIFICATION:\n"
            "  Notice: TEST-NOTSO-1\n"
            "  Message type: TEST_MSG\n"
            "  Event type: TEST_EVENT\n"
            "  Event class: Example close approach\n"
            "  Status: ACTIVE\n"
            "  Subject: Example subject\n"
            "  Company: Example Operator\n"
            "  Published: 2026-06-05T10:00:00+00:00\n"
            "  Effective until: 2026-06-06T10:00:00+00:00\n"
            "  UDL created: 2026-06-05T10:05:00+00:00\n"
            "  Satellite: 99999\n"
            "  Satellites: 99999, 99998\n"
            "  Source link: https://notso.example/test-1\n\n"
        )
        assert NO_MANEUVERS in prompt

    async def test_satellite_ids_stored_as_numbers_still_reach_the_prompt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # UDL may send SatIds as numbers, and older rows hold them so.
        notification = make_notification(notso_identifier="TEST-NOTSO-1", sat_ids=[99999, 99998])
        session = evaluation_session(notification, maneuvers=[])
        prompt = await prompt_for(monkeypatch, session, notification)
        assert "  Satellites: 99999, 99998\n" in prompt

    @pytest.mark.parametrize("sat_ids", [None, [], ["TEST-SAT"]])
    async def test_without_a_satellite_number_no_maneuvers_are_looked_up(
        self, monkeypatch: pytest.MonkeyPatch, sat_ids: list[str] | None
    ) -> None:
        notification = make_notification(notso_identifier="TEST-NOTSO-1", sat_ids=sat_ids)
        session = evaluation_session(notification)
        prompt = await prompt_for(monkeypatch, session, notification)
        assert session.execute.await_count == 3
        assert NO_MANEUVERS in prompt

    async def test_related_maneuvers_show_the_fields_they_carry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notification = make_notification(notso_identifier="TEST-NOTSO-1", sat_no=99999)
        maneuvers = [
            make_maneuver(
                sat_no=99999,
                event_start_time=datetime(2026, 6, 4, 8, 0, tzinfo=UTC),
                mnvr_type="TEST_TYPE",
                maneuver_status="COMPLETED",
                delta_v=0.0,
                source="test-source",
                description="  Example burn, no change to the approach.  ",
            ),
            make_maneuver(
                sat_no=99999,
                event_stop_time=datetime(2026, 6, 3, 9, 0, tzinfo=UTC),
                mnvr_type="",
                description="",
            ),
        ]
        session = evaluation_session(notification, maneuvers=maneuvers)
        prompt = await prompt_for(monkeypatch, session, notification)
        assert (
            "\n\nRELATED MANEUVERS (same satellite, last 30 days):\n"
            "  - Sat 99999 | start=2026-06-04T08:00:00+00:00 | type=TEST_TYPE"
            " | status=COMPLETED | deltaV=0.0 | source=test-source\n"
            "    Example burn, no change to the approach.\n"
            "  - Sat 99999 | stop=2026-06-03T09:00:00+00:00\n\n"
        ) in prompt

    async def test_team_chat_reads_oldest_first_with_names_falling_back_to_ids(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        chat = [  # newest first, as the query returns them
            chat_message(
                datetime(2026, 6, 5, 11, 45, tzinfo=UTC), "Escalated to\nthe duty officer. "
            ),
            chat_message(
                datetime(2026, 6, 5, 11, 30, tzinfo=UTC),
                "Anyone seen the new NOTSO?",
                channel_name=None,
                channel_id="test-channel-2",
                user_display_name=None,
                user_id="test-user-2",
            ),
        ]
        session = evaluation_session(notification, chat=chat)
        prompt = await prompt_for(monkeypatch, session, notification)
        assert (
            f"{NO_MANEUVERS}\n\n"
            "TEAM CHAT (last 6 hours):\n"
            "- [2026-06-05 11:30] #test-channel-2 @test-user-2: Anyone seen the new NOTSO?\n"
            "- [2026-06-05 11:45] #example-ops @Example Analyst: Escalated to the duty officer.\n\n"
            "AVAILABLE PROCEDURES: (none uploaded)"
        ) in prompt

    @pytest.mark.parametrize(("length", "shown"), [(500, "x" * 500), (501, "x" * 500 + "...")])
    async def test_a_chat_message_is_cut_after_500_characters(
        self, monkeypatch: pytest.MonkeyPatch, length: int, shown: str
    ) -> None:
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        session = evaluation_session(notification, chat=[chat_message(NOW, "x" * length)])
        prompt = await prompt_for(monkeypatch, session, notification)
        assert f"@Example Analyst: {shown}\n\n" in prompt

    @pytest.mark.parametrize(
        "setting", ["MATTERMOST_PROMPT_WINDOW_HOURS", "MATTERMOST_MAX_MESSAGES_IN_PROMPT"]
    )
    async def test_team_chat_is_left_out_when_either_chat_setting_is_zero(
        self, monkeypatch: pytest.MonkeyPatch, settings_env: SettingsEnv, setting: str
    ) -> None:
        settings_env(**{setting: "0"})
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        session = evaluation_session(notification, chat=None)
        prompt = await prompt_for(monkeypatch, session, notification)
        assert session.execute.await_count == 2
        assert "TEAM CHAT" not in prompt

    async def test_each_procedure_is_shown_with_its_description_and_content(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        guide = make_procedure("Example procedure", description="What to do for an approach")
        write_file(guide.id, guide.filename, b"1. Notify the duty officer.\n2. Release a NOTSO.")
        handover = make_procedure(
            "Example handover", filename="handover.txt", content_type="text/plain"
        )
        write_file(handover.id, handover.filename, b"Read the log.")
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        session = evaluation_session(notification, procedures=[guide, handover])
        prompt = await prompt_for(monkeypatch, session, notification)
        assert (
            "\n\nAVAILABLE PROCEDURES:\n\n"
            f"PROCEDURE id={guide.id} name='Example procedure'\n"
            "  Description: What to do for an approach\n"
            "  Content:\n"
            "1. Notify the duty officer.\n2. Release a NOTSO.\n\n"
            f"PROCEDURE id={handover.id} name='Example handover'\n"
            "  Content:\n"
            "Read the log.\n\n"
        ) in prompt

    @pytest.mark.parametrize(
        ("content_type", "stored"),
        [("application/pdf", True), ("text/markdown", False)],
        ids=["unsupported-type", "file-missing"],
    )
    async def test_a_procedure_without_a_text_preview_sends_the_operator_to_the_file(
        self, monkeypatch: pytest.MonkeyPatch, content_type: str, stored: bool
    ) -> None:
        procedure = make_procedure(
            "Example checklist", filename="checklist.pdf", content_type=content_type
        )
        if stored:
            write_file(procedure.id, procedure.filename, b"%PDF-1.7")
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        session = evaluation_session(notification, procedures=[procedure])
        prompt = await prompt_for(monkeypatch, session, notification)
        assert f"PROCEDURE id={procedure.id} name='Example checklist'\n{NO_PREVIEW}\n\n" in prompt

    async def test_a_procedure_longer_than_the_preview_is_cut_and_marked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        preview_bytes = 64 * 1024
        procedure = make_procedure(
            "Example manual", filename="manual.txt", content_type="text/plain"
        )
        write_file(procedure.id, procedure.filename, b"a" * (preview_bytes + 1))
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        session = evaluation_session(notification, procedures=[procedure])
        prompt = await prompt_for(monkeypatch, session, notification)
        assert "  Content:\n" + "a" * preview_bytes + "\n  ... (truncated)\n\n" in prompt
        assert "a" * (preview_bytes + 1) not in prompt


class TestTheQueries:
    async def test_the_notification_is_found_by_id_and_procedures_read_oldest_first(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        session = evaluation_session(notification)
        await prompt_for(monkeypatch, session, notification)
        sql, params = sent(session, 0)
        assert sql.endswith("FROM notification WHERE notification.id = %(id_1)s::UUID")
        assert params == {"id_1": notification.id}
        sql, params = sent(session, 1)
        assert sql.endswith("FROM procedure ORDER BY procedure.created_at")
        assert params == {}

    async def test_maneuvers_are_read_for_each_satellite_once_within_30_days(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notification = make_notification(sat_no=99999, sat_ids=["99998", "TEST-SAT", "99999"])
        session = evaluation_session(notification, maneuvers=[])
        before = datetime.now(UTC)
        await prompt_for(monkeypatch, session, notification)
        after = datetime.now(UTC)
        sql, params = sent(session, 2)
        assert sql.endswith(
            "FROM maneuver WHERE maneuver.sat_no IN (__[POSTCOMPILE_sat_no_1]) "
            "AND maneuver.classification_marking IN (__[POSTCOMPILE_classification_marking_1]) "
            "AND (maneuver.event_start_time IS NULL OR maneuver.event_start_time >= "
            "%(event_start_time_1)s::TIMESTAMP WITH TIME ZONE) "
            "ORDER BY maneuver.event_start_time DESC NULLS LAST LIMIT %(param_1)s::INTEGER"
        )
        assert params["sat_no_1"] == [99999, 99998]
        # Only maneuvers whose marking is cleared for the assistant.
        assert params["classification_marking_1"] == ["U"]
        window = timedelta(days=30)
        assert before - window <= params["event_start_time_1"] <= after - window
        assert params["param_1"] == 10

    async def test_team_chat_is_the_newest_messages_inside_the_window(
        self, monkeypatch: pytest.MonkeyPatch, settings_env: SettingsEnv
    ) -> None:
        settings_env(MATTERMOST_PROMPT_WINDOW_HOURS="12", MATTERMOST_MAX_MESSAGES_IN_PROMPT="5")
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        session = evaluation_session(notification, chat=[chat_message(NOW, "Watching it.")])
        before = datetime.now(UTC)
        prompt = await prompt_for(monkeypatch, session, notification)
        after = datetime.now(UTC)
        sql, params = sent(session, 2)
        assert sql.endswith(
            "FROM mattermost_message WHERE mattermost_message.posted_at >= "
            "%(posted_at_1)s::TIMESTAMP WITH TIME ZONE "
            "ORDER BY mattermost_message.posted_at DESC LIMIT %(param_1)s::INTEGER"
        )
        window = timedelta(hours=12)
        assert before - window <= params["posted_at_1"] <= after - window
        assert params["param_1"] == 5
        assert "TEAM CHAT (last 12 hours):\n- [2026-06-05 12:00] #example-ops" in prompt


class TestEvaluateNotification:
    async def test_an_unknown_notification_raises_and_nothing_is_asked_or_stored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = use_claude(monkeypatch, FakeClaude())
        session = FakeSession([scalar_result(None)])
        missing = synthetic_id()
        with pytest.raises(NotificationNotFoundError, match=str(missing)):
            await evaluate(session, missing)
        assert fake.calls == []
        assert session.added == []
        session.flush.assert_not_awaited()

    async def test_a_valid_reply_is_stored_for_the_caller_to_commit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        procedure = make_procedure("Example procedure")
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        session = evaluation_session(notification, procedures=[procedure])
        cited = [
            {"procedure_id": str(procedure.id), "name": "Example procedure", "reason": "Due."},
            {"procedure_id": "test-invented-id", "name": "Example drill", "reason": "Guess."},
        ]
        body = reply_body(applicable_procedures=cited, open_questions=["Is the owner aware?"])
        fake = use_claude(monkeypatch, FakeClaude(reply(json.dumps(body))))
        outcome = await evaluate(session, notification.id)
        row = outcome.evaluation
        assert session.added == [row]
        session.flush.assert_awaited_once()
        session.commit.assert_not_awaited()
        assert outcome.persistent_failure is False
        assert (row.notification_id, row.error, row.model) == (notification.id, None, REPLY_MODEL)
        assert row.procedures_used == [str(procedure.id)]
        assert row.summary == SUMMARY
        assert row.structured == {
            "summary": SUMMARY,
            "applicable_procedures": [
                {"procedure_id": str(procedure.id), "name": "Example procedure", "reason": "Due."},
                {"procedure_id": None, "name": "Example drill", "reason": "Guess."},
            ],
            "next_actions": [
                {
                    "action": "Notify the duty officer",
                    "urgency": "high",
                    "deadline": None,
                    "rationale": "Step 1 of the example procedure.",
                }
            ],
            "open_questions": ["Is the owner aware?"],
        }
        [call] = fake.calls
        assert (call["purpose"], call["max_tokens"]) == ("assistant.evaluate", 4096)
        assert "You must respond with a single JSON object and nothing else." in call["system"]
        assert "Do not invent procedure ids." in call["system"]

    async def test_an_empty_summary_is_stored_as_no_summary_returned(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        use_claude(monkeypatch, FakeClaude(reply(json.dumps(reply_body(summary="")))))
        row = (await evaluate(evaluation_session(notification), notification.id)).evaluation
        assert row.summary == "No summary returned."
        assert row.structured["summary"] == ""
        assert row.error is None

    async def test_an_unusable_reply_is_retried_once_with_a_nudge(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        unusable = reply("Notify the duty officer, then release a NOTSO.")
        fake = use_claude(monkeypatch, FakeClaude(unusable, valid_reply()))
        outcome = await evaluate(evaluation_session(notification), notification.id)
        first, second = fake.calls
        assert second["user"].startswith(first["user"] + "\n\n")
        nudge = second["user"].removeprefix(first["user"])
        assert "Return only the JSON object described in the instructions" in nudge
        assert outcome.evaluation.error is None
        assert outcome.evaluation.summary == SUMMARY

    @pytest.mark.parametrize(
        ("unusable", "error"),
        [
            ("Notify the duty officer.", "Model response contained no JSON object"),
            (
                '{"next_actions": []}',
                "Model response did not match the evaluation schema (1 errors)",
            ),
            (
                '{"summary": "nul \\u0000 inside"}',
                "Model response held a character Holly cannot store",
            ),
        ],
    )
    async def test_a_second_unusable_reply_is_stored_as_the_error_with_no_advice(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        unusable: str,
        error: str,
    ) -> None:
        caplog.set_level(logging.INFO, logger=assistant.__name__)
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        fake = use_claude(monkeypatch, FakeClaude(reply(unusable), reply(unusable)))
        outcome = await evaluate(evaluation_session(notification), notification.id)
        assert len(fake.calls) == 2
        row = outcome.evaluation
        assert row.error == error
        assert row.structured == EMPTY_EVALUATION
        assert row.summary == "Assistant evaluation could not be generated."
        assert row.model == CONFIGURED_MODEL
        assert outcome.persistent_failure is False
        warnings = [
            record.getMessage()
            for record in caplog.records
            if record.name == assistant.__name__ and record.levelno == logging.WARNING
        ]
        assert warnings == [f"Assistant evaluation failed for {notification.id}: {error}"]

    @pytest.mark.parametrize(
        "failure",
        [
            AssistantError("Anthropic API error: overloaded"),
            AssistantError("The daily assistant token cap is spent.", persistent=True),
        ],
        ids=["transient", "persistent"],
    )
    async def test_a_failed_call_is_stored_without_a_retry(
        self, monkeypatch: pytest.MonkeyPatch, failure: AssistantError
    ) -> None:
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        fake = use_claude(monkeypatch, FakeClaude(failure))
        outcome = await evaluate(evaluation_session(notification), notification.id)
        assert len(fake.calls) == 1
        assert outcome.persistent_failure is failure.persistent
        assert outcome.evaluation.error == str(failure)
        assert outcome.evaluation.structured == EMPTY_EVALUATION

    async def test_a_truncated_reply_is_refused_without_a_retry(
        self, monkeypatch: pytest.MonkeyPatch, settings_env: SettingsEnv
    ) -> None:
        settings_env(ANTHROPIC_MAX_TOKENS="1000")
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        cut_short = reply('{"summary": "A close appro', truncated=True)
        fake = use_claude(monkeypatch, FakeClaude(cut_short))
        outcome = await evaluate(evaluation_session(notification), notification.id)
        [call] = fake.calls
        assert call["max_tokens"] == 1000
        assert outcome.evaluation.error == (
            "Model response was truncated at 1000 tokens before completing the JSON. "
            "Raise ANTHROPIC_MAX_TOKENS."
        )
        assert outcome.persistent_failure is False

    async def test_without_an_api_key_the_failure_is_persistent_and_nothing_is_sent(
        self, monkeypatch: pytest.MonkeyPatch, settings_env: SettingsEnv
    ) -> None:
        def never_sent(*_args: object) -> NoReturn:
            raise AssertionError("an evaluation without a key reached the Anthropic API")

        settings_env(ANTHROPIC_API_KEY="")
        monkeypatch.setattr(claude, "_create_message", never_sent)
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        outcome = await evaluate(evaluation_session(notification), notification.id)
        assert outcome.persistent_failure is True
        assert outcome.evaluation.error == "ANTHROPIC_API_KEY is not configured"
        assert outcome.evaluation.model == CONFIGURED_MODEL


class TestTheMarkingGate:
    @pytest.mark.parametrize("marking", ["U//TEST-NOT-CLEARED", None, "", "u", " U"])
    async def test_a_notice_whose_marking_is_not_cleared_is_never_sent(
        self, monkeypatch: pytest.MonkeyPatch, marking: str | None
    ) -> None:
        def never_sent(*_args: object) -> NoReturn:
            raise AssertionError("a notice that is not cleared reached the Anthropic API")

        monkeypatch.setattr(claude, "_create_message", never_sent)
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        notification.classification_marking = marking
        session = FakeSession([scalar_result(notification)])
        outcome = await evaluate(session, notification.id)
        row = outcome.evaluation
        # Only the notice was read: no procedures, maneuvers or chat were gathered for it.
        assert session.execute.await_count == 1
        assert session.added == [row]
        assert row.error == NOT_CLEARED
        assert (row.summary, row.structured, row.procedures_used) == (
            "Not evaluated.",
            EMPTY_EVALUATION,
            [],
        )
        assert outcome.persistent_failure is False
        # The dashboard reads it as withheld, a decision, not a failed evaluation.
        row.id, row.evaluated_at = uuid.uuid4(), NOW
        assert AssistantEvaluationRead.model_validate(row).withheld is True

    def test_a_failed_evaluation_is_not_withheld(self) -> None:
        read = AssistantEvaluationRead(
            id=uuid.uuid4(),
            notification_id=uuid.uuid4(),
            summary="",
            structured={},
            procedures_used=[],
            model="test-model",
            error="unparseable output",
            evaluated_at=NOW,
        )
        assert read.withheld is False
        assert read.model_dump()["withheld"] is False

    async def test_a_marking_the_data_owner_has_cleared_is_sent(
        self, monkeypatch: pytest.MonkeyPatch, settings_env: SettingsEnv
    ) -> None:
        settings_env(ASSISTANT_CLEARED_MARKINGS='["U", "U//TEST-CLEARED"]')
        notification = make_notification(classification_marking="U//TEST-CLEARED")
        fake = use_claude(monkeypatch, FakeClaude(valid_reply()))
        outcome = await evaluate(evaluation_session(notification), notification.id)
        assert len(fake.calls) == 1
        assert outcome.evaluation.error is None


class TestEvaluateOnce:
    async def test_it_stores_the_evaluation_in_a_session_of_its_own(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        session = evaluation_session(notification)
        opened = open_sessions(monkeypatch, session)
        use_claude(monkeypatch, FakeClaude(valid_reply()))
        run = await evaluate_once(notification.id)
        assert opened == [session]
        [row] = session.added
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(row)
        assert run.persistent_failure is False
        assert (run.evaluation.id, run.evaluation.notification_id) == (row.id, notification.id)
        assert (run.evaluation.evaluated_at, run.evaluation.error) == (NOW, None)
        assert run.evaluation.structured["next_actions"][0]["action"] == "Notify the duty officer"

    async def test_a_persistent_failure_is_stored_and_reported(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        session = evaluation_session(notification)
        open_sessions(monkeypatch, session)
        spent = AssistantError("The daily assistant token cap is spent.", persistent=True)
        use_claude(monkeypatch, FakeClaude(spent))
        run = await evaluate_once(notification.id)
        session.commit.assert_awaited_once()
        assert run.persistent_failure is True
        assert run.evaluation.error == "The daily assistant token cap is spent."
        assert run.evaluation.structured == EMPTY_EVALUATION

    async def test_an_unknown_notification_raises_and_commits_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session = FakeSession([scalar_result(None)])
        open_sessions(monkeypatch, session)
        use_claude(monkeypatch, FakeClaude())
        with pytest.raises(NotificationNotFoundError):
            await evaluate_once(synthetic_id())
        session.commit.assert_not_awaited()

    async def test_a_request_for_a_notification_in_flight_joins_that_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notification = make_notification(notso_identifier="TEST-NOTSO-1")
        session = evaluation_session(notification)
        opened = open_sessions(monkeypatch, session)  # only one: a second run could not open one
        fake = use_claude(monkeypatch, HeldClaude(valid_reply()))
        first = asyncio.create_task(evaluate_once(notification.id))
        await fake.arrivals(1)
        second = asyncio.create_task(evaluate_once(notification.id))
        await asyncio.sleep(0)  # the second request finds the first still with Claude
        fake.release.set()
        first_run, second_run = await asyncio.gather(first, second)
        assert second_run is first_run
        assert len(fake.calls) == 1
        assert opened == [session]

    async def test_requests_for_different_notifications_do_not_wait_on_each_other(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notices = [make_notification(notso_identifier=f"TEST-NOTSO-{n}") for n in (1, 2)]
        open_sessions(monkeypatch, *(evaluation_session(n) for n in notices))
        fake = use_claude(monkeypatch, HeldClaude(valid_reply(), valid_reply()))
        runs = [asyncio.create_task(evaluate_once(n.id)) for n in notices]
        await fake.arrivals(2)  # both are with Claude at the same time
        fake.release.set()
        finished = await asyncio.gather(*runs)
        assert [run.evaluation.notification_id for run in finished] == [n.id for n in notices]
        assert len(fake.calls) == 2


async def test_the_latest_evaluation_is_read_newest_first() -> None:
    notification_id = synthetic_id()
    row = AssistantEvaluation(
        id=synthetic_id(),
        notification_id=notification_id,
        summary=SUMMARY,
        structured=reply_body(),
        procedures_used=[],
        model=CONFIGURED_MODEL,
        error=None,
        evaluated_at=NOW,
    )
    session = FakeSession([scalar_result(row)])
    assert await get_latest_evaluation(session, notification_id) is row  # type: ignore[arg-type]
    sql, params = sent(session, 0)
    assert sql.endswith(
        "FROM assistant_evaluation "
        "WHERE assistant_evaluation.notification_id = %(notification_id_1)s::UUID "
        "ORDER BY assistant_evaluation.evaluated_at DESC LIMIT %(param_1)s::INTEGER"
    )
    assert params == {"notification_id_1": notification_id, "param_1": 1}
