"""The App Store's DAST scan starts the container with none of Holly's settings
(app/dast_scan.py): under its flag alone, Holly fills in a throwaway signing key, a temporary
store and no background pulls, logs what it set but never a value, and serves without a
database, each request that needs one answering 503."""

import json
import os
import stat
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import dast_scan
from app.config import MIN_SECRET_KEY_LENGTH, get_settings
from app.factory import create_app


def logged(captured: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in captured.splitlines() if line.startswith("{")]


@pytest.mark.parametrize("value", [None, "false", "0", "no", "maybe", ""])
def test_without_the_flag_nothing_changes(
    value: str | None, capsys: pytest.CaptureFixture[str]
) -> None:
    env = {} if value is None else {"APPSTORE_DAST_SCAN": value}
    before = dict(env)
    assert dast_scan.prepare_scan_environment(env) is False
    assert env == before
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("APPSTORE_DAST_SCAN", "true"),
        ("APPSTORE_DAST_SCAN", "True"),
        ("APPSTORE_DAST_SCAN", "1"),
        ("APPSTORE_DAST_SCAN", "yes"),
        # The settings read a name in any letter case, so the scan step does too.
        ("appstore_dast_scan", "true"),
    ],
)
def test_the_flag_fills_in_what_the_scan_leaves_out(
    name: str, value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    env = {name: value}
    assert dast_scan.prepare_scan_environment(env) is True
    assert len(env["APP_SECRET_KEY"]) >= MIN_SECRET_KEY_LENGTH
    assert env["BACKGROUND_REFRESH_ENABLED"] == "false"
    store = Path(env["PROCEDURE_STORAGE_PATH"])
    assert store.is_absolute()
    assert os.access(store, os.W_OK)
    # Private to Holly's own user.
    assert stat.S_IMODE(store.stat().st_mode) == 0o700
    captured = capsys.readouterr().out
    [line] = logged(captured)
    assert line["event"] == "dast_scan"
    assert line["status"] == "active"
    assert line["generated_secret_key"] is True
    assert line["temporary_store"] is True
    assert line["database"] is False
    # The key is never logged.
    assert env["APP_SECRET_KEY"] not in captured


def test_what_is_set_is_kept_and_the_background_pulls_stay_off(
    capsys: pytest.CaptureFixture[str],
) -> None:
    env = {
        "APPSTORE_DAST_SCAN": "true",
        "APP_SECRET_KEY": "k" * 40,
        "STORAGE_MOUNT_PATH": "/data",
        "DATABASE_URL": "postgresql://scan@db.invalid/scan",
        "BACKGROUND_REFRESH_ENABLED": "true",
    }
    assert dast_scan.prepare_scan_environment(env) is True
    assert env["APP_SECRET_KEY"] == "k" * 40
    assert "PROCEDURE_STORAGE_PATH" not in env
    assert env["BACKGROUND_REFRESH_ENABLED"] == "false"
    [line] = logged(capsys.readouterr().out)
    assert (line["generated_secret_key"], line["temporary_store"], line["database"]) == (
        False,
        False,
        True,
    )


def test_two_containers_get_different_keys_and_stores() -> None:
    first: dict[str, str] = {"APPSTORE_DAST_SCAN": "true"}
    second = dict(first)
    dast_scan.prepare_scan_environment(first)
    dast_scan.prepare_scan_environment(second)
    assert first["APP_SECRET_KEY"] != second["APP_SECRET_KEY"]
    assert first["PROCEDURE_STORAGE_PATH"] != second["PROCEDURE_STORAGE_PATH"]


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_key_is_replaced(blank: str) -> None:
    env = {"APPSTORE_DAST_SCAN": "true", "APP_SECRET_KEY": blank, "STORAGE_MOUNT_PATH": "/data"}
    dast_scan.prepare_scan_environment(env)
    assert len(env["APP_SECRET_KEY"].strip()) >= MIN_SECRET_KEY_LENGTH


@pytest.mark.parametrize(
    ("database", "logged_as"),
    [
        ({"POSTGRES_HOST": "db.invalid"}, True),
        ({"DATABASE_URL": ""}, False),
        ({"DATABASE_URL": "   "}, False),
    ],
)
def test_the_log_says_whether_a_database_was_given(
    database: dict[str, str], logged_as: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    env = {"APPSTORE_DAST_SCAN": "true", "STORAGE_MOUNT_PATH": "/data", **database}
    dast_scan.prepare_scan_environment(env)
    [line] = logged(capsys.readouterr().out)
    assert line["database"] is logged_as


@pytest.fixture(autouse=True)
def _temporary_stores_in_tmp_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The scan step's temporary stores land under the test's own directory, not the host's /tmp.
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))


@pytest.fixture
def scan_without_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[TestClient]:
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.delenv("APP_SECRET_KEY")
    monkeypatch.setenv("APPSTORE_DAST_SCAN", "true")
    dast_scan.prepare_scan_environment(os.environ)
    monkeypatch.setenv("PROCEDURE_STORAGE_PATH", str(tmp_path / "procedures"))
    get_settings.cache_clear()
    with TestClient(create_app(static_dir=tmp_path / "not-built")) as client:
        yield client


@pytest.mark.parametrize("path", ["/", "/healthz", "/readyz", "/livez", "/ping", "/status"])
def test_with_no_database_the_probes_and_status_answer(
    scan_without_database: TestClient, path: str
) -> None:
    assert scan_without_database.get(path).status_code == 200


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/api/v1/health"), ("GET", "/api/v1/health/detailed")],
)
def test_with_no_database_a_request_that_needs_one_answers_503(
    scan_without_database: TestClient, method: str, path: str
) -> None:
    response = scan_without_database.request(method, path)
    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable"}
    # The usual headers still apply.
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-request-id"]
