"""The Comms page's channel routes (app/api/v1/routes/mattermost.py): the channel list with what
Holly holds of each channel, the follow list any signed-in user may change, the review of new
channels, a sweep on demand and message search (ADR-015). Every name and id is made up."""

import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import httpx2
import pytest
from sqlalchemy.dialects import postgresql

from app.api.v1.routes import mattermost as routes
from app.models.mattermost_channel import MattermostChannel
from app.models.user import User
from app.services.mattermost_channels import SWEEP_STATE, SweepResult
from app.services.mattermost_ingest import MattermostIngestResult
from fakes import NOW, FakeSession, make_user, rows_result, scalar_result

UseSession = Callable[[FakeSession], FakeSession]
SignIn = Callable[[User], User]
POSTGRESQL = postgresql.dialect()  # type: ignore[no-untyped-call]
QueryPairs = list[tuple[str, str | int | float | bool | None]]
CHANNELS = "/api/v1/mattermost/channels"
MESSAGES = "/api/v1/mattermost/messages"


def stored(channel_id: str, name: str, **fields: Any) -> MattermostChannel:
    values: dict[str, Any] = {
        "team_id": "team-1",
        "team_name": "Team One",
        "display_name": name.title(),
        "channel_type": "O",
        "archived": False,
        "closed": False,
        "closed_at": None,
        "accessible": True,
        "following": True,
        "reviewed": True,
        "first_seen_at": NOW - timedelta(days=1),
        "last_seen_at": NOW,
        **fields,
    }
    return MattermostChannel(mm_channel_id=channel_id, name=name, **values)


def sql(session: FakeSession, call: int) -> str:
    statement = session.execute.await_args_list[call].args[0]
    text = statement.compile(dialect=POSTGRESQL, compile_kwargs={"literal_binds": True})
    return " ".join(str(text).split())


@pytest.fixture
def analyst(sign_in: SignIn) -> User:
    return sign_in(make_user(username="analyst"))


