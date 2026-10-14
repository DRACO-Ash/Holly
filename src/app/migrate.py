"""Apply the database migrations, once per container start.

gunicorn calls run_migrations from its master process before any worker starts
(app/gunicorn_conf.py). Alembic's env.py takes a PostgreSQL advisory lock for the run, so if
the platform starts two containers at once, the second waits and then finds nothing to do.
A migration that fails stops the container, with Alembic's error in the log.

The migrations ship inside the package (app/migrations), so the container needs no
alembic.ini; that file at the repository root serves the developer's alembic command line and
points at the same directory.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.logging import log_event

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def alembic_config() -> Config:
    """The Alembic configuration the container uses: the packaged migrations, no ini file."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return config


def run_migrations(config: Config | None = None) -> None:
    log_event("migrations", status="starting")
    command.upgrade(config or alembic_config(), "head")
    log_event("migrations", status="applied")
