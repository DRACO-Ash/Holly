"""Configuration: PORT resolution, then the settings Holly validates at boot. Each unsafe or
incomplete setting stops the container with a clear message (fail closed).

Expected values are literals, never the module's own constants, so a changed bound fails here.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError

from app.config import Settings, asyncpg_url, get_settings, resolve_port

# Non-ASCII digits, built from code points so the source stays plain ASCII.
# str.isdigit() is true for both, so the ASCII check is what must refuse them.
FULL_WIDTH_8080 = "".join(chr(code) for code in (0xFF18, 0xFF10, 0xFF18, 0xFF10))
SUPERSCRIPT_TWO = chr(0x00B2)


def test_port_defaults_to_8080_when_absent() -> None:
    assert resolve_port({}) == 8080


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
def test_blank_port_falls_back_to_8080(raw: str) -> None:
    assert resolve_port({"PORT": raw}) == 8080


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", 1), ("8080", 8080), (" 3000\n", 3000), ("65535", 65535)],
)
def test_canonical_port_is_honoured(raw: str, expected: int) -> None:
    assert resolve_port({"PORT": raw}) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "0",
        "00001",
        "08080",
        "65536",
        "99999",
        "100000",
        "-1",
        "+80",
        "8_080",
        "80.0",
        "abc",
        '"8080"',
        "8080 --check-config",
        FULL_WIDTH_8080,
        SUPERSCRIPT_TWO,
        # Past Python's 4,300-digit int() limit: only the length guard keeps this message ours.
        "1" * 5000,
    ],
)
def test_malformed_port_fails_closed(raw: str) -> None:
    with pytest.raises(ValueError, match="PORT must be a whole number"):
        resolve_port({"PORT": raw})


class TestDatabaseUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "postgres://holly@db.example:5432/holly",
            "postgresql://holly@db.example:5432/holly",
            "postgresql+asyncpg://holly@db.example:5432/holly",
            "POSTGRES://holly@db.example:5432/holly",
        ],
    )
    def test_every_postgres_scheme_becomes_asyncpg(self, url: str) -> None:
        assert asyncpg_url(url) == "postgresql+asyncpg://holly@db.example:5432/holly"

    @pytest.mark.parametrize(
        "url",
        ["mysql://holly@db.example/holly", "db.example/holly", "postgresql:///holly", ""],
    )
    def test_anything_else_fails_closed(self, url: str) -> None:
        with pytest.raises(ValueError, match="DATABASE_URL must be a postgres"):
            asyncpg_url(url)

    def test_the_message_never_repeats_the_url(self) -> None:
        with pytest.raises(ValueError, match="DATABASE_URL") as raised:
            asyncpg_url("mysql://holly:pw-in-url@db.example/holly")
        assert "pw-in-url" not in str(raised.value)


@pytest.fixture
def build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Callable[..., Settings]:
    """Settings from the test environment plus overrides. The working directory moves to an
    empty one, so a developer's local .env file is never read."""
    monkeypatch.chdir(tmp_path)

    def make(**overrides: Any) -> Settings:
        if any(name.startswith("postgres_") for name in overrides):
            monkeypatch.delenv("DATABASE_URL", raising=False)
        return Settings(**overrides)

    return make


Build = Callable[..., Settings]


class TestSettingsFailClosed:
    def test_the_test_environment_is_valid(self, build: Build) -> None:
        assert build().app_env == "production"

    @pytest.mark.parametrize(
        ("overrides", "problem"),
        [
            ({"app_secret_key": SecretStr("s" * 31)}, "APP_SECRET_KEY must be at least 32"),
            ({"app_allowed_origins": ["*"]}, r"never the \* wildcard"),
            ({"udl_base_url": "http://udl.example"}, "UDL_BASE_URL must use https"),
            ({"mattermost_url": "http://chat.example"}, "MATTERMOST_URL must use https"),
            ({"udl_verify_ssl": False}, "UDL_VERIFY_SSL may be false only in development"),
            ({"procedure_storage_path": "relative/dir"}, "must be absolute and not the root"),
            ({"procedure_storage_path": "/"}, "must be absolute and not the root"),
            ({"database_url": "mysql://db.example/holly"}, "DATABASE_URL must be a postgres"),
        ],
    )
    def test_each_unsafe_setting_stops_the_boot(
        self, build: Build, overrides: dict[str, Any], problem: str
    ) -> None:
        with pytest.raises(ValidationError, match=problem):
            build(**overrides)

    def test_every_problem_is_reported_at_once(self, build: Build) -> None:
        with pytest.raises(ValidationError) as raised:
            build(app_secret_key=SecretStr("short"), udl_verify_ssl=False)
        assert "APP_SECRET_KEY" in str(raised.value)
        assert "UDL_VERIFY_SSL" in str(raised.value)

    def test_development_allows_plain_http_and_unverified_tls(self, build: Build) -> None:
        settings = build(
            app_env="development",
            udl_base_url="http://localhost:9000",
            mattermost_url="http://localhost:8065",
            udl_verify_ssl=False,
        )
        assert settings.udl_verify_ssl is False

    def test_no_database_settings_stops_the_boot(
        self, build: Build, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DATABASE_URL")
        with pytest.raises(ValidationError, match="set DATABASE_URL, or POSTGRES_HOST"):
            build()

    def test_the_postgres_parts_need_a_password(self, build: Build) -> None:
        with pytest.raises(ValidationError, match="POSTGRES_PASSWORD is required"):
            build(postgres_host="db", postgres_db="holly", postgres_user="holly")


class TestResolvedValues:
    def test_the_url_is_built_from_the_parts_with_each_part_quoted(self, build: Build) -> None:
        settings = build(
            postgres_host="db.example",
            postgres_port=6543,
            postgres_db="holly",
            postgres_user="ops@holly",
            postgres_password=SecretStr("p%w:d/@"),
        )
        assert settings.sqlalchemy_url() == (
            "postgresql+asyncpg://ops%40holly:p%25w%3Ad%2F%40@db.example:6543/holly"
        )

    def test_database_url_wins_over_the_parts(
        self, build: Build, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("POSTGRES_HOST", "ignored.example")
        assert build().sqlalchemy_url() == "postgresql+asyncpg://holly@db.invalid:5432/holly_test"

    @pytest.mark.parametrize(
        ("explicit", "mount", "expected"),
        [
            ("/srv/procedures", "/data", "/srv/procedures"),
            (None, "/mnt/store", "/mnt/store/procedures"),
            (None, None, "/data/procedures"),
        ],
    )
    def test_the_procedure_store_is_explicit_then_injected_then_default(
        self,
        build: Build,
        monkeypatch: pytest.MonkeyPatch,
        explicit: str | None,
        mount: str | None,
        expected: str,
    ) -> None:
        monkeypatch.delenv("PROCEDURE_STORAGE_PATH")
        settings = build(procedure_storage_path=explicit, storage_mount_path=mount)
        assert str(settings.procedure_dir()) == expected

    def test_get_settings_reads_once_and_caches(self) -> None:
        assert get_settings() is get_settings()
