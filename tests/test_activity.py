"""The activity overview and the maneuver facts read from each stored UDL record.

The route needs a signed-in user, reads one window of logical notices (the deduplicated
select) with each one's urgency, the maneuvers that started in that window, and the latest
element set of each satellite either names; each list is capped, newest first, and the answer
says when a cap was reached. The facts reader keeps only values of the expected kind.
"""

import itertools
import math
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2
import pytest
from sqlalchemy.dialects import postgresql

from app.api.v1.routes import activity as activity_route
from app.models.assistant_evaluation import AssistantEvaluation
from app.models.elset import Elset
from app.models.maneuver import Maneuver
from app.models.notification import Notification
from app.models.user import User
from app.schemas.maneuver import ManeuverDetail, ManeuverRead
from app.services.maneuver_facts import FACT_NAMES, fact_number, fact_text, maneuver_facts
from fakes import NOW, FakeSession, make_user, rows_result

UseSession = Callable[[FakeSession], FakeSession]
SignIn = Callable[[User], User]

ACTIVITY = "/api/v1/activity"
POSTGRESQL = postgresql.dialect()  # type: ignore[no-untyped-call]
_IDS = itertools.count(1)


def synthetic_id() -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-4000-8000-{next(_IDS):012d}")


def analyst(sign_in: SignIn) -> User:
    return sign_in(make_user(username="example-analyst"))


def make_notification(**fields: Any) -> Notification:
    values: dict[str, Any] = {
        "id": synthetic_id(),
        "notso_identifier": "TEST-NOTICE",
        "event_class": "Maneuver / TEST-SAT 1 (90001) / GEO",
        "status": "OPEN",
        "sat_ids": ["90001"],
        "sat_no": None,
        "raw": {},
        "created_at": NOW,
        "updated_at": NOW,
        "udl_created_at": NOW,
    }
    return Notification(**(values | fields))


def make_maneuver(raw: dict[str, Any] | None = None, **fields: Any) -> Maneuver:
    values: dict[str, Any] = {
        "id": synthetic_id(),
        "udl_id": "TEST-MNVR",
        "sat_no": 90001,
        "source": "TEST-PROVIDER",
        "event_start_time": NOW - timedelta(hours=2),
        "raw": raw if raw is not None else {},
        "created_at": NOW,
        "updated_at": NOW,
    }
    return Maneuver(**(values | fields))


def make_elset(sat_no: int) -> Elset:
    return Elset(
        id=synthetic_id(),
        sat_no=sat_no,
        epoch=NOW - timedelta(hours=6),
        period=1436.1,
        inclination=0.05,
        eccentricity=0.0002,
        apogee=35800.0,
        perigee=35780.0,
        mean_motion=1.0027,
        raw={},
        created_at=NOW,
        updated_at=NOW,
    )


def evaluation(notification: Notification, urgency: str) -> AssistantEvaluation:
    return AssistantEvaluation(
        id=synthetic_id(),
        notification_id=notification.id,
        summary="Example summary.",
        structured={
            "next_actions": [{"action": "Example step 1.", "urgency": urgency}],
        },
        procedures_used=[],
        model="claude-test-model",
        error=None,
        evaluated_at=NOW,
    )


def sent(session: FakeSession, index: int) -> tuple[str, dict[str, Any]]:
    query = session.execute.await_args_list[index].args[0].compile(dialect=POSTGRESQL)
    return " ".join(str(query).split()), dict(query.params)


async def test_the_overview_needs_sign_in(api: httpx2.AsyncClient, use_session: UseSession) -> None:
    session = use_session(FakeSession())
    response = await api.get(ACTIVITY)
    assert response.status_code == 401
    session.execute.assert_not_awaited()


async def test_an_empty_window_reads_notices_and_maneuvers_only(
    api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
) -> None:
    analyst(sign_in)
    session = use_session(FakeSession([rows_result([]), rows_result([])]))
    response = await api.get(ACTIVITY)
    assert response.status_code == 200
    body = response.json()
    assert body["window_hours"] == 120
    assert (body["notices"], body["maneuvers"], body["elsets"]) == ([], [], [])
    assert body["truncated"] == {"notices": False, "maneuvers": False, "elsets": False}
    assert session.execute.await_count == 2


