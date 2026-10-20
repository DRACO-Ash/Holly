"""Runtime configuration, read from the environment only and validated at the boundary.

Two layers. resolve_port reads PORT on its own, so the gunicorn configuration and the
development server can bind without loading anything else. Settings holds everything the
application needs; get_settings() reads it once, when the application first asks, and the
validators stop a misconfigured container at boot with a clear message rather than letting it
fail later or run insecurely (security-hardening, fail closed).
"""

import ipaddress
import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, SettingsError
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

DEFAULT_PORT = 8080
MAX_PORT = 65535
_MAX_PORT_DIGITS = len(str(MAX_PORT))

MIN_SECRET_KEY_LENGTH = 32
DEFAULT_PROCEDURE_DIR = "/data/procedures"
ASYNCPG_SCHEME = "postgresql+asyncpg"
_POSTGRES_SCHEMES = frozenset({"postgres", "postgresql", ASYNCPG_SCHEME})


def resolve_port(environ: Mapping[str, str]) -> int:
    """Return the port to listen on: PORT when set, otherwise 8080 (the App Store contract).

    PORT must be a canonical whole number from 1 to 65535: ASCII digits only, no sign and no
    leading zero. Surrounding whitespace is ignored. Anything else fails closed with a clear
    message instead of falling back quietly, because a silent fallback would listen on a port
    the platform is not probing.
    """
    raw = environ.get("PORT", "").strip()
    if not raw:
        return DEFAULT_PORT
    if (
        raw.isascii()
        and raw.isdigit()
        and not raw.startswith("0")
        and len(raw) <= _MAX_PORT_DIGITS
        and int(raw) <= MAX_PORT
    ):
        return int(raw)
    msg = f"PORT must be a whole number from 1 to {MAX_PORT}, got {raw[:16]!r}"
    raise ValueError(msg)


_BAD_DATABASE_URL = "DATABASE_URL must be a postgres:// or postgresql:// URL with a host"
# A host name or an IPv4 address; an IPv6 address is checked by the ipaddress module. The
# underscore is allowed because container platforms name services with it, as in holly_db.
_HOST_NAME = re.compile(r"[A-Za-z0-9._\-]+")


def _is_host(host: str | None) -> bool:
    """A host name or an IP address. Anything else means the URL does not read as its author
    meant, as when an unencoded @ in the password moves the end of the password into the host."""
    if host is None or _HOST_NAME.fullmatch(host):
        return host is not None
    try:
        ipaddress.IPv6Address(host)
    except ValueError:
        return False
    return True


def asyncpg_url(url: str) -> URL:
    """The connection URL with the asyncpg driver, whichever postgres scheme it arrived with.

    The App Store POSTGRESQL add-on injects a connection URL; its exact scheme is not confirmed,
    so postgres://, postgresql:// and postgresql+asyncpg:// are all accepted. SQLAlchemy's own
    parser reads it once, and the parsed URL is what connects, so the check and the connection
    cannot read it differently. Anything else fails closed. The URL carries a password, so no
    message ever repeats it.
    """
    parsed = _postgres_url(url)
    if parsed is None:
        raise ValueError(_BAD_DATABASE_URL)
    return _with_asyncpg_ssl(parsed.set(drivername=ASYNCPG_SCHEME))


def _postgres_url(url: str) -> URL | None:
    # A second @ is inside the password, unencoded. SQLAlchemy could read part of the password
    # as a plain host name, which the connection would then look up in DNS.
    if url.count("@") > 1:
        return None
    try:
        parsed = make_url(url)
    except (ArgumentError, ValueError, TypeError):
        # Each of the parser's errors quotes the URL, or the part of it that would not parse.
        return None
    port_ok = parsed.port is None or 0 < parsed.port <= MAX_PORT
    postgres = parsed.drivername.lower() in _POSTGRES_SCHEMES
    return parsed if postgres and _is_host(parsed.host) and port_ok else None


def _with_asyncpg_ssl(url: URL) -> URL:
    """libpq's sslmode renamed to asyncpg's ssl, which takes the same values. SQLAlchemy hands
    every query parameter to asyncpg, which has no sslmode and would refuse the first
    connection. An ssl parameter already present wins."""
    if "sslmode" not in url.query:
        return url
    given = url.query["sslmode"]
    # Given more than once, libpq takes the last value.
    sslmode = given if isinstance(given, str) else given[-1]
    url = url.difference_update_query(["sslmode"])
    return url if "ssl" in url.query else url.update_query_dict({"ssl": sslmode})


