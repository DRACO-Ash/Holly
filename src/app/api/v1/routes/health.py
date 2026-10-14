"""Database-aware health checks for operators.

The platform probes (/healthz and the rest, in app/factory.py) touch nothing. These two do
touch the database, so they report whether Holly can actually serve data.
"""

import logging
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.config import get_settings
from app.dependencies import DbSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: DbSession) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/health/detailed")
async def health_detailed(db: DbSession) -> dict[str, Any]:
    settings = get_settings()
    try:
        await db.execute(text("SELECT 1"))
        database = "ok"
    except (SQLAlchemyError, OSError) as exc:
        logger.warning("Database health check failed: %s", type(exc).__name__)
        database = "down"
    udl_configured = bool(settings.udl_username and settings.udl_password.get_secret_value())
    return {
        "status": "ok" if database == "ok" else "degraded",
        "version": __version__,
        "environment": settings.app_env,
        "components": {
            "database": database,
            "udl_credentials": "configured" if udl_configured else "missing",
        },
    }
