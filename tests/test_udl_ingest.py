"""UDL ingest: what one pull asks UDL for, what it writes and reports, and the audit row it
leaves; the read-time de-duplication of notifications; and the refresh-token block-list.

The UDL client runs against an httpx2.MockTransport, the database is a FakeSession whose
statements are compiled for PostgreSQL and read back, and the audit chain is replaced with a
recorder that also refuses a row written after the run has committed. The record mapping is
covered by test_elset_ingest_mapping.py and test_notification_ingest_mapping.py; the mapping
cases here are only the ones those files do not reach, plus the maneuver mapper, which has no
file of its own.
"""

import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock

import httpx2
import pytest
from sqlalchemy import BigInteger, DateTime, Float, Integer, String, Text, func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ClauseElement

from app.models.maneuver import Maneuver
from app.models.notification import Notification
from app.models.revoked_jti import RevokedJti
from app.services import elset_ingest, maneuver_ingest, notification_ingest, udl_records
from app.services.elset_ingest import ingest_elsets
from app.services.maneuver_ingest import ingest_maneuvers
from app.services.notification_ingest import ingest_notifications
from app.services.notification_query import (
    aliased_deduped_notifications,
    deduped_notifications_select,
    notification_group_key,
)
from app.services.token_revocation import is_revoked, revoke
from app.services.udl_client import UDLClient, UDLClientError
from app.services.udl_records import IngestResult, upsert_rows
from fakes import NOW, FakeSession, rows_result, scalar_result

# SQLAlchemy leaves the dialect constructor untyped, so one instance serves the whole file.
POSTGRESQL = postgresql.dialect()  # type: ignore[no-untyped-call]
# Test-only UDL credentials, never sent anywhere: every request goes to a mock transport.
UDL_USER, UDL_KEY = "analyst", "pw-1"
WINDOW_START = datetime(2026, 6, 1, tzinfo=UTC)
GROUP_KEY = "coalesce(notification.event_id, notification.notso_identifier, notification.udl_id)"

ELSET_RECORD: dict[str, Any] = {
    "id": "TEST-ELSET-1",
    "satNo": 99999,
    "epoch": "2026-06-01T00:00:00.000000Z",
    "meanMotion": 15.5,
    "eccentricity": 0.0001,
    "inclination": 51.6,
    "raan": 10.0,
    "argOfPerigee": 20.0,
    "meanAnomaly": 30.0,
    "revNo": 100,
    "bstar": 0.0001,
    "meanMotionDot": 0.0,
    "meanMotionDDot": 0.0,
    "semiMajorAxis": 6800.0,
    "period": 92.0,
    "apogee": 420.0,
    "perigee": 410.0,
    "line1": "1 99999U TEST",
    "line2": "2 99999 TEST",
    "classificationMarking": "U",
    "dataMode": "TEST",
    "source": "TEST-SOURCE",
}
MANEUVER_RECORD: dict[str, Any] = {
    "id": "TEST-MNVR-1",
    "satNo": 99999,
    "dataMode": "TEST",
    "source": "TEST-SOURCE",
    "classificationMarking": "U",
    "createdBy": "example-analyst",
    "origNetwork": "TEST-NET",
    "origin": "TEST-ORIGIN",
    "mnvrType": "TEST",
    "description": "Synthetic manoeuvre",
    "propulsionType": "TEST-PROPULSION",
    "maneuverStatus": "TEST-STATUS",
    "responsibleNation": "TEST",
    "createdAt": "2026-06-01T01:00:00Z",
    "eventStartTime": "2026-06-01T00:00:00Z",
    "eventStopTime": "2026-06-01T00:10:00Z",
    "deltaV": 0.5,
    "thrustMag": 1.5,
    "thrustDuration": 30.0,
}
NOTIFICATION_RECORD: dict[str, Any] = {
    "id": "TEST-NOTIF-1",
    "msgType": "TACREP_NOTSO",
    "dataMode": "TEST",
    "source": "TEST-SOURCE",
    "classificationMarking": "U",
    "createdBy": "example-analyst",
    "origNetwork": "TEST-NET",
    "createdAt": "2026-06-01T01:00:00Z",
    "region": "TEST-REGION",
    "effectiveFrom": "2026-06-01T00:00:00Z",
    "effectiveUntil": "2026-06-08T00:00:00Z",
    "msgBody": {
        "NOTSO": "TEST-NOTSO-1",
        "Event_Class": "TEST-CLASS",
        "Event_Type": "TEST-EVENT",
        "Event_Id": "TEST-EVENT-1",
        "Status": "OPEN",
        "Event_Description": "Synthetic notice",
        "Company_Name": "Example Operator",
        "NOTSO_Link": "https://notso.example/TEST-NOTSO-1",
        "Publish_Date": "2026-06-01T00:30:00Z",
        "SatIds": ["99999"],
    },
}


