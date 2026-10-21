import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.db.base import Base
from app.models import (  # noqa: F401  registers every model on Base.metadata
    assistant_evaluation,
    audit,
    elset,
    event_summary,
    event_timer,
    maneuver,
    mattermost_channel,
    mattermost_message,
    notification,
    procedure,
    revoked_jti,
    shift_note,
    shift_summary,
    user,
)

# Serialises migration runs across containers that start together: the second waits for the
# first to commit, then finds the schema already at head. The value is arbitrary but fixed.
MIGRATION_ADVISORY_LOCK_KEY = 0x484F4C4C

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().sqlalchemy_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
    )
    with context.begin_transaction():
        connection.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_ADVISORY_LOCK_KEY}
        )
        context.run_migrations()


async def run_migrations_online() -> None:
    # The parsed URL goes to the engine as it is, never through config.set_main_option, which
    # routes through ConfigParser and treats a `%` in the password as interpolation syntax,
    # and never as text, which SQLAlchemy would parse a second time.
    section = config.get_section(config.config_ini_section, {})
    connectable = async_engine_from_config(
        section, prefix="sqlalchemy.", url=get_settings().sqlalchemy_url(), hide_parameters=True
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
