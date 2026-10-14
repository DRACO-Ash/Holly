"""Claude's three-sentence narrative of one logical event (services/event_summary.py): which
publications share an event key, what Claude is shown about them and in what order, how the
reply is held to three sentences, and the row that is upserted, with an assistant failure
stored as the row's error rather than raised. call_claude is replaced with a recorder, so no
test reaches the Anthropic API. Every value here is synthetic."""

import uuid
from datetime import timedelta
from typing import Any, NamedTuple

import pytest
from sqlalchemy.dialects import postgresql

from app.models.event_summary import EventSummary
from app.models.notification import Notification
from app.services import event_summary
from app.services.claude import AssistantError, ClaudeReply
from app.services.event_summary import SummaryOutcome, compute_event_key, generate_event_summary
from fakes import NOW, FakeSession, scalar_result

# One PostgreSQL dialect compiles every statement here. SQLAlchemy leaves its constructor
# unannotated, hence the one ignore.
POSTGRESQL = postgresql.dialect()  # type: ignore[no-untyped-call]

EVENT = "TEST-EVENT-1"
REPLY = "The event was first reported. Its status then changed. It is now resolved."
HEADER = "EVENT PUBLICATIONS (oldest to newest):\n\n"


def synthetic_id(number: int) -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-4000-8000-{number:012d}")


def publication(number: int, **fields: Any) -> Notification:
    """Synthetic publication `number`, as the database would return it."""
    fields.setdefault("created_at", NOW)
    return Notification(id=synthetic_id(number), raw={}, **fields)


class ClaudeStub:
    """Stands in for call_claude: records each request, then answers with `reply`, or raises
    `error` when one is set."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.reply = ClaudeReply(text=REPLY, model="claude-test", truncated=False)
        self.error: Exception | None = None

    async def __call__(
        self, system_prompt: str, user_message: str, *, max_tokens: int, purpose: str
    ) -> ClaudeReply:
        self.requests.append(
            {
                "system_prompt": system_prompt,
                "user_message": user_message,
                "max_tokens": max_tokens,
                "purpose": purpose,
            }
        )
        if self.error is not None:
            raise self.error
        return self.reply


@pytest.fixture(autouse=True)
def claude(monkeypatch: pytest.MonkeyPatch) -> ClaudeStub:
    stub = ClaudeStub()
    monkeypatch.setattr(event_summary, "call_claude", stub)
    return stub


class Summarised(NamedTuple):
    outcome: SummaryOutcome
    session: FakeSession
    stored: EventSummary


async def summarise(publications: list[Notification]) -> Summarised:
    """Summarise `publications` as one event, against a session whose read-back finds a row."""
    stored = EventSummary(event_key=EVENT)
    session = FakeSession([None, scalar_result(stored)])
    outcome = await generate_event_summary(session, EVENT, publications)  # type: ignore[arg-type]
    return Summarised(outcome, session, stored)


def compiled(session: FakeSession, call: int) -> tuple[str, dict[str, Any]]:
    """The SQL and parameters of the session's `call`th statement, as PostgreSQL receives them."""
    result = session.execute.await_args_list[call].args[0].compile(dialect=POSTGRESQL)
    return " ".join(str(result).split()), dict(result.params)


def stored_values(session: FakeSession) -> dict[str, Any]:
    """The column values the summary upsert writes. The primary key is not among them: its
    column default fills it when the statement runs."""
    _sql, params = compiled(session, 0)
    del params["id"]
    return params


class TestTheEventKey:
    @pytest.mark.parametrize(
        ("identifiers", "expected"),
        [
            (
                {"event_id": EVENT, "notso_identifier": "TEST-NOTSO-1", "udl_id": "test-udl-1"},
                EVENT,
            ),
            (
                {"event_id": None, "notso_identifier": "TEST-NOTSO-1", "udl_id": "test-udl-1"},
                "TEST-NOTSO-1",
            ),
            ({"event_id": "", "notso_identifier": "", "udl_id": "test-udl-1"}, "test-udl-1"),
        ],
    )
    def test_the_key_is_the_first_identifier_present(
        self, identifiers: dict[str, str | None], expected: str
    ) -> None:
        assert compute_event_key(publication(1, **identifiers)) == expected

    def test_a_publication_with_no_identifier_is_an_event_of_its_own(self) -> None:
        assert compute_event_key(publication(7)) == "00000000-0000-4000-8000-000000000007"


