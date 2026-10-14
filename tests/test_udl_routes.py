"""The UDL-backed read routes (element sets, maneuvers, notifications) and the ingest and
refresh triggers beside them: filters, sorting and paging reach the SQL, an unknown id is a
404, a UDL failure is a 502 in Holly's own words, a manual refresh counts against the caller's
assistant limit, and every route needs a signed-in user.

The SQL each route sent is read back from the FakeSession and compiled for PostgreSQL. The
UDL client runs against an httpx2.MockTransport, never the network, and the notification
cycle is replaced with a recorder.
"""

import re
import typing
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import httpx2
import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError

from app.api.v1.routes.elsets import ElsetSortColumn
from app.api.v1.routes.maneuvers import ManeuverSortColumn
from app.api.v1.routes.notifications import NotificationSortColumn
from app.core.rate_limit import ASSISTANT_LIMIT
from app.models.elset import Elset
from app.models.maneuver import Maneuver
from app.models.notification import Notification
from app.models.user import User
from app.services.udl_client import UDLClient
from app.services.udl_records import IngestResult
from fakes import NOW, FakeSession, make_user, rows_result, scalar_result

UseSession = Callable[[FakeSession], FakeSession]
SignIn = Callable[[User], User]
Handler = Callable[[httpx2.Request], httpx2.Response]

# SQLAlchemy leaves the dialect constructor untyped, so one instance serves the whole file.
POSTGRESQL = postgresql.dialect()  # type: ignore[no-untyped-call]
# Test-only UDL credentials, never sent anywhere: every request goes to a mock transport.
UDL_USER, UDL_KEY = "analyst", "pw-1"
KNOWN_ID = "00000000-0000-4000-8000-000000000001"
# What an upstream failure might say about UDL's insides; none of it may reach a browser.
UPSTREAM_DETAIL = "db-7.example at 198.51.100.7"
DEDUP = (
    "SELECT DISTINCT ON (coalesce(notification.event_id, notification.notso_identifier, "
    "notification.udl_id))"
)
ELSETS, MANEUVERS, NOTIFICATIONS = "/api/v1/elsets", "/api/v1/maneuvers", "/api/v1/notifications"
LIST_ROUTES = [ELSETS, MANEUVERS, NOTIFICATIONS]
INGEST_REQUESTS = [
    ("/api/v1/elsets/ingest", {"epoch_gte": "2026-06-01T00:00:00Z"}),
    ("/api/v1/notifications/ingest", {}),
]


@pytest.fixture(autouse=True)
def cycle_runs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The notification cycle (UDL pull, assistant, summaries), replaced with a recorder."""
    runs: list[str] = []

    def run_now() -> None:
        runs.append("cycle")

    monkeypatch.setattr(
        "app.api.v1.routes.notifications.run_pull_notifications_now",
        AsyncMock(side_effect=run_now),
    )
    return runs


@pytest.fixture
def udl_answers(monkeypatch: pytest.MonkeyPatch) -> Callable[[Handler], None]:
    """Point the ingest routes' UDL client at a mock transport that answers with `handler`."""

    def install(handler: Handler) -> None:
        def open_client() -> UDLClient:
            return UDLClient(
                base_url="https://udl.example/udl",
                username=UDL_USER,
                password=UDL_KEY,
                transport=httpx2.MockTransport(handler),
            )

        monkeypatch.setattr("app.api.v1.common.UDLClient", open_client)

    return install


def no_request_expected(request: httpx2.Request) -> httpx2.Response:
    pytest.fail(f"UDL was called unexpectedly: {request.url}")


def answering(status: int, text: str) -> Handler:
    return lambda _request: httpx2.Response(status, text=text)


def unreachable(request: httpx2.Request) -> httpx2.Response:
    msg = "connect failed to 198.51.100.7"
    raise httpx2.ConnectError(msg, request=request)


