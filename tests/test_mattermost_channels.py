"""The channel sweep (app/services/mattermost_channels.py): which channels the bot can read,
which are closed, which are new, and which Holly pulls (ADR-015). Every name and id here is
made up for the tests."""

from collections.abc import Callable
from datetime import timedelta
from functools import partial
from typing import Any, cast
from unittest.mock import AsyncMock

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mattermost_channel import MattermostChannel
from app.services import mattermost_channels, mattermost_ingest
from app.services.mattermost_channels import (
    SWEEP_STATE,
    FoundChannel,
    channels_to_pull,
    found_channel,
    is_closed,
    list_bot_channels,
    record_sweep,
    sweep_channels,
)
from app.services.mattermost_client import MattermostClient, MattermostClientError
from fakes import NOW, FakeSession, rows_result, scalar_result

SettingsEnv = Callable[..., None]
API = "/api/v4"
BASE_URL = "https://chat.example.test"
BOT_TOKEN = "tok-1"  # noqa: S105
Route = tuple[int, Any]


class FakeMattermost:
    def __init__(self, routes: dict[str, Route]) -> None:
        self.routes = routes
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        status, body = self.routes.get(request.url.path, (404, {"message": "no such route"}))
        return httpx2.Response(status, json=body)

    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]


def client_for(server: FakeMattermost) -> MattermostClient:
    return MattermostClient(
        base_url=BASE_URL, bot_token=BOT_TOKEN, transport=httpx2.MockTransport(server)
    )


def channel(
    channel_id: str, name: str, *, kind: str = "O", display: str | None = None, deleted: int = 0
) -> dict[str, Any]:
    return {
        "id": channel_id,
        "type": kind,
        "name": name,
        "display_name": display if display is not None else name.title(),
        "delete_at": deleted,
    }


def team_routes(*teams: tuple[str, str, list[dict[str, Any]]]) -> dict[str, Route]:
    routes: dict[str, Route] = {
        f"{API}/users/me": (200, {"username": "test-bot"}),
        f"{API}/users/me/teams": (
            200,
            [{"id": team_id, "display_name": name} for team_id, name, _ in teams],
        ),
    }
    for team_id, _name, channels in teams:
        routes[f"{API}/users/me/teams/{team_id}/channels"] = (200, channels)
    return routes


def found(channel_id: str, name: str, **fields: Any) -> FoundChannel:
    values: dict[str, Any] = {
        "team_id": "team-1",
        "team_name": "Team One",
        "display_name": name.title(),
        "channel_type": "O",
        "archived": False,
        **fields,
    }
    # As found_channel decides it, from the names it was sent.
    values.setdefault("closed", is_closed(name, values["display_name"], values["archived"]))
    return FoundChannel(mm_channel_id=channel_id, name=name, **values)


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
        "last_seen_at": NOW - timedelta(minutes=1),
        **fields,
    }
    return MattermostChannel(mm_channel_id=channel_id, name=name, **values)


def db(session: FakeSession) -> AsyncSession:
    return cast(AsyncSession, session)


class TestTheClosedRule:
    @pytest.mark.parametrize(
        "name",
        [
            "CLOSED - Op Falcon",
            "op-falcon-closed",
            "Closed",
            "closed_ops",
            "Op (closed)",
            "2026 CLOSED",
        ],
    )
    def test_the_word_closed_in_any_case_closes_a_channel(self, name: str) -> None:
        assert is_closed(name, None, archived=False)

    @pytest.mark.parametrize(
        "name", ["Disclosed reports", "closedown-plan", "enclosed", "Op Falcon"]
    )
    def test_a_word_that_only_holds_the_letters_does_not(self, name: str) -> None:
        assert not is_closed(name, None, archived=False)

    def test_the_display_name_counts_as_well_as_the_name(self) -> None:
        assert is_closed("op-falcon", "Op Falcon CLOSED", archived=False)

    def test_an_archived_channel_is_closed_whatever_its_name(self) -> None:
        assert is_closed("op-falcon", "Op Falcon", archived=True)


