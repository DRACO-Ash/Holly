"""The schema migrations Holly applies at container start (app/migrate.py).

Alembic's offline mode runs every migration's upgrade and downgrade code and emits the SQL
instead of executing it, so these tests read the whole schema history without a database.
The online path, which holds the advisory lock, is exercised against a real PostgreSQL by the
container smoke rung (scripts/smoke-container.sh).
"""

import asyncio
import configparser
import io
import json
import logging
import re
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url
from sqlalchemy.exc import InterfaceError, OperationalError

from app import migrate
from app.db.base import Base
from app.migrate import MIGRATIONS_DIR, alembic_config, run_migrations
from app.models import (  # noqa: F401  registers every model on Base.metadata
    assistant_evaluation,
    audit,
    elset,
    event_summary,
    event_timer,
    maneuver,
    mattermost_message,
    notification,
    procedure,
    revoked_jti,
    shift_note,
    shift_summary,
    user,
)

ROOT = Path(__file__).resolve().parent.parent


def offline_sql(direction: str, target: str) -> str:
    config = alembic_config()
    buffer = io.StringIO()
    config.output_buffer = buffer
    getattr(command, direction)(config, target, sql=True)
    return buffer.getvalue()


def test_there_is_one_linear_history_with_one_head() -> None:
    scripts = ScriptDirectory.from_config(alembic_config())
    assert len(scripts.get_heads()) == 1
    revisions = list(scripts.walk_revisions())
    assert len(revisions) == 19
    # The container smoke rung reads the head from the newest file's name.
    newest = sorted(path.stem for path in (MIGRATIONS_DIR / "versions").glob("0*.py"))[-1]
    assert scripts.get_current_head() == newest
    assert all(not isinstance(revision.down_revision, tuple) for revision in revisions)


def test_upgrading_to_head_builds_every_table_the_models_describe() -> None:
    sql = offline_sql("upgrade", "head")
    created = set(re.findall(r"CREATE TABLE (\S+) \(", sql))
    renamed = dict(re.findall(r"ALTER TABLE (\S+) RENAME TO (\S+);", sql))
    final = {renamed.get(name, name) for name in created} - {"alembic_version"}
    assert final == set(Base.metadata.tables)
    assert "CREATE SCHEMA IF NOT EXISTS audit" in sql
    assert sql.rstrip().endswith("COMMIT;")


def test_downgrading_to_base_drops_everything_again() -> None:
    sql = offline_sql("downgrade", "head:base")
    dropped = set(re.findall(r"DROP TABLE (\S+);", sql))
    renamed = dict(re.findall(r"ALTER TABLE (\S+) RENAME TO (\S+);", sql))
    original_names = {renamed.get(name, name) for name in Base.metadata.tables}
    assert original_names <= dropped


def test_the_audit_log_refuses_every_change_but_an_insert() -> None:
    sql = offline_sql("upgrade", "head")
    assert (
        "CREATE TRIGGER audit_log_append_only BEFORE UPDATE OR DELETE OR TRUNCATE ON "
        "audit.audit_log FOR EACH STATEMENT EXECUTE FUNCTION audit.refuse_change()"
    ) in sql
    assert "RAISE EXCEPTION 'audit.audit_log is append-only'" in sql


def test_timers_gain_a_recurrence_anchor_set_from_their_target() -> None:
    sql = offline_sql("upgrade", "head")
    assert "ALTER TABLE event_timer ADD COLUMN recurrence_anchor TIMESTAMP WITH TIME ZONE" in sql
    assert (
        "UPDATE event_timer SET recurrence_anchor = target_time WHERE recurrence <> 'none'" in sql
    )


