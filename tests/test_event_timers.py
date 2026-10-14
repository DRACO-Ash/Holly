"""Operator countdown timers (app/api/v1/routes/event_timers.py): creating a timer,
acknowledging its pre-alert, dismissing it or rolling a recurring one forward, and deleting it.

The clock and the audit chain are replaced, so each test states exactly when "now" is and
reads what a route stored and audited. No database is contacted. Every id, label and event key
here is synthetic.
"""

import itertools
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from typing import Any
from unittest.mock import AsyncMock

import httpx2
import pytest
from sqlalchemy.dialects import registry
from sqlalchemy.engine import Dialect

from app.models.event_timer import EventTimer
from app.models.user import User
from fakes import NOW, FakeSession, make_user, rows_result, scalar_result

UseSession = Callable[[FakeSession], FakeSession]
SignIn = Callable[[User], User]

TIMERS_URL = "/api/v1/event-timers"
TIMER_ROUTES = [
    ("POST", TIMERS_URL + "/{}/acknowledge-pre-alert"),
    ("POST", TIMERS_URL + "/{}/dismiss"),
    ("DELETE", TIMERS_URL + "/{}"),
]
LABEL = "TEST-SAT 99999 pass"
EVENT_KEY = "TEST-EVENT-1"

_ids = itertools.count(1)


def synthetic_id() -> uuid.UUID:
    """The next obviously synthetic id: 00000000-0000-4000-8000-000000000001, then ...0002."""
    return uuid.UUID(f"00000000-0000-4000-8000-{next(_ids):012d}")


def example_analyst() -> User:
    user = make_user(username="example.analyst")
    user.id = synthetic_id()
    return user


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def make_timer(
    *,
    target: datetime = NOW,
    recurrence: str = "none",
    pre_alert_fired_at: datetime | None = None,
    dismissed_at: datetime | None = None,
    dismissed_by: uuid.UUID | None = None,
) -> EventTimer:
    """A stored timer, as the database would return it."""
    return EventTimer(
        id=synthetic_id(),
        event_key=EVENT_KEY,
        label=LABEL,
        target_time=target,
        pre_alert_minutes=5,
        recurrence=recurrence,
        pre_alert_fired_at=pre_alert_fired_at,
        dismissed_at=dismissed_at,
        dismissed_by=dismissed_by,
        created_by=synthetic_id(),
        shift_date=None,
        created_at=NOW,
        updated_at=NOW,
    )


# PostgreSQL's own dialect, so each statement compiles exactly as the database receives it.
POSTGRESQL: Dialect = registry.load("postgresql")()


def database(*results: Any) -> FakeSession:
    """A FakeSession that also does what PostgreSQL would for a new row: flush gives it an id
    and refresh loads the timestamps the server sets. `results` answer the queries in order."""
    session = FakeSession(list(results))

    def flush() -> None:
        for row in session.added:
            if row.id is None:
                row.id = synthetic_id()

    def refresh(row: Any) -> None:
        if row.created_at is None:
            row.created_at = row.updated_at = NOW

    session.flush.side_effect = flush
    session.refresh.side_effect = refresh
    return session


def statement(session: FakeSession, index: int) -> tuple[str, list[Any]]:
    """The session's `index`th query as PostgreSQL would receive it, whitespace collapsed,
    and its bound values in order."""
    compiled = session.execute.await_args_list[index].args[0].compile(dialect=POSTGRESQL)
    return " ".join(str(compiled).split()), list(compiled.params.values())


@dataclass
class AuditCall:
    """One audit row a route asked for: the session it went to, whether that session had
    already committed (the row would then miss the change's transaction), and its fields."""

    session: FakeSession
    after_commit: bool
    fields: dict[str, Any]


@pytest.fixture(autouse=True)
def audits(monkeypatch: pytest.MonkeyPatch) -> list[AuditCall]:
    calls: list[AuditCall] = []

    def record(db: FakeSession, **fields: Any) -> None:
        calls.append(AuditCall(db, db.commit.await_count > 0, fields))

    monkeypatch.setattr("app.api.v1.routes.event_timers.write_audit", AsyncMock(side_effect=record))
    return calls