class TestAChannelRecord:
    def test_a_public_or_private_channel_is_kept_with_its_names(self) -> None:
        kept = found_channel(channel("chan-1", "op-falcon", kind="P"), "team-1", "Team One")
        assert kept == FoundChannel(
            mm_channel_id="chan-1",
            team_id="team-1",
            team_name="Team One",
            name="op-falcon",
            display_name="Op-Falcon",
            channel_type="P",
            archived=False,
        )

    @pytest.mark.parametrize(
        "record",
        [
            channel("chan-1", "direct", kind="D"),
            channel("chan-1", "group", kind="G"),
            channel("chan/../x", "op"),
            channel("chan-1", ""),
            channel("chan-1", "bad\x00name"),
            channel("chan-1", "bad\u202ename"),
            {"id": 7, "type": "O", "name": "op"},
            {"id": "chan-1", "type": ["O"], "name": "op"},
            {"id": "chan-1", "type": {"O": 1}, "name": "op"},
            ["not", "a", "record"],
        ],
    )
    def test_a_conversation_or_a_malformed_record_is_left_out(self, record: object) -> None:
        assert found_channel(record, "team-1", None) is None

    def test_delete_at_marks_it_archived_and_a_true_value_does_not(self) -> None:
        archived = found_channel(channel("chan-1", "op", deleted=1_700_000_000_000), "t", None)
        assert archived is not None
        assert archived.archived is True
        kept = found_channel({**channel("chan-2", "op"), "delete_at": True}, "t", None)
        assert kept is not None
        assert kept.archived is False

    @pytest.mark.parametrize(
        "display",
        [
            "CLOSED \U0001f469\u200d\U0001f4bb dev",
            "CLOSED\tOp Falcon",
            "Op Falcon\u200b CLOSED",
            "Op Falcon CLO\u200bSED",
            "Op Falcon \u202eCLOSED",
            "Op Falcon " + "x" * 300 + " CLOSED",
            "Op Falcon CLO\u034fSED",
            "Op Falcon CLO\ufe0fSED",
            "Op Falcon CLO\U000e0100SED",
            "Op Falcon CLO\u3164SED",
            "Op Falcon CLO\x00SED",
            "Op Falcon \uff23\uff2c\uff2f\uff33\uff25\uff24",
            "Op Falcon \U0001d402\U0001d40b\U0001d40e\U0001d412\U0001d404\U0001d403",
        ],
    )
    def test_closed_in_a_display_name_holly_cannot_show_still_closes_it(self, display: str) -> None:
        kept = found_channel({**channel("chan-1", "op-falcon"), "display_name": display}, "t", None)
        assert kept is not None
        assert kept.closed is True

    @pytest.mark.parametrize(
        "display",
        [
            "Disclosed reports",
            "\u0106LOSED",
            "CLO\u0301SED",
            "CLOSEDOWN",
            "Op \u0421LOSED",
            ["CLOSED"],
        ],
    )
    def test_another_word_letter_or_value_leaves_it_open(self, display: object) -> None:
        # An accented letter is another letter, and a Cyrillic look-alike is accepted as a gap
        # (SECURITY.md); a display name that is not text is never Mattermost's.
        kept = found_channel({**channel("chan-1", "op-falcon"), "display_name": display}, "t", None)
        assert kept is not None
        assert kept.closed is False

    def test_a_name_without_the_word_stays_open_whatever_it_holds(self) -> None:
        kept = found_channel(
            {
                **channel("chan-1", "op-falcon"),
                "display_name": "Disclosed\u200b \U0001f469\u200d\U0001f4bb",
            },
            "t",
            None,
        )
        assert kept is not None
        assert kept.closed is False

    @pytest.mark.parametrize("deleted", [1.5e12, 1, float("inf"), float("nan")])
    def test_any_number_above_nothing_in_delete_at_archives_it(self, deleted: float) -> None:
        kept = found_channel({**channel("chan-1", "op"), "delete_at": deleted}, "t", None)
        assert kept is not None
        assert (kept.archived, kept.closed) == (True, True)

    async def test_a_known_channel_renamed_closed_in_a_way_holly_cannot_show_closes(
        self,
    ) -> None:
        row = stored("chan-1", "ops")
        raw = {**channel("chan-1", "ops"), "display_name": "CLOSED\tOps"}
        swept = found_channel(raw, "team-1", "Team One")
        assert swept is not None
        result = await record_sweep(db(FakeSession([rows_result([row])])), [swept], NOW)
        assert (row.closed, result.closed, row.display_name) == (True, 1, None)

    def test_long_names_are_cut_and_a_bad_display_name_is_dropped(self) -> None:
        kept = found_channel({**channel("chan-1", "n" * 300), "display_name": "bad\x07"}, "t", None)
        assert kept is not None
        assert len(kept.name) == 200
        assert kept.display_name is None