def test_users_gain_a_password_change_flag_and_a_token_version_existing_ones_keep() -> None:
    sql = offline_sql("upgrade", "head")
    assert (
        "ALTER TABLE app_user ADD COLUMN must_change_password BOOLEAN DEFAULT false NOT NULL" in sql
    )
    assert "ALTER TABLE app_user ADD COLUMN token_version INTEGER DEFAULT 0 NOT NULL" in sql
    # The rollback to V0.9 runs this downgrade (operator manual, section 06): both columns go.
    down = offline_sql("downgrade", "0018_user_password_state:0017_audit_append_only")
    assert "ALTER TABLE app_user DROP COLUMN token_version" in down
    assert "ALTER TABLE app_user DROP COLUMN must_change_password" in down


def test_channels_get_a_table_of_their_own_followed_and_new_by_default() -> None:
    sql = offline_sql("upgrade", "head")
    assert "CREATE TABLE mattermost_channel (" in sql
    assert "following BOOLEAN DEFAULT true NOT NULL" in sql
    assert "reviewed BOOLEAN DEFAULT false NOT NULL" in sql
    assert "CONSTRAINT uq_mattermost_channel_mm_channel_id UNIQUE (mm_channel_id)" in sql


def test_the_developer_ini_points_at_the_packaged_migrations() -> None:
    parser = configparser.ConfigParser(defaults={"here": str(ROOT)})
    parser.read(ROOT / "alembic.ini")
    assert Path(parser["alembic"]["script_location"]).resolve() == MIGRATIONS_DIR


@contextmanager
def preserved_logging() -> Iterator[None]:
    """The developer ini configures logging from its own sections; put everything back."""
    root = logging.getLogger()
    named = [logging.getLogger(name) for name in ("alembic", "sqlalchemy.engine")]
    saved = (root.handlers[:], root.level, [logger.level for logger in named])
    try:
        yield
    finally:
        root.handlers[:] = saved[0]
        root.setLevel(saved[1])
        for logger, level in zip(named, saved[2], strict=True):
            logger.setLevel(level)


def test_the_developer_ini_runs_the_same_history() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    buffer = io.StringIO()
    config.output_buffer = buffer
    with preserved_logging():
        command.upgrade(config, "head", sql=True)
    assert buffer.getvalue() == offline_sql("upgrade", "head")


def test_the_container_config_needs_no_ini_file() -> None:
    config = alembic_config()
    assert config.config_file_name is None
    assert config.get_main_option("script_location") == str(MIGRATIONS_DIR)