class FrozenClock:
    """Stands in for the datetime class the timer routes read the time from."""

    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self, tz: tzinfo | None = None) -> datetime:
        assert tz is UTC, "the timer routes read the time in UTC"
        return self.current


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> FrozenClock:
    """Every test runs at NOW (noon on 5 June 2026, UTC) unless it moves the clock."""
    frozen = FrozenClock(NOW)
    monkeypatch.setattr("app.api.v1.routes.event_timers.datetime", frozen)
    return frozen


class TestListTimers:
    async def test_the_active_list_hides_timers_dismissed_over_12_hours_ago(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(example_analyst())
        timers = [
            make_timer(target=NOW - timedelta(hours=1), dismissed_at=NOW - timedelta(hours=2)),
            make_timer(target=NOW + timedelta(hours=1)),
        ]
        session = use_session(database(rows_result(timers)))
        response = await api.get(TIMERS_URL)
        assert response.status_code == 200
        items = response.json()["items"]
        assert [item["id"] for item in items] == [str(timer.id) for timer in timers]
        assert items[0]["dismissed_at"] == "2026-06-05T10:00:00Z"
        sql, values = statement(session, 0)
        assert ("WHERE event_timer.dismissed_at IS NULL OR event_timer.dismissed_at >= ") in sql
        assert sql.endswith("ORDER BY event_timer.target_time ASC")
        assert values == [NOW - timedelta(hours=12)]

    async def test_include_dismissed_lists_every_timer(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(example_analyst())
        session = use_session(database(rows_result([])))
        response = await api.get(TIMERS_URL, params={"include_dismissed": "true"})
        assert response.json() == {"items": []}
        sql, values = statement(session, 0)
        assert " WHERE " not in sql
        assert sql.endswith("ORDER BY event_timer.target_time ASC")
        assert values == []


class TestCreateTimer:
    async def test_a_timer_is_stored_and_audited(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audits: list[AuditCall],
    ) -> None:
        user = sign_in(example_analyst())
        session = use_session(database())
        response = await api.post(
            TIMERS_URL,
            json={
                "label": f"  {LABEL}  ",
                "target_time": "2026-06-05T14:00:00Z",
                "event_key": EVENT_KEY,
                "pre_alert_minutes": 10,
                "recurrence": "weekly",
                "shift_date": "2026-06-05",
            },
        )
        assert response.status_code == 201
        [timer] = session.added
        assert timer.recurrence_anchor == utc(2026, 6, 5, 14)
        assert response.json() == {
            "id": str(timer.id),
            "event_key": EVENT_KEY,
            "label": LABEL,
            "target_time": "2026-06-05T14:00:00Z",
            "pre_alert_minutes": 10,
            "recurrence": "weekly",
            "pre_alert_fired_at": None,
            "dismissed_at": None,
            "dismissed_by": None,
            "created_by": str(user.id),
            "shift_date": "2026-06-05",
            "created_at": "2026-06-05T12:00:00Z",
            "updated_at": "2026-06-05T12:00:00Z",
        }
        [audit] = audits
        assert audit.fields == {
            "action_type": "event_timer.create",
            "entity_type": "event_timer",
            "entity_id": str(timer.id),
            "user_id": user.id,
            "ip_address": "127.0.0.1",
            "detail": {
                "label": LABEL,
                "event_key": EVENT_KEY,
                "target_time": "2026-06-05T14:00:00+00:00",
                "pre_alert_minutes": 10,
                "recurrence": "weekly",
            },
        }
        assert audit.session is session
        assert not audit.after_commit
        session.commit.assert_awaited_once()

    async def test_a_target_without_a_zone_is_read_as_utc(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(example_analyst())
        session = use_session(database())
        response = await api.post(
            TIMERS_URL, json={"label": LABEL, "target_time": "2026-06-05T14:00:00"}
        )
        assert response.status_code == 201
        [timer] = session.added
        assert timer.target_time.tzinfo is UTC
        assert timer.target_time == utc(2026, 6, 5, 14)
        assert response.json()["target_time"] == "2026-06-05T14:00:00Z"

    async def test_a_target_with_an_offset_keeps_its_instant(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(example_analyst())
        session = use_session(database())
        response = await api.post(
            TIMERS_URL, json={"label": LABEL, "target_time": "2026-06-05T16:00:00+02:00"}
        )
        assert response.status_code == 201
        assert session.added[0].target_time == utc(2026, 6, 5, 14)

    async def test_the_defaults_are_a_five_minute_pre_alert_and_no_recurrence(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(example_analyst())
        use_session(database())
        response = await api.post(
            TIMERS_URL, json={"label": LABEL, "target_time": "2026-06-05T14:00:00Z"}
        )
        assert response.status_code == 201
        body = response.json()
        assert (body["pre_alert_minutes"], body["recurrence"]) == (5, "none")
        assert (body["event_key"], body["shift_date"]) == (None, None)

    @pytest.mark.parametrize(
        "change",
        [
            {"label": ""},
            {"label": "x" * 201},
            {"target_time": "tomorrow"},
            {"pre_alert_minutes": -1},
            {"pre_alert_minutes": 721},
            {"recurrence": "yearly"},
            {"event_key": "k" * 201},
            {"target_time": "1999-12-31T23:59:59Z"},
            {"target_time": "2100-01-01T00:00:00Z"},
            {"target_time": "2100-01-01T00:00:00"},
        ],
    )
    async def test_a_malformed_timer_is_422_and_nothing_is_stored(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audits: list[AuditCall],
        change: dict[str, object],
    ) -> None:
        sign_in(example_analyst())
        session = use_session(database())
        body = {"label": LABEL, "target_time": "2026-06-05T14:00:00Z", **change}
        assert (await api.post(TIMERS_URL, json=body)).status_code == 422
        assert session.added == []
        assert audits == []

    @pytest.mark.parametrize("missing", ["label", "target_time"])
    async def test_a_timer_without_its_label_or_target_is_422(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, missing: str
    ) -> None:
        sign_in(example_analyst())
        session = use_session(database())
        body = {"label": LABEL, "target_time": "2026-06-05T14:00:00Z"}
        del body[missing]
        assert (await api.post(TIMERS_URL, json=body)).status_code == 422
        assert session.added == []

    async def test_a_blank_label_is_refused(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(example_analyst())
        session = use_session(database())
        response = await api.post(
            TIMERS_URL, json={"label": "   ", "target_time": "2026-06-05T14:00:00Z"}
        )
        assert response.status_code in {400, 422}
        assert session.added == []


class TestAcknowledgePreAlert:
    async def test_the_first_acknowledgement_records_now_and_is_audited(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audits: list[AuditCall],
    ) -> None:
        user = sign_in(example_analyst())
        timer = make_timer(target=NOW + timedelta(minutes=3))
        session = use_session(database(scalar_result(timer)))
        response = await api.post(f"{TIMERS_URL}/{timer.id}/acknowledge-pre-alert")
        assert response.status_code == 200
        assert response.json()["pre_alert_fired_at"] == "2026-06-05T12:00:00Z"
        assert timer.pre_alert_fired_at == NOW
        assert timer.dismissed_at is None
        [audit] = audits
        assert audit.fields == {
            "action_type": "event_timer.acknowledge_pre_alert",
            "entity_type": "event_timer",
            "entity_id": str(timer.id),
            "user_id": user.id,
            "ip_address": "127.0.0.1",
            "detail": {"label": LABEL},
        }
        assert not audit.after_commit
        session.commit.assert_awaited_once()

    async def test_a_repeat_acknowledgement_changes_nothing(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audits: list[AuditCall],
    ) -> None:
        sign_in(example_analyst())
        earlier = NOW - timedelta(minutes=2)
        timer = make_timer(target=NOW + timedelta(minutes=3), pre_alert_fired_at=earlier)
        session = use_session(database(scalar_result(timer)))
        response = await api.post(f"{TIMERS_URL}/{timer.id}/acknowledge-pre-alert")
        assert response.status_code == 200
        assert response.json()["pre_alert_fired_at"] == "2026-06-05T11:58:00Z"
        assert timer.pre_alert_fired_at == earlier
        assert audits == []
        session.commit.assert_not_awaited()


class TestDismissOneShot:
    async def test_a_one_shot_timer_is_dismissed_by_the_operator(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audits: list[AuditCall],
    ) -> None:
        user = sign_in(example_analyst())
        timer = make_timer(target=NOW - timedelta(minutes=2))
        session = use_session(database(scalar_result(timer)))
        response = await api.post(f"{TIMERS_URL}/{timer.id}/dismiss")
        assert response.status_code == 200
        body = response.json()
        assert (body["dismissed_at"], body["dismissed_by"], body["target_time"]) == (
            "2026-06-05T12:00:00Z",
            str(user.id),
            "2026-06-05T11:58:00Z",
        )
        # Dismissed before its pre-alert was seen, so the pre-alert must not fire later.
        assert timer.pre_alert_fired_at == NOW
        [audit] = audits
        assert audit.fields == {
            "action_type": "event_timer.dismiss",
            "entity_type": "event_timer",
            "entity_id": str(timer.id),
            "user_id": user.id,
            "ip_address": "127.0.0.1",
            "detail": {"label": LABEL, "target_time": "2026-06-05T11:58:00+00:00"},
        }
        assert not audit.after_commit
        session.commit.assert_awaited_once()

    async def test_dismissing_keeps_the_time_the_pre_alert_fired(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(example_analyst())
        fired = NOW - timedelta(minutes=7)
        timer = make_timer(target=NOW - timedelta(minutes=2), pre_alert_fired_at=fired)
        use_session(database(scalar_result(timer)))
        response = await api.post(f"{TIMERS_URL}/{timer.id}/dismiss")
        assert response.status_code == 200
        assert timer.pre_alert_fired_at == fired
        assert timer.dismissed_at == NOW

    async def test_an_already_dismissed_timer_is_left_as_it_was(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audits: list[AuditCall],
    ) -> None:
        sign_in(example_analyst())
        dismissed_at, dismissed_by = NOW - timedelta(hours=1), synthetic_id()
        timer = make_timer(dismissed_at=dismissed_at, dismissed_by=dismissed_by)
        session = use_session(database(scalar_result(timer)))
        response = await api.post(f"{TIMERS_URL}/{timer.id}/dismiss")
        assert response.status_code == 200
        assert response.json()["dismissed_by"] == str(dismissed_by)
        assert (timer.dismissed_at, timer.dismissed_by) == (dismissed_at, dismissed_by)
        assert audits == []
        session.commit.assert_not_awaited()


ROLL_FORWARD_CASES = [
    pytest.param(
        "daily",
        utc(2026, 6, 5, 9),
        utc(2026, 6, 5, 9, 30),
        utc(2026, 6, 6, 9),
        id="daily",
    ),
    pytest.param(
        "daily",
        utc(2026, 6, 4, 9),
        utc(2026, 6, 5, 11),
        utc(2026, 6, 6, 9),
        id="daily dismissed the next morning skips the occurrence already past",
    ),
    pytest.param(
        "daily",
        utc(2026, 6, 4, 12),
        utc(2026, 6, 5, 12),
        utc(2026, 6, 6, 12),
        id="daily occurrence at exactly now is not in the future",
    ),
    pytest.param(
        "daily",
        utc(2026, 6, 5, 12, 3),
        utc(2026, 6, 5, 12),
        utc(2026, 6, 6, 12, 3),
        id="daily dismissed during its pre-alert skips that occurrence",
    ),
    pytest.param(
        "weekly",
        utc(2026, 6, 5, 9),
        utc(2026, 6, 5, 9, 30),
        utc(2026, 6, 12, 9),
        id="weekly",
    ),
    pytest.param(
        "monthly",
        utc(2026, 6, 5, 9),
        utc(2026, 6, 5, 9, 30),
        utc(2026, 7, 5, 9),
        id="monthly",
    ),
    pytest.param(
        "monthly",
        utc(2026, 12, 15, 9),
        utc(2026, 12, 15, 9, 30),
        utc(2027, 1, 15, 9),
        id="monthly across the year end",
    ),
    pytest.param(
        "monthly",
        utc(2026, 1, 31, 9),
        utc(2026, 1, 31, 10),
        utc(2026, 2, 28, 9),
        id="monthly 31 January rolls to 28 February",
    ),
    pytest.param(
        "monthly",
        utc(2028, 1, 31, 9),
        utc(2028, 1, 31, 10),
        utc(2028, 2, 29, 9),
        id="monthly 31 January rolls to 29 February in a leap year",
    ),
]


class TestRollForward:
    @pytest.mark.parametrize(("recurrence", "target", "now", "expected"), ROLL_FORWARD_CASES)
    async def test_dismissing_a_recurring_timer_moves_it_to_its_next_future_occurrence(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audits: list[AuditCall],
        clock: FrozenClock,
        recurrence: str,
        target: datetime,
        now: datetime,
        expected: datetime,
    ) -> None:
        sign_in(example_analyst())
        clock.current = now
        timer = make_timer(target=target, recurrence=recurrence)
        use_session(database(scalar_result(timer)))
        response = await api.post(f"{TIMERS_URL}/{timer.id}/dismiss")
        assert response.status_code == 200
        assert timer.target_time == expected
        assert datetime.fromisoformat(response.json()["target_time"]) == expected
        assert timer.dismissed_at is None
        assert audits[0].fields["detail"]["next_target"] == expected.isoformat()

    async def test_a_rolled_forward_timer_stays_active_with_a_fresh_pre_alert(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audits: list[AuditCall],
        clock: FrozenClock,
    ) -> None:
        user = sign_in(example_analyst())
        clock.current = utc(2026, 6, 5, 9, 30)
        timer = make_timer(
            target=utc(2026, 6, 5, 9), recurrence="daily", pre_alert_fired_at=utc(2026, 6, 5, 8, 55)
        )
        session = use_session(database(scalar_result(timer)))
        response = await api.post(f"{TIMERS_URL}/{timer.id}/dismiss")
        assert response.status_code == 200
        body = response.json()
        assert (body["dismissed_at"], body["dismissed_by"], body["pre_alert_fired_at"]) == (
            None,
            None,
            None,
        )
        [audit] = audits
        assert audit.fields == {
            "action_type": "event_timer.roll_forward",
            "entity_type": "event_timer",
            "entity_id": str(timer.id),
            "user_id": user.id,
            "ip_address": "127.0.0.1",
            "detail": {
                "label": LABEL,
                "recurrence": "daily",
                "previous_target": "2026-06-05T09:00:00+00:00",
                "next_target": "2026-06-06T09:00:00+00:00",
            },
        }
        assert not audit.after_commit
        session.commit.assert_awaited_once()

    async def test_a_monthly_timer_keeps_its_day_of_the_month_after_a_short_month(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        clock: FrozenClock,
    ) -> None:
        sign_in(example_analyst())
        clock.current = utc(2026, 3, 1, 12)
        timer = make_timer(target=utc(2026, 1, 31, 9), recurrence="monthly")
        use_session(database(scalar_result(timer)))
        await api.post(f"{TIMERS_URL}/{timer.id}/dismiss")
        assert timer.target_time == utc(2026, 3, 31, 9)


class TestTheRecurrenceAnchor:
    async def test_a_monthly_timer_returns_to_its_day_across_dismissals(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        clock: FrozenClock,
    ) -> None:
        sign_in(example_analyst())
        timer = make_timer(target=utc(2026, 1, 31, 9), recurrence="monthly")
        timer.recurrence_anchor = utc(2026, 1, 31, 9)
        fired_and_dismissed = [
            (utc(2026, 1, 31, 10), utc(2026, 2, 28, 9)),
            (utc(2026, 2, 28, 10), utc(2026, 3, 31, 9)),
            (utc(2026, 3, 31, 10), utc(2026, 4, 30, 9)),
            (utc(2026, 4, 30, 10), utc(2026, 5, 31, 9)),
        ]
        for dismissed_at, next_target in fired_and_dismissed:
            clock.current = dismissed_at
            use_session(database(scalar_result(timer)))
            assert (await api.post(f"{TIMERS_URL}/{timer.id}/dismiss")).status_code == 200
            assert timer.target_time == next_target
            assert timer.recurrence_anchor == utc(2026, 1, 31, 9)

    async def test_a_timer_from_before_the_anchor_counts_from_its_current_target(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        clock: FrozenClock,
    ) -> None:
        sign_in(example_analyst())
        clock.current = utc(2026, 6, 5, 9, 30)
        timer = make_timer(target=utc(2026, 6, 5, 9), recurrence="weekly")
        assert timer.recurrence_anchor is None
        use_session(database(scalar_result(timer)))
        await api.post(f"{TIMERS_URL}/{timer.id}/dismiss")
        assert timer.recurrence_anchor == utc(2026, 6, 5, 9)
        assert timer.target_time == utc(2026, 6, 12, 9)

    @pytest.mark.parametrize(
        ("recurrence", "expected"),
        [
            ("daily", utc(2026, 6, 6, 9)),
            ("weekly", utc(2026, 6, 6, 9)),
            ("monthly", utc(2026, 7, 1, 9)),
        ],
    )
    async def test_a_long_overdue_timer_jumps_straight_to_its_next_occurrence(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        clock: FrozenClock,
        recurrence: str,
        expected: datetime,
    ) -> None:
        # 1 January 2000 was a Saturday, as is 6 June 2026.
        sign_in(example_analyst())
        clock.current = utc(2026, 6, 5, 12)
        timer = make_timer(target=utc(2000, 1, 1, 9), recurrence=recurrence)
        use_session(database(scalar_result(timer)))
        await api.post(f"{TIMERS_URL}/{timer.id}/dismiss")
        assert timer.target_time == expected

    async def test_an_unknown_recurrence_is_dismissed_once_and_never_loops(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        clock: FrozenClock,
    ) -> None:
        # A value written outside the API, which validates the choice.
        user = sign_in(example_analyst())
        clock.current = utc(2026, 6, 5, 12)
        timer = make_timer(target=utc(2026, 6, 5, 9), recurrence="hourly")
        use_session(database(scalar_result(timer)))
        response = await api.post(f"{TIMERS_URL}/{timer.id}/dismiss")
        assert response.status_code == 200
        assert timer.target_time == utc(2026, 6, 5, 9)
        assert (timer.dismissed_at, timer.dismissed_by) == (utc(2026, 6, 5, 12), user.id)


class TestDeleteTimer:
    async def test_a_timer_is_deleted_and_audited(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audits: list[AuditCall],
    ) -> None:
        user = sign_in(example_analyst())
        timer = make_timer()
        session = use_session(database(scalar_result(timer)))
        response = await api.delete(f"{TIMERS_URL}/{timer.id}")
        assert response.status_code == 204
        assert response.content == b""
        session.delete.assert_awaited_once_with(timer)
        [audit] = audits
        assert audit.fields == {
            "action_type": "event_timer.delete",
            "entity_type": "event_timer",
            "entity_id": str(timer.id),
            "user_id": user.id,
            "ip_address": "127.0.0.1",
            "detail": {"label": LABEL},
        }
        assert not audit.after_commit
        session.commit.assert_awaited_once()


class TestTimerLookup:
    @pytest.mark.parametrize(("method", "path"), TIMER_ROUTES)
    async def test_an_unknown_timer_is_404_and_nothing_is_written(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audits: list[AuditCall],
        method: str,
        path: str,
    ) -> None:
        sign_in(example_analyst())
        session = use_session(database(scalar_result(None)))
        missing = synthetic_id()
        response = await api.request(method, path.format(missing))
        assert response.status_code == 404
        assert response.json() == {"detail": "Timer not found"}
        assert statement(session, 0)[1] == [missing]
        assert audits == []
        session.commit.assert_not_awaited()
        session.delete.assert_not_awaited()

    @pytest.mark.parametrize(("method", "path"), TIMER_ROUTES)
    async def test_a_timer_id_that_is_not_a_uuid_is_422(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        method: str,
        path: str,
    ) -> None:
        sign_in(example_analyst())
        session = use_session(database())
        response = await api.request(method, path.format("not-a-timer-id"))
        assert response.status_code == 422
        session.execute.assert_not_awaited()


@pytest.mark.parametrize(
    ("method", "path"), [("GET", TIMERS_URL), ("POST", TIMERS_URL), *TIMER_ROUTES]
)
async def test_every_route_requires_sign_in(
    api: httpx2.AsyncClient,
    use_session: UseSession,
    audits: list[AuditCall],
    method: str,
    path: str,
) -> None:
    session = use_session(FakeSession())
    creates = (method, path) == ("POST", TIMERS_URL)
    body = {"label": LABEL, "target_time": "2026-06-05T14:00:00Z"} if creates else None
    response = await api.request(method, path.format(synthetic_id()), json=body)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    session.execute.assert_not_awaited()
    assert audits == []
