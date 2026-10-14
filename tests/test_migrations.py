"""The schema migrations Holly applies at container start (app/migrate.py).

Alembic's offline mode runs every migration's upgrade and downgrade code and emits the SQL
instead of executing it, so these tests read the whole schema history without a database.
The online path, which holds the advisory lock, is exercised against a real PostgreSQL by the
container smoke rung (scripts/smoke-container.sh).
"""

import configparser
import io
import json
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

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
    assert len(revisions) == 17
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
