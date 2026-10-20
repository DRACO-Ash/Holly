"""The Mattermost integration: what the bot client sends and how it fails, the ingest that stores
each channel's new posts once, and the signed-in messages route.

Mattermost is an in-memory fake behind httpx2.MockTransport, the database a FakeSession, and the
audit chain (test_audit covers it) a recorder, so each test reads exactly what was sent and
stored. Every id, name, host and address here is synthetic: hosts sit under the reserved
.example domain and addresses in the 192.0.2.0/24 documentation range.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from functools import partial
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import httpx2
import pytest
from sqlalchemy import Insert, Table, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import TOKEN_HEADER
from app.models.mattermost_message import MattermostMessage
from app.models.user import User
from app.services import mattermost_ingest
from app.services.mattermost_client import (
    MattermostAuthError,
    MattermostClient,
    MattermostClientError,
    datetime_to_ms,
    ms_to_datetime,
)
from app.services.mattermost_ingest import MattermostIngestResult, ingest_mattermost_messages
from fakes import NOW, FakeSession, make_user, rows_result, scalar_result

Route = tuple[int, Any]
Handler = Callable[[httpx2.Request], httpx2.Response]
SettingsEnv = Callable[..., None]
UseSession = Callable[[FakeSession], FakeSession]
SignIn = Callable[[User], User]

# Short placeholders handed to the client in place of a bot token. Neither is a credential.
BOT_TOKEN = "tok-1"  # noqa: S105
CONFIGURED_TOKEN = "tok-2"  # noqa: S105
BASE_URL = "https://mattermost.example/chat/"
SERVER_URL = "https://mattermost.example"
API = "/api/v4"
T0 = 1_780_660_800_000  # NOW (2026-06-05 12:00 UTC) in epoch milliseconds
CLIENT_LOG = "app.services.mattermost_client"
INGEST_LOG = "app.services.mattermost_ingest"
MESSAGES = "/api/v1/mattermost/messages"
# Every passing route test names a start time: without one the route fails today, a defect
# test_a_request_without_a_start_time_reads_every_message records.
SINCE_JUNE = {"posted_at_gte": "2026-06-01T00:00:00Z"}
# One PostgreSQL dialect compiles every statement here. SQLAlchemy leaves its constructor
# untyped.
POSTGRESQL = postgresql.dialect()  # type: ignore[no-untyped-call]


class FakeMattermost:
    """Mattermost in miniature: a canned status and JSON body per path, 404 for any other path,
    and a record of every request it was sent."""

    def __init__(self, routes: dict[str, Route]) -> None:
        self.routes = routes
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        status, body = self.routes.get(request.url.path, (404, {"message": "no such route"}))
        return httpx2.Response(status, json=body)

    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]


ServeMattermost = Callable[[dict[str, Route]], FakeMattermost]


def mm_client(handler: Handler) -> MattermostClient:
    return MattermostClient(
        base_url=BASE_URL, bot_token=BOT_TOKEN, transport=httpx2.MockTransport(handler)
    )


def answer(status: int, text: str) -> Handler:
    """A handler that answers every request with this status and plain-text body."""

    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status, text=text)

    return handler


def logged(caplog: pytest.LogCaptureFixture, logger: str) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == logger]


def post(
    post_id: str,
    *,
    user_id: str = "user-1",
    at: int = T0,
    message: str | None = None,
    kind: str = "",
) -> dict[str, Any]:
    """A post as Mattermost returns it, reduced to the fields Holly reads."""
    return {
        "id": post_id,
        "create_at": at,
        "user_id": user_id,
        "message": f"message {post_id}" if message is None else message,
        "type": kind,
    }


def posts_page(*posts: dict[str, Any], order: list[str] | None = None) -> Route:
    """Mattermost's answer to a posts query: each post keyed by id, and the ids newest first."""
    ids = [p["id"] for p in posts] if order is None else order
    return 200, {"order": ids, "posts": {p["id"]: p for p in posts}}


def posts_path(channel_id: str) -> str:
    return f"{API}/channels/{channel_id}/posts"


def inserted(count: int) -> SimpleNamespace:
    """The result of the INSERT: rowcount is how many rows the database actually added."""
    return SimpleNamespace(rowcount=count)


async def run_ingest(session: FakeSession, **options: Any) -> MattermostIngestResult:
    return await ingest_mattermost_messages(cast(AsyncSession, session), **options)


def compiled(statement: Any) -> Any:
    return statement.compile(dialect=POSTGRESQL)