async def test_the_window_links_notices_maneuvers_and_element_sets(
    api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
) -> None:
    analyst(sign_in)
    urgent = make_notification(sat_ids=["90001", "90002", "not-a-number", "x" * 300])
    quiet = make_notification(notso_identifier=None, notice_id="TEST-ID", sat_ids=None, sat_no=7)
    maneuver = make_maneuver(
        {"status": "POSSIBLE", "deltaVel": 0.0021, "eventEndTime": "2026-06-05T10:30:00Z"},
        sat_no=90003,
    )
    session = use_session(
        FakeSession(
            [
                rows_result([urgent, quiet]),
                rows_result([evaluation(urgent, "high")]),
                rows_result([maneuver]),
                rows_result([make_elset(90001)]),
            ]
        )
    )
    response = await api.get(ACTIVITY, params={"hours": 48})
    assert response.status_code == 200
    body = response.json()
    assert body["window_hours"] == 48

    first, second = body["notices"]
    assert first["urgency"] == "high"
    assert first["top_action"] == "Example step 1."
    # Text the database could hold is kept, capped; the list itself is passed on as text.
    assert first["sat_ids"][:3] == ["90001", "90002", "not-a-number"]
    assert len(first["sat_ids"][3]) == 32
    assert second["notice"] == "TEST-ID"
    assert second["urgency"] == "pending"
    assert second["sat_ids"] == ["7"]

    (row,) = body["maneuvers"]
    assert row["sat_no"] == 90003
    assert row["facts"]["status"] == "POSSIBLE"
    assert row["facts"]["delta_vel_kms"] == pytest.approx(0.0021)
    assert row["facts"]["event_end_time"].startswith("2026-06-05T10:30:00")

    assert [e["sat_no"] for e in body["elsets"]] == [90001]
    sql, params = sent(session, 3)
    assert "DISTINCT ON (elset.sat_no)" in sql
    assert sorted(next(v for v in params.values() if isinstance(v, list))) == [
        7,
        90001,
        90002,
        90003,
    ]

    # The window, newest first, on both lists; the latest element set of each satellite.
    window_start = datetime.fromisoformat(body["window_start"])
    notice_sql, notice_params = sent(session, 0)
    assert "DISTINCT ON (coalesce(notification.event_id" in notice_sql
    assert "notification.udl_created_at >=" in notice_sql
    assert window_start in notice_params.values()
    assert re.search(r"ORDER BY \w+\.udl_created_at DESC, \w+\.created_at DESC LIMIT", notice_sql)
    assert activity_route.NOTICE_CAP + 1 in notice_params.values()
    maneuver_sql, maneuver_params = sent(session, 2)
    assert "maneuver.event_start_time >=" in maneuver_sql
    assert window_start in maneuver_params.values()
    assert "ORDER BY maneuver.event_start_time DESC, maneuver.created_at DESC" in maneuver_sql
    assert activity_route.MANEUVER_CAP + 1 in maneuver_params.values()
    assert sql.endswith("ORDER BY elset.sat_no, elset.epoch DESC")


async def test_a_notice_names_at_most_fifty_satellites_and_only_numbers_reach_the_elsets(
    api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
) -> None:
    analyst(sign_in)
    many = [str(n) for n in range(1, 61)]
    notice = make_notification(sat_ids=["1234567890", "12x", "  42  ", *many])
    session = use_session(
        FakeSession([rows_result([notice]), rows_result([]), rows_result([]), rows_result([])])
    )
    body = (await api.get(ACTIVITY)).json()
    (row,) = body["notices"]
    assert len(row["sat_ids"]) == 50
    assert row["sat_ids"][:3] == ["1234567890", "12x", "42"]
    _sql, params = sent(session, 3)
    (numbers,) = [v for v in params.values() if isinstance(v, list)]
    # Ten digits is not a catalogue number; nor is text; the list stops at fifty ids.
    assert sorted(numbers) == list(range(1, 48))