@pytest.fixture
def audit_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def record(_db: object, **kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(routes, "write_audit", AsyncMock(side_effect=record))
    return calls


@pytest.mark.usefixtures("analyst")
class TestTheChannelList:
    async def test_open_channels_come_first_by_name_each_with_what_holly_holds(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        zulu = stored("chan-z", "zulu")
        alpha = stored("chan-a", "alpha", reviewed=False)
        shut = stored("chan-c", "aardvark-closed", closed=True, closed_at=NOW, following=False)
        hour = math.floor(datetime.now(UTC).timestamp() / 3600)
        session = use_session(
            FakeSession(
                [
                    rows_result([zulu, shut, alpha]),
                    rows_result([("chan-a", 5, NOW)]),
                    rows_result(
                        [("chan-a", hour, 3), ("chan-a", hour - 23, 2), ("chan-a", hour - 30, 9)]
                    ),
                ]
            )
        )
        SWEEP_STATE.ok = True
        SWEEP_STATE.bot = "test-bot"
        response = await api.get(CHANNELS)
        assert response.status_code == 200
        body = response.json()
        assert [c["mm_channel_id"] for c in body["channels"]] == ["chan-a", "chan-z", "chan-c"]
        first = body["channels"][0]
        assert first["status"] == "open"
        assert first["is_new"] is True
        assert first["pulled"] is True
        assert first["message_count"] == 5
        assert first["activity"][23] == 3
        assert first["activity"][0] == 2
        assert sum(first["activity"]) == 5
        assert len(first["activity"]) == 24
        closed = body["channels"][2]
        assert (closed["status"], closed["pulled"], closed["message_count"]) == ("closed", False, 0)
        assert closed["activity"] == [0] * 24
        assert body["sweep"]["ok"] is True
        assert body["sweep"]["bot"] == "test-bot"
        assert body["sweep"]["interval_seconds"] == 60
        # Activity is counted in UTC hours from the epoch, whatever the session's time zone.
        hours = "floor(EXTRACT(epoch FROM mattermost_message.posted_at) / CAST(3600 AS NUMERIC))"
        assert hours in sql(session, 2)

    async def test_since_a_last_visit_each_channel_counts_what_arrived_after_it(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        ops = stored("chan-o", "ops")
        quiet = stored("chan-q", "quiet")
        session = use_session(
            FakeSession(
                [
                    rows_result([ops, quiet]),
                    rows_result([("chan-o", 7, NOW)]),
                    rows_result([]),
                    rows_result([("chan-o", 3)]),
                ]
            )
        )
        response = await api.get(CHANNELS, params={"since": "2026-06-05T09:00:00Z"})
        assert response.status_code == 200
        counts = {c["mm_channel_id"]: c["new_since"] for c in response.json()["channels"]}
        assert counts == {"chan-o": 3, "chan-q": 0}
        assert "mattermost_message.posted_at > '2026-06-05 09:00:00+00:00'" in sql(session, 3)

    async def test_without_a_last_visit_no_count_is_given_or_asked_for(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        session = use_session(
            FakeSession([rows_result([stored("chan-o", "ops")]), rows_result([]), rows_result([])])
        )
        response = await api.get(CHANNELS)
        assert response.json()["channels"][0]["new_since"] is None
        assert session.execute.await_count == 3

    @pytest.mark.parametrize("since", ["2026-06-05T09:00:00", "yesterday"])
    async def test_a_last_visit_without_its_time_zone_is_refused_before_any_query(
        self, api: httpx2.AsyncClient, use_session: UseSession, since: str
    ) -> None:
        session = use_session(FakeSession())
        response = await api.get(CHANNELS, params={"since": since})
        assert response.status_code == 422
        session.execute.assert_not_awaited()

    async def test_with_no_channel_found_yet_the_list_is_empty_and_asks_nothing_more(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        session = use_session(FakeSession([rows_result([])]))
        response = await api.get(CHANNELS)
        assert response.json()["channels"] == []
        assert session.execute.await_count == 1


class TestFollowingAChannel:
    async def test_any_signed_in_user_may_unfollow_and_it_is_audited(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        analyst: User,
        audit_calls: list[dict[str, Any]],
    ) -> None:
        row = stored("chan-1", "ops")
        session = use_session(FakeSession([scalar_result(row), rows_result([]), rows_result([])]))
        response = await api.patch(f"{CHANNELS}/chan-1", json={"following": False})
        assert response.status_code == 200
        assert response.json()["following"] is False
        assert response.json()["pulled"] is False
        assert (row.following, row.following_changed_by) == (False, analyst.id)
        assert row.following_changed_at is not None
        [call] = audit_calls
        assert call["action_type"] == "mattermost.channel.update"
        assert call["entity_id"] == "chan-1"
        assert call["user_id"] == analyst.id
        assert call["detail"] == {"channel": "Ops", "following": {"from": True, "to": False}}
        session.commit.assert_awaited_once()

    @pytest.mark.usefixtures("analyst")
    async def test_reviewing_a_new_channel_is_audited_and_a_repeat_changes_nothing(
        self, api: httpx2.AsyncClient, use_session: UseSession, audit_calls: list[dict[str, Any]]
    ) -> None:
        row = stored("chan-1", "ops", reviewed=False)
        use_session(FakeSession([scalar_result(row), rows_result([]), rows_result([])]))
        response = await api.patch(f"{CHANNELS}/chan-1", json={"reviewed": True})
        assert response.json()["is_new"] is False
        assert audit_calls[0]["detail"] == {"channel": "Ops", "reviewed": True}
        session = use_session(FakeSession([scalar_result(row), rows_result([]), rows_result([])]))
        await api.patch(f"{CHANNELS}/chan-1", json={"reviewed": True, "following": True})
        assert len(audit_calls) == 1
        session.commit.assert_not_awaited()

    @pytest.mark.usefixtures("analyst", "audit_calls")
    async def test_a_closed_channel_cannot_be_followed(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        row = stored("chan-1", "ops-closed", closed=True, following=False)
        session = use_session(FakeSession([scalar_result(row)]))
        response = await api.patch(f"{CHANNELS}/chan-1", json={"following": True})
        assert response.status_code == 409
        assert response.json() == {
            "detail": "This channel is closed: Holly pulls nothing more from it."
        }
        assert row.following is False
        session.commit.assert_not_awaited()

    @pytest.mark.usefixtures("analyst")
    async def test_an_unknown_channel_is_404(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        use_session(FakeSession([scalar_result(None)]))
        response = await api.patch(f"{CHANNELS}/chan-9", json={"following": False})
        assert response.status_code == 404

    @pytest.mark.usefixtures("analyst")
    @pytest.mark.parametrize(
        ("path", "body"),
        [
            ("chan-1", {}),
            ("chan-1", {"reviewed": False}),
            ("chan-1", {"following": "yes"}),
            ("bad.id", {"following": False}),
            ("x" * 65, {"following": False}),
        ],
    )
    async def test_a_change_that_names_nothing_or_a_malformed_id_is_refused_before_any_query(
        self, api: httpx2.AsyncClient, use_session: UseSession, path: str, body: dict[str, Any]
    ) -> None:
        session = use_session(FakeSession())
        response = await api.patch(f"{CHANNELS}/{path}", json=body)
        assert response.status_code == 422
        session.execute.assert_not_awaited()


class TestReviewingEveryNewChannel:
    async def test_each_new_channel_is_reviewed_in_one_audited_change(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        analyst: User,
        audit_calls: list[dict[str, Any]],
    ) -> None:
        rows = [stored("chan-2", "zeta", reviewed=False), stored("chan-1", "alpha", reviewed=False)]
        session = use_session(FakeSession([rows_result(rows)]))
        response = await api.post(f"{CHANNELS}/reviewed")
        assert response.json() == {"reviewed": 2}
        assert all(row.reviewed for row in rows)
        [call] = audit_calls
        assert call["action_type"] == "mattermost.channel.review"
        assert call["user_id"] == analyst.id
        assert call["detail"] == {"count": 2, "channels": ["Alpha", "Zeta"]}
        assert "WHERE mattermost_channel.reviewed IS false" in sql(session, 0)

    @pytest.mark.usefixtures("analyst")
    async def test_with_nothing_new_nothing_is_written(
        self, api: httpx2.AsyncClient, use_session: UseSession, audit_calls: list[dict[str, Any]]
    ) -> None:
        session = use_session(FakeSession([rows_result([])]))
        assert (await api.post(f"{CHANNELS}/reviewed")).json() == {"reviewed": 0}
        assert audit_calls == []
        session.commit.assert_not_awaited()


class TestASweepOnDemand:
    async def test_it_runs_the_cycle_as_the_caller_and_reports_what_it_found(
        self, api: httpx2.AsyncClient, analyst: User, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tally = MattermostIngestResult(
            channels_polled=3, inserted=7, sweep=SweepResult(found=4, new=1, closed=1)
        )
        run = AsyncMock(return_value=tally)
        monkeypatch.setattr(routes, "run_mattermost_now", run)
        SWEEP_STATE.ok = True
        response = await api.post("/api/v1/mattermost/sweep")
        assert response.status_code == 200
        assert response.json() == {
            "ok": True,
            "problem": None,
            "found": 4,
            "new": 1,
            "closed": 1,
            "reopened": 0,
            "lost": 0,
            "channels_polled": 3,
            "channels_failed": 0,
            "inserted": 7,
        }
        assert run.await_args is not None
        assert run.await_args.args[0] == analyst.id

    @pytest.mark.usefixtures("analyst")
    async def test_a_failed_sweep_says_why_and_six_a_minute_is_the_limit(
        self, api: httpx2.AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            routes, "run_mattermost_now", AsyncMock(return_value=MattermostIngestResult())
        )
        SWEEP_STATE.ok = False
        SWEEP_STATE.problem = "Mattermost returned HTTP 500."
        first = await api.post("/api/v1/mattermost/sweep")
        assert (first.json()["ok"], first.json()["problem"], first.json()["found"]) == (
            False,
            "Mattermost returned HTTP 500.",
            0,
        )
        for _ in range(5):
            await api.post("/api/v1/mattermost/sweep")
        limited = await api.post("/api/v1/mattermost/sweep")
        assert limited.status_code == 429
        assert limited.headers["retry-after"]


@pytest.mark.usefixtures("analyst")
class TestSearchingMessages:
    async def test_several_channels_and_a_search_narrow_the_count_and_the_page(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        session = use_session(FakeSession([scalar_result(0), rows_result([])]))
        response = await api.get(
            MESSAGES,
            params=[("channel_id", "chan-1"), ("channel_id", "chan-2"), ("q", " 50%_off\\ ")],
        )
        assert response.status_code == 200
        for call in (0, 1):
            text = sql(session, call)
            assert "mattermost_message.channel_id IN ('chan-1', 'chan-2')" in text
            assert "mattermost_message.message ILIKE" in text
            assert "ESCAPE '\\'" in text
            statement = session.execute.await_args_list[call].args[0]
            patterns = [
                value
                for value in statement.compile(dialect=POSTGRESQL).params.values()
                if isinstance(value, str) and value.startswith("%")
            ]
            # The search is trimmed, and its own wildcards and escape are taken literally.
            assert patterns == ["%50\\%\\_off\\\\%"]

    async def test_a_blank_search_filters_nothing(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        session = use_session(FakeSession([scalar_result(0), rows_result([])]))
        await api.get(MESSAGES, params={"q": "   "})
        assert "WHERE" not in sql(session, 1)

    @pytest.mark.parametrize(
        "params",
        [
            [("q", "x" * 201)],
            [("channel_id", f"chan-{n}") for n in range(201)],
            [("q", "bad\x00")],
        ],
    )
    async def test_a_search_or_a_channel_list_too_long_is_refused_before_any_query(
        self, api: httpx2.AsyncClient, use_session: UseSession, params: QueryPairs
    ) -> None:
        session = use_session(FakeSession())
        response = await api.get(MESSAGES, params=params)
        assert response.status_code == 422
        session.execute.assert_not_awaited()