def _https_problem(name: str, value: str) -> str | None:
    try:
        scheme = urlsplit(value).scheme
    except ValueError:
        # The parser's own message quotes the URL's host part, which may carry credentials.
        scheme = ""
    if value and scheme != "https":
        return f"{name} must use https outside development"
    return None


class Settings(BaseSettings):
    """Every setting Holly reads. Each field is read from the environment variable of the
    same name in upper case (APP_SECRET_KEY for app_secret_key), or from a local .env file in
    development. Secrets are SecretStr, so they never appear in a repr or a log line.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "production"] = "production"
    # Set to true by the App Store when its DAST scan starts the container with none of Holly's
    # settings (app/dast_scan.py). Only then may the database settings be absent.
    appstore_dast_scan: bool = False
    app_secret_key: SecretStr
    # Browser origins allowed to call the API cross-origin. Empty by default: the dashboard is
    # served from the same origin, so no cross-origin access is needed.
    app_allowed_origins: list[str] = Field(default_factory=list)

    # PostgreSQL: DATABASE_URL (the App Store POSTGRESQL add-on), or the POSTGRES_* parts.
    database_url: SecretStr | None = None
    postgres_host: str | None = None
    postgres_port: int = Field(default=5432, ge=1, le=MAX_PORT)
    postgres_db: str | None = None
    postgres_user: str | None = None
    postgres_password: SecretStr | None = None

    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=30, ge=1, le=24 * 60)
    jwt_refresh_token_expire_days: int = Field(default=7, ge=1, le=90)

    mattermost_url: str = ""
    mattermost_bot_token: SecretStr = SecretStr("")
    # Comma-separated Mattermost channel ids to poll. Channels the bot account is not a member
    # of are skipped (Mattermost answers 403).
    mattermost_channel_ids: str = ""
    mattermost_interval_seconds: int = Field(default=60, ge=10)
    mattermost_prompt_window_hours: int = Field(default=6, ge=0)
    mattermost_max_messages_in_prompt: int = Field(default=30, ge=0)

    udl_base_url: str = "https://unifieddatalibrary.com/udl"
    udl_username: str = ""
    udl_password: SecretStr = SecretStr("")
    udl_request_timeout_seconds: int = Field(default=30, ge=1, le=300)
    udl_verify_ssl: bool = True

    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_max_tokens: int = Field(default=4096, ge=256, le=16000)
    # Hard cap on assistant tokens (input plus output) per UTC day, across every caller. Once
    # it is reached, every assistant call fails closed until the next UTC day.
    llm_daily_token_cap: int = Field(default=2_000_000, ge=0)
    # The UDL classification markings whose notifications may be sent to the assistant, matched
    # exactly as UDL writes them. A notice with any other marking, or none, never leaves Holly.
    # Clearing a further marking is the data owner's decision; until then only U is cleared.
    assistant_cleared_markings: list[str] = Field(default_factory=lambda: ["U"])

    # Where uploaded procedures are stored: PROCEDURE_STORAGE_PATH when set, otherwise the
    # FILE_STORAGE add-on's STORAGE_MOUNT_PATH plus /procedures, otherwise /data/procedures.
    procedure_storage_path: str | None = None
    storage_mount_path: str | None = None

    background_refresh_enabled: bool = True
    background_auto_evaluate: bool = True
    background_max_evaluations_per_cycle: int = Field(default=20, ge=0)
    background_max_event_summaries_per_cycle: int = Field(default=20, ge=0)
    # Per-surface cadences. Notifications change slowly and want a wide picture (5 days), so
    # they refresh hourly. Maneuvers are time-critical and refresh every 10 minutes.
    background_notification_interval_seconds: int = Field(default=3600, ge=60)
    background_notification_window_hours: int = Field(default=120, ge=1)
    background_maneuver_interval_seconds: int = Field(default=600, ge=60)
    background_maneuver_window_hours: int = Field(default=48, ge=1)

    @field_validator(
        "database_url",
        "postgres_host",
        "postgres_db",
        "postgres_user",
        "postgres_password",
        mode="before",
    )
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        # A database variable set to nothing reads as unset, everywhere: outside the DAST scan
        # it is refused as missing, and under the scan it does not stop a start with no database.
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def _fail_closed(self) -> Self:
        problems = [
            *self._secret_problems(),
            *([] if self._scan_without_database() else self._database_problems()),
            *self._transport_problems(),
            *self._storage_problems(),
        ]
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def _secret_problems(self) -> list[str]:
        problems = []
        key = self.app_secret_key.get_secret_value()
        if len(key) < MIN_SECRET_KEY_LENGTH:
            problems.append(f"APP_SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters")
        elif not key.strip():
            problems.append("APP_SECRET_KEY must not be blank")
        if "*" in self.app_allowed_origins:
            problems.append("APP_ALLOWED_ORIGINS must list origins, never the * wildcard")
        return problems

    def has_database(self) -> bool:
        """Whether database settings are present; the validator holds them complete if so."""
        return self.database_url is not None or self.postgres_host is not None

    def _scan_without_database(self) -> bool:
        """The DAST scan gives the container no settings: then, and only then, Holly serves
        without a database, and each request that needs one answers 503
        (DatabaseNotConfiguredError). Half a set of database settings is still refused."""
        no_database_setting = self.database_url is None and all(
            value is None
            for value in (
                self.postgres_host,
                self.postgres_db,
                self.postgres_user,
                self.postgres_password,
            )
        )
        return self.appstore_dast_scan and no_database_setting

    def _database_problems(self) -> list[str]:
        if self.database_url is not None:
            try:
                asyncpg_url(self.database_url.get_secret_value())
            except ValueError:
                # The fixed message, never the error's own text, which could quote the URL.
                return [_BAD_DATABASE_URL]
            return []
        if None in (self.postgres_host, self.postgres_db, self.postgres_user):
            return [
                "set DATABASE_URL, or POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER and "
                "POSTGRES_PASSWORD"
            ]
        if self.postgres_password is None:
            return ["POSTGRES_PASSWORD is required with the POSTGRES_* settings"]
        if not _is_host(self.postgres_host):
            return ["POSTGRES_HOST must be a host name or an IP address"]
        return []

    def _transport_problems(self) -> list[str]:
        if self.app_env == "development":
            return []
        problems = [
            _https_problem("UDL_BASE_URL", self.udl_base_url),
            _https_problem("MATTERMOST_URL", self.mattermost_url),
        ]
        if not self.udl_verify_ssl:
            problems.append("UDL_VERIFY_SSL may be false only in development")
        return [problem for problem in problems if problem]

    def _storage_problems(self) -> list[str]:
        path = self.procedure_dir()
        if not path.is_absolute() or path == PurePosixPath(path.anchor):
            return [f"the procedure storage path must be absolute and not the root, got {path}"]
        return []

    def procedure_dir(self) -> PurePosixPath:
        """The directory for uploaded procedures, resolved explicit, then injected, then default."""
        if self.procedure_storage_path:
            return PurePosixPath(self.procedure_storage_path)
        if self.storage_mount_path:
            return PurePosixPath(self.storage_mount_path) / "procedures"
        return PurePosixPath(DEFAULT_PROCEDURE_DIR)

    def sqlalchemy_url(self) -> URL:
        """The asyncpg connection URL, parsed once and handed to the engine as it is. It carries
        the password: SQLAlchemy masks it when the URL is printed, so never render it otherwise."""
        if not self.has_database():
            raise DatabaseNotConfiguredError
        if self.database_url is not None:
            return asyncpg_url(self.database_url.get_secret_value())
        # The validator guarantees every part is present when DATABASE_URL is unset. Built from
        # its parts, the URL is never parsed, so no character in them can change its meaning.
        password = self.postgres_password.get_secret_value() if self.postgres_password else None
        return URL.create(
            ASYNCPG_SCHEME,
            username=self.postgres_user,
            password=password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


class DatabaseNotConfiguredError(RuntimeError):
    """Holly runs without a database, as it does only in the App Store's DAST scan."""

    def __init__(self) -> None:
        super().__init__("Holly has no database in this DAST scan")


class InvalidSettingsError(RuntimeError):
    """Holly's settings are missing or unsafe. It is a RuntimeError because gunicorn prints a
    RuntimeError raised at start as one line and exits 1, with no traceback. The message names
    each variable at fault and never repeats a value: pydantic's own message echoes the raw
    input, which can hold part of a password."""


def _problems(exc: ValidationError) -> str:
    problems = []
    for error in exc.errors():
        message = error["msg"].removeprefix("Value error, ")
        location = error["loc"]
        problems.append(f"{str(location[0]).upper()}: {message}" if location else message)
    return "; ".join(problems)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The validated settings, read from the environment once per process. Settings that fail
    validation stop the process with InvalidSettingsError."""
    try:
        return Settings()  # type: ignore[call-arg]  # pydantic-settings fills the fields from the environment
    except ValidationError as exc:
        msg = f"Holly cannot start: {_problems(exc)}"
        raise InvalidSettingsError(msg) from None
    except SettingsError as exc:
        # A value that could not be parsed at all, such as origins that are not a JSON list.
        msg = f"Holly cannot start: {exc}"
        raise InvalidSettingsError(msg) from None
