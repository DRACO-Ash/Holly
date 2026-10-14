"""The background refresh loops (services/background_refresh.py): what each pull asks UDL and
Mattermost for, which notifications and events the notification cycle hands to the assistant,
that every failure is logged and survived, and that each loop runs its job on its own cadence
until it is stopped. The ingest, evaluation and summary services are replaced with recorders
autospecced from the real functions, every database session is scripted, and only this
module's view of asyncio.sleep is replaced, so the loops run fast and nothing leaves the
process. Every value here is synthetic."""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, fields
from datetime import UTC, datetime, timedelta
from typing import Any, Self
from unittest.mock import AsyncMock, create_autospec

import pytest
from sqlalchemy.dialects import postgresql

from app.models.event_summary import EventSummary
from app.models.notification import Notification
from app.schemas.assistant import AssistantEvaluationRead
from app.services import assistant, background_refresh
from app.services.assistant import EvaluationRun
from app.services.event_summary import SummaryOutcome
from app.services.udl_client import UDLAuthError, UDLClientError
from fakes import NOW, FakeSession, rows_result

SettingsEnv = Callable[..., None]
MODULE = background_refresh.__name__
EVENT = "TEST-EVENT-1"

# One PostgreSQL dialect compiles every statement here. SQLAlchemy leaves its constructor
# unannotated, hence the one ignore.
POSTGRESQL = postgresql.dialect()  # type: ignore[no-untyped-call]

# The two UDL pulls share their error handling: (function, ingest service, log label).
UDL_PULLS = {
    "notifications": ("_pull_notifications_once", "ingest_notifications", "Notification"),
    "maneuvers": ("_pull_maneuvers_once", "ingest_maneuvers", "Maneuver"),
}


def synthetic_id(number: int) -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-4000-8000-{number:012d}")


def publication(number: int, event_key: str, hours_ago: int) -> Notification:
    """Synthetic publication `number` of the logical event `event_key`."""
    published = NOW - timedelta(hours=hours_ago)
    return Notification(
        id=synthetic_id(number),
        event_id=event_key,
        classification_marking="U",
        udl_created_at=published,
        created_at=published,
        raw={},
    )


def stored_summary(
    event_key: str, seen: list[Notification], error: str | None = None
) -> EventSummary:
    """A summary already stored, written from the publications in `seen`."""
    return EventSummary(
        event_key=event_key, source_notification_ids=[str(each.id) for each in seen], error=error
    )


def history_session(history: list[Notification]) -> FakeSession:
    """The session one stale event is regenerated in; its first query reads the event's
    full history."""
    return FakeSession([rows_result(history)])


def evaluation_run(*, persistent: bool = False, error: str | None = None) -> EvaluationRun:
    """What evaluate_once returns for one notification."""
    evaluation = AssistantEvaluationRead(
        id=synthetic_id(900),
        notification_id=synthetic_id(901),
        summary="Example evaluation.",
        structured={},
        procedures_used=[],
        model="claude-test",
        error=error,
        evaluated_at=NOW,
    )
    return EvaluationRun(evaluation=evaluation, persistent_failure=persistent)


def summary_outcome(
    event_key: str, *, persistent: bool = False, error: str | None = None
) -> SummaryOutcome:
    """What generate_event_summary returns for one event: a stored summary, or for a failure,
    no summary and the error."""
    if error is not None:
        return SummaryOutcome(summary=None, error=error, persistent_failure=persistent)
    return SummaryOutcome(summary=EventSummary(event_key=event_key, narrative="Example narrative."))


@dataclass(frozen=True)
class Services:
    """The services the loops call. Each recorder is autospecced from the real function, so a
    call the real service would refuse fails the test."""

    ingest_notifications: Any
    ingest_maneuvers: Any
    ingest_mattermost_messages: Any
    evaluate_once: Any
    generate_event_summary: Any


@pytest.fixture(autouse=True)
def services(monkeypatch: pytest.MonkeyPatch) -> Services:
    names = [field.name for field in fields(Services)]
    recorders = Services(
        **{name: create_autospec(getattr(background_refresh, name)) for name in names}
    )
    recorders.evaluate_once.return_value = evaluation_run()
    recorders.generate_event_summary.side_effect = lambda _db, key, _publications: summary_outcome(
        key
    )
    for name in names:
        monkeypatch.setattr(background_refresh, name, getattr(recorders, name))
    return recorders


class SessionFactory:
    """Stands in for get_session_factory(). Each session opened is the next one the test
    scripted, or an empty one when it scripted too few; every session opened and closed is
    recorded, so a test states exactly the sessions the code under test used."""

    def __init__(self) -> None:
        self.scripted: list[FakeSession] = []
        self.opened: list[FakeSession] = []
        self.closed: list[FakeSession] = []

    def script(self, *sessions: FakeSession) -> list[FakeSession]:
        self.scripted.extend(sessions)
        return list(sessions)

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[FakeSession]:
        session = self.scripted.pop(0) if self.scripted else FakeSession()
        self.opened.append(session)
        try:
            yield session
        finally:
            self.closed.append(session)