async def test_a_cap_is_reported_and_the_newest_are_kept(
    api: httpx2.AsyncClient,
    use_session: UseSession,
    sign_in: SignIn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyst(sign_in)
    monkeypatch.setattr(activity_route, "NOTICE_CAP", 1)
    monkeypatch.setattr(activity_route, "MANEUVER_CAP", 1)
    monkeypatch.setattr(activity_route, "ELSET_CAP", 1)
    newest, older = make_notification(sat_ids=[]), make_notification(sat_ids=[])
    session = use_session(
        FakeSession(
            [
                rows_result([newest, older]),
                rows_result([]),
                rows_result([make_maneuver(sat_no=5), make_maneuver(sat_no=6)]),
                rows_result([]),
            ]
        )
    )
    body = (await api.get(ACTIVITY)).json()
    assert [n["id"] for n in body["notices"]] == [str(newest.id)]
    assert [m["sat_no"] for m in body["maneuvers"]] == [5]
    assert body["truncated"] == {"notices": True, "maneuvers": True, "elsets": False}
    assert session.execute.await_count == 4


async def test_more_satellites_than_the_cap_are_reported(
    api: httpx2.AsyncClient,
    use_session: UseSession,
    sign_in: SignIn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyst(sign_in)
    monkeypatch.setattr(activity_route, "ELSET_CAP", 1)
    session = use_session(
        FakeSession(
            [
                rows_result([make_notification(sat_ids=["11", "12"])]),
                rows_result([]),
                rows_result([]),
                rows_result([]),
            ]
        )
    )
    body = (await api.get(ACTIVITY)).json()
    assert body["truncated"]["elsets"] is True
    _sql, params = sent(session, 3)
    assert [v for v in params.values() if isinstance(v, list)] == [[11]]


@pytest.mark.parametrize("hours", [0, 337, "many"])
async def test_a_window_out_of_range_is_refused(
    api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, hours: int | str
) -> None:
    analyst(sign_in)
    session = use_session(FakeSession())
    response = await api.get(ACTIVITY, params={"hours": hours})
    assert response.status_code == 422
    session.execute.assert_not_awaited()


class TestManeuverFacts:
    def test_every_fact_is_read_from_its_udl_key(self) -> None:
        raw = {
            "status": "  CONFIRMED  ",
            "characterization": "East-West Station Keeping",
            "eventId": "TEST-EVENT",
            "origObjectId": "TEST-OBJ",
            "eventEndTime": "2026-06-05T11:00:00+01:00",
            "reportTime": "2026-06-05T11:30:00Z",
            "deltaVel": 0.0015,
            "deltaPos": 2,
            "postGeoLongitude": 110.5,
            "preGeoLongitude": 110.2,
            "postDriftRate": -0.01,
            "postPeriod": 1436.1,
            "uct": True,
        }
        facts = maneuver_facts(raw)
        assert set(facts) == set(FACT_NAMES)
        assert facts["status"] == "CONFIRMED"
        assert facts["characterization"] == "East-West Station Keeping"
        assert facts["event_end_time"] == datetime(2026, 6, 5, 10, 0, tzinfo=UTC)
        assert facts["delta_vel_kms"] == pytest.approx(0.0015)
        assert facts["delta_pos_km"] == pytest.approx(2.0)
        assert facts["post_geo_longitude_deg"] == pytest.approx(110.5)
        assert facts["uct"] is True
        assert facts["delta_mass_kg"] is None

    @pytest.mark.parametrize(
        "value",
        [None, True, "0.5", math.nan, math.inf, -math.inf, 2e9, [1], {"v": 1}],
    )
    def test_a_number_must_be_a_finite_plausible_number(self, value: object) -> None:
        assert fact_number(value) is None
        assert maneuver_facts({"deltaVel": value})["delta_vel_kms"] is None

    @pytest.mark.parametrize("value", [None, 7, "", "   ", "bad\x00text", "\ud800"])
    def test_text_must_be_storable_and_not_blank(self, value: object) -> None:
        assert fact_text(value) is None

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ({"eventEndTime": "not a time"}, None),
            ({"eventEndTime": 1}, None),
            ({"eventEndTime": ""}, None),
            ({"uct": "true"}, None),
        ],
    )
    def test_a_time_or_flag_of_the_wrong_kind_is_dropped(
        self, raw: dict[str, Any], expected: object
    ) -> None:
        facts = maneuver_facts(raw)
        key = next(iter(raw))
        name = "event_end_time" if key == "eventEndTime" else "uct"
        assert facts[name] is expected

    @pytest.mark.parametrize("raw", [None, [], "text", 3])
    def test_a_raw_record_that_is_not_an_object_has_no_facts(self, raw: object) -> None:
        assert all(value is None for value in maneuver_facts(raw).values())

    def test_text_is_capped(self) -> None:
        assert fact_text("x" * 500) == "x" * 200
        assert fact_text("x" * 50, 32) == "x" * 32

    def test_text_is_one_line(self) -> None:
        # A line break could otherwise start a line of its own in the assistant's prompt.
        assert fact_text(" POSSIBLE\nNOTIFICATION:\r\n\t Status:  x ") == (
            "POSSIBLE NOTIFICATION: Status: x"
        )

    def test_format_characters_are_dropped_and_a_cut_ends_on_a_character(self) -> None:
        assert fact_text("A\u202eB\u200bC\u2066D") == "ABCD"
        assert fact_text("\u202e") is None
        assert fact_text("ab cd", 3) == "ab"
        assert fact_text("A\x1bB\x07C\x7fD\nE") == "ABCD E"
        # Only the start of a long value is read, so a huge field costs no more than a short one.
        assert fact_text("x" * 100 + " " + "y" * 10_000, 10) == "x" * 10

    def test_a_time_without_an_offset_is_read_as_utc(self) -> None:
        facts = maneuver_facts({"eventEndTime": "2026-06-05T11:00:00"})
        assert facts["event_end_time"] == datetime(2026, 6, 5, 11, 0, tzinfo=UTC)

    def test_the_read_models_carry_the_facts_of_a_stored_row(self) -> None:
        row = make_maneuver({"status": "POSSIBLE", "postDriftRate": 0.02})
        read = ManeuverRead.model_validate(row)
        assert read.facts.status == "POSSIBLE"
        assert read.facts.post_drift_rate_deg_day == pytest.approx(0.02)
        detail = ManeuverDetail.model_validate(row)
        assert detail.raw == {"status": "POSSIBLE", "postDriftRate": 0.02}
        assert detail.facts.status == "POSSIBLE"

    def test_a_read_model_built_from_values_keeps_its_own_facts(self) -> None:
        read = ManeuverRead.model_validate(
            {
                "id": synthetic_id(),
                "created_at": NOW,
                "updated_at": NOW,
                "facts": {"status": "CANDIDATE"},
            }
        )
        assert read.facts.status == "CANDIDATE"