class TestWhatClaudeIsShown:
    async def test_one_capped_request_is_made_under_its_own_purpose(
        self, claude: ClaudeStub
    ) -> None:
        await summarise([publication(1, udl_created_at=NOW)])
        [request] = claude.requests
        assert request["max_tokens"] == 400
        assert request["purpose"] == "assistant.event_summary"
        assert "STRICT 3-sentence maximum" in request["system_prompt"]

    async def test_publications_are_shown_oldest_first_whatever_order_they_arrive_in(
        self, claude: ClaudeStub
    ) -> None:
        oldest = publication(1, udl_created_at=NOW - timedelta(hours=3), description="First.")
        # Without a UDL timestamp, the time Holly stored a publication places it.
        unstamped = publication(
            2, udl_created_at=None, created_at=NOW - timedelta(hours=2), description="Second."
        )
        newest = publication(3, udl_created_at=NOW - timedelta(hours=1), description="Third.")
        await summarise([newest, oldest, unstamped])
        assert claude.requests[0]["user_message"] == (
            HEADER + "Publication 1 | udl_created=2026-06-05T09:00:00+00:00\n"
            "  description: First.\n\n"
            "Publication 2\n"
            "  description: Second.\n\n"
            "Publication 3 | udl_created=2026-06-05T11:00:00+00:00\n"
            "  description: Third."
        )

    async def test_a_long_history_is_shown_as_its_first_and_newest_publications(
        self, claude: ClaudeStub
    ) -> None:
        history = [
            publication(n, udl_created_at=NOW + timedelta(minutes=n), description=f"Update {n}.")
            for n in range(1, 26)
        ]
        run = await summarise(history)
        message = claude.requests[0]["user_message"]
        assert message.startswith(
            "EVENT PUBLICATIONS (oldest to newest; the first and the newest 19 of 25):\n\n"
            "Publication 1 | udl_created=2026-06-05T12:01:00+00:00\n  description: Update 1.\n\n"
            "Publication 7 | udl_created=2026-06-05T12:07:00+00:00\n  description: Update 7.\n\n"
        )
        shown = [int(line.split()[1]) for line in message.splitlines() if line.startswith("Pub")]
        assert shown == [1, *range(7, 26)]
        # The summary still covers, and lists, every publication.
        values = stored_values(run.session)
        assert values["publication_count"] == 25
        assert values["source_notification_ids"] == [str(p.id) for p in history]

    async def test_a_publication_shows_every_field_it_has(self, claude: ClaudeStub) -> None:
        await summarise(
            [
                publication(
                    1,
                    udl_created_at=NOW - timedelta(hours=3),
                    status="TEST-STATUS",
                    event_type="TEST",
                    event_class="TEST-CLASS",
                    subject="Example subject",
                    region="TEST-REGION",
                    sat_no=99999,
                    # Ingest keeps UDL's SatIds as sent, so an entry can be a JSON number.
                    sat_ids=[99999, "TEST-SAT"],
                    description="  Example description.\n",
                    effective_from=NOW - timedelta(hours=2),
                    effective_until=NOW + timedelta(hours=22),
                )
            ]
        )
        assert claude.requests[0]["user_message"] == (
            HEADER + "Publication 1 | udl_created=2026-06-05T09:00:00+00:00"
            " | status=TEST-STATUS | event_type=TEST\n"
            "  event_class: TEST-CLASS\n"
            "  subject: Example subject\n"
            "  region: TEST-REGION\n"
            "  sat_no: 99999\n"
            "  sat_ids: 99999, TEST-SAT\n"
            "  description: Example description.\n"
            "  effective_from: 2026-06-05T10:00:00+00:00\n"
            "  effective_until: 2026-06-06T10:00:00+00:00"
        )

    async def test_empty_fields_and_a_subject_repeating_the_class_are_left_out(
        self, claude: ClaudeStub
    ) -> None:
        await summarise(
            [
                publication(
                    1,
                    udl_created_at=NOW - timedelta(hours=3),
                    status="",
                    event_class="TEST-CLASS",
                    subject="TEST-CLASS",
                    region="",
                    sat_ids=[],
                    description="   ",
                )
            ]
        )
        assert claude.requests[0]["user_message"] == (
            HEADER + "Publication 1 | udl_created=2026-06-05T09:00:00+00:00\n"
            "  event_class: TEST-CLASS"
        )


