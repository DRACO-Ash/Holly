"""Configuration: PORT resolution, then the settings Holly validates at boot. Each unsafe or
incomplete setting stops the container with a clear message (fail closed).

Expected values are literals, never the module's own constants, so a changed bound fails here.
"""

import runpy
import string
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

import pytest
import sqlalchemy.ext.asyncio
from pydantic import SecretStr, ValidationError
from sqlalchemy.engine import URL

from app.config import InvalidSettingsError, Settings, asyncpg_url, get_settings, resolve_port
from app.factory import create_app

# Non-ASCII digits, built from code points so the source stays plain ASCII.
# str.isdigit() is true for both, so the ASCII check is what must refuse them.
FULL_WIDTH_8080 = "".join(chr(code) for code in (0xFF18, 0xFF10, 0xFF18, 0xFF10))
SUPERSCRIPT_TWO = chr(0x00B2)
# NFKC normalisation turns it into @: Python's URL parser once refused a netloc holding it and
# quoted the netloc, password included. SQLAlchemy's parser keeps it as part of the password.
FULL_WIDTH_AT = chr(0xFF20)
FULL_WIDTH_CREDENTIAL = f"Zq7x{FULL_WIDTH_AT}SYNTHpw9X"
# An unencoded @ in a password: SQLAlchemy reads the end of the password as the host.
REFUSED_CREDENTIAL = "Zq7x@SYNTHpw9X"


def fragments_in(text: str, *secrets: str) -> list[str]:
    """Each five-character piece of the secrets that appears in `text`."""
    pieces = {secret[start : start + 5] for secret in secrets for start in range(len(secret) - 4)}
    return sorted(piece for piece in pieces if piece in text)


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
        rendered = asyncpg_url(url).render_as_string(hide_password=False)
        assert rendered == "postgresql+asyncpg://holly@db.example:5432/holly"

    @pytest.mark.parametrize(
        "url",
        [
            "mysql://holly@db.example/holly",
            "db.example/holly",
            "postgresql:///holly",
            "",
            "postgresql://holly@db.example:0/holly",
            "postgresql://holly@db.example:65536/holly",
            "postgresql://holly@db.example:port/holly",
            "postgresql://holly@db example/holly",
            "postgresql://holly@[db:5432]/holly",
            "postgresql://holly:Kx7p@SYNTHqW/m2v9@pg:5432/holly",
        ],
    )
    def test_anything_else_fails_closed(self, url: str) -> None:
        with pytest.raises(ValueError, match="DATABASE_URL must be a postgres"):
            asyncpg_url(url)

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("?sslmode=require", {"ssl": "require"}),
            (
                "?sslmode=verify-full&connect_timeout=10",
                {"ssl": "verify-full", "connect_timeout": "10"},
            ),
            ("?ssl=require", {"ssl": "require"}),
            ("?ssl=disable&sslmode=require", {"ssl": "disable"}),
            ("?sslmode=disable&sslmode=require", {"ssl": "require"}),
            ("", {}),
        ],
    )
    def test_libpq_sslmode_becomes_asyncpg_ssl(self, query: str, expected: dict[str, str]) -> None:
        url = asyncpg_url(f"postgres://holly:p%40ss@db.example:5432/holly{query}")
        assert (url.drivername, url.username, url.password) == (
            "postgresql+asyncpg",
            "holly",
            "p@ss",
        )
        assert (url.host, url.port, url.database) == ("db.example", 5432, "holly")
        assert dict(url.query) == expected

    @pytest.mark.parametrize("host", ["db.example", "holly_db", "10.0.0.7", "::1", "fd00::5"])
    def test_a_host_name_or_any_ip_address_is_a_host(self, host: str) -> None:
        bracketed = f"[{host}]" if ":" in host else host
        assert asyncpg_url(f"postgresql://holly@{bracketed}:5432/holly").host == host

    def test_the_message_never_repeats_the_url(self) -> None:
        with pytest.raises(ValueError, match="DATABASE_URL") as raised:
            asyncpg_url("mysql://holly:pw-in-url@db.example/holly")
        assert "pw-in-url" not in str(raised.value)

    def test_a_password_holding_a_full_width_at_is_kept_exactly(self) -> None:
        url = asyncpg_url(f"postgresql://holly:{FULL_WIDTH_CREDENTIAL}@pg:5432/holly")
        assert (url.password, url.host, url.database) == (FULL_WIDTH_CREDENTIAL, "pg", "holly")

    def test_a_url_read_with_part_of_its_password_as_host_is_refused_without_repeating_it(
        self,
    ) -> None:
        url = f"postgresql://holly:{REFUSED_CREDENTIAL}@pg:5432/holly"
        with pytest.raises(ValueError, match="DATABASE_URL must be a postgres") as raised:
            asyncpg_url(url)
        assert raised.value.__context__ is None, "no error of the parser's is chained"
        assert (
            fragments_in("".join(traceback.format_exception(raised.value)), REFUSED_CREDENTIAL)
            == []
        )


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

    def test_a_service_name_with_an_underscore_is_a_host(self, build: Build) -> None:
        settings = build(
            postgres_host="holly_db",
            postgres_db="holly",
            postgres_user="holly",
            postgres_password=SecretStr("unused-in-tests"),
        )
        assert settings.sqlalchemy_url().host == "holly_db"

    @pytest.mark.parametrize(
        ("part", "problem"),
        [
            ({"postgres_host": "db/holly"}, "POSTGRES_HOST must be a host name or an IP address"),
            ({"postgres_host": "user@db"}, "POSTGRES_HOST must be a host name or an IP address"),
            ({"postgres_host": "db:5432"}, "POSTGRES_HOST must be a host name or an IP address"),
            ({"postgres_host": "fe80::1::2"}, "POSTGRES_HOST must be a host name or an IP address"),
        ],
    )
    def test_each_postgres_part_must_be_what_it_says(
        self, build: Build, part: dict[str, Any], problem: str
    ) -> None:
        parts = {
            "postgres_host": "db",
            "postgres_db": "holly",
            "postgres_user": "holly",
            "postgres_password": SecretStr("unused-in-tests"),
        }
        with pytest.raises(ValidationError, match=problem):
            build(**(parts | part))