class TestListingTheBotsChannels:
    async def test_every_team_is_listed_and_a_channel_in_two_teams_is_kept_once(self) -> None:
        server = FakeMattermost(
            team_routes(
                ("team-1", "Team One", [channel("chan-1", "ops"), channel("dm-1", "x", kind="D")]),
                ("team-2", "Team Two", [channel("chan-1", "ops"), channel("chan-2", "intel")]),
            )
        )
        async with client_for(server) as client:
            channels, skipped = await list_bot_channels(client)
        assert sorted(c.mm_channel_id for c in channels) == ["chan-1", "chan-2"]
        # The direct message is left out by design, not counted as skipped.
        assert skipped == 0
        assert f"{API}/users/me/teams/team-2/channels" in server.paths()
        assert server.requests[1].url.params["include_deleted"] == "true"

    async def test_a_malformed_team_or_channel_is_counted_skipped(self) -> None:
        routes = team_routes(("team-1", "Team One", [channel("chan-1", "ops"), {"id": "x"}]))
        routes[f"{API}/users/me/teams"] = (200, [{"id": "team-1"}, {"id": "bad/id"}, "junk"])
        async with client_for(FakeMattermost(routes)) as client:
            channels, skipped = await list_bot_channels(client)
        assert [c.mm_channel_id for c in channels] == ["chan-1"]
        assert skipped == 3

    async def test_a_type_that_is_not_text_is_counted_skipped_not_raised(self) -> None:
        odd = [{**channel("chan-1", "ops"), "type": ["O"]}, {**channel("chan-2", "x"), "type": {}}]
        routes = team_routes(("team-1", "Team One", odd))
        async with client_for(FakeMattermost(routes)) as client:
            assert await list_bot_channels(client) == ([], 2)

    async def test_more_teams_or_channels_than_the_caps_fail_the_sweep(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(mattermost_channels, "MAX_TEAMS", 1)
        monkeypatch.setattr(mattermost_channels, "MAX_CHANNELS", 1)
        two_teams = team_routes(("team-1", "One", []), ("team-2", "Two", []))
        async with client_for(FakeMattermost(two_teams)) as client:
            with pytest.raises(MattermostClientError, match="more than 1 teams"):
                await list_bot_channels(client)
        two_channels = team_routes(("team-1", "One", [channel("c-1", "a"), channel("c-2", "b")]))
        async with client_for(FakeMattermost(two_channels)) as client:
            with pytest.raises(MattermostClientError, match="more than 1 channels"):
                await list_bot_channels(client)
        one_each = team_routes(("team-1", "One", [channel("c-1", "a")]))
        async with client_for(FakeMattermost(one_each)) as client:
            assert len((await list_bot_channels(client))[0]) == 1

    async def test_a_listing_that_fails_part_way_fails_the_whole(self) -> None:
        routes = team_routes(("team-1", "Team One", [channel("chan-1", "ops")]))
        routes[f"{API}/users/me/teams"] = (200, [{"id": "team-1"}, {"id": "team-2"}])
        async with client_for(FakeMattermost(routes)) as client:
            with pytest.raises(MattermostClientError):
                await list_bot_channels(client)


class TestRecordingASweep:
    async def test_a_new_channel_is_followed_at_once_and_new_and_a_closed_one_dated(self) -> None:
        session = FakeSession([rows_result([stored("chan-0", "known")])])
        sweep = [found("chan-0", "known"), found("chan-1", "ops"), found("chan-2", "x-closed")]
        result = await record_sweep(db(session), sweep, NOW)
        fresh, closed = session.added
        assert (fresh.mm_channel_id, fresh.following, fresh.reviewed) == ("chan-1", True, False)
        assert (fresh.first_seen_at, fresh.last_seen_at, fresh.closed) == (NOW, NOW, False)
        # One found already closed is nothing to review: Holly pulls nothing from it.
        assert (closed.closed, closed.closed_at, closed.reviewed) == (True, NOW, True)
        assert (result.found, result.new) == (3, 1)
        session.flush.assert_awaited_once()

    async def test_on_the_first_sweep_the_seeded_channels_arrive_reviewed(
        self, settings_env: SettingsEnv
    ) -> None:
        settings_env(MATTERMOST_CHANNEL_IDS="chan-1, not/an/id")
        session = FakeSession([rows_result([])])
        sweep = [found("chan-1", "ops"), found("chan-2", "intel")]
        result = await record_sweep(db(session), sweep, NOW)
        seeded, other = session.added
        assert (seeded.reviewed, other.reviewed) == (True, False)
        assert (seeded.following, other.following) == (True, True)
        assert result.new == 1

    async def test_a_seed_the_first_sweep_does_not_find_is_logged(
        self, settings_env: SettingsEnv, caplog: pytest.LogCaptureFixture
    ) -> None:
        settings_env(MATTERMOST_CHANNEL_IDS="chan-1,chan-9,chan-8")
        await record_sweep(db(FakeSession([rows_result([])])), [found("chan-1", "ops")], NOW)
        assert [r.getMessage() for r in caplog.records] == [
            "The sweep did not find 2 channel(s) MATTERMOST_CHANNEL_IDS names: chan-8, chan-9"
        ]

    async def test_a_seed_entry_is_trimmed_and_one_that_is_not_an_id_is_ignored(
        self, settings_env: SettingsEnv
    ) -> None:
        settings_env(MATTERMOST_CHANNEL_IDS=" chan-1 ,,chan/2, ,chan-3")
        assert mattermost_channels.seed_channel_ids() == {"chan-1", "chan-3"}

    async def test_after_the_first_sweep_the_seed_no_longer_counts(
        self, settings_env: SettingsEnv
    ) -> None:
        settings_env(MATTERMOST_CHANNEL_IDS="chan-1")
        session = FakeSession([rows_result([stored("chan-0", "known")])])
        await record_sweep(db(session), [found("chan-0", "known"), found("chan-1", "ops")], NOW)
        [added] = session.added
        assert added.reviewed is False

    async def test_a_known_channel_takes_its_new_names_and_closes_or_reopens(self) -> None:
        renamed = stored("chan-1", "ops")
        reopened = stored("chan-2", "intel-closed", closed=True, closed_at=NOW - timedelta(days=2))
        archived = stored("chan-3", "logs")
        session = FakeSession([rows_result([renamed, reopened, archived])])
        sweep = [
            found("chan-1", "ops-2", display_name="Ops Two", team_name="Team Renamed"),
            found("chan-2", "intel"),
            found("chan-3", "logs", archived=True),
        ]
        result = await record_sweep(db(session), sweep, NOW)
        assert (renamed.name, renamed.display_name, renamed.team_name) == (
            "ops-2",
            "Ops Two",
            "Team Renamed",
        )
        assert (reopened.closed, reopened.closed_at) == (False, None)
        assert (archived.closed, archived.archived, archived.closed_at) == (True, True, NOW)
        assert (result.closed, result.reopened, result.new) == (1, 1, 0)
        assert session.added == []
        assert all(row.last_seen_at == NOW for row in (renamed, reopened, archived))

    async def test_a_channel_still_closed_keeps_the_date_it_closed(self) -> None:
        since = NOW - timedelta(days=3)
        row = stored("chan-1", "ops-closed", closed=True, closed_at=since)
        result = await record_sweep(
            db(FakeSession([rows_result([row])])), [found("chan-1", "ops-closed")], NOW
        )
        assert row.closed_at == since
        assert result.closed == 0

    async def test_a_sweep_that_skipped_a_record_marks_nothing_lost(self) -> None:
        row = stored("chan-1", "ops")
        result = await record_sweep(db(FakeSession([rows_result([row])])), [], NOW, skipped=1)
        assert (row.accessible, result.lost, result.skipped) == (True, 0, 1)

    async def test_a_channel_no_longer_found_is_lost_once_and_found_again_later(self) -> None:
        row = stored("chan-1", "ops")
        result = await record_sweep(db(FakeSession([rows_result([row])])), [], NOW)
        assert (row.accessible, result.lost) == (False, 1)
        again = await record_sweep(db(FakeSession([rows_result([row])])), [], NOW)
        assert again.lost == 0
        await record_sweep(db(FakeSession([rows_result([row])])), [found("chan-1", "ops")], NOW)
        assert row.accessible is True


class TestASweep:
    async def test_a_sweep_records_its_success_and_asks_the_bots_name_once(self) -> None:
        server = FakeMattermost(team_routes(("team-1", "Team One", [channel("chan-1", "ops")])))
        session = FakeSession([rows_result([]), rows_result([])])
        async with client_for(server) as client:
            first = await sweep_channels(db(session), client)
            await sweep_channels(db(session), client)
        assert first is not None
        assert first.found == 1
        assert SWEEP_STATE.ok is True
        assert SWEEP_STATE.problem is None
        assert SWEEP_STATE.bot == "test-bot"
        assert SWEEP_STATE.last_at is not None
        assert server.paths().count(f"{API}/users/me") == 1

    async def test_a_failed_sweep_changes_nothing_and_says_why_in_holly_s_words(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        routes = team_routes()
        routes[f"{API}/users/me/teams"] = (500, {"message": "upstream detail never shown"})
        session = FakeSession()
        async with client_for(FakeMattermost(routes)) as client:
            assert await sweep_channels(db(session), client) is None
        session.execute.assert_not_awaited()
        assert SWEEP_STATE.ok is False
        assert SWEEP_STATE.problem == "Mattermost returned HTTP 500."
        # The operator's log says so in the same words; the client's own warning keeps
        # Mattermost's body for the server log alone.
        swept = [r.getMessage() for r in caplog.records if r.name.endswith("mattermost_channels")]
        assert swept == ["Mattermost channel sweep failed: Mattermost returned HTTP 500."]

    async def test_any_other_failure_fails_closed_in_holly_s_words(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        server = FakeMattermost(team_routes(("team-1", "Team One", [channel("chan-1", "ops")])))
        monkeypatch.setattr(
            mattermost_channels, "record_sweep", AsyncMock(side_effect=RuntimeError("boom"))
        )
        session = FakeSession()
        async with client_for(server) as client:
            assert await sweep_channels(db(session), client) is None
        session.rollback.assert_awaited_once()
        assert SWEEP_STATE.ok is False
        assert SWEEP_STATE.problem == mattermost_channels.UNEXPECTED
        assert "boom" not in SWEEP_STATE.problem
        assert "Mattermost channel sweep crashed" in caplog.text

    async def test_a_sweep_that_skipped_records_says_so_in_the_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        server = FakeMattermost(team_routes(("team-1", "Team One", [{"id": "x"}])))
        async with client_for(server) as client:
            result = await sweep_channels(db(FakeSession([rows_result([])])), client)
        assert result is not None
        assert result.skipped == 1
        assert "skipped 1 malformed record(s); none marked lost" in caplog.text


class TestTheChannelsToPull:
    async def test_followed_open_readable_channels_are_pulled_with_their_names(self) -> None:
        rows = [
            stored("chan-3", "zeta"),
            stored("chan-1", "alpha", display_name=None),
            stored("chan-2", "unfollowed", following=False),
            stored("chan-4", "shut", closed=True),
            stored("chan-5", "gone", accessible=False),
        ]
        pulled = await channels_to_pull(db(FakeSession([rows_result(rows)])))
        assert pulled == {"chan-1": "alpha", "chan-3": "Zeta"}

    async def test_before_any_sweep_the_settings_name_the_channels(
        self, settings_env: SettingsEnv
    ) -> None:
        settings_env(MATTERMOST_CHANNEL_IDS="chan-2, chan-1")
        pulled = await channels_to_pull(db(FakeSession([rows_result([])])))
        assert pulled == {"chan-1": None, "chan-2": None}


async def test_a_cycle_sweeps_then_pulls_the_followed_open_channels_and_audits_both(
    monkeypatch: pytest.MonkeyPatch, settings_env: SettingsEnv
) -> None:
    routes = team_routes(
        ("team-1", "Team One", [channel("chan-1", "ops"), channel("chan-2", "old-closed")])
    )
    routes[f"{API}/channels/chan-1/posts"] = (200, {"order": [], "posts": {}})
    server = FakeMattermost(routes)
    settings_env(MATTERMOST_URL=BASE_URL, MATTERMOST_BOT_TOKEN=BOT_TOKEN)
    bound = partial(MattermostClient, transport=httpx2.MockTransport(server))
    monkeypatch.setattr(mattermost_ingest, "MattermostClient", bound)
    audit = AsyncMock()
    monkeypatch.setattr(mattermost_ingest, "write_audit", audit)
    session = FakeSession()

    def execute(statement: object, *_args: object) -> object:
        # The channel table holds what the sweep has added so far, as a flushed session would.
        if str(statement).startswith("SELECT mattermost_channel"):
            return rows_result(list(session.added))
        return scalar_result(None)

    session.execute.side_effect = execute
    asked_at_commit: list[list[str]] = []
    session.commit.side_effect = lambda: asked_at_commit.append(server.paths())
    result = await mattermost_ingest.ingest_mattermost_messages(db(session))
    assert result.sweep is not None
    assert (result.sweep.found, result.sweep.new, result.sweep.closed) == (2, 1, 0)
    assert result.channels_polled == 1
    # The closed channel is never asked for, and the pulled one's name came from the sweep.
    assert f"{API}/channels/chan-2/posts" not in server.paths()
    assert f"{API}/channels/chan-1" not in server.paths()
    [call] = audit.await_args_list
    assert call.kwargs["detail"]["sweep"] == {
        "found": 2,
        "new": 1,
        "closed": 0,
        "reopened": 0,
        "lost": 0,
        "skipped": 0,
    }
    # The sweep is committed before any post is asked for, then the pull with its audit row.
    assert session.commit.await_count == 2
    assert not any(path.endswith("/posts") for path in asked_at_commit[0])
    assert f"{API}/channels/chan-1/posts" in asked_at_commit[1]


async def test_a_sweep_that_changed_nothing_and_pulled_nothing_is_committed_not_audited(
    monkeypatch: pytest.MonkeyPatch, settings_env: SettingsEnv
) -> None:
    server = FakeMattermost(team_routes(("team-1", "Team One", [channel("chan-1", "o-closed")])))
    settings_env(MATTERMOST_URL=BASE_URL, MATTERMOST_BOT_TOKEN=BOT_TOKEN)
    bound = partial(MattermostClient, transport=httpx2.MockTransport(server))
    monkeypatch.setattr(mattermost_ingest, "MattermostClient", bound)
    audit = AsyncMock()
    monkeypatch.setattr(mattermost_ingest, "write_audit", audit)
    known = stored("chan-1", "o-closed", closed=True, closed_at=NOW)
    session = FakeSession([rows_result([known]), rows_result([known])])
    result = await mattermost_ingest.ingest_mattermost_messages(db(session))
    assert result.sweep is not None
    assert result.channels_polled == 0
    audit.assert_not_awaited()
    # Only the sweep's own commit: when each channel was last seen is kept.
    session.commit.assert_awaited_once()


async def test_a_sweep_that_only_lost_a_channel_is_audited(
    monkeypatch: pytest.MonkeyPatch, settings_env: SettingsEnv
) -> None:
    server = FakeMattermost(team_routes(("team-1", "Team One", [])))
    settings_env(MATTERMOST_URL=BASE_URL, MATTERMOST_BOT_TOKEN=BOT_TOKEN)
    bound = partial(MattermostClient, transport=httpx2.MockTransport(server))
    monkeypatch.setattr(mattermost_ingest, "MattermostClient", bound)
    audit = AsyncMock()
    monkeypatch.setattr(mattermost_ingest, "write_audit", audit)
    gone = stored("chan-1", "ops")
    session = FakeSession([rows_result([gone]), rows_result([gone])])
    await mattermost_ingest.ingest_mattermost_messages(db(session))
    [call] = audit.await_args_list
    assert call.kwargs["detail"]["sweep"]["lost"] == 1
    assert session.commit.await_count == 2


async def test_a_sweep_that_only_skipped_a_record_is_audited(
    monkeypatch: pytest.MonkeyPatch, settings_env: SettingsEnv
) -> None:
    known = stored("chan-1", "o-closed", closed=True, closed_at=NOW)
    server = FakeMattermost(
        team_routes(("team-1", "Team One", [channel("chan-1", "o-closed"), {"id": "x"}]))
    )
    settings_env(MATTERMOST_URL=BASE_URL, MATTERMOST_BOT_TOKEN=BOT_TOKEN)
    bound = partial(MattermostClient, transport=httpx2.MockTransport(server))
    monkeypatch.setattr(mattermost_ingest, "MattermostClient", bound)
    audit = AsyncMock()
    monkeypatch.setattr(mattermost_ingest, "write_audit", audit)
    session = FakeSession([rows_result([known]), rows_result([known])])
    result = await mattermost_ingest.ingest_mattermost_messages(db(session))
    assert result.channels_polled == 0
    [call] = audit.await_args_list
    assert call.kwargs["detail"]["sweep"]["skipped"] == 1
    assert session.commit.await_count == 2


def test_a_pulled_channel_is_followed_open_and_readable() -> None:
    assert mattermost_channels.is_pulled(stored("c", "a"))
    for field in ({"following": False}, {"closed": True}, {"accessible": False}):
        assert not mattermost_channels.is_pulled(stored("c", "a", **field))


def test_the_sweep_state_is_forgotten_between_tests() -> None:
    assert SWEEP_STATE.last_at is None
    mattermost_channels.SWEEP_STATE.ok = True
    mattermost_channels.forget_sweep()
    assert SWEEP_STATE.ok is None
