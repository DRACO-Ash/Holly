"""The database-aware health reads under /api/v1. Unlike the platform probes, these touch the
database, so they say whether Holly can actually serve data."""

from collections.abc import Callable

import httpx2
import pytest
from sqlalchemy.exc import OperationalError

from app import __version__
from fakes import FakeSession

UseSession = Callable[[FakeSession], FakeSession]
CONFIGURED_UDL = {"UDL_USERNAME": "analyst", "UDL_PASSWORD": "pw-1"}


async def test_health_returns_ok_after_a_database_round_trip(
    api: httpx2.AsyncClient, use_session: UseSession
) -> None:
    session = use_session(FakeSession([None]))
    response = await api.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "SELECT 1" in str(session.execute.await_args_list[0].args[0])


async def test_detailed_health_reports_each_component(
    api: httpx2.AsyncClient, use_session: UseSession
) -> None:
    use_session(FakeSession([None]))
    response = await api.get("/api/v1/health/detailed")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": __version__,
        "environment": "production",
        "components": {"database": "ok", "udl_credentials": "missing"},
    }


@pytest.mark.parametrize(
    "failure",
    [OperationalError("SELECT 1", {}, Exception("connection refused")), OSError("unreachable")],
)
async def test_detailed_health_is_degraded_when_the_database_is_down(
    api: httpx2.AsyncClient, use_session: UseSession, failure: Exception
) -> None:
    use_session(FakeSession([failure]))
    body = (await api.get("/api/v1/health/detailed")).json()
    assert body["status"] == "degraded"
    assert body["components"]["database"] == "down"
    assert "connection refused" not in str(body)


async def test_detailed_health_reports_configured_udl_credentials_without_them(
    api: httpx2.AsyncClient, use_session: UseSession, settings_env: Callable[..., None]
) -> None:
    settings_env(**CONFIGURED_UDL)
    use_session(FakeSession([None]))
    response = await api.get("/api/v1/health/detailed")
    assert response.json()["components"]["udl_credentials"] == "configured"
    assert "pw-1" not in response.text
    assert "analyst" not in response.text