def sql(statement: Any) -> str:
    """The statement as PostgreSQL receives it, with its values inline and whitespace collapsed."""
    text = statement.compile(dialect=POSTGRESQL, compile_kwargs={"literal_binds": True})
    return " ".join(str(text).split())


def insert_statements(session: FakeSession) -> list[Any]:
    statements = [call.args[0] for call in session.execute.await_args_list]
    return [statement for statement in statements if isinstance(statement, Insert)]


def stored_rows(session: FakeSession) -> list[dict[str, Any]]:
    """Every row the session was asked to insert, in order, read back from each multi-row
    INSERT's parameters (SQLAlchemy names them column_m0, column_m1 and so on). The id is left
    out: its default is drawn only when the statement runs."""
    rows: list[dict[str, Any]] = []
    for statement in insert_statements(session):
        by_index: dict[int, dict[str, Any]] = {}
        for name, value in compiled(statement).params.items():
            column, marker, index = name.rpartition("_m")
            if marker and index.isdigit() and column != "id":
                by_index.setdefault(int(index), {})[column] = value
        rows.extend(by_index[position] for position in sorted(by_index))
    return rows


@pytest.fixture(autouse=True)
def audit(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """The audit chain replaced by a recorder, so a test reads exactly what the ingest asked it
    to store. The recorder also checks the row is written before the commit, so it lands in the
    same transaction as the messages."""

    def before_the_commit(db: FakeSession, **_fields: Any) -> None:
        db.commit.assert_not_awaited()

    recorder = AsyncMock(side_effect=before_the_commit)
    monkeypatch.setattr(mattermost_ingest, "write_audit", recorder)
    return recorder


@pytest.fixture
def serve_mattermost(monkeypatch: pytest.MonkeyPatch, settings_env: SettingsEnv) -> ServeMattermost:
    """Configure Mattermost and serve it from a fake. The ingest builds its own client with no
    way to hand it a transport, so the client class it uses is swapped, at module level, for one
    bound to the fake's transport. The URL and token still come from the settings."""

    def install(routes: dict[str, Route]) -> FakeMattermost:
        settings_env(MATTERMOST_URL=SERVER_URL, MATTERMOST_BOT_TOKEN=BOT_TOKEN)
        server = FakeMattermost(routes)
        bound = partial(MattermostClient, transport=httpx2.MockTransport(server))
        monkeypatch.setattr(mattermost_ingest, "MattermostClient", bound)
        return server

    return install


class TestTheClient:
    async def test_the_token_goes_only_in_a_bearer_header_to_the_configured_server(self) -> None:
        channel = {"id": "chan-1", "name": "example-channel"}
        server = FakeMattermost({f"/chat{API}/channels/chan-1": (200, channel)})
        async with mm_client(server) as client:
            assert await client.get_channel("chan-1") == channel
        [request] = server.requests
        assert request.method == "GET"
        assert str(request.url) == "https://mattermost.example/chat/api/v4/channels/chan-1"
        assert request.headers["authorization"] == f"Bearer {BOT_TOKEN}"
        carriers = [name for name, value in request.headers.items() if BOT_TOKEN in value]
        assert carriers == ["authorization"]
        assert BOT_TOKEN not in str(request.url)

    async def test_each_read_asks_its_own_endpoint_and_returns_the_body_unchanged(self) -> None:
        user = {"id": "user-1", "username": "example.analyst"}
        page = {"order": ["post-1"], "posts": {"post-1": post("post-1")}}
        server = FakeMattermost(
            {
                f"/chat{API}/users/user-1": (200, user),
                f"/chat{API}/channels/chan-1/posts": (200, page),
            }
        )
        async with mm_client(server) as client:
            assert await client.get_user("user-1") == user
            assert await client.get_channel_posts_since("chan-1", T0) == page
            await client.get_channel_posts_since("chan-1", T0, per_page=50)
        posts_url = "https://mattermost.example/chat/api/v4/channels/chan-1/posts"
        assert [str(request.url) for request in server.requests] == [
            "https://mattermost.example/chat/api/v4/users/user-1",
            f"{posts_url}?since={T0}&per_page=200",
            f"{posts_url}?since={T0}&per_page=50",
        ]

    async def test_unset_arguments_come_from_the_settings(self, settings_env: SettingsEnv) -> None:
        settings_env(MATTERMOST_URL="https://chat.example/", MATTERMOST_BOT_TOKEN=CONFIGURED_TOKEN)
        server = FakeMattermost({f"{API}/users/user-1": (200, {"id": "user-1"})})
        async with MattermostClient(transport=httpx2.MockTransport(server)) as client:
            await client.get_user("user-1")
        [request] = server.requests
        assert str(request.url) == "https://chat.example/api/v4/users/user-1"
        assert request.headers["authorization"] == f"Bearer {CONFIGURED_TOKEN}"

    @pytest.mark.parametrize(
        ("status", "message"),
        [
            (401, "Mattermost rejected the bot token (401)."),
            (403, "Mattermost denied access (403): is the bot in the channel?"),
        ],
    )
    async def test_401_and_403_are_auth_errors_that_carry_no_upstream_detail(
        self, status: int, message: str
    ) -> None:
        with pytest.raises(MattermostAuthError) as raised:
            async with mm_client(answer(status, "upstream detail")) as client:
                await client.get_channel("chan-1")
        assert str(raised.value) == message

    @pytest.mark.parametrize("status", [400, 404, 500, 503])
    async def test_an_upstream_error_body_is_logged_never_returned(
        self, caplog: pytest.LogCaptureFixture, status: int
    ) -> None:
        body = "upstream detail: example fault"
        with pytest.raises(MattermostClientError) as raised:
            async with mm_client(answer(status, body)) as client:
                await client.get_channel("chan-1")
        assert not isinstance(raised.value, MattermostAuthError)
        assert str(raised.value) == f"Mattermost returned HTTP {status}."
        assert logged(caplog, CLIENT_LOG) == [
            f"Mattermost /channels/chan-1 returned HTTP {status}: {body}"
        ]

    async def test_only_the_first_200_characters_of_an_error_body_are_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with pytest.raises(MattermostClientError):
            async with mm_client(answer(500, "x" * 200 + "beyond-the-cap")) as client:
                await client.get_channel("chan-1")
        assert logged(caplog, CLIENT_LOG) == [
            "Mattermost /channels/chan-1 returned HTTP 500: " + "x" * 200
        ]

    @pytest.mark.parametrize("failure", [httpx2.ConnectError, httpx2.ReadTimeout])
    async def test_a_transport_failure_names_only_its_type(
        self, failure: type[httpx2.TransportError]
    ) -> None:
        def handler(request: httpx2.Request) -> httpx2.Response:
            msg = "no route to 192.0.2.10"
            raise failure(msg, request=request)

        with pytest.raises(MattermostClientError) as raised:
            async with mm_client(handler) as client:
                await client.get_channel("chan-1")
        assert str(raised.value) == f"Mattermost request failed: {failure.__name__}"
        assert isinstance(raised.value.__cause__, failure)

    @pytest.mark.parametrize(
        ("status", "body", "message"),
        [
            (200, "<html>Sign in</html>", "^Mattermost response was not valid JSON.$"),
            (200, [{"id": "chan-1"}], "^Mattermost response was not a JSON object"),
            (302, "Moved", "^Mattermost returned HTTP 302.$"),
        ],
    )
    async def test_an_answer_that_is_not_a_json_object_is_a_client_error(
        self, status: int, body: object, message: str
    ) -> None:
        def handler(_request: httpx2.Request) -> httpx2.Response:
            if isinstance(body, str):
                return httpx2.Response(status, text=body)
            return httpx2.Response(status, json=body)

        with pytest.raises(MattermostClientError, match=message):
            async with mm_client(handler) as client:
                await client.get_channel("chan-1")

    @pytest.mark.parametrize("identifier", ["../users/me", "chan-1/posts", "a?b=c", "", "x" * 65])
    async def test_a_malformed_id_never_reaches_a_request_path(self, identifier: str) -> None:
        server = FakeMattermost({})
        with pytest.raises(MattermostClientError, match="malformed"):
            async with mm_client(server) as client:
                await client.get_user(identifier)
        assert server.requests == []

    @pytest.mark.parametrize(("base_url", "bot_token"), [("", BOT_TOKEN), (BASE_URL, "")])
    async def test_a_client_missing_its_url_or_token_refuses_to_open(
        self, base_url: str, bot_token: str
    ) -> None:
        server = FakeMattermost({})
        client = MattermostClient(
            base_url=base_url, bot_token=bot_token, transport=httpx2.MockTransport(server)
        )
        with pytest.raises(MattermostClientError, match="not configured"):
            async with client:
                pass
        assert server.requests == []

    async def test_reads_are_refused_unless_the_client_is_open(self) -> None:
        server = FakeMattermost({f"/chat{API}/channels/chan-1": (200, {"id": "chan-1"})})
        client = mm_client(server)
        with pytest.raises(MattermostClientError, match="async context manager"):
            await client.get_channel("chan-1")
        async with client:
            assert await client.get_channel("chan-1") == {"id": "chan-1"}
        with pytest.raises(MattermostClientError, match="async context manager"):
            await client.get_channel("chan-1")
        await client.__aexit__(None, None, None)  # a second close is harmless
        assert len(server.requests) == 1


class TestEpochMilliseconds:
    @pytest.mark.parametrize(
        "moment",
        [
            datetime(2026, 6, 5, 12, 0),  # noqa: DTZ001  a naive time, which is read as UTC
            datetime(2026, 6, 5, 12, 0, tzinfo=UTC),
            datetime(2026, 6, 5, 14, 0, tzinfo=timezone(timedelta(hours=2))),
        ],
    )
    def test_a_time_becomes_milliseconds_since_the_epoch_in_utc(self, moment: datetime) -> None:
        assert datetime_to_ms(moment) == T0

    def test_milliseconds_become_an_aware_utc_time_that_round_trips(self) -> None:
        moment = ms_to_datetime(T0 + 123)
        assert moment == datetime(2026, 6, 5, 12, 0, 0, 123000, tzinfo=UTC)
        assert moment.tzinfo is UTC
        assert datetime_to_ms(moment) == T0 + 123


class TestTheIngest:
    async def test_new_posts_are_stored_with_their_author_and_channel_names(
        self, serve_mattermost: ServeMattermost
    ) -> None:
        newer = post("post-2", user_id="user-2", at=T0 + 90_000, kind="custom_example")
        older = post("post-1")
        serve_mattermost(
            {
                posts_path("chan-1"): posts_page(newer, older),
                f"{API}/channels/chan-1": (200, {"display_name": "Example Channel"}),
                f"{API}/users/user-1": (200, {"nickname": "Example Analyst"}),
                f"{API}/users/user-2": (200, {"username": "example.operator"}),
            }
        )
        session = FakeSession([scalar_result(None), inserted(2)])
        result = await run_ingest(session, channel_ids=["chan-1"])
        assert result == MattermostIngestResult(channels_polled=1, pulled=2, inserted=2)
        assert stored_rows(session) == [
            {
                "mm_post_id": "post-2",
                "channel_id": "chan-1",
                "channel_name": "Example Channel",
                "user_id": "user-2",
                "user_display_name": "example.operator",
                "posted_at": datetime(2026, 6, 5, 12, 1, 30, tzinfo=UTC),
                "message": "message post-2",
                "post_type": "custom_example",
                "raw": newer,
            },
            {
                "mm_post_id": "post-1",
                "channel_id": "chan-1",
                "channel_name": "Example Channel",
                "user_id": "user-1",
                "user_display_name": "Example Analyst",
                "posted_at": NOW,
                "message": "message post-1",
                "post_type": None,
                "raw": older,
            },
        ]

    @pytest.mark.parametrize(
        ("user_answer", "channel_answer", "user_name", "channel_name"),
        [
            (
                (200, {"nickname": "Example Analyst", "username": "example.analyst"}),
                (200, {"display_name": "Example Channel", "name": "example-channel"}),
                "Example Analyst",
                "Example Channel",
            ),
            (
                (200, {"nickname": "", "username": "example.analyst"}),
                (200, {"display_name": "", "name": "example-channel"}),
                "example.analyst",
                "example-channel",
            ),
            ((200, {"nickname": "", "username": ""}), (200, {}), None, None),
            ((404, {"message": "gone"}), (403, {"message": "no"}), None, None),
        ],
        ids=["preferred", "fallback", "unnamed", "lookup-failed"],
    )
    async def test_names_fall_back_and_a_failed_lookup_leaves_the_name_empty(
        self,
        serve_mattermost: ServeMattermost,
        user_answer: Route,
        channel_answer: Route,
        user_name: str | None,
        channel_name: str | None,
    ) -> None:
        serve_mattermost(
            {
                posts_path("chan-1"): posts_page(post("post-1")),
                f"{API}/users/user-1": user_answer,
                f"{API}/channels/chan-1": channel_answer,
            }
        )
        session = FakeSession([scalar_result(None), inserted(1)])
        result = await run_ingest(session, channel_ids=["chan-1"])
        [row] = stored_rows(session)
        assert (row["user_display_name"], row["channel_name"]) == (user_name, channel_name)
        assert result.inserted == 1

    async def test_each_name_is_looked_up_once_per_run_even_when_the_lookup_fails(
        self, serve_mattermost: ServeMattermost
    ) -> None:
        server = serve_mattermost(
            {
                posts_path("chan-1"): posts_page(post("post-2", user_id="user-2"), post("post-1")),
                posts_path("chan-2"): posts_page(post("post-4", user_id="user-2"), post("post-3")),
                f"{API}/channels/chan-1": (200, {"name": "example-channel-1"}),
                f"{API}/channels/chan-2": (200, {"name": "example-channel-2"}),
                f"{API}/users/user-1": (200, {"username": "example.analyst"}),
                f"{API}/users/user-2": (500, {"message": "upstream fault"}),
            }
        )
        session = FakeSession([scalar_result(None), inserted(2), scalar_result(None), inserted(2)])
        await run_ingest(session, channel_ids=["chan-1", "chan-2"])
        assert server.paths() == [
            posts_path("chan-1"),
            f"{API}/channels/chan-1",
            f"{API}/users/user-2",
            f"{API}/users/user-1",
            posts_path("chan-2"),
            f"{API}/channels/chan-2",
        ]
        names = [(row["mm_post_id"], row["user_display_name"]) for row in stored_rows(session)]
        assert names == [
            ("post-2", None),
            ("post-1", "example.analyst"),
            ("post-4", None),
            ("post-3", "example.analyst"),
        ]

    async def test_system_blank_undated_and_missing_posts_are_skipped_without_lookups(
        self, serve_mattermost: ServeMattermost
    ) -> None:
        server = serve_mattermost(
            {
                posts_path("chan-1"): posts_page(
                    post("post-5"),
                    post("post-4", user_id="user-9", kind="system_join_channel"),
                    post("post-3", user_id="user-9", message="   "),
                    {**post("post-2", user_id="user-9"), "create_at": "2026-06-05"},
                    order=["post-5", "post-4", "post-3", "post-2", "post-1"],
                ),
                f"{API}/channels/chan-1": (200, {"name": "example-channel"}),
                f"{API}/users/user-1": (200, {"username": "example.analyst"}),
            }
        )
        session = FakeSession([scalar_result(None), inserted(1)])
        result = await run_ingest(session, channel_ids=["chan-1"])
        assert result == MattermostIngestResult(channels_polled=1, pulled=5, inserted=1, skipped=4)
        assert [row["mm_post_id"] for row in stored_rows(session)] == ["post-5"]
        assert f"{API}/users/user-9" not in server.paths()

    async def test_malformed_posts_are_skipped_and_never_abort_the_run(
        self, serve_mattermost: ServeMattermost
    ) -> None:
        malformed: dict[str, object] = {
            "no-id": {**post("no-id"), "id": None},
            "bad-path": {**post("bad-path"), "id": "../users/me"},
            "not-an-object": "not an object",
            "flag-time": {**post("flag-time"), "create_at": True},
            "far-future": {**post("far-future"), "create_at": 10**20},
            "number-text": {**post("number-text"), "message": 123},
        }
        page = {"order": [*malformed, ["a", "list"], "post-1"], "posts": {**malformed}}
        page["posts"]["post-1"] = post("post-1")  # type: ignore[index]
        serve_mattermost(
            {
                posts_path("chan-1"): (200, page),
                f"{API}/channels/chan-1": (200, {"name": "example-channel"}),
                f"{API}/users/user-1": (200, {"username": "example.analyst"}),
            }
        )
        session = FakeSession([scalar_result(None), inserted(1)])
        result = await run_ingest(session, channel_ids=["chan-1"])
        assert result == MattermostIngestResult(channels_polled=1, pulled=8, inserted=1, skipped=7)
        assert [row["mm_post_id"] for row in stored_rows(session)] == ["post-1"]

    @pytest.mark.parametrize("author", ["", "../users/me", None])
    async def test_a_missing_or_malformed_author_is_stored_empty_and_never_looked_up(
        self, serve_mattermost: ServeMattermost, author: str | None
    ) -> None:
        server = serve_mattermost(
            {
                posts_path("chan-1"): posts_page({**post("post-1"), "user_id": author}),
                f"{API}/channels/chan-1": (200, {"name": "example-channel"}),
            }
        )
        session = FakeSession([scalar_result(None), inserted(1)])
        await run_ingest(session, channel_ids=["chan-1"])
        [row] = stored_rows(session)
        assert (row["user_id"], row["user_display_name"]) == ("", None)
        assert not [path for path in server.paths() if "/users/" in path]

    async def test_long_names_are_cut_to_fit_their_columns(
        self, serve_mattermost: ServeMattermost
    ) -> None:
        serve_mattermost(
            {
                posts_path("chan-1"): posts_page(post("post-1", kind="x" * 60)),
                f"{API}/channels/chan-1": (200, {"display_name": "C" * 300}),
                f"{API}/users/user-1": (200, {"nickname": "N" * 300}),
            }
        )
        session = FakeSession([scalar_result(None), inserted(1)])
        await run_ingest(session, channel_ids=["chan-1"])
        [row] = stored_rows(session)
        assert row["channel_name"] == "C" * 200
        assert row["user_display_name"] == "N" * 200
        assert row["post_type"] == "x" * 50

    @pytest.mark.parametrize(
        "page", [{"order": "post-1", "posts": {}}, {"order": ["post-1"], "posts": ["post-1"]}]
    )
    async def test_a_posts_answer_in_the_wrong_shape_fails_only_that_channel(
        self, serve_mattermost: ServeMattermost, audit: AsyncMock, page: dict[str, object]
    ) -> None:
        serve_mattermost({posts_path("chan-1"): (200, page)})
        session = FakeSession([scalar_result(None)])
        result = await run_ingest(session, channel_ids=["chan-1"])
        assert result == MattermostIngestResult(channels_failed=1)
        assert insert_statements(session) == []
        assert audit.await_args_list[-1].kwargs["detail"]["channels_failed"] == 1

    async def test_a_channel_with_nothing_worth_storing_writes_no_rows(
        self, serve_mattermost: ServeMattermost
    ) -> None:
        serve_mattermost(
            {
                posts_path("chan-1"): posts_page(post("post-1", kind="system_add_to_channel")),
                f"{API}/channels/chan-1": (200, {"name": "example-channel"}),
            }
        )
        session = FakeSession([scalar_result(None)])
        result = await run_ingest(session, channel_ids=["chan-1"])
        assert result == MattermostIngestResult(channels_polled=1, pulled=1, skipped=1)
        assert insert_statements(session) == []

    async def test_the_first_run_asks_for_the_last_24_hours(
        self, serve_mattermost: ServeMattermost
    ) -> None:
        server = serve_mattermost({posts_path("chan-1"): posts_page()})
        session = FakeSession([scalar_result(None)])
        earliest = datetime_to_ms(datetime.now(UTC) - timedelta(hours=24))
        result = await run_ingest(session, channel_ids=["chan-1"])
        latest = datetime_to_ms(datetime.now(UTC) - timedelta(hours=24))
        [request] = server.requests
        assert earliest <= int(request.url.params["since"]) <= latest
        assert result == MattermostIngestResult(channels_polled=1)
        high_water = sql(session.execute.await_args_list[0].args[0])
        assert high_water.startswith("SELECT max(mattermost_message.posted_at)")
        assert high_water.endswith("WHERE mattermost_message.channel_id = 'chan-1'")

    async def test_later_runs_ask_only_for_posts_after_the_newest_one_held(
        self, serve_mattermost: ServeMattermost
    ) -> None:
        server = serve_mattermost({posts_path("chan-1"): posts_page()})
        await run_ingest(FakeSession([scalar_result(NOW)]), channel_ids=["chan-1"])
        [request] = server.requests
        assert dict(request.url.params) == {"since": str(T0 + 1), "per_page": "200"}

    async def test_posts_already_held_are_left_to_the_unique_post_id(
        self, serve_mattermost: ServeMattermost
    ) -> None:
        serve_mattermost(
            {
                posts_path("chan-1"): posts_page(post("post-3"), post("post-2"), post("post-1")),
                f"{API}/channels/chan-1": (200, {"name": "example-channel"}),
                f"{API}/users/user-1": (200, {"username": "example.analyst"}),
            }
        )
        # The database already holds post-1 and post-2, so it adds only post-3.
        session = FakeSession([scalar_result(None), inserted(1)])
        result = await run_ingest(session, channel_ids=["chan-1"])
        assert result == MattermostIngestResult(channels_polled=1, pulled=3, inserted=1)
        [insert] = insert_statements(session)
        assert str(compiled(insert)).endswith(
            "ON CONFLICT ON CONSTRAINT uq_mattermost_message_post_id DO NOTHING"
        )
        table = cast(Table, MattermostMessage.__table__)
        unique = {
            constraint.name: [column.name for column in constraint.columns]
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        assert unique["uq_mattermost_message_post_id"] == ["mm_post_id"]

    @pytest.mark.parametrize(
        ("status", "outcome"),
        [
            (401, "skipped: Mattermost rejected the bot token (401)."),
            (403, "skipped: Mattermost denied access (403): is the bot in the channel?"),
            (500, "failed: Mattermost returned HTTP 500."),
        ],
    )
    async def test_a_channel_that_cannot_be_read_is_counted_and_the_rest_still_ingest(
        self,
        serve_mattermost: ServeMattermost,
        audit: AsyncMock,
        caplog: pytest.LogCaptureFixture,
        status: int,
        outcome: str,
    ) -> None:
        serve_mattermost(
            {
                posts_path("chan-locked"): (status, {"message": "upstream detail"}),
                posts_path("chan-1"): posts_page(post("post-1")),
                f"{API}/channels/chan-1": (200, {"name": "example-channel"}),
                f"{API}/users/user-1": (200, {"username": "example.analyst"}),
            }
        )
        session = FakeSession([scalar_result(None), scalar_result(None), inserted(1)])
        result = await run_ingest(session, channel_ids=["chan-locked", "chan-1"])
        assert result == MattermostIngestResult(
            channels_polled=1, channels_failed=1, pulled=1, inserted=1
        )
        assert [row["mm_post_id"] for row in stored_rows(session)] == ["post-1"]
        assert logged(caplog, INGEST_LOG) == [f"Mattermost channel chan-locked {outcome}"]
        assert audit.await_args_list[0].kwargs["detail"]["channels_failed"] == 1
        session.commit.assert_awaited_once()

    async def test_a_run_is_audited_and_committed_with_its_rows(
        self, serve_mattermost: ServeMattermost, audit: AsyncMock
    ) -> None:
        serve_mattermost(
            {
                posts_path("chan-1"): posts_page(
                    post("post-2", kind="system_join_channel"), post("post-1")
                ),
                f"{API}/channels/chan-1": (200, {"name": "example-channel"}),
                f"{API}/users/user-1": (200, {"username": "example.analyst"}),
            }
        )
        actor = uuid.uuid4()
        session = FakeSession([scalar_result(None), inserted(1)])
        await run_ingest(
            session, channel_ids=["chan-1"], user_id_actor=actor, ip_address="192.0.2.9"
        )
        [call] = audit.await_args_list
        assert call.args == (session,)
        assert call.kwargs == {
            "action_type": "mattermost.ingest",
            "entity_type": "mattermost_ingest_run",
            "user_id": actor,
            "ip_address": "192.0.2.9",
            "detail": {
                "channels_polled": 1,
                "channels_failed": 0,
                "pulled": 2,
                "inserted": 1,
                "skipped": 1,
            },
        }
        session.commit.assert_awaited_once()

    async def test_without_a_server_the_run_is_abandoned_and_every_channel_counted_failed(
        self,
        serve_mattermost: ServeMattermost,
        settings_env: SettingsEnv,
        audit: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        server = serve_mattermost({})
        settings_env(MATTERMOST_URL="")
        session = FakeSession()
        result = await run_ingest(session, channel_ids=["chan-1", "chan-2"])
        assert result == MattermostIngestResult(channels_failed=2)
        assert server.requests == []
        session.execute.assert_not_awaited()
        assert audit.await_args_list[0].kwargs["detail"]["channels_failed"] == 2
        session.commit.assert_awaited_once()
        assert logged(caplog, INGEST_LOG) == [
            "Mattermost ingest aborted: "
            "Mattermost is not configured (MATTERMOST_URL / MATTERMOST_BOT_TOKEN)."
        ]

    async def test_channels_come_from_the_settings_when_none_are_given(
        self, serve_mattermost: ServeMattermost, settings_env: SettingsEnv
    ) -> None:
        server = serve_mattermost(
            {posts_path("chan-1"): posts_page(), posts_path("chan-2"): posts_page()}
        )
        settings_env(MATTERMOST_CHANNEL_IDS=" chan-1 , ,chan-2,")
        result = await run_ingest(FakeSession([scalar_result(None), scalar_result(None)]))
        assert server.paths() == [posts_path("chan-1"), posts_path("chan-2")]
        assert result == MattermostIngestResult(channels_polled=2)

    @pytest.mark.parametrize(("channel_ids", "configured"), [([], "chan-1"), (None, " , ")])
    async def test_with_no_channels_nothing_is_asked_stored_or_audited(
        self,
        serve_mattermost: ServeMattermost,
        settings_env: SettingsEnv,
        audit: AsyncMock,
        channel_ids: list[str] | None,
        configured: str,
    ) -> None:
        server = serve_mattermost({})
        settings_env(MATTERMOST_CHANNEL_IDS=configured)
        session = FakeSession()
        result = await run_ingest(session, channel_ids=channel_ids)
        assert result == MattermostIngestResult()
        assert server.requests == []
        session.execute.assert_not_awaited()
        audit.assert_not_awaited()
        session.commit.assert_not_awaited()


def stored_message(post_id: str, posted_at: datetime) -> MattermostMessage:
    return MattermostMessage(
        id=uuid.uuid4(),
        mm_post_id=post_id,
        channel_id="chan-1",
        channel_name="Example Channel",
        user_id="user-1",
        user_display_name="Example Analyst",
        posted_at=posted_at,
        message=f"message {post_id}",
        post_type=None,
        raw={"id": post_id, "props": {"kept": "server-side"}},
        created_at=NOW,
        updated_at=NOW,
    )


class TestTheMessagesRoute:
    @pytest.mark.parametrize("token", [None, "not.a.real.jwt"])
    async def test_it_requires_sign_in(
        self, api: httpx2.AsyncClient, use_session: UseSession, token: str | None
    ) -> None:
        session = use_session(FakeSession())
        headers = {TOKEN_HEADER: token} if token else {}
        response = await api.get(MESSAGES, params=SINCE_JUNE, headers=headers)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        session.execute.assert_not_awaited()

    @pytest.mark.parametrize(
        ("paging", "limit", "offset"),
        [({}, 100, 0), ({"limit": 2, "offset": 4}, 2, 4), ({"limit": 500}, 500, 0)],
    )
    async def test_a_page_comes_back_newest_first_with_the_total(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        paging: dict[str, int],
        limit: int,
        offset: int,
    ) -> None:
        sign_in(make_user())
        rows = [
            stored_message("post-2", NOW),
            stored_message("post-1", NOW - timedelta(minutes=5)),
        ]
        session = use_session(FakeSession([scalar_result(57), rows_result(rows)]))
        query: dict[str, str | int] = {**SINCE_JUNE, **paging}
        response = await api.get(MESSAGES, params=query)
        assert response.status_code == 200
        body = response.json()
        assert (body["total"], body["limit"], body["offset"]) == (57, limit, offset)
        assert [item["mm_post_id"] for item in body["items"]] == ["post-2", "post-1"]
        count, page = (sql(call.args[0]) for call in session.execute.await_args_list)
        assert count.startswith("SELECT count(*)")
        assert page.endswith(
            "FROM mattermost_message "
            "WHERE mattermost_message.posted_at >= '2026-06-01 00:00:00+00:00' "
            f"ORDER BY mattermost_message.posted_at DESC LIMIT {limit} OFFSET {offset}"
        )

    async def test_a_message_is_returned_without_its_raw_mattermost_payload(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        message = stored_message("post-1", NOW)
        use_session(FakeSession([scalar_result(1), rows_result([message])]))
        response = await api.get(MESSAGES, params=SINCE_JUNE)
        assert response.json()["items"] == [
            {
                "id": str(message.id),
                "mm_post_id": "post-1",
                "channel_id": "chan-1",
                "channel_name": "Example Channel",
                "user_id": "user-1",
                "user_display_name": "Example Analyst",
                "posted_at": "2026-06-05T12:00:00Z",
                "message": "message post-1",
                "post_type": None,
                "created_at": "2026-06-05T12:00:00Z",
                "updated_at": "2026-06-05T12:00:00Z",
            }
        ]

    async def test_each_filter_narrows_both_the_count_and_the_page(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession([scalar_result(0), rows_result([])]))
        response = await api.get(
            MESSAGES, params={"channel_id": "chan-1", "user_id": "user-1", **SINCE_JUNE}
        )
        assert response.status_code == 200
        where = (
            "WHERE mattermost_message.channel_id = 'chan-1' "
            "AND mattermost_message.user_id = 'user-1' "
            "AND mattermost_message.posted_at >= '2026-06-01 00:00:00+00:00'"
        )
        count, page = (sql(call.args[0]) for call in session.execute.await_args_list)
        assert where in count
        assert where in page

    @pytest.mark.parametrize(
        "params",
        [{"limit": 0}, {"limit": 501}, {"offset": -1}, {"posted_at_gte": "not-a-time"}],
    )
    async def test_paging_or_a_start_time_out_of_bounds_is_422(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        params: dict[str, int | str],
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession())
        query: dict[str, str | int] = {**SINCE_JUNE, **params}
        response = await api.get(MESSAGES, params=query)
        assert response.status_code == 422
        session.execute.assert_not_awaited()

    async def test_a_request_without_a_start_time_reads_every_message(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession([scalar_result(0), rows_result([])]))
        # The dashboard's own request (frontend/src/pages/Mattermost.tsx) names no start time.
        response = await api.get(
            MESSAGES, params={"channel_id": "chan-1", "limit": 50, "offset": 0}
        )
        assert response.status_code == 200
        page = sql(session.execute.await_args_list[1].args[0])
        assert "WHERE mattermost_message.channel_id = 'chan-1' ORDER BY" in page