class TestTheStoredSummary:
    @pytest.mark.parametrize(
        ("reply", "narrative"),
        [
            ("First. Second! Third? Fourth.", "First. Second! Third?"),
            ("  Only one sentence.  ", "Only one sentence."),
            ("Value 1.5 was reported. It held.", "Value 1.5 was reported. It held."),
            ("Line one.\nLine two.\n\nLine three.\nLine four.", "Line one. Line two. Line three."),
        ],
    )
    async def test_the_narrative_is_held_to_three_sentences(
        self, claude: ClaudeStub, reply: str, narrative: str
    ) -> None:
        claude.reply = ClaudeReply(text=reply, model="claude-test", truncated=False)
        run = await summarise([publication(1, udl_created_at=NOW)])
        assert stored_values(run.session)["narrative"] == narrative

    async def test_a_summary_is_upserted_from_the_publications_and_read_back(self) -> None:
        older = publication(1, udl_created_at=NOW - timedelta(hours=2))
        newer = publication(2, udl_created_at=NOW - timedelta(hours=1))
        run = await summarise([newer, older])
        assert stored_values(run.session) == {
            "event_key": EVENT,
            "narrative": REPLY,
            "source_notification_ids": [str(older.id), str(newer.id)],
            "latest_notification_id": newer.id,
            "publication_count": 2,
            "model": "claude-test",
            "error": None,
        }
        sql, params = compiled(run.session, 1)
        assert "FROM event_summary WHERE event_summary.event_key = " in sql
        assert params == {"event_key_1": EVENT}
        assert run.outcome == SummaryOutcome(summary=run.stored, persistent_failure=False)

    async def test_a_rerun_replaces_the_earlier_summary_and_bumps_its_updated_at(self) -> None:
        run = await summarise([publication(1, udl_created_at=NOW)])
        sql, _params = compiled(run.session, 0)
        assert sql.startswith("INSERT INTO event_summary ")
        assert sql.split(" ON CONFLICT ", 1)[1] == (
            "ON CONSTRAINT uq_event_summary_event_key DO UPDATE SET "
            "narrative = excluded.narrative, "
            "source_notification_ids = excluded.source_notification_ids, "
            "latest_notification_id = excluded.latest_notification_id, "
            "publication_count = excluded.publication_count, "
            "model = excluded.model, "
            "error = excluded.error, "
            "updated_at = now()"
        )

    @pytest.mark.parametrize("arrival", [(0, 1), (1, 0)], ids=["in id order", "reversed"])
    async def test_on_a_timestamp_tie_the_id_decides_which_is_latest(
        self, arrival: tuple[int, int]
    ) -> None:
        tied = [publication(1, udl_created_at=NOW), publication(2, udl_created_at=NOW)]
        run = await summarise([tied[index] for index in arrival])
        values = stored_values(run.session)
        assert values["source_notification_ids"] == [str(tied[0].id), str(tied[1].id)]
        assert values["latest_notification_id"] == tied[1].id

    @pytest.mark.parametrize("persistent", [False, True])
    async def test_an_assistant_failure_writes_nothing_and_is_not_raised(
        self, claude: ClaudeStub, caplog: pytest.LogCaptureFixture, persistent: bool
    ) -> None:
        # Nothing is written, so an earlier narrative and the publications it lists stay as
        # they were, and the event stays stale for the next cycle to try again.
        claude.error = AssistantError("Example assistant failure", persistent=persistent)
        session = FakeSession()
        only = [publication(1, udl_created_at=NOW)]
        outcome = await generate_event_summary(session, EVENT, only)  # type: ignore[arg-type]
        assert outcome == SummaryOutcome(
            summary=None, error="Example assistant failure", persistent_failure=persistent
        )
        session.execute.assert_not_awaited()
        assert f"Event summary failed for {EVENT}: Example assistant failure" in caplog.messages

    async def test_an_empty_publication_list_is_refused_before_claude_is_asked(
        self, claude: ClaudeStub
    ) -> None:
        session = FakeSession()
        with pytest.raises(AssistantError, match="empty publication list"):
            await generate_event_summary(session, EVENT, [])  # type: ignore[arg-type]
        assert claude.requests == []
        session.execute.assert_not_awaited()

    async def test_any_other_failure_is_left_for_the_caller_to_roll_back(
        self, claude: ClaudeStub
    ) -> None:
        claude.error = RuntimeError("Example unexpected failure")
        session = FakeSession()
        only = [publication(1, udl_created_at=NOW)]
        with pytest.raises(RuntimeError, match="Example unexpected failure"):
            await generate_event_summary(session, EVENT, only)  # type: ignore[arg-type]
        session.execute.assert_not_awaited()