class TestResolvedValues:
    def test_the_url_is_built_from_the_parts_with_each_part_quoted(self, build: Build) -> None:
        settings = build(
            postgres_host="db.example",
            postgres_port=6543,
            postgres_db="holly",
            postgres_user="ops@holly",
            postgres_password=SecretStr("p%w:d/@"),
        )
        url = settings.sqlalchemy_url()
        assert (url.username, url.password) == ("ops@holly", "p%w:d/@")
        assert (url.host, url.port, url.database) == ("db.example", 6543, "holly")
        assert url.render_as_string(hide_password=False) == (
            "postgresql+asyncpg://ops%40holly:p%25w%3Ad%2F%40@db.example:6543/holly"
        )
        assert "p%25w" not in str(url), "printing the URL masks the password"

    def test_database_url_wins_over_the_parts(
        self, build: Build, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("POSTGRES_HOST", "ignored.example")
        rendered = build().sqlalchemy_url().render_as_string(hide_password=False)
        assert rendered == "postgresql+asyncpg://holly@db.invalid:5432/holly_test"

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


class TestABadEnvironmentStopsTheBootClearly:
    """get_settings() runs first in the gunicorn master, where the migrations need the database
    settings. A failure there must name the variable and repeat no value."""

    CONNECTION_URL = "postgresql://holly:unused-in-tests@db.invalid:5432/holly"

    @pytest.fixture(autouse=True)
    def _empty_cwd(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("DATABASE_URL", self.CONNECTION_URL)
        get_settings.cache_clear()

    def refused(self) -> InvalidSettingsError:
        with pytest.raises(InvalidSettingsError) as raised:
            get_settings()
        error = raised.value
        assert error.__cause__ is None
        assert error.__suppress_context__, "the pydantic error, with its input, is dropped"
        printed = "".join(traceback.format_exception(error))
        assert "unused-in-tests" not in printed
        assert "db.invalid" not in printed
        return error

    def refusal(self) -> str:
        return str(self.refused())

    def test_a_missing_variable_is_named(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("APP_SECRET_KEY")
        assert self.refusal() == "Holly cannot start: APP_SECRET_KEY: Field required"

    def test_an_unsafe_value_is_named_without_repeating_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_SECRET_KEY", "k" * 31)
        message = self.refusal()
        assert message.startswith("Holly cannot start: APP_SECRET_KEY must be at least 32")
        assert "k" * 31 not in message

    def test_a_value_that_cannot_be_parsed_is_named(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ALLOWED_ORIGINS", "not-a-json-list")
        message = self.refusal()
        assert message.startswith("Holly cannot start: ")
        assert "app_allowed_origins" in message
        assert "not-a-json-list" not in message

    def test_a_value_of_the_wrong_type_is_named(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POSTGRES_PORT", "abc")
        assert self.refusal().startswith(
            "Holly cannot start: POSTGRES_PORT: Input should be a valid integer"
        )

    @pytest.mark.parametrize(
        ("problem", "named"),
        [
            ({"POSTGRES_PORT": "abc"}, "POSTGRES_PORT: Input should be a valid integer"),
            ({"UDL_BASE_URL": "http://udl.example"}, "UDL_BASE_URL must use https"),
            (
                {"DATABASE_URL": f"postgresql://holly:{REFUSED_CREDENTIAL}@pg:5432/holly"},
                "DATABASE_URL must be a postgres",
            ),
        ],
        ids=[
            "a field of the wrong type",
            "a setting the boot check refuses",
            "a URL the parser refuses",
        ],
    )
    def test_no_fragment_of_any_secret_reaches_the_message(
        self, monkeypatch: pytest.MonkeyPatch, problem: dict[str, str], named: str
    ) -> None:
        # Synthetic secrets, each distinctive, set beside one problem on each error path. Only
        # the credential in the URL is scanned for: its scheme, host and database name are not
        # secret, and a printed file path may well hold them.
        url_credential = "Zq7xSYNTHETICpw9X"
        secrets = {
            "APP_SECRET_KEY": "SYNTHk3yQm8vXr2nWz6pLb9sYc4jFd7gNa5u",
            "ANTHROPIC_API_KEY": "SYNTHapiRt5wKp8zMx2nQv7cJh4b",
            "UDL_PASSWORD": "SYNTHudlUb7kWe3rPz9m",
            "MATTERMOST_BOT_TOKEN": "SYNTHbotMb4tNc8xQr2w",
        }
        environment = secrets | {
            "DATABASE_URL": f"postgresql://holly:{url_credential}@pg:5432/holly"
        }
        for name, value in (environment | problem).items():
            monkeypatch.setenv(name, value)
        error = self.refused()
        assert named in str(error)
        printed = "".join(traceback.format_exception(error))
        assert fragments_in(printed, url_credential, REFUSED_CREDENTIAL, *secrets.values()) == []

    def test_a_service_url_the_parser_refuses_is_named_without_repeating_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Python's URL parser refuses this netloc and quotes it, credentials included.
        monkeypatch.setenv("UDL_BASE_URL", f"https://ops:{FULL_WIDTH_CREDENTIAL}@udl.example/udl")
        error = self.refused()
        assert str(error) == "Holly cannot start: UDL_BASE_URL must use https outside development"
        assert fragments_in("".join(traceback.format_exception(error)), FULL_WIDTH_CREDENTIAL) == []

    def test_the_worker_refuses_as_the_master_does(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("APP_SECRET_KEY")
        with pytest.raises(InvalidSettingsError, match="APP_SECRET_KEY: Field required"):
            create_app()

    def test_the_master_refuses_before_any_migration_connects(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The real gunicorn hook and the real Alembic environment, up to the settings read that
        # precedes the database connection.
        monkeypatch.delenv("APP_SECRET_KEY")
        on_starting = runpy.run_module("app.gunicorn_conf")["on_starting"]
        monkeypatch.setitem(on_starting.__globals__, "configure_logging", lambda: None)
        with pytest.raises(InvalidSettingsError, match="APP_SECRET_KEY: Field required"):
            on_starting(object())

    def test_gunicorn_prints_the_refusal_as_one_line(self) -> None:
        # gunicorn's BaseApplication.run catches RuntimeError around the master's start, where
        # on_starting runs the migrations, and prints "Error: <message>" with no traceback.
        assert issubclass(InvalidSettingsError, RuntimeError)


class _StoppedBeforeConnectingError(Exception):
    """Raised in place of the engine, so the master's migration run ends before any network."""


# Every printable punctuation character, unencoded, inside a synthetic password.
PUNCTUATED = {mark: f"Kx7p{mark}SYNTHqWm2" for mark in string.punctuation}


class TestEveryPasswordCharacterReachesTheEngineExactly:
    """A provider may inject a DATABASE_URL whose password is not percent-encoded. The master's
    real start-up hook and the real Alembic environment run up to the engine, which is replaced
    by a recorder. Each character but @ reaches the engine exactly; @ stops the boot with the
    fixed message. Nothing printed on the way holds any piece of the password."""

    @pytest.fixture(autouse=True)
    def _empty_cwd(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.chdir(tmp_path)
        get_settings.cache_clear()

    def start_master(self, monkeypatch: pytest.MonkeyPatch, secret: str, handed: list[URL]) -> None:
        monkeypatch.setenv(
            "DATABASE_URL", f"postgresql://holly:{secret}@pg:5432/holly?sslmode=require"
        )

        def recorder(_configuration: object, prefix: str, **kwargs: Any) -> NoReturn:
            assert prefix == "sqlalchemy."
            handed.append(kwargs["url"])
            raise _StoppedBeforeConnectingError

        # env.py imports the factory when Alembic loads it, so it picks up the recorder.
        monkeypatch.setattr(sqlalchemy.ext.asyncio, "async_engine_from_config", recorder)
        on_starting = runpy.run_module("app.gunicorn_conf")["on_starting"]
        monkeypatch.setitem(on_starting.__globals__, "configure_logging", lambda: None)
        on_starting(object())

    @pytest.mark.parametrize(
        "mark", [mark for mark in PUNCTUATED if mark != "@"], ids=lambda mark: f"U+{ord(mark):04X}"
    )
    def test_the_password_reaches_the_engine_exactly(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], mark: str
    ) -> None:
        secret = PUNCTUATED[mark]
        handed: list[URL] = []
        with pytest.raises(_StoppedBeforeConnectingError) as raised:
            self.start_master(monkeypatch, secret, handed)
        [url] = handed
        assert (url.drivername, url.username, url.password) == (
            "postgresql+asyncpg",
            "holly",
            secret,
        )
        assert (url.host, url.port, url.database, dict(url.query)) == (
            "pg",
            5432,
            "holly",
            {"ssl": "require"},
        )
        printed = capsys.readouterr().out + "".join(traceback.format_exception(raised.value))
        assert fragments_in(printed, secret) == []

    @pytest.mark.parametrize(
        "secret",
        # Alone, SQLAlchemy reads the rest as a host it refuses; followed by / or ?, it would
        # read a plain host name out of the password and look it up.
        [PUNCTUATED["@"], "Kx7p@SYNTHqW/m2v9", "Kx7p@SYNTHqW?m2v9"],
        ids=["at", "at-then-slash", "at-then-question-mark"],
    )
    def test_an_unencoded_at_stops_the_boot_with_the_fixed_message(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], secret: str
    ) -> None:
        handed: list[URL] = []
        with pytest.raises(InvalidSettingsError) as raised:
            self.start_master(monkeypatch, secret, handed)
        assert str(raised.value) == (
            "Holly cannot start: "
            "DATABASE_URL must be a postgres:// or postgresql:// URL with a host"
        )
        assert handed == [], "no engine was made"
        assert raised.value.__cause__ is None
        printed = capsys.readouterr().out + "".join(traceback.format_exception(raised.value))
        assert fragments_in(printed, secret) == []