def statements(session: FakeSession) -> list[str]:
    """Each statement the session executed, compiled for PostgreSQL with its values inline."""
    compiled = (
        call.args[0].compile(dialect=POSTGRESQL, compile_kwargs={"literal_binds": True})
        for call in session.execute.await_args_list
    )
    return [" ".join(str(text).split()) for text in compiled]


def page_session(total: int = 0, rows: list[Any] | None = None) -> FakeSession:
    """A session answering a paged list: the COUNT first, then the page."""
    return FakeSession([scalar_result(total), rows_result(rows or [])])


def make_elset(**overrides: Any) -> Elset:
    fields: dict[str, Any] = {
        "id": uuid.uuid4(),
        "udl_id": "TEST-ELSET-1",
        "sat_no": 99999,
        "epoch": NOW,
        "mean_motion": 15.5,
        "data_mode": "TEST",
        "classification_marking": "U",
        "raw": {"id": "TEST-ELSET-1", "satNo": 99999},
        "created_at": NOW,
        "updated_at": NOW,
    }
    return Elset(**(fields | overrides))


def make_maneuver(**overrides: Any) -> Maneuver:
    fields: dict[str, Any] = {
        "id": uuid.uuid4(),
        "udl_id": "TEST-MNVR-1",
        "sat_no": 99999,
        "mnvr_type": "TEST",
        "event_start_time": NOW,
        "data_mode": "TEST",
        "classification_marking": "U",
        "raw": {"id": "TEST-MNVR-1", "satNo": 99999},
        "created_at": NOW,
        "updated_at": NOW,
    }
    return Maneuver(**(fields | overrides))


def make_notification(**overrides: Any) -> Notification:
    fields: dict[str, Any] = {
        "id": uuid.uuid4(),
        "udl_id": "TEST-NOTIF-1",
        "msg_type": "TACREP_NOTSO",
        "status": "OPEN",
        "sat_no": 99999,
        "sat_ids": ["99999"],
        "data_mode": "TEST",
        "classification_marking": "U",
        "raw": {"id": "TEST-NOTIF-1", "msgType": "TACREP_NOTSO"},
        "created_at": NOW,
        "updated_at": NOW,
    }
    return Notification(**(fields | overrides))