@pytest.fixture(autouse=True)
def audit_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """write_audit, where every UDL ingest calls it, replaced with a recorder. The audit row
    belongs to the run's own transaction, so one written after the run committed fails the test."""
    calls: list[dict[str, Any]] = []

    def record(db: FakeSession, **kwargs: Any) -> None:
        assert db.commit.await_count == 0, "the audit row was written after the run committed"
        calls.append(kwargs)

    monkeypatch.setattr(udl_records, "write_audit", AsyncMock(side_effect=record))
    return calls


def as_db(session: FakeSession) -> AsyncSession:
    return cast("AsyncSession", session)


def udl_serving(
    records: list[dict[str, Any]], requests: list[httpx2.Request], status: int = 200
) -> UDLClient:
    """A UDL client whose every query answers with `records`, noting each request it makes."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(status, json=records)

    return UDLClient(
        base_url="https://udl.example/udl",
        username=UDL_USER,
        password=UDL_KEY,
        transport=httpx2.MockTransport(handler),
    )


def upsert_session(*known_udl_ids: str) -> FakeSession:
    """A session for one upsert: the udl_ids already stored, then the upsert itself."""
    return FakeSession([rows_result([(udl_id,) for udl_id in known_udl_ids]), None])


def sql(statement: ClauseElement) -> str:
    compiled = statement.compile(dialect=POSTGRESQL, compile_kwargs={"literal_binds": True})
    return " ".join(str(compiled).split())


def lookup_sql(session: FakeSession) -> str:
    """The SELECT that asked which of the pulled udl_ids are already stored."""
    return sql(session.execute.await_args_list[0].args[0])


def upsert_sql(session: FakeSession) -> str:
    """The INSERT ... ON CONFLICT the session ran, as PostgreSQL SQL with placeholders (a JSONB
    value cannot be written inline)."""
    compiled = session.execute.await_args_list[1].args[0].compile(dialect=POSTGRESQL)
    return " ".join(str(compiled).split())


def upserted_rows(session: FakeSession) -> list[dict[str, Any]]:
    """The rows the upsert wrote, one per VALUES group, read from SQLAlchemy's bound parameters,
    which it names <column>_m<row> in a multi-row INSERT."""
    compiled = session.execute.await_args_list[1].args[0].compile(dialect=POSTGRESQL)
    rows: dict[int, dict[str, Any]] = {}
    for name, value in compiled.params.items():
        match = re.fullmatch(r"(?P<column>\w+)_m(?P<row>\d+)", name)
        if match and match["column"] != "id":
            rows.setdefault(int(match["row"]), {})[match["column"]] = value
    return [rows[number] for number in sorted(rows)]


async def run_ingest(kind: str, session: FakeSession, client: UDLClient) -> IngestResult:
    if kind == "elset":
        return await ingest_elsets(as_db(session), client, epoch_gte=WINDOW_START)
    if kind == "maneuver":
        return await ingest_maneuvers(as_db(session), client, event_start_time_gte=WINDOW_START)
    return await ingest_notifications(as_db(session), client)


def maneuver(udl_id: str, **fields: Any) -> dict[str, Any]:
    return {"id": udl_id, "satNo": 99999, **fields}


class TestUpsert:
    async def test_new_and_already_stored_records_count_as_inserted_and_updated(self) -> None:
        session = upsert_session("TEST-MNVR-B")
        records = [maneuver("TEST-MNVR-A"), maneuver("TEST-MNVR-B"), maneuver("TEST-MNVR-C")]
        async with udl_serving(records, []) as client:
            result = await run_ingest("maneuver", session, client)
        assert result == IngestResult(pulled=3, inserted=2, updated=1, skipped=0)
        assert lookup_sql(session) == (
            "SELECT maneuver.udl_id FROM maneuver WHERE maneuver.udl_id "
            "IN ('TEST-MNVR-A', 'TEST-MNVR-B', 'TEST-MNVR-C')"
        )
        assert [row["udl_id"] for row in upserted_rows(session)] == [
            "TEST-MNVR-A",
            "TEST-MNVR-B",
            "TEST-MNVR-C",
        ]

    async def test_a_record_repeated_in_one_pull_is_written_once_in_its_latest_version(
        self,
    ) -> None:
        session = upsert_session()
        records = [
            maneuver("TEST-MNVR-A", mnvrType="TEST-FIRST"),
            maneuver("TEST-MNVR-B"),
            maneuver("TEST-MNVR-A", mnvrType="TEST-LATEST"),
        ]
        async with udl_serving(records, []) as client:
            result = await run_ingest("maneuver", session, client)
        assert result == IngestResult(pulled=3, inserted=2, updated=0, skipped=1)
        assert lookup_sql(session).endswith("IN ('TEST-MNVR-A', 'TEST-MNVR-B')")
        assert [(row["udl_id"], row["mnvr_type"]) for row in upserted_rows(session)] == [
            ("TEST-MNVR-A", "TEST-LATEST"),
            ("TEST-MNVR-B", None),
        ]

    async def test_a_record_without_a_udl_id_is_skipped(self) -> None:
        session = upsert_session()
        records: list[dict[str, Any]] = [
            {"satNo": 99999},
            {"id": ""},
            {"id": None},
            maneuver("TEST-MNVR-A"),
        ]
        async with udl_serving(records, []) as client:
            result = await run_ingest("maneuver", session, client)
        assert result == IngestResult(pulled=4, inserted=1, updated=0, skipped=3)
        assert [row["udl_id"] for row in upserted_rows(session)] == ["TEST-MNVR-A"]

    async def test_a_record_its_table_cannot_store_is_skipped_named_and_not_quoted(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        session = upsert_session()
        records = [
            maneuver("TEST-MNVR-A", mnvrType="T" * 101),
            maneuver("TEST-MNVR-B", source=12345),
            maneuver("TEST-MNVR-C", satNo=2**40),
            maneuver("TEST-MNVR-D"),
        ]
        with caplog.at_level(logging.WARNING, logger="app.services.udl_records"):
            async with udl_serving(records, []) as client:
                result = await run_ingest("maneuver", session, client)
        assert result == IngestResult(pulled=4, inserted=1, updated=0, skipped=3)
        assert [row["udl_id"] for row in upserted_rows(session)] == ["TEST-MNVR-D"]
        assert caplog.messages == [
            "Skipping UDL record TEST-MNVR-A: mnvr_type is longer than 100 characters",
            "Skipping UDL record TEST-MNVR-B: source is not text",
            "Skipping UDL record TEST-MNVR-C: sat_no is out of range",
        ]

    @pytest.mark.parametrize(
        ("column_type", "value", "problem"),
        [
            (String(5), "12345", None),
            (String(5), "123456", "is longer than 5 characters"),
            (Text(), "x" * 10_000, None),
            (String(5), 7, "is not text"),
            (Integer(), 7, None),
            (Integer(), 2**31, "is out of range"),
            (Integer(), 1.5, "is not a whole number"),
            (Integer(), True, "is not a whole number"),
            (BigInteger(), 2**40, None),
            (Float(), 1, None),
            (Float(), "1.5", "is not a number"),
            (Float(), False, "is not a number"),
            (DateTime(timezone=True), NOW, None),
            (DateTime(timezone=True), "2026-06-01", "is not a time"),
            (JSONB(), {"any": ["shape"]}, None),
        ],
    )
    def test_each_column_type_takes_only_what_postgresql_can_store(
        self, column_type: Any, value: Any, problem: str | None
    ) -> None:
        assert udl_records._unfit(column_type, value) == problem

    @pytest.mark.parametrize("records", [[], [{"satNo": 99999}]], ids=["empty", "all-skipped"])
    async def test_a_pull_with_nothing_to_write_touches_no_table_but_is_still_audited(
        self, audit_calls: list[dict[str, Any]], records: list[dict[str, Any]]
    ) -> None:
        session = FakeSession()  # any statement at all would fail: it has no results to give
        async with udl_serving(records, []) as client:
            result = await run_ingest("maneuver", session, client)
        assert result == IngestResult(
            pulled=len(records), inserted=0, updated=0, skipped=len(records)
        )
        session.execute.assert_not_awaited()
        [call] = audit_calls
        assert call["detail"]["pulled"] == len(records)
        session.commit.assert_awaited_once()

    async def test_rows_of_different_shapes_are_filled_out_so_no_value_is_dropped(self) -> None:
        # A multi-row VALUES clause takes its columns from the first row, so without the
        # fill a column the first row lacks would be dropped from every later row unseen.
        session = upsert_session("TEST-MNVR-C")
        rows: list[dict[str, Any]] = [
            {"udl_id": "TEST-MNVR-A", "raw": {"id": "TEST-MNVR-A"}},
            {"udl_id": "TEST-MNVR-B", "raw": {"id": "TEST-MNVR-B"}, "sat_no": 99999},
            {"udl_id": "TEST-MNVR-C", "raw": {"id": "TEST-MNVR-C"}, "delta_v": 0.5},
        ]
        inserted, updated = await upsert_rows(
            as_db(session),
            Maneuver,
            rows,
            constraint="uq_maneuver_udl_id",
            updatable=["sat_no", "delta_v", "raw"],
        )
        assert (inserted, updated) == (2, 1)
        assert [(row["sat_no"], row["delta_v"]) for row in rows] == [
            (None, None),
            (99999, None),
            (None, 0.5),
        ]
        assert [(row["sat_no"], row["delta_v"]) for row in upserted_rows(session)] == [
            (None, None),
            (99999, None),
            (None, 0.5),
        ]

    async def test_an_empty_upsert_issues_no_statement(self) -> None:
        session = FakeSession()
        result = await upsert_rows(
            as_db(session), Maneuver, [], constraint="uq_maneuver_udl_id", updatable=["raw"]
        )
        assert result == (0, 0)
        session.execute.assert_not_awaited()

    @pytest.mark.parametrize(
        ("kind", "record", "table", "constraint", "width"),
        [
            ("elset", ELSET_RECORD, "elset", "uq_elset_udl_id", 22),
            ("maneuver", MANEUVER_RECORD, "maneuver", "uq_maneuver_udl_id", 19),
            ("notification", NOTIFICATION_RECORD, "notification", "uq_notification_udl_id", 24),
        ],
    )
    async def test_a_republished_record_updates_every_column_it_carries(
        self, kind: str, record: dict[str, Any], table: str, constraint: str, width: int
    ) -> None:
        session = upsert_session(record["id"])
        async with udl_serving([record], []) as client:
            result = await run_ingest(kind, session, client)
        assert result == IngestResult(pulled=1, inserted=0, updated=1, skipped=0)
        text = upsert_sql(session)
        inserted = re.fullmatch(
            r"INSERT INTO (?P<table>\w+) \((?P<columns>[^)]*)\) VALUES .*", text
        )
        assert inserted is not None
        assert inserted["table"] == table
        head, _, assignments = text.partition(" DO UPDATE SET ")
        assert head.endswith(f"ON CONFLICT ON CONSTRAINT {constraint}")
        updated = dict(item.split(" = ", 1) for item in assignments.split(", "))
        # The premise: the record fills every column the table takes from UDL, so the
        # comparison covers them all rather than whatever a sparse record happened to carry.
        columns = [c for c in inserted["columns"].split(", ") if c not in {"id", "udl_id"}]
        assert len(columns) == width
        assert updated == {c: f"excluded.{c}" for c in columns} | {"updated_at": "now()"}


class TestIngestRuns:
    async def test_an_elset_pull_asks_udl_for_its_window_and_audits_the_run(
        self, audit_calls: list[dict[str, Any]]
    ) -> None:
        user_id = uuid.uuid4()
        session = upsert_session()
        requests: list[httpx2.Request] = []
        async with udl_serving([ELSET_RECORD], requests) as client:
            result = await ingest_elsets(
                as_db(session),
                client,
                epoch_gte=WINDOW_START,
                sat_no=99999,
                data_mode="TEST",
                max_results=10,
                user_id=user_id,
                ip_address="192.0.2.10",
            )
        assert result == IngestResult(pulled=1, inserted=1, updated=0, skipped=0)
        [request] = requests
        assert request.url.path == "/udl/elset"
        assert dict(request.url.params) == {
            "epoch": ">2026-06-01T00:00:00.000000Z",
            "satNo": "99999",
            "dataMode": "TEST",
            "maxResults": "10",
        }
        [call] = audit_calls
        assert {key: call[key] for key in ("action_type", "entity_type", "user_id")} == {
            "action_type": "udl.elset.ingest",
            "entity_type": "elset_ingest_run",
            "user_id": user_id,
        }
        assert call["ip_address"] == "192.0.2.10"
        # The elset run records its data_mode, as the maneuver and notification runs do.
        assert (
            call["detail"].items()
            >= {
                "epoch_gte": "2026-06-01T00:00:00+00:00",
                "sat_no": 99999,
                "data_mode": "TEST",
                "max_results": 10,
                "pulled": 1,
                "inserted": 1,
                "updated": 0,
                "skipped": 0,
            }.items()
        )
        session.commit.assert_awaited_once()

    async def test_a_maneuver_pull_asks_udl_for_its_window_and_audits_the_run(
        self, audit_calls: list[dict[str, Any]]
    ) -> None:
        user_id = uuid.uuid4()
        session = upsert_session("TEST-MNVR-1")
        requests: list[httpx2.Request] = []
        records = [MANEUVER_RECORD, maneuver("TEST-MNVR-2"), {"satNo": 99999}]
        async with udl_serving(records, requests) as client:
            result = await ingest_maneuvers(
                as_db(session),
                client,
                event_start_time_gte=WINDOW_START,
                sat_no=99999,
                data_mode="TEST",
                max_results=10,
                user_id=user_id,
                ip_address="192.0.2.10",
            )
        assert result == IngestResult(pulled=3, inserted=1, updated=1, skipped=1)
        [request] = requests
        assert request.url.path == "/udl/maneuver"
        assert dict(request.url.params) == {
            "eventStartTime": ">2026-06-01T00:00:00.000000Z",
            "satNo": "99999",
            "dataMode": "TEST",
            "maxResults": "10",
        }
        assert audit_calls == [
            {
                "action_type": "udl.maneuver.ingest",
                "entity_type": "maneuver_ingest_run",
                "user_id": user_id,
                "ip_address": "192.0.2.10",
                "detail": {
                    "event_start_time_gte": "2026-06-01T00:00:00+00:00",
                    "sat_no": 99999,
                    "data_mode": "TEST",
                    "max_results": 10,
                    "pulled": 3,
                    "inserted": 1,
                    "updated": 1,
                    "skipped": 1,
                },
            }
        ]
        session.commit.assert_awaited_once()

    @pytest.mark.parametrize(
        ("arguments", "params", "recorded"),
        [
            (
                {
                    "msg_type": "TACREP_NOTSO",
                    "created_at_gte": WINDOW_START,
                    "data_mode": "TEST",
                    "source": "TEST-SOURCE",
                    "max_results": 10,
                },
                {
                    "msgType": "TACREP_NOTSO",
                    "createdAt": ">2026-06-01T00:00:00.000000Z",
                    "dataMode": "TEST",
                    "source": "TEST-SOURCE",
                    "maxResults": "10",
                },
                {
                    "msg_type": "TACREP_NOTSO",
                    "created_at_gte": "2026-06-01T00:00:00+00:00",
                    "data_mode": "TEST",
                    "source": "TEST-SOURCE",
                    "max_results": 10,
                },
            ),
            (
                {},
                {},
                {
                    "msg_type": None,
                    "created_at_gte": None,
                    "data_mode": None,
                    "source": None,
                    "max_results": None,
                },
            ),
        ],
        ids=["every-filter", "no-filter"],
    )
    async def test_a_notification_pull_asks_udl_for_its_filters_and_audits_the_run(
        self,
        audit_calls: list[dict[str, Any]],
        arguments: dict[str, Any],
        params: dict[str, str],
        recorded: dict[str, Any],
    ) -> None:
        user_id = uuid.uuid4()
        session = upsert_session()
        requests: list[httpx2.Request] = []
        async with udl_serving([NOTIFICATION_RECORD], requests) as client:
            result = await ingest_notifications(
                as_db(session), client, user_id=user_id, ip_address="192.0.2.10", **arguments
            )
        assert result == IngestResult(pulled=1, inserted=1, updated=0, skipped=0)
        [request] = requests
        assert request.url.path == "/udl/notification"
        assert dict(request.url.params) == params
        assert audit_calls == [
            {
                "action_type": "udl.notification.ingest",
                "entity_type": "notification_ingest_run",
                "user_id": user_id,
                "ip_address": "192.0.2.10",
                "detail": recorded | {"pulled": 1, "inserted": 1, "updated": 0, "skipped": 0},
            }
        ]
        session.commit.assert_awaited_once()

    @pytest.mark.parametrize("kind", ["elset", "maneuver", "notification"])
    async def test_a_failed_pull_writes_and_audits_nothing(
        self, audit_calls: list[dict[str, Any]], kind: str
    ) -> None:
        session = FakeSession()
        with pytest.raises(UDLClientError, match="UDL returned HTTP 503"):
            async with udl_serving([], [], status=503) as client:
                await run_ingest(kind, session, client)
        session.execute.assert_not_awaited()
        session.commit.assert_not_awaited()
        assert audit_calls == []


class TestMappingGaps:
    @pytest.mark.parametrize(
        "record",
        [
            {"idElset": "TEST-ELSET-A", "noradCatId": "99999", "epochDate": "2026-06-01T00:00Z"},
            {"elsetId": "TEST-ELSET-A", "noradId": 99999, "epochTime": "2026-06-01T00:00Z"},
            {"id": "", "idElset": "TEST-ELSET-A", "sat_no": 99999, "epoch": "2026-06-01T00:00Z"},
        ],
        ids=["idElset-noradCatId-epochDate", "elsetId-noradId-epochTime", "blank-id-falls-back"],
    )
    def test_an_elset_is_read_from_any_of_its_known_field_names(
        self, record: dict[str, Any]
    ) -> None:
        mapped = elset_ingest._map_udl_record(record)
        assert mapped is not None
        assert (mapped["udl_id"], mapped["sat_no"], mapped["epoch"]) == (
            "TEST-ELSET-A",
            99999,
            datetime(2026, 6, 1, tzinfo=UTC),
        )

    def test_an_elset_epoch_that_is_already_a_datetime_is_kept(self) -> None:
        mapped = elset_ingest._map_udl_record({"id": "TEST-ELSET-A", "satNo": 99999, "epoch": NOW})
        assert mapped is not None
        assert mapped["epoch"] is NOW

    @pytest.mark.parametrize(
        ("record", "logged"),
        [
            (
                {"id": "TEST-ELSET-A", "satNo": 99999, "epoch": "yesterday"},
                "Could not parse elset epoch 'yesterday'; skipping",
            ),
            (
                {"id": "TEST-ELSET-A", "satNo": 99999, "epoch": 1780000000},
                "Unexpected elset epoch type int; skipping",
            ),
            (
                {"id": "TEST-ELSET-A", "satNo": "TEST-SAT", "epoch": "2026-06-01T00:00Z"},
                "Skipping UDL elset record: id='TEST-ELSET-A' sat_no='TEST-SAT' "
                "epoch='2026-06-01T00:00Z' keys=['epoch', 'id', 'satNo']",
            ),
        ],
        ids=["unparseable-epoch", "numeric-epoch", "non-numeric-sat-no"],
    )
    def test_an_unusable_elset_is_skipped_and_named_in_the_log(
        self, caplog: pytest.LogCaptureFixture, record: dict[str, Any], logged: str
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="app.services.elset_ingest"):
            assert elset_ingest._map_udl_record(record) is None
        assert caplog.messages == [logged]

    def test_every_maneuver_field_is_mapped_to_its_typed_column(self) -> None:
        mapped = maneuver_ingest._map_udl_record(MANEUVER_RECORD)
        assert mapped == {
            "udl_id": "TEST-MNVR-1",
            "raw": MANEUVER_RECORD,
            "data_mode": "TEST",
            "source": "TEST-SOURCE",
            "classification_marking": "U",
            "created_by": "example-analyst",
            "orig_network": "TEST-NET",
            "origin": "TEST-ORIGIN",
            "mnvr_type": "TEST",
            "description": "Synthetic manoeuvre",
            "propulsion_type": "TEST-PROPULSION",
            "maneuver_status": "TEST-STATUS",
            "responsible_nation": "TEST",
            "udl_created_at": datetime(2026, 6, 1, 1, 0, tzinfo=UTC),
            "event_start_time": datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
            "event_stop_time": datetime(2026, 6, 1, 0, 10, tzinfo=UTC),
            "delta_v": 0.5,
            "thrust_magnitude": 1.5,
            "thrust_duration": 30.0,
            "sat_no": 99999,
        }

    def test_maneuver_numbers_given_as_text_are_converted(self) -> None:
        record = {"id": "TEST-MNVR-1", "satNo": "99999", "deltaV": "0.5", "thrustMag": "2"}
        mapped = maneuver_ingest._map_udl_record(record)
        assert mapped is not None
        assert (mapped["sat_no"], mapped["delta_v"], mapped["thrust_magnitude"]) == (
            99999,
            0.5,
            2.0,
        )

    def test_unusable_maneuver_values_are_left_out_rather_than_failing_the_record(self) -> None:
        record = {
            "id": "TEST-MNVR-1",
            "satNo": "TEST-SAT",
            "deltaV": "fast",
            "thrustMag": None,
            "eventStartTime": "soon",
            "eventStopTime": "",
            "description": "",
            "mnvrType": None,
        }
        assert maneuver_ingest._map_udl_record(record) == {"udl_id": "TEST-MNVR-1", "raw": record}

    def test_a_maneuver_time_that_is_already_a_datetime_is_kept(self) -> None:
        mapped = maneuver_ingest._map_udl_record({"id": "TEST-MNVR-1", "eventStartTime": NOW})
        assert mapped is not None
        assert mapped["event_start_time"] is NOW

    @pytest.mark.parametrize("record", [{"satNo": 99999}, {"id": ""}, {"id": None}])
    def test_a_maneuver_without_a_udl_id_is_not_mapped(self, record: dict[str, Any]) -> None:
        assert maneuver_ingest._map_udl_record(record) is None

    @pytest.mark.parametrize("sat_ids", [[], None], ids=["empty-list", "absent"])
    def test_a_notification_without_a_satellite_list_falls_back_to_its_flat_sat_no(
        self, sat_ids: object
    ) -> None:
        record = {"id": "TEST-NOTIF-1", "satNo": "99999", "msgBody": {"SatIds": sat_ids}}
        mapped = notification_ingest._map_udl_record(record)
        assert mapped is not None
        assert "sat_ids" not in mapped
        assert mapped["sat_no"] == 99999

    def test_a_notification_takes_its_message_body_over_the_flat_fallbacks(self) -> None:
        record = {
            "id": "TEST-NOTIF-1",
            "noticeId": "TEST-FLAT-NOTICE",
            "subject": "Flat subject",
            "text": "Flat text",
            "msgBody": {
                "NOTSO": "TEST-NOTSO-1",
                "Event_Class": "TEST-CLASS",
                "Event_Description": "Body description",
            },
        }
        mapped = notification_ingest._map_udl_record(record)
        assert mapped is not None
        assert (mapped["notice_id"], mapped["subject"], mapped["description"]) == (
            "TEST-NOTSO-1",
            "TEST-CLASS",
            "Body description",
        )

    @pytest.mark.parametrize(
        ("times", "until"),
        [
            (
                {
                    "effectiveUntil": "2026-06-08T00:00:00Z",
                    "expirationTime": "2026-07-01T00:00:00Z",
                },
                datetime(2026, 6, 8, tzinfo=UTC),
            ),
            ({"expirationTime": "2026-07-01T00:00:00Z"}, datetime(2026, 7, 1, tzinfo=UTC)),
            (
                {"effectiveUntil": "later", "expirationTime": "2026-07-01T00:00:00Z"},
                datetime(2026, 7, 1, tzinfo=UTC),
            ),
        ],
        ids=["until-wins", "expiration-fallback", "unparseable-until-falls-back"],
    )
    def test_a_notification_expiry_comes_from_the_first_usable_field(
        self, times: dict[str, str], until: datetime
    ) -> None:
        mapped = notification_ingest._map_udl_record({"id": "TEST-NOTIF-1", **times})
        assert mapped is not None
        assert mapped["effective_until"] == until

    def test_an_unparseable_publish_date_is_left_out(self) -> None:
        record = {"id": "TEST-NOTIF-1", "msgBody": {"Publish_Date": "not a date", "Status": "OPEN"}}
        mapped = notification_ingest._map_udl_record(record)
        assert mapped is not None
        assert "publish_date" not in mapped
        assert mapped["status"] == "OPEN"


class TestNotificationQuery:
    def test_a_notice_is_grouped_by_event_then_notso_then_udl_id(self) -> None:
        assert sql(notification_group_key()) == GROUP_KEY

    @pytest.mark.parametrize("conditions", [None, []], ids=["none", "empty"])
    def test_the_freshest_publication_of_each_notice_is_kept(
        self, conditions: list[Any] | None
    ) -> None:
        # DISTINCT ON keeps the first row of each group in ORDER BY order, so the order after
        # the key decides which publication survives: the latest UDL time, then the newest row.
        text = sql(deduped_notifications_select(conditions))
        assert text.startswith(f"SELECT DISTINCT ON ({GROUP_KEY}) notification.")
        assert text.endswith(
            f"FROM notification ORDER BY {GROUP_KEY}, "
            "notification.udl_created_at DESC NULLS LAST, notification.created_at DESC"
        )

    def test_conditions_select_the_rows_before_they_are_grouped(self) -> None:
        text = sql(
            deduped_notifications_select(
                [Notification.status == "OPEN", Notification.sat_no == 99999]
            )
        )
        assert (
            "FROM notification WHERE notification.status = 'OPEN' "
            f"AND notification.sat_no = 99999 ORDER BY {GROUP_KEY}, "
        ) in text

    def test_the_alias_and_the_count_both_read_the_deduplicated_rows(self) -> None:
        alias, subquery = aliased_deduped_notifications([Notification.status == "OPEN"])
        deduplicated = f"DISTINCT ON ({GROUP_KEY}) notification.msg_type AS msg_type, "
        selected = sql(select(alias.id, alias.udl_created_at))
        assert selected.startswith("SELECT anon_1.id, anon_1.udl_created_at FROM (SELECT ")
        assert deduplicated in selected
        assert selected.endswith("notification.created_at DESC) AS anon_1")
        counted = sql(select(func.count()).select_from(subquery))
        assert counted.startswith("SELECT count(*) AS count_1 FROM (SELECT ")
        assert deduplicated in counted
        assert "WHERE notification.status = 'OPEN'" in counted


class TestTokenRevocation:
    @pytest.mark.parametrize(("stored", "revoked"), [("test-jti-1", True), (None, False)])
    async def test_a_jti_is_revoked_only_when_the_block_list_holds_it(
        self, stored: str | None, revoked: bool
    ) -> None:
        session = FakeSession([scalar_result(stored)])
        assert await is_revoked(as_db(session), "test-jti-1") is revoked
        [call] = session.execute.await_args_list
        assert sql(call.args[0]) == (
            "SELECT revoked_jti.jti FROM revoked_jti WHERE revoked_jti.jti = 'test-jti-1' LIMIT 1"
        )

    @pytest.mark.parametrize("user_id", [uuid.UUID(int=1), None], ids=["user", "no-user"])
    async def test_revoking_a_new_jti_adds_it_to_the_block_list(
        self, user_id: uuid.UUID | None
    ) -> None:
        session = FakeSession([scalar_result(None)])
        await revoke(as_db(session), jti="test-jti-1", user_id=user_id, expires_at=NOW)
        [row] = session.added
        assert isinstance(row, RevokedJti)
        assert (row.jti, row.user_id, row.expires_at) == ("test-jti-1", user_id, NOW)
        session.flush.assert_awaited_once()

    async def test_revoking_a_jti_twice_adds_nothing(self) -> None:
        session = FakeSession([scalar_result("test-jti-1")])
        await revoke(as_db(session), jti="test-jti-1", user_id=None, expires_at=NOW)
        assert session.added == []
        session.flush.assert_not_awaited()