@pytest.fixture(autouse=True)
def audits(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """write_audit, where the cycle's evaluations and narratives reach it, replaced with a
    recorder of each row and the session it was written in."""
    rows: list[dict[str, Any]] = []

    def record(db: FakeSession, **row: Any) -> None:
        rows.append({"db": db, **row})

    recorder = AsyncMock(side_effect=record)
    monkeypatch.setattr(background_refresh, "write_audit", recorder)
    monkeypatch.setattr(assistant, "write_audit", recorder)
    return rows


@pytest.fixture(autouse=True)
def sessions(monkeypatch: pytest.MonkeyPatch) -> SessionFactory:
    factory = SessionFactory()
    monkeypatch.setattr(background_refresh, "get_session_factory", lambda: factory)
    return factory


@pytest.fixture(autouse=True)
def _pinned_settings(settings_env: SettingsEnv) -> None:
    """The settings these tests otherwise take as given, pinned so no local value moves them."""
    settings_env(
        BACKGROUND_AUTO_EVALUATE="true",
        BACKGROUND_MAX_EVALUATIONS_PER_CYCLE="20",
        BACKGROUND_MAX_EVENT_SUMMARIES_PER_CYCLE="20",
    )


class FakeUDLClient:
    """Stands in for UDLClient; it never makes a request."""

    def __init__(self) -> None:
        self.closed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.closed = True


@pytest.fixture
def udl(monkeypatch: pytest.MonkeyPatch) -> list[FakeUDLClient]:
    """Every UDL client the code under test opens."""
    clients: list[FakeUDLClient] = []

    def open_client() -> FakeUDLClient:
        clients.append(FakeUDLClient())
        return clients[-1]

    monkeypatch.setattr(background_refresh, "UDLClient", open_client)
    return clients


def compiled(session: FakeSession, call: int = 0) -> tuple[str, dict[str, Any]]:
    """The SQL and parameters of the session's `call`th statement, as PostgreSQL receives them."""
    result = (
        session.execute.await_args_list[call]
        .args[0]
        .compile(dialect=POSTGRESQL, compile_kwargs={"render_postcompile": True})
    )
    return " ".join(str(result).split()), dict(result.params)


async def timed(call: Awaitable[None]) -> tuple[datetime, datetime]:
    """The wall-clock span `call` ran in, to check a window it computed from the time."""
    before = datetime.now(UTC)
    await call
    return before, datetime.now(UTC)


def assert_window_start(start: datetime, *, hours: int, span: tuple[datetime, datetime]) -> None:
    earliest, latest = (moment - timedelta(hours=hours) for moment in span)
    assert earliest <= start <= latest


def logged(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    """The module's own log records at `level`."""
    return [each for each in caplog.records if each.name == MODULE and each.levelno == level]


def messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    return [record.getMessage() for record in logged(caplog, level)]


def raised(record: logging.LogRecord) -> BaseException | None:
    """The exception whose traceback a record carries."""
    return record.exc_info[1] if record.exc_info else None


def keys_summarised(services: Services) -> list[str]:
    return [call.args[1] for call in services.generate_event_summary.await_args_list]


class TestTheUDLPulls:
    async def test_notifications_are_pulled_for_their_window(
        self,
        settings_env: SettingsEnv,
        sessions: SessionFactory,
        udl: list[FakeUDLClient],
        services: Services,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        settings_env(BACKGROUND_NOTIFICATION_WINDOW_HOURS="7")
        caplog.set_level(logging.INFO, logger=MODULE)
        [session] = sessions.script(FakeSession())
        span = await timed(background_refresh._pull_notifications_once())
        [client] = udl
        call = services.ingest_notifications.await_args
        assert call.args == (session, client)
        query = dict(call.kwargs)
        assert_window_start(query.pop("created_at_gte"), hours=7, span=span)
        # The module's own UDL query values.
        assert query == {"msg_type": "TACREP_NOTSO", "data_mode": "REAL", "source": "JCO"}
        assert client.closed
        assert sessions.closed == [session]
        assert messages(caplog, logging.INFO) == ["Notification ingest complete (window: last 7h)"]

    async def test_maneuvers_are_pulled_for_their_window(
        self,
        settings_env: SettingsEnv,
        sessions: SessionFactory,
        udl: list[FakeUDLClient],
        services: Services,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        settings_env(BACKGROUND_MANEUVER_WINDOW_HOURS="5")
        caplog.set_level(logging.INFO, logger=MODULE)
        [session] = sessions.script(FakeSession())
        span = await timed(background_refresh._pull_maneuvers_once())
        [client] = udl
        call = services.ingest_maneuvers.await_args
        assert call.args == (session, client)
        query = dict(call.kwargs)
        assert_window_start(query.pop("event_start_time_gte"), hours=5, span=span)
        assert query == {"data_mode": "REAL"}
        assert client.closed
        assert sessions.closed == [session]
        assert messages(caplog, logging.INFO) == ["Maneuver ingest complete (window: last 5h)"]

    @pytest.mark.usefixtures("udl")
    @pytest.mark.parametrize("pull", list(UDL_PULLS))
    @pytest.mark.parametrize(
        ("error_type", "level", "message", "with_traceback"),
        [
            (UDLAuthError, logging.WARNING, "{} ingest skipped: UDL auth failed (detail)", False),
            (UDLClientError, logging.WARNING, "{} ingest failed: detail", False),
            (RuntimeError, logging.ERROR, "{} ingest crashed unexpectedly", True),
        ],
    )
    async def test_a_failed_pull_is_logged_and_survived(
        self,
        sessions: SessionFactory,
        services: Services,
        caplog: pytest.LogCaptureFixture,
        pull: str,
        error_type: type[Exception],
        level: int,
        message: str,
        with_traceback: bool,
    ) -> None:
        function, ingest, label = UDL_PULLS[pull]
        sessions.script(FakeSession())
        error = error_type("detail")
        getattr(services, ingest).side_effect = error
        await getattr(background_refresh, function)()
        [record] = logged(caplog, level)
        assert record.getMessage() == message.format(label)
        assert raised(record) is (error if with_traceback else None)

    @pytest.mark.parametrize("pull", list(UDL_PULLS))
    async def test_without_udl_credentials_a_pull_is_skipped_before_it_opens_a_session(
        self,
        sessions: SessionFactory,
        services: Services,
        caplog: pytest.LogCaptureFixture,
        pull: str,
    ) -> None:
        # The real UDL client, which the test environment leaves without credentials.
        function, ingest, label = UDL_PULLS[pull]
        await getattr(background_refresh, function)()
        assert sessions.opened == []
        getattr(services, ingest).assert_not_awaited()
        assert messages(caplog, logging.WARNING) == [
            f"{label} ingest failed: UDL credentials are not configured "
            "(UDL_USERNAME / UDL_PASSWORD)."
        ]


class TestTheMattermostPull:
    async def test_messages_are_ingested_in_a_session_of_their_own(
        self, sessions: SessionFactory, services: Services
    ) -> None:
        [session] = sessions.script(FakeSession())
        await background_refresh._pull_mattermost_once()
        services.ingest_mattermost_messages.assert_awaited_once_with(session)
        assert sessions.closed == [session]

    async def test_a_failed_pull_is_logged_and_survived(
        self, sessions: SessionFactory, services: Services, caplog: pytest.LogCaptureFixture
    ) -> None:
        sessions.script(FakeSession())
        error = RuntimeError("Example unexpected failure")
        services.ingest_mattermost_messages.side_effect = error
        await background_refresh._pull_mattermost_once()
        [record] = logged(caplog, logging.ERROR)
        assert record.getMessage() == "Mattermost ingest crashed unexpectedly"
        assert raised(record) is error


class TestAutoEvaluation:
    async def test_nothing_happens_when_it_is_switched_off(
        self, settings_env: SettingsEnv, sessions: SessionFactory, services: Services
    ) -> None:
        settings_env(BACKGROUND_AUTO_EVALUATE="false")
        await background_refresh._auto_evaluate_phase()
        assert sessions.opened == []
        services.evaluate_once.assert_not_awaited()

    async def test_with_nothing_to_evaluate_the_phase_stays_quiet(
        self, sessions: SessionFactory, services: Services, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO, logger=MODULE)
        sessions.script(FakeSession([rows_result([])]))
        await background_refresh._auto_evaluate_phase()
        services.evaluate_once.assert_not_awaited()
        assert messages(caplog, logging.INFO) == []

    async def test_it_asks_for_the_newest_unevaluated_latest_versions_in_the_window(
        self, settings_env: SettingsEnv, sessions: SessionFactory, services: Services
    ) -> None:
        settings_env(
            BACKGROUND_NOTIFICATION_WINDOW_HOURS="9", BACKGROUND_MAX_EVALUATIONS_PER_CYCLE="3"
        )
        [session] = sessions.script(FakeSession([rows_result([])]))
        span = await timed(background_refresh._auto_evaluate_phase())
        sql, params = compiled(session)
        # The latest publication of each logical notice in the window...
        assert (
            "SELECT DISTINCT ON (coalesce(notification.event_id, "
            "notification.notso_identifier, notification.udl_id))"
        ) in sql
        assert "FROM notification WHERE notification.udl_created_at >= " in sql
        assert_window_start(params["udl_created_at_1"], hours=9, span=span)
        # ...whose marking is cleared for the assistant...
        assert "AND notification.classification_marking IN (" in sql
        assert params["classification_marking_1_1"] == "U"
        # ...that has no evaluation yet, newest first, at most the configured number of them.
        assert (
            "LEFT OUTER JOIN assistant_evaluation "
            "ON assistant_evaluation.notification_id = anon_1.id "
            "WHERE assistant_evaluation.id IS NULL "
            "ORDER BY anon_1.udl_created_at DESC LIMIT "
        ) in sql
        assert params["param_1"] == 3
        services.evaluate_once.assert_not_awaited()

    async def test_each_is_evaluated_in_turn_and_a_crash_skips_only_that_one(
        self,
        sessions: SessionFactory,
        services: Services,
        audits: list[dict[str, Any]],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        ids = [synthetic_id(number) for number in (1, 2, 3)]
        sessions.script(FakeSession([rows_result([(each,) for each in ids])]))
        crash = RuntimeError("Example unexpected failure")
        services.evaluate_once.side_effect = [evaluation_run(), crash, evaluation_run()]
        await background_refresh._auto_evaluate_phase()
        assert [call.args for call in services.evaluate_once.await_args_list] == [
            (each,) for each in ids
        ]
        [record] = logged(caplog, logging.ERROR)
        assert record.getMessage() == f"Auto-evaluate failed for notification {ids[1]}"
        assert raised(record) is crash
        # Each notice the assistant was shown is audited, in a session of its own.
        assert [row["entity_id"] for row in audits] == [str(ids[0]), str(ids[2])]
        first = audits[0]
        assert first["action_type"] == "assistant.evaluate"
        assert first["entity_type"] == "notification"
        assert first["detail"] == {
            "trigger": "background",
            "evaluation_id": str(evaluation_run().evaluation.id),
            "model": "claude-test",
            "procedures_used": [],
            "had_error": False,
        }
        first["db"].commit.assert_awaited_once()

    async def test_when_a_sending_cannot_be_audited_no_further_notice_is_sent(
        self,
        sessions: SessionFactory,
        services: Services,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        ids = [synthetic_id(number) for number in (1, 2)]
        sessions.script(FakeSession([rows_result([(each,) for each in ids])]))
        broken = RuntimeError("Example audit failure")
        monkeypatch.setattr(assistant, "write_audit", AsyncMock(side_effect=broken))
        await background_refresh._auto_evaluate_phase()
        assert [call.args for call in services.evaluate_once.await_args_list] == [(ids[0],)]
        [record] = logged(caplog, logging.ERROR)
        assert record.getMessage() == f"Could not audit the evaluation of {ids[0]}; stopping"
        assert raised(record) is broken

    async def test_a_persistent_failure_stops_the_cycle_early(
        self, sessions: SessionFactory, services: Services, caplog: pytest.LogCaptureFixture
    ) -> None:
        ids = [synthetic_id(number) for number in (1, 2, 3)]
        sessions.script(FakeSession([rows_result([(each,) for each in ids])]))
        services.evaluate_once.side_effect = [
            evaluation_run(),
            evaluation_run(persistent=True, error="Example persistent failure"),
            evaluation_run(),
        ]
        await background_refresh._auto_evaluate_phase()
        assert [call.args for call in services.evaluate_once.await_args_list] == [
            (each,) for each in ids[:2]
        ]
        assert messages(caplog, logging.WARNING) == [
            "Stopping auto-evaluate cycle early: Example persistent failure"
        ]


class TestEventSummaries:
    async def test_it_reads_the_window_oldest_first_with_the_id_breaking_a_tie(
        self, settings_env: SettingsEnv, sessions: SessionFactory
    ) -> None:
        settings_env(BACKGROUND_NOTIFICATION_WINDOW_HOURS="9")
        [session] = sessions.script(FakeSession([rows_result([])]))
        span = await timed(background_refresh._event_summary_phase())
        sql, params = compiled(session)
        assert "FROM notification WHERE notification.udl_created_at >= " in sql
        assert "AND notification.classification_marking IN (" in sql
        assert params["classification_marking_1_1"] == "U"
        assert sql.endswith("ORDER BY notification.udl_created_at ASC, notification.id ASC")
        assert_window_start(params["udl_created_at_1"], hours=9, span=span)

    async def test_with_nothing_in_the_window_nothing_is_summarised(
        self, sessions: SessionFactory, services: Services
    ) -> None:
        sessions.script(FakeSession([rows_result([])]))
        await background_refresh._event_summary_phase()
        assert len(sessions.opened) == 1
        services.generate_event_summary.assert_not_awaited()

    @pytest.mark.parametrize(
        ("window", "seen", "stale"),
        [
            pytest.param((1, 2), None, True, id="no summary yet"),
            pytest.param((1, 2), (1, 2), False, id="every publication seen"),
            pytest.param((1, 2), (1,), True, id="a newer publication unseen"),
            pytest.param((0, 1, 2), (1, 2), True, id="a late older publication unseen"),
            pytest.param((1, 2), (0, 1, 2), False, id="an older publication aged out"),
            pytest.param((1, 2), "failed", True, id="a summary that records a failure"),
        ],
    )
    async def test_a_summary_is_stale_only_while_the_window_holds_a_publication_it_has_not_seen(
        self,
        sessions: SessionFactory,
        services: Services,
        window: tuple[int, ...],
        seen: tuple[int, ...] | str | None,
        stale: bool,
    ) -> None:
        history = [publication(1, EVENT, 30), publication(2, EVENT, 20), publication(3, EVENT, 10)]
        if seen is None:
            stored = []
        elif isinstance(seen, str):
            # Every publication is listed, but the row records a failure, as old rows can.
            stored = [stored_summary(EVENT, history, error="Example assistant failure")]
        else:
            stored = [stored_summary(EVENT, [history[i] for i in seen])]
        sessions.script(
            FakeSession([rows_result([history[i] for i in window])]),
            FakeSession([rows_result(stored)]),
            history_session(history),
        )
        await background_refresh._event_summary_phase()
        assert keys_summarised(services) == ([EVENT] if stale else [])
        assert len(sessions.opened) == (3 if stale else 2)

    async def test_a_regenerated_summary_is_built_from_the_events_full_history(
        self, sessions: SessionFactory, services: Services
    ) -> None:
        history = [publication(1, EVENT, 200), publication(2, EVENT, 20), publication(3, EVENT, 10)]
        # The oldest publication has left the window; the newest is one the summary has not seen.
        _window, _lookup, per_event = sessions.script(
            FakeSession([rows_result(history[1:])]),
            FakeSession([rows_result([stored_summary(EVENT, history[:2])])]),
            history_session(history),
        )
        await background_refresh._event_summary_phase()
        services.generate_event_summary.assert_awaited_once_with(per_event, EVENT, history)
        per_event.commit.assert_awaited_once()
        sql, params = compiled(per_event)
        assert sql.startswith("SELECT notification.")
        assert (
            "FROM notification WHERE coalesce(notification.event_id, "
            "notification.notso_identifier, notification.udl_id) = "
        ) in sql
        # Only the publications whose marking is cleared for the assistant.
        assert "AND notification.classification_marking IN (" in sql
        assert params == {"coalesce_1": EVENT, "classification_marking_1_1": "U"}

    async def test_each_stale_event_is_regenerated_in_a_session_of_its_own(
        self, sessions: SessionFactory, services: Services, audits: list[dict[str, Any]]
    ) -> None:
        first = [publication(1, "TEST-EVENT-1", 6), publication(2, "TEST-EVENT-1", 3)]
        second = [publication(3, "TEST-EVENT-2", 5), publication(4, "TEST-EVENT-2", 4)]
        current = [publication(5, "TEST-EVENT-3", 2)]
        window, lookup, *per_event = sessions.script(
            # As the query returns them: oldest first.
            FakeSession([rows_result([first[0], second[0], second[1], first[1], current[0]])]),
            FakeSession([rows_result([stored_summary("TEST-EVENT-3", current)])]),
            history_session(first),
            history_session(second),
        )
        await background_refresh._event_summary_phase()
        assert [call.args for call in services.generate_event_summary.await_args_list] == [
            (per_event[0], "TEST-EVENT-1", first),
            (per_event[1], "TEST-EVENT-2", second),
        ]
        for session in per_event:
            session.commit.assert_awaited_once()
        assert sessions.opened == [window, lookup, *per_event]
        # Each event's sending is audited in the same transaction as its narrative.
        assert audits == [
            {
                "db": per_event[0],
                "action_type": "assistant.event_summary",
                "entity_type": "event",
                "entity_id": "TEST-EVENT-1",
                "detail": {"trigger": "background", "publications": 2, "had_error": False},
            },
            {
                "db": per_event[1],
                "action_type": "assistant.event_summary",
                "entity_type": "event",
                "entity_id": "TEST-EVENT-2",
                "detail": {"trigger": "background", "publications": 2, "had_error": False},
            },
        ]
        # The stored summaries were looked up for exactly the events in the window.
        sql, params = compiled(lookup)
        assert "FROM event_summary WHERE event_summary.event_key IN (" in sql
        assert sorted(params.values()) == ["TEST-EVENT-1", "TEST-EVENT-2", "TEST-EVENT-3"]

    async def test_when_every_summary_is_current_nothing_is_regenerated_or_announced(
        self, sessions: SessionFactory, services: Services, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO, logger=MODULE)
        in_window = [publication(1, EVENT, 2), publication(2, EVENT, 1)]
        sessions.script(
            FakeSession([rows_result(in_window)]),
            FakeSession([rows_result([stored_summary(EVENT, in_window)])]),
        )
        await background_refresh._event_summary_phase()
        services.generate_event_summary.assert_not_awaited()
        assert len(sessions.opened) == 2
        assert messages(caplog, logging.INFO) == []

    async def test_the_cap_takes_the_newest_events_first(
        self, settings_env: SettingsEnv, sessions: SessionFactory, services: Services
    ) -> None:
        settings_env(BACKGROUND_MAX_EVENT_SUMMARIES_PER_CYCLE="2")
        # Oldest first, as the query returns them. Each event's newest publication places it:
        # TEST-EVENT-2 (1 hour ago), then TEST-EVENT-3 (5 hours), then TEST-EVENT-1 (10 hours).
        in_window = [
            publication(1, "TEST-EVENT-1", 30),
            publication(2, "TEST-EVENT-2", 20),
            publication(3, "TEST-EVENT-3", 15),
            publication(4, "TEST-EVENT-1", 10),
            publication(5, "TEST-EVENT-3", 5),
            publication(6, "TEST-EVENT-2", 1),
        ]
        sessions.script(
            FakeSession([rows_result(in_window)]),
            FakeSession([rows_result([])]),
            history_session([in_window[1], in_window[5]]),
            history_session([in_window[2], in_window[4]]),
        )
        await background_refresh._event_summary_phase()
        assert keys_summarised(services) == ["TEST-EVENT-2", "TEST-EVENT-3"]
        assert len(sessions.opened) == 4

    @pytest.mark.parametrize(
        ("failing_step", "summarised"),
        [
            ("history", ["TEST-EVENT-2"]),
            ("generate", [EVENT, "TEST-EVENT-2"]),
            ("commit", [EVENT, "TEST-EVENT-2"]),
        ],
    )
    async def test_a_failed_summary_is_rolled_back_and_the_next_event_still_runs(
        self,
        sessions: SessionFactory,
        services: Services,
        caplog: pytest.LogCaptureFixture,
        failing_step: str,
        summarised: list[str],
    ) -> None:
        # TEST-EVENT-1 is the newer event, so it is regenerated first.
        in_window = [publication(1, "TEST-EVENT-2", 2), publication(2, EVENT, 1)]
        error = RuntimeError("Example unexpected failure")
        history = error if failing_step == "history" else rows_result([in_window[1]])
        _window, _lookup, first, second = sessions.script(
            FakeSession([rows_result(in_window)]),
            FakeSession([rows_result([])]),
            FakeSession([history]),
            history_session([in_window[0]]),
        )
        if failing_step == "generate":
            services.generate_event_summary.side_effect = [error, summary_outcome("TEST-EVENT-2")]
        if failing_step == "commit":
            first.commit.side_effect = error
        await background_refresh._event_summary_phase()
        first.rollback.assert_awaited_once()
        second.commit.assert_awaited_once()
        second.rollback.assert_not_awaited()
        assert keys_summarised(services) == summarised
        [record] = logged(caplog, logging.ERROR)
        assert record.getMessage() == f"Event summary failed for {EVENT}"
        assert raised(record) is error

    async def test_a_persistent_failure_stops_the_cycle(
        self,
        sessions: SessionFactory,
        services: Services,
        audits: list[dict[str, Any]],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # TEST-EVENT-1 is the newer event, so it is regenerated first.
        in_window = [publication(1, "TEST-EVENT-2", 2), publication(2, EVENT, 1)]
        _window, _lookup, first = sessions.script(
            FakeSession([rows_result(in_window)]),
            FakeSession([rows_result([])]),
            history_session([in_window[1]]),
        )
        services.generate_event_summary.side_effect = [
            summary_outcome(EVENT, persistent=True, error="Example persistent failure")
        ]
        await background_refresh._event_summary_phase()
        first.commit.assert_awaited_once()
        assert keys_summarised(services) == [EVENT]
        assert len(sessions.opened) == 3
        # The attempt is audited, marked as failed.
        assert [(row["entity_id"], row["detail"]["had_error"]) for row in audits] == [(EVENT, True)]
        assert messages(caplog, logging.WARNING) == [
            "Stopping event summary cycle early: Example persistent failure"
        ]


def record_step(steps: list[str], name: str, result: object = None) -> Callable[..., object]:
    """A side effect that notes `name` on the list of steps and answers with `result`."""

    def side_effect(*_args: object, **_kwargs: object) -> object:
        steps.append(name)
        return result

    return side_effect


class TestTheNotificationCycle:
    @pytest.mark.usefixtures("udl")
    async def test_a_cycle_pulls_then_evaluates_then_summarises(
        self, sessions: SessionFactory, services: Services
    ) -> None:
        steps: list[str] = []
        services.ingest_notifications.side_effect = record_step(steps, "pull")
        services.evaluate_once.side_effect = record_step(steps, "evaluate", evaluation_run())
        services.generate_event_summary.side_effect = record_step(
            steps, "summarise", summary_outcome(EVENT)
        )
        published = publication(1, EVENT, 1)
        sessions.script(
            FakeSession(),
            FakeSession([rows_result([(synthetic_id(1),)])]),
            FakeSession(),  # the evaluation's audit row
            FakeSession([rows_result([published])]),
            FakeSession([rows_result([])]),
            history_session([published]),
        )
        await background_refresh.run_pull_notifications_now()
        assert steps == ["pull", "evaluate", "summarise"]
        assert len(sessions.opened) == 6

    async def test_a_refresh_during_a_running_cycle_joins_it(
        self,
        settings_env: SettingsEnv,
        sessions: SessionFactory,
        udl: list[FakeUDLClient],
        services: Services,
    ) -> None:
        settings_env(BACKGROUND_AUTO_EVALUATE="false")
        pulling, release = asyncio.Event(), asyncio.Event()

        async def slow_pull(*_args: object, **_kwargs: object) -> None:
            pulling.set()
            await release.wait()

        services.ingest_notifications.side_effect = slow_pull
        sessions.script(FakeSession(), FakeSession([rows_result([])]))
        async with asyncio.timeout(1):
            scheduled = asyncio.create_task(background_refresh.run_pull_notifications_now())
            await pulling.wait()
            manual = asyncio.create_task(background_refresh.run_pull_notifications_now())
            await asyncio.sleep(0)
            release.set()
            await asyncio.gather(scheduled, manual)
        services.ingest_notifications.assert_awaited_once()
        assert len(udl) == 1
        assert len(sessions.opened) == 2


Sleep = Callable[[float], Awaitable[None]]


class AsyncioWithSleep:
    """The asyncio module as the module under test sees it, with only sleep replaced."""

    def __init__(self, sleep: Sleep) -> None:
        self.sleep = sleep

    def __getattr__(self, name: str) -> Any:
        return getattr(asyncio, name)


def replace_sleep(monkeypatch: pytest.MonkeyPatch, sleep: Sleep) -> None:
    monkeypatch.setattr(background_refresh, "asyncio", AsyncioWithSleep(sleep))


class ScriptedSleep:
    """Stands in for asyncio.sleep: notes each interval on the timeline and returns at once,
    except that sleep number `park_on` waits until its task is cancelled."""

    def __init__(self, timeline: list[str], *, park_on: int) -> None:
        self.timeline = timeline
        self.park_on = park_on
        self.calls = 0
        self.parked = asyncio.Event()

    async def __call__(self, seconds: float) -> None:
        self.calls += 1
        self.timeline.append(f"sleep {seconds}s")
        if self.calls == self.park_on:
            self.parked.set()
            await asyncio.Event().wait()


class Job:
    """A loop's job: notes each run on the timeline, and can be scripted to fail or to hang
    until it is cancelled."""

    def __init__(
        self, timeline: list[str], *, failures: list[Exception] | None = None, hang: bool = False
    ) -> None:
        self.timeline = timeline
        self.failures = list(failures or [])
        self.hang = hang
        self.running = asyncio.Event()

    async def __call__(self) -> None:
        self.timeline.append("job")
        self.running.set()
        if self.hang:
            await asyncio.Event().wait()
        if self.failures:
            raise self.failures.pop(0)


async def cancel_and_wait(task: asyncio.Task[None]) -> None:
    """Cancel a loop and wait for it to end; a loop that will not end fails the test."""
    task.cancel()
    done, _pending = await asyncio.wait({task}, timeout=1)
    assert task in done


async def stop_loops(tasks: list[asyncio.Task[None]]) -> None:
    """Run stop_background_loops in a task of its own and wait for it with a timeout that never
    cancels it, so a stop that will not finish fails the test rather than hanging it."""
    stopping = asyncio.create_task(background_refresh.stop_background_loops(tasks))
    done, _pending = await asyncio.wait({stopping}, timeout=1)
    assert stopping in done
    await stopping


class TestRunForever:
    async def test_a_loop_runs_its_job_then_sleeps_its_interval_until_cancelled(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO, logger=MODULE)
        timeline: list[str] = []
        sleep = ScriptedSleep(timeline, park_on=3)
        replace_sleep(monkeypatch, sleep)
        loop = asyncio.create_task(background_refresh.run_forever("example", Job(timeline), 42))
        async with asyncio.timeout(1):
            await sleep.parked.wait()
        await cancel_and_wait(loop)
        assert loop.cancelled()
        assert timeline == ["job", "sleep 42s", "job", "sleep 42s", "job", "sleep 42s"]
        assert messages(caplog, logging.INFO) == ["Background example loop enabled: every 42s"]

    async def test_a_failed_job_is_logged_and_the_loop_carries_on(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        timeline: list[str] = []
        sleep = ScriptedSleep(timeline, park_on=2)
        replace_sleep(monkeypatch, sleep)
        error = RuntimeError("Example unexpected failure")
        job = Job(timeline, failures=[error])
        loop = asyncio.create_task(background_refresh.run_forever("example", job, 42))
        async with asyncio.timeout(1):
            await sleep.parked.wait()
        await cancel_and_wait(loop)
        assert timeline == ["job", "sleep 42s", "job", "sleep 42s"]
        [record] = logged(caplog, logging.ERROR)
        assert record.getMessage() == "Background example cycle crashed (continuing)"
        assert raised(record) is error

    async def test_cancelling_the_loop_itself_mid_job_ends_it_without_a_complaint(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        timeline: list[str] = []
        replace_sleep(monkeypatch, ScriptedSleep(timeline, park_on=1))
        job = Job(timeline, hang=True)
        loop = asyncio.create_task(background_refresh.run_forever("example", job, 42))
        async with asyncio.timeout(1):
            await job.running.wait()
        await cancel_and_wait(loop)
        assert loop.cancelled()
        assert timeline == ["job"]
        assert logged(caplog, logging.ERROR) == []
        assert logged(caplog, logging.WARNING) == []

    @pytest.mark.usefixtures("udl")
    async def test_a_cycle_cancelled_by_another_caller_does_not_end_the_loop(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sessions: SessionFactory,
        services: Services,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        pulling = asyncio.Event()

        async def slow_pull(*_args: object, **_kwargs: object) -> None:
            pulling.set()
            await asyncio.Event().wait()

        services.ingest_notifications.side_effect = slow_pull
        sessions.script(FakeSession())
        timeline: list[str] = []
        sleep = ScriptedSleep(timeline, park_on=1)
        replace_sleep(monkeypatch, sleep)
        # An operator's manual refresh leads the cycle, and the hourly loop joins it...
        manual = asyncio.create_task(background_refresh.run_pull_notifications_now())
        async with asyncio.timeout(1):
            await pulling.wait()
        hourly = background_refresh.run_pull_notifications_now
        loop = asyncio.create_task(background_refresh.run_forever("notifications", hourly, 3600))
        await asyncio.sleep(0)
        # ...then the operator's request goes away, taking the shared cycle with it.
        manual.cancel()
        async with asyncio.timeout(1):
            await sleep.parked.wait()
        assert manual.cancelled()
        services.ingest_notifications.assert_awaited_once()
        assert not loop.done()
        assert timeline == ["sleep 3600s"]
        assert messages(caplog, logging.WARNING) == [
            "Background notifications cycle was cancelled by another caller (continuing)"
        ]
        # A cancellation of the loop itself still ends it.
        await cancel_and_wait(loop)
        assert loop.cancelled()


class LoopJob:
    """One surface's job: notes the task that ran it."""

    def __init__(self, surface: str, ran: list[tuple[str, str]]) -> None:
        self.surface = surface
        self.ran = ran

    async def __call__(self) -> None:
        task = asyncio.current_task()
        assert task is not None
        self.ran.append((self.surface, task.get_name()))


class ParkingSleep:
    """Stands in for asyncio.sleep: notes which task slept for how long, then waits until that
    task is cancelled."""

    def __init__(self, loops: int) -> None:
        self.loops = loops
        self.slept: dict[str, float] = {}
        self.all_parked = asyncio.Event()

    async def __call__(self, seconds: float) -> None:
        task = asyncio.current_task()
        assert task is not None
        self.slept[task.get_name()] = seconds
        if len(self.slept) == self.loops:
            self.all_parked.set()
        await asyncio.Event().wait()


class TestStartAndStop:
    async def test_each_surface_runs_in_its_own_named_loop_on_its_own_cadence(
        self, settings_env: SettingsEnv, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings_env(
            BACKGROUND_NOTIFICATION_INTERVAL_SECONDS="1800",
            BACKGROUND_MANEUVER_INTERVAL_SECONDS="120",
            MATTERMOST_INTERVAL_SECONDS="30",
        )
        ran: list[tuple[str, str]] = []
        for surface, job in (
            ("notifications", "run_pull_notifications_now"),
            ("maneuvers", "_pull_maneuvers_once"),
            ("mattermost", "_pull_mattermost_once"),
        ):
            monkeypatch.setattr(background_refresh, job, LoopJob(surface, ran))
        sleep = ParkingSleep(loops=3)
        replace_sleep(monkeypatch, sleep)
        tasks = background_refresh.start_background_loops()
        async with asyncio.timeout(1):
            await sleep.all_parked.wait()
        await stop_loops(tasks)
        assert [task.get_name() for task in tasks] == [
            "holly-notifications",
            "holly-maneuvers",
            "holly-mattermost",
        ]
        assert sorted(ran) == [
            ("maneuvers", "holly-maneuvers"),
            ("mattermost", "holly-mattermost"),
            ("notifications", "holly-notifications"),
        ]
        assert sleep.slept == {
            "holly-notifications": 1800,
            "holly-maneuvers": 120,
            "holly-mattermost": 30,
        }
        assert all(task.cancelled() for task in tasks)

    async def test_a_loop_that_already_died_is_logged_and_the_others_are_still_stopped(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        error = RuntimeError("Example unexpected failure")
        died = asyncio.create_task(Job([], failures=[error])(), name="holly-example")
        running = asyncio.create_task(Job([], hang=True)())
        await asyncio.wait({died})
        await stop_loops([died, running])
        assert running.cancelled()
        [record] = logged(caplog, logging.ERROR)
        assert record.getMessage() == "Background task holly-example exited with error"
        assert raised(record) is error

    async def test_stopping_does_not_swallow_its_callers_own_cancellation(self) -> None:
        winding_down, release = asyncio.Event(), asyncio.Event()

        async def loop() -> None:
            """A loop that winds down slowly once cancelled; a second cancellation ends it."""
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                winding_down.set()
                await release.wait()
                raise

        running = asyncio.create_task(loop())
        await asyncio.sleep(0)
        stopping = asyncio.create_task(background_refresh.stop_background_loops([running]))
        async with asyncio.timeout(1):
            await winding_down.wait()
        # Shutdown cancels the caller while it is still waiting for the loop.
        stopping.cancel()
        done, _pending = await asyncio.wait({stopping}, timeout=1)
        assert stopping in done
        assert stopping.cancelled()
        assert running.cancelled()

    async def test_stopping_waits_for_every_loop_to_finish_winding_down(self) -> None:
        wound_down: list[str] = []

        async def loop(name: str, steps: int) -> None:
            """A loop that, like one cancelled while it closes its database session, takes
            `steps` more steps to end once it is cancelled."""
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                for _ in range(steps):
                    await asyncio.sleep(0)
                wound_down.append(name)
                raise

        tasks = [asyncio.create_task(loop("quick", 0)), asyncio.create_task(loop("slow", 5))]
        await asyncio.sleep(0)
        await stop_loops(tasks)
        assert wound_down == ["quick", "slow"]
        assert all(task.cancelled() for task in tasks)