class TestElsetList:
    async def test_every_filter_and_the_requested_order_reach_the_sql(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        elset = make_elset()
        session = use_session(page_session(41, [elset]))
        response = await api.get(
            ELSETS,
            params={
                "sat_no": 99999,
                "epoch_gte": "2026-06-01T00:00:00Z",
                "epoch_lte": "2026-06-02T00:00:00Z",
                "sort_by": "mean_motion",
                "sort_dir": "asc",
                "limit": 20,
                "offset": 40,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert (body["total"], body["limit"], body["offset"]) == (41, 20, 40)
        assert [item["id"] for item in body["items"]] == [str(elset.id)]
        assert "raw" not in body["items"][0]
        where = (
            "WHERE elset.sat_no = 99999 AND elset.epoch >= '2026-06-01 00:00:00+00:00' "
            "AND elset.epoch <= '2026-06-02 00:00:00+00:00'"
        )
        counted, paged = statements(session)
        assert counted.startswith("SELECT count(*) AS count_1 FROM (SELECT ")
        assert counted.endswith(f"FROM elset {where}) AS anon_1")
        assert paged.endswith(
            f"FROM elset {where} ORDER BY elset.mean_motion ASC NULLS LAST LIMIT 20 OFFSET 40"
        )

    async def test_the_default_page_is_the_first_50_newest_epoch_first(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        session = use_session(page_session())
        response = await api.get(ELSETS)
        assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}
        assert statements(session)[1].endswith(
            "ORDER BY elset.epoch DESC NULLS LAST LIMIT 50 OFFSET 0"
        )

    async def test_a_zero_filter_value_is_applied_not_ignored(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        session = use_session(page_session())
        await api.get(ELSETS, params={"sat_no": 0})
        assert "FROM elset WHERE elset.sat_no = 0 ORDER BY" in statements(session)[1]


class TestManeuverList:
    async def test_every_filter_and_the_requested_order_reach_the_sql(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        maneuver = make_maneuver()
        session = use_session(page_session(3, [maneuver]))
        response = await api.get(
            MANEUVERS,
            params={
                "sat_no": 99999,
                "mnvr_type": "TEST",
                "event_start_time_gte": "2026-06-01T00:00:00Z",
                "event_start_time_lte": "2026-06-02T00:00:00Z",
                "sort_by": "sat_no",
                "sort_dir": "asc",
                "limit": 5,
                "offset": 10,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert (body["total"], body["limit"], body["offset"]) == (3, 5, 10)
        assert [item["id"] for item in body["items"]] == [str(maneuver.id)]
        where = (
            "WHERE maneuver.sat_no = 99999 AND maneuver.mnvr_type = 'TEST' "
            "AND maneuver.event_start_time >= '2026-06-01 00:00:00+00:00' "
            "AND maneuver.event_start_time <= '2026-06-02 00:00:00+00:00'"
        )
        counted, paged = statements(session)
        assert counted.endswith(f"FROM maneuver {where}) AS anon_1")
        # The newest row breaks a tie, so a page boundary never splits equal keys at random.
        assert paged.endswith(
            f"FROM maneuver {where} ORDER BY maneuver.sat_no ASC NULLS LAST, "
            "maneuver.created_at DESC LIMIT 5 OFFSET 10"
        )

    async def test_the_default_page_is_the_first_50_latest_event_first(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        session = use_session(page_session())
        response = await api.get(MANEUVERS)
        assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}
        assert statements(session)[1].endswith(
            "ORDER BY maneuver.event_start_time DESC NULLS LAST, "
            "maneuver.created_at DESC LIMIT 50 OFFSET 0"
        )


class TestNotificationList:
    async def test_every_filter_reaches_the_one_row_per_notice_query(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        notification = make_notification()
        session = use_session(page_session(9, [notification]))
        response = await api.get(
            NOTIFICATIONS,
            params={
                "msg_type": "TACREP_NOTSO",
                "event_type": "TEST-EVENT",
                "status": "OPEN",
                "sat_no": 99999,
                "effective_from_gte": "2026-06-01T00:00:00Z",
                "effective_from_lte": "2026-06-30T00:00:00Z",
                "created_at_gte": "2026-05-01T00:00:00Z",
                "sort_by": "publish_date",
                "sort_dir": "asc",
                "limit": 5,
                "offset": 10,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert (body["total"], body["limit"], body["offset"]) == (9, 5, 10)
        assert [item["id"] for item in body["items"]] == [str(notification.id)]
        counted, paged = statements(session)
        # Both the total and the page count logical notices, not UDL publications.
        for text in (counted, paged):
            assert DEDUP in text
            for clause in (
                ".msg_type = 'TACREP_NOTSO'",
                ".event_type = 'TEST-EVENT'",
                ".status = 'OPEN'",
                ".sat_no = 99999",
                ".effective_from >= '2026-06-01 00:00:00+00:00'",
                ".effective_from <= '2026-06-30 00:00:00+00:00'",
                ".udl_created_at >= '2026-05-01 00:00:00+00:00'",
            ):
                assert clause in text
        assert counted.startswith("SELECT count(*) AS count_1 FROM (SELECT ")
        assert paged.endswith(
            "AS anon_1 ORDER BY anon_1.publish_date ASC NULLS LAST, "
            "anon_1.created_at DESC LIMIT 5 OFFSET 10"
        )

    async def test_the_default_page_is_the_first_50_latest_publication_first(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        session = use_session(page_session())
        response = await api.get(NOTIFICATIONS)
        assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}
        assert statements(session)[1].endswith(
            "AS anon_1 ORDER BY anon_1.udl_created_at DESC NULLS LAST, "
            "anon_1.created_at DESC LIMIT 50 OFFSET 0"
        )


class TestOptionalFilters:
    @pytest.mark.parametrize("path", LIST_ROUTES)
    async def test_a_list_without_filters_answers_200_with_no_where_clause(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, path: str
    ) -> None:
        sign_in(make_user())
        session = use_session(page_session())
        response = await api.get(path)
        assert response.status_code == 200
        for text in statements(session):
            assert " WHERE " not in text

    @pytest.mark.parametrize(
        ("path", "param", "value", "clause"),
        [
            (ELSETS, "sat_no", 99999, "sat_no = 99999"),
            (ELSETS, "epoch_gte", "2026-06-01T00:00:00Z", "epoch >= '2026-06-01 00:00:00+00:00'"),
            (ELSETS, "epoch_lte", "2026-06-02T00:00:00Z", "epoch <= '2026-06-02 00:00:00+00:00'"),
            (MANEUVERS, "sat_no", 99999, "sat_no = 99999"),
            (MANEUVERS, "mnvr_type", "TEST", "mnvr_type = 'TEST'"),
            (
                MANEUVERS,
                "event_start_time_gte",
                "2026-06-01T00:00:00Z",
                "event_start_time >= '2026-06-01 00:00:00+00:00'",
            ),
            (
                MANEUVERS,
                "event_start_time_lte",
                "2026-06-02T00:00:00Z",
                "event_start_time <= '2026-06-02 00:00:00+00:00'",
            ),
            *(
                (NOTIFICATIONS, param, value, clause)
                for param, value, clause in [
                    ("msg_type", "TACREP_NOTSO", "msg_type = 'TACREP_NOTSO'"),
                    ("event_type", "TEST-EVENT", "event_type = 'TEST-EVENT'"),
                    ("status", "OPEN", "status = 'OPEN'"),
                    ("sat_no", 99999, "sat_no = 99999"),
                    (
                        "effective_from_gte",
                        "2026-06-01T00:00:00Z",
                        "effective_from >= '2026-06-01 00:00:00+00:00'",
                    ),
                    (
                        "effective_from_lte",
                        "2026-06-30T00:00:00Z",
                        "effective_from <= '2026-06-30 00:00:00+00:00'",
                    ),
                    (
                        "created_at_gte",
                        "2026-05-01T00:00:00Z",
                        "udl_created_at >= '2026-05-01 00:00:00+00:00'",
                    ),
                ]
            ),
        ],
    )
    async def test_one_filter_alone_is_the_only_clause_in_the_sql(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        path: str,
        param: str,
        value: str | int,
        clause: str,
    ) -> None:
        # Every other filter is omitted, so each case also proves an absent one adds nothing.
        sign_in(make_user())
        session = use_session(page_session())
        response = await api.get(path, params={param: value})
        assert response.status_code == 200
        for text in statements(session):
            assert text.count(" WHERE ") == 1
            assert re.search(rf" WHERE \w+\.{re.escape(clause)}(\)| ORDER BY )", text), text


class TestSortingAndPaging:
    @pytest.mark.parametrize(
        ("path", "column", "sorted_by"),
        [
            *((ELSETS, c, f"elset.{c}") for c in typing.get_args(ElsetSortColumn)),
            *((MANEUVERS, c, f"maneuver.{c}") for c in typing.get_args(ManeuverSortColumn)),
            *((NOTIFICATIONS, c, f"anon_1.{c}") for c in typing.get_args(NotificationSortColumn)),
        ],
    )
    async def test_every_advertised_sort_column_sorts_by_that_column(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        path: str,
        column: str,
        sorted_by: str,
    ) -> None:
        sign_in(make_user())
        session = use_session(page_session())
        response = await api.get(path, params={"sort_by": column})
        assert response.status_code == 200
        assert f"ORDER BY {sorted_by} DESC NULLS LAST" in statements(session)[1]

    @pytest.mark.parametrize("path", LIST_ROUTES)
    @pytest.mark.parametrize(
        "params",
        [
            {"sort_by": "raw"},
            {"sort_by": "__class__"},
            {"sort_by": "epoch; DROP TABLE elset"},
            {"sort_dir": "sideways"},
            {"limit": 0},
            {"limit": 501},
            {"offset": -1},
        ],
    )
    async def test_an_unlisted_sort_or_a_page_out_of_bounds_is_422(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        path: str,
        params: dict[str, Any],
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession())
        response = await api.get(path, params=params)
        assert response.status_code == 422
        session.execute.assert_not_awaited()

    @pytest.mark.parametrize("path", LIST_ROUTES)
    @pytest.mark.parametrize("limit", [1, 500])
    async def test_a_page_size_at_either_bound_is_accepted(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        path: str,
        limit: int,
    ) -> None:
        sign_in(make_user())
        session = use_session(page_session())
        response = await api.get(path, params={"limit": limit, "offset": 0})
        assert response.status_code == 200
        assert statements(session)[1].endswith(f"LIMIT {limit} OFFSET 0")


class TestGetById:
    @pytest.mark.parametrize(
        ("path", "table", "label"),
        [
            ("elsets", "elset", "Elset"),
            ("maneuvers", "maneuver", "Maneuver"),
            ("notifications", "notification", "Notification"),
        ],
    )
    async def test_an_unknown_id_is_404(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        path: str,
        table: str,
        label: str,
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession([scalar_result(None)]))
        response = await api.get(f"/api/v1/{path}/{KNOWN_ID}")
        assert response.status_code == 404
        assert response.json() == {"detail": f"{label} not found"}
        [lookup] = statements(session)
        assert lookup.endswith(f"FROM {table} WHERE {table}.id = '{KNOWN_ID}'")

    @pytest.mark.parametrize(
        ("path", "row"),
        [
            ("elsets", make_elset()),
            ("maneuvers", make_maneuver()),
            ("notifications", make_notification()),
        ],
    )
    async def test_a_known_id_returns_the_detail_with_the_raw_payload(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        path: str,
        row: Elset | Maneuver | Notification,
    ) -> None:
        sign_in(make_user())
        use_session(FakeSession([scalar_result(row)]))
        response = await api.get(f"/api/v1/{path}/{row.id}")
        assert response.status_code == 200
        body = response.json()
        assert (body["id"], body["udl_id"], body["raw"]) == (str(row.id), row.udl_id, row.raw)

    @pytest.mark.parametrize("path", LIST_ROUTES)
    async def test_an_id_that_is_not_a_uuid_is_422(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, path: str
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession())
        assert (await api.get(f"{path}/not-a-uuid")).status_code == 422
        session.execute.assert_not_awaited()


class TestIngest:
    async def test_the_elset_ingest_runs_with_the_request_and_returns_its_counts(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        udl_answers: Callable[[Handler], None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        user = sign_in(make_user())
        session = use_session(FakeSession())
        udl_answers(no_request_expected)
        ingest = AsyncMock(return_value=IngestResult(pulled=4, inserted=2, updated=1, skipped=1))
        monkeypatch.setattr("app.api.v1.routes.elsets.ingest_elsets", ingest)
        response = await api.post(
            "/api/v1/elsets/ingest",
            json={"epoch_gte": "2026-06-01T00:00:00Z", "sat_no": 99999, "max_results": 100},
        )
        assert response.status_code == 200
        assert response.json() == {"pulled": 4, "inserted": 2, "updated": 1, "skipped": 1}
        ingest.assert_awaited_once()
        assert ingest.await_args is not None
        db, client = ingest.await_args.args
        assert db is session
        assert isinstance(client, UDLClient)
        assert ingest.await_args.kwargs == {
            "epoch_gte": datetime(2026, 6, 1, tzinfo=UTC),
            "sat_no": 99999,
            "max_results": 100,
            "user_id": user.id,
            "ip_address": "127.0.0.1",
        }

    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            (
                {},
                {
                    "msg_type": "TACREP_NOTSO",
                    "created_at_gte": None,
                    "data_mode": None,
                    "source": None,
                    "max_results": None,
                },
            ),
            (
                {
                    "msg_type": "TEST-MSG",
                    "created_at_gte": "2026-06-01T00:00:00Z",
                    "data_mode": "TEST",
                    "source": "TEST-SOURCE",
                    "max_results": 25,
                },
                {
                    "msg_type": "TEST-MSG",
                    "created_at_gte": datetime(2026, 6, 1, tzinfo=UTC),
                    "data_mode": "TEST",
                    "source": "TEST-SOURCE",
                    "max_results": 25,
                },
            ),
        ],
        ids=["defaults", "every-field"],
    )
    async def test_the_notification_ingest_runs_with_the_request_and_returns_its_counts(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        udl_answers: Callable[[Handler], None],
        monkeypatch: pytest.MonkeyPatch,
        body: dict[str, Any],
        expected: dict[str, Any],
    ) -> None:
        user = sign_in(make_user())
        session = use_session(FakeSession())
        udl_answers(no_request_expected)
        ingest = AsyncMock(return_value=IngestResult(pulled=5, inserted=1, updated=3, skipped=1))
        monkeypatch.setattr("app.api.v1.routes.notifications.ingest_notifications", ingest)
        response = await api.post("/api/v1/notifications/ingest", json=body)
        assert response.status_code == 200
        assert response.json() == {"pulled": 5, "inserted": 1, "updated": 3, "skipped": 1}
        ingest.assert_awaited_once()
        assert ingest.await_args is not None
        db, client = ingest.await_args.args
        assert db is session
        assert isinstance(client, UDLClient)
        assert ingest.await_args.kwargs == expected | {
            "user_id": user.id,
            "ip_address": "127.0.0.1",
        }

    @pytest.mark.parametrize(("path", "body"), INGEST_REQUESTS)
    @pytest.mark.parametrize(
        ("handler", "detail"),
        [
            (answering(500, f"stack trace: {UPSTREAM_DETAIL}"), "UDL returned HTTP 500."),
            (
                answering(401, f"no such user analyst, {UPSTREAM_DETAIL}"),
                "UDL rejected credentials (401).",
            ),
            (answering(200, f"<html>{UPSTREAM_DETAIL}</html>"), "UDL response was not valid JSON."),
            (unreachable, "UDL request failed: ConnectError"),
        ],
        ids=["http-500", "http-401", "not-json", "unreachable"],
    )
    async def test_a_udl_failure_is_a_502_that_never_repeats_the_upstream_body(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        udl_answers: Callable[[Handler], None],
        path: str,
        body: dict[str, Any],
        handler: Handler,
        detail: str,
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession())
        udl_answers(handler)
        response = await api.post(path, json=body)
        assert response.status_code == 502
        assert response.json() == {"detail": detail}
        for leaked in ("db-7.example", "198.51.100.7", "analyst"):
            assert leaked not in response.text
        session.execute.assert_not_awaited()
        session.commit.assert_not_awaited()

    @pytest.mark.parametrize(("path", "body"), INGEST_REQUESTS)
    async def test_an_ingest_without_udl_credentials_is_a_502(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        path: str,
        body: dict[str, Any],
    ) -> None:
        # conftest.py leaves UDL_USERNAME and UDL_PASSWORD empty, so the real client refuses.
        sign_in(make_user())
        session = use_session(FakeSession())
        response = await api.post(path, json=body)
        assert response.status_code == 502
        assert response.json() == {
            "detail": "UDL credentials are not configured (UDL_USERNAME / UDL_PASSWORD)."
        }
        session.execute.assert_not_awaited()

    async def test_only_a_udl_failure_becomes_a_502(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        udl_answers: Callable[[Handler], None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Any other error carries text that is not Holly's own, so it must never be echoed.
        sign_in(make_user())
        use_session(FakeSession())
        udl_answers(no_request_expected)
        failure = OperationalError("INSERT", {}, Exception("db-7.example refused the connection"))
        monkeypatch.setattr(
            "app.api.v1.routes.elsets.ingest_elsets", AsyncMock(side_effect=failure)
        )
        with pytest.raises(OperationalError):
            await api.post("/api/v1/elsets/ingest", json={"epoch_gte": "2026-06-01T00:00:00Z"})

    @pytest.mark.parametrize(
        "body",
        [
            {},
            {"epoch_gte": "yesterday"},
            {"epoch_gte": "2026-06-01", "sat_no": "ISS"},
            {"epoch_gte": "2026-06-01", "max_results": 0},
            {"epoch_gte": "2026-06-01", "max_results": 10_001},
        ],
    )
    async def test_a_malformed_elset_ingest_is_422(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        udl_answers: Callable[[Handler], None],
        body: dict[str, Any],
    ) -> None:
        sign_in(make_user())
        use_session(FakeSession())
        udl_answers(no_request_expected)
        assert (await api.post("/api/v1/elsets/ingest", json=body)).status_code == 422


@pytest.mark.parametrize("max_results", [0, 10_001])
async def test_a_notification_ingest_beyond_the_page_cap_is_422(
    api: httpx2.AsyncClient,
    use_session: UseSession,
    sign_in: SignIn,
    udl_answers: Callable[[Handler], None],
    max_results: int,
) -> None:
    sign_in(make_user())
    use_session(FakeSession())
    udl_answers(no_request_expected)
    response = await api.post("/api/v1/notifications/ingest", json={"max_results": max_results})
    assert response.status_code == 422


class TestRefresh:
    async def test_a_refresh_runs_the_cycle_and_answers_202(
        self, api: httpx2.AsyncClient, sign_in: SignIn, cycle_runs: list[str]
    ) -> None:
        sign_in(make_user())
        response = await api.post("/api/v1/notifications/refresh")
        assert response.status_code == 202
        assert response.json() == {"status": "complete"}
        assert cycle_runs == ["cycle"]

    async def test_each_refresh_counts_against_the_callers_assistant_limit(
        self, api: httpx2.AsyncClient, sign_in: SignIn, cycle_runs: list[str]
    ) -> None:
        user = sign_in(make_user())
        for _ in range(ASSISTANT_LIMIT.limit - 1):
            ASSISTANT_LIMIT.record(str(user.id))
        assert (await api.post("/api/v1/notifications/refresh")).status_code == 202
        refused = await api.post("/api/v1/notifications/refresh")
        assert refused.status_code == 429
        assert int(refused.headers["retry-after"]) >= 1
        assert cycle_runs == ["cycle"]

    async def test_another_users_refreshes_do_not_count_against_this_one(
        self, api: httpx2.AsyncClient, sign_in: SignIn, cycle_runs: list[str]
    ) -> None:
        other = make_user(username="example-analyst")
        for _ in range(ASSISTANT_LIMIT.limit):
            ASSISTANT_LIMIT.record(str(other.id))
        sign_in(make_user())
        assert (await api.post("/api/v1/notifications/refresh")).status_code == 202
        assert cycle_runs == ["cycle"]


class TestSignIn:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", ELSETS),
            ("GET", f"{ELSETS}/{KNOWN_ID}"),
            ("POST", f"{ELSETS}/ingest"),
            ("GET", MANEUVERS),
            ("GET", f"{MANEUVERS}/{KNOWN_ID}"),
            ("GET", NOTIFICATIONS),
            ("GET", f"{NOTIFICATIONS}/{KNOWN_ID}"),
            ("POST", f"{NOTIFICATIONS}/ingest"),
            ("POST", f"{NOTIFICATIONS}/refresh"),
        ],
    )
    async def test_every_route_requires_sign_in_and_touches_nothing(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        udl_answers: Callable[[Handler], None],
        cycle_runs: list[str],
        method: str,
        path: str,
    ) -> None:
        session = use_session(FakeSession())
        udl_answers(no_request_expected)
        body = {"epoch_gte": "2026-06-01T00:00:00Z"} if method == "POST" else None
        response = await api.request(method, path, json=body)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        session.execute.assert_not_awaited()
        assert cycle_runs == []
