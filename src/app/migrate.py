"""Apply the database migrations, once per container start.

gunicorn calls run_migrations from its master process before any worker starts
(app/gunicorn_conf.py). Alembic's env.py takes a PostgreSQL advisory lock for the run, so if
the platform starts two containers at once, the second waits and then finds nothing to do.
A migration that fails stops the container, with Alembic's error in the log.

The migrations ship inside the package (app/migrations), so the container needs no
alembic.ini; that file at the repository root serves the developer's alembic command line and
points at the same directory.
"""

import asyncio
import time
from collections.abc import Callable
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.logging import log_event

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
# The database may come up after the container, the add-on's and the DAST scan's alike: the
# master asks for about a minute before it gives up (the platform's scan log advises this).
# Only a database that cannot be reached, says it is starting (SQLSTATE 57P03) or drops the
# connection (class 08) is waited for; one that answers and refuses (a wrong password, a
# missing database or role) stops the start at once, naming the refusal.
DATABASE_WAIT_SECONDS = 60
DATABASE_RETRY_SECONDS = 2
_CONNECT_TIMEOUT_SECONDS = 5
_STARTING_UP = "57P03"
_CONNECTION_CLASS = "08"


async def _database_answers(url: URL) -> None:
    engine = create_async_engine(
        url, hide_parameters=True, connect_args={"timeout": _CONNECT_TIMEOUT_SECONDS}
    )
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


def _refusal(exc: SQLAlchemyError) -> tuple[str | None, str]:
    """The SQLSTATE and the driver's own error class behind a database error; neither holds a
    value from the connection."""
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None)
    cause = orig.__cause__ if orig is not None and orig.__cause__ is not None else orig
    return sqlstate, type(cause if cause is not None else exc).__name__


def wait_for_database(
    url: URL,
    *,
    deadline_seconds: float = DATABASE_WAIT_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Return once the database answers, retrying for about deadline_seconds while it cannot be
    reached or is starting; stop the start at once on any other refusal. Every line names an
    error's SQLSTATE and type, never its text, which could quote the URL."""
    started = clock()
    attempt = 0
    while True:
        attempt += 1
        try:
            asyncio.run(_database_answers(url))
        except SQLAlchemyError as exc:
            sqlstate, error = _refusal(exc)
            transient = sqlstate == _STARTING_UP or (sqlstate or "").startswith(_CONNECTION_CLASS)
            if not transient:
                msg = (
                    f"the database refused the connection (SQLSTATE {sqlstate or 'none'}, {error})"
                )
                raise RuntimeError(msg) from None
        except OSError as exc:
            error = type(exc).__name__
        else:
            log_event("database_wait", status="ready", attempts=attempt)
            return
        if clock() - started >= deadline_seconds:
            msg = (
                f"the database could not be reached within about {deadline_seconds:g} seconds "
                f"(last error: {error})"
            )
            raise RuntimeError(msg) from None
        log_event("database_wait", status="retrying", attempt=attempt, error=error)
        sleep(DATABASE_RETRY_SECONDS)


def alembic_config() -> Config:
    """The Alembic configuration the container uses: the packaged migrations, no ini file."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return config


def run_migrations(config: Config | None = None) -> None:
    log_event("migrations", status="starting")
    command.upgrade(config or alembic_config(), "head")
    log_event("migrations", status="applied")
