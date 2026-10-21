"""Shared fixtures: the app is built by its factory and driven in-process.

Holly validates its settings at boot and fails closed, so the suite sets every setting it reads
before any test module imports the app. Each value is test-only: the database host is under
the reserved .invalid domain and is never contacted (tests replace the session), the signing
key is random per run, and every integration credential is empty, which also overrides any
value a developer's local .env file would supply. Nothing here is a credential.
"""

import os
import secrets
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.update(
    {
        "APP_ENV": "production",
        "APP_SECRET_KEY": secrets.token_urlsafe(48),
        "APP_ALLOWED_ORIGINS": "[]",
        "DATABASE_URL": "postgresql://holly@db.invalid:5432/holly_test",
        "UDL_BASE_URL": "https://udl.invalid/udl",
        "UDL_USERNAME": "",
        "UDL_PASSWORD": "",
        "MATTERMOST_URL": "",
        "MATTERMOST_BOT_TOKEN": "",
        "MATTERMOST_CHANNEL_IDS": "",
        "ANTHROPIC_API_KEY": "",
        "BACKGROUND_REFRESH_ENABLED": "false",
    }
)

# The environment above must be set before the application is imported.
from app.config import get_settings
from app.core import rate_limit
from app.db.session import get_db
from app.dependencies import get_current_user
from app.factory import create_app
from app.models.user import User
from app.services import claude, mattermost_channels
from fakes import FakeSession


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Each test gets its own procedure store, fresh settings, and empty limiter and budget
    counters, so no test can see what another left behind."""
    monkeypatch.setenv("PROCEDURE_STORAGE_PATH", str(tmp_path / "procedures"))
    monkeypatch.delenv("STORAGE_MOUNT_PATH", raising=False)
    get_settings.cache_clear()
    rate_limit.reset_all()
    mattermost_channels.forget_sweep()
    claude.BUDGET.day = None
    claude.BUDGET.spent = 0
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings_env(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Set environment variables for one test and make the next get_settings() read them."""

    def apply(**values: str) -> None:
        for name, value in values.items():
            monkeypatch.setenv(name, value)
        get_settings.cache_clear()

    return apply


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """The app with its lifespan run, as a source checkout serves it (no dashboard built)."""
    with TestClient(create_app(static_dir=tmp_path / "not-built")) as test_client:
        yield test_client


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    """A fresh app for one test, so dependency overrides never leak between tests."""
    return create_app(static_dir=tmp_path / "not-built")


@pytest.fixture
def use_session(api_app: FastAPI) -> Callable[[FakeSession], FakeSession]:
    """Route every request's database session to the given fake."""

    def install(session: FakeSession) -> FakeSession:
        def _get_db() -> Iterator[FakeSession]:
            yield session

        api_app.dependency_overrides[get_db] = _get_db
        return session

    return install


@pytest.fixture
def sign_in(api_app: FastAPI) -> Callable[[User], User]:
    """Treat every request as made by the given user, skipping the token check."""

    def install(user: User) -> User:
        api_app.dependency_overrides[get_current_user] = lambda: user
        return user

    return install


@pytest.fixture
async def api(api_app: FastAPI) -> AsyncIterator[httpx2.AsyncClient]:
    """An HTTP client wired straight to the app, without running its lifespan."""
    transport = httpx2.ASGITransport(app=api_app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://holly.test") as client:
        yield client