def test_run_migrations_upgrades_to_head_and_logs_each_step(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[tuple[Config, str]] = []
    monkeypatch.setattr(command, "upgrade", lambda config, target: calls.append((config, target)))
    run_migrations()
    [(config, target)] = calls
    assert target == "head"
    assert config.get_main_option("script_location") == str(MIGRATIONS_DIR)
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [(event["event"], event["status"]) for event in events] == [
        ("migrations", "starting"),
        ("migrations", "applied"),
    ]


def test_a_failed_migration_stops_the_start(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_config: Config, _target: str) -> None:
        msg = "relation already exists"
        raise RuntimeError(msg)

    monkeypatch.setattr(command, "upgrade", fail)
    with pytest.raises(RuntimeError, match="relation already exists"):
        run_migrations()


class _AdaptedError(Exception):
    """Shaped like SQLAlchemy's asyncpg adapter error: a sqlstate, the driver's error as its
    cause."""

    def __init__(self, sqlstate: str, driver: BaseException) -> None:
        super().__init__("adapted")
        self.sqlstate = sqlstate
        self.__cause__ = driver


_DRIVER_ERRORS = {
    "28P01": "InvalidPasswordError",
    "3D000": "InvalidCatalogNameError",
    "57P03": "CannotConnectNowError",
    "08006": "ConnectionFailureError",
}


def refused(sqlstate: str) -> OperationalError:
    driver = type(_DRIVER_ERRORS[sqlstate], (Exception,), {})("no value in here")
    return OperationalError("SELECT 1", {}, _AdaptedError(sqlstate, driver))


class TestWaitForDatabase:
    """The master asks for the database for about a minute before it gives up, since the
    add-on's database, and the DAST scan's, may come up after the container."""

    URL = make_url("postgresql+asyncpg://holly:not-a-real-password@db.invalid:5432/holly")

    def run(
        self, monkeypatch: pytest.MonkeyPatch, outcomes: list[BaseException | None]
    ) -> list[float]:
        # Each outcome in turn: an exception is raised, None means the database answered.
        monkeypatch.setattr(migrate, "_database_answers", AsyncMock(side_effect=outcomes))
        slept: list[float] = []
        now = [0.0]

        def sleep(seconds: float) -> None:
            slept.append(seconds)
            now[0] += seconds

        migrate.wait_for_database(self.URL, deadline_seconds=5, clock=lambda: now[0], sleep=sleep)
        return slept

    def test_a_database_that_answers_at_once_is_not_waited_for(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert self.run(monkeypatch, [None]) == []
        assert '"status": "ready", "attempts": 1' in capsys.readouterr().out

    def test_a_database_that_comes_up_late_is_waited_for(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        slept = self.run(
            monkeypatch,
            [ConnectionRefusedError(), refused("57P03"), refused("08006"), None],
        )
        assert slept == [migrate.DATABASE_RETRY_SECONDS] * 3
        out = capsys.readouterr().out
        assert '"error": "ConnectionRefusedError"' in out
        assert '"error": "CannotConnectNowError"' in out
        assert '"status": "ready", "attempts": 4' in out

    @pytest.mark.parametrize(
        ("sqlstate", "named"),
        [("28P01", "SQLSTATE 28P01, InvalidPasswordError"), ("3D000", "SQLSTATE 3D000")],
    )
    def test_a_database_that_answers_and_refuses_stops_the_start_at_once(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        sqlstate: str,
        named: str,
    ) -> None:
        with pytest.raises(RuntimeError, match=rf"refused the connection \({named}") as raised:
            self.run(monkeypatch, [refused(sqlstate)])
        # Not retried: a wrong password or a missing database will not clear on its own.
        assert "database_wait" not in capsys.readouterr().out
        assert raised.value.__cause__ is None
        assert raised.value.__suppress_context__

    def test_a_refusal_with_no_sqlstate_stops_the_start_naming_its_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bare = InterfaceError("SELECT 1", {}, Exception("connection settings were not valid"))
        with pytest.raises(RuntimeError, match=r"SQLSTATE none, Exception\)"):
            self.run(monkeypatch, [bare])

    def test_a_database_that_never_answers_stops_the_start_naming_the_error_alone(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(
            RuntimeError,
            match=r"could not be reached within about 5 seconds \(last error: gaierror\)",
        ) as raised:
            self.run(monkeypatch, [socket.gaierror("db.invalid holly not-a-real-password")] * 10)
        assert "not-a-real-password" not in str(raised.value)
        assert "not-a-real-password" not in capsys.readouterr().out
        assert raised.value.__cause__ is None
        assert raised.value.__suppress_context__

    def test_any_other_failure_is_not_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with pytest.raises(ValueError, match="not a connection problem"):
            self.run(monkeypatch, [ValueError("not a connection problem")])

    def test_the_probe_hides_parameters_bounds_the_connect_and_always_disposes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        made: list[dict[str, object]] = []
        disposed: list[bool] = []

        class Connection:
            async def __aenter__(self) -> "Connection":
                return self

            async def __aexit__(self, *_exc: object) -> None:
                return None

            async def execute(self, statement: object) -> None:
                assert str(statement) == "SELECT 1"
                raise ConnectionResetError

        class Engine:
            def connect(self) -> Connection:
                return Connection()

            async def dispose(self) -> None:
                disposed.append(True)

        def engine(url: object, **kwargs: object) -> Engine:
            made.append({"url": url, **kwargs})
            return Engine()

        monkeypatch.setattr(migrate, "create_async_engine", engine)
        with pytest.raises(ConnectionResetError):
            asyncio.run(migrate._database_answers(self.URL))
        assert made == [{"url": self.URL, "hide_parameters": True, "connect_args": {"timeout": 5}}]
        assert disposed == [True]
