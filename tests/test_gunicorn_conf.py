"""The container's gunicorn settings bind through the validated PORT parser."""

import importlib
import runpy
from types import SimpleNamespace
from typing import Any

import pytest
from gunicorn.config import Config

from app.config import get_settings


def load_settings(monkeypatch: pytest.MonkeyPatch, port: str | None) -> dict[str, Any]:
    if port is None:
        monkeypatch.delenv("PORT", raising=False)
    else:
        monkeypatch.setenv("PORT", port)
    return runpy.run_module("app.gunicorn_conf")


@pytest.mark.parametrize(
    ("port", "bind"),
    [(None, "0.0.0.0:8080"), ("9090", "0.0.0.0:9090"), (" 3000\n", "0.0.0.0:3000")],
)
def test_bind_uses_the_validated_port(
    monkeypatch: pytest.MonkeyPatch, port: str | None, bind: str
) -> None:
    assert load_settings(monkeypatch, port)["bind"] == bind


@pytest.mark.parametrize("port", ["0", "8080 --check-config", "9090 # the app port"])
def test_a_malformed_port_stops_the_container(monkeypatch: pytest.MonkeyPatch, port: str) -> None:
    with pytest.raises(ValueError, match="PORT must be a whole number"):
        load_settings(monkeypatch, port)


def test_control_socket_is_off_and_one_uvicorn_worker_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = load_settings(monkeypatch, None)
    assert settings["control_socket_disable"] is True
    assert settings["worker_class"] == "uvicorn_worker.UvicornWorker"
    # One worker, so the background loops, the rate limits and the assistant cap run once.
    assert settings["workers"] == 1


def test_the_master_migrates_then_bootstraps_the_admin_before_any_worker_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = load_settings(monkeypatch, None)
    environ = settings["os"].environ
    calls: list[str] = []
    monkeypatch.setitem(
        settings["on_starting"].__globals__, "run_migrations", lambda: calls.append("migrate")
    )
    monkeypatch.setitem(
        settings["on_starting"].__globals__, "configure_logging", lambda: calls.append("log")
    )
    monkeypatch.setitem(
        settings["on_starting"].__globals__,
        "prepare_scan_environment",
        lambda env: calls.append(f"scan:{env is environ}"),
    )
    monkeypatch.setitem(
        settings["on_starting"].__globals__,
        "wait_for_database",
        lambda url: calls.append(f"wait:{url.host}"),
    )
    monkeypatch.setitem(
        settings["on_starting"].__globals__,
        "run_admin_bootstrap",
        # The bootstrap sees the live environment, with the password still in it.
        lambda env: calls.append(f"admin:{env is environ}:{'ADMIN_PASSWORD' in env}"),
    )
    monkeypatch.setenv("ADMIN_PASSWORD", "p" * 16)
    # gunicorn's own Config copies the environment, password included, before this hook runs.
    server = SimpleNamespace(cfg=Config())
    assert server.cfg.env_orig["ADMIN_PASSWORD"] == "p" * 16
    settings["on_starting"](server)
    # The scan step runs before anything reads the settings; the wait before the migrations.
    assert calls == ["log", "scan:True", "wait:db.invalid", "migrate", "admin:True:True"]
    # The worker forks without the admin password in its environment or in gunicorn's copy.
    assert "ADMIN_PASSWORD" not in environ
    assert "ADMIN_PASSWORD" not in server.cfg.env_orig


def test_with_no_database_under_the_scan_nothing_is_migrated_or_bootstrapped(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = load_settings(monkeypatch, None)
    hook = settings["on_starting"]
    called: list[str] = []
    for name in ("wait_for_database", "run_migrations", "run_admin_bootstrap"):
        monkeypatch.setitem(hook.__globals__, name, lambda *_args, name=name: called.append(name))
    monkeypatch.setitem(hook.__globals__, "configure_logging", lambda: None)
    for name in ("DATABASE_URL", "APP_SECRET_KEY", "PROCEDURE_STORAGE_PATH"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APPSTORE_DAST_SCAN", "true")
    get_settings.cache_clear()
    hook(SimpleNamespace(cfg=Config()))
    assert called == []
    assert '"event": "migrations", "service": "holly", "request_id": "-", "status": "skipped"' in (
        capsys.readouterr().out
    )


def test_gunicorn_knows_every_setting_the_module_defines(monkeypatch: pytest.MonkeyPatch) -> None:
    # gunicorn ignores a name it does not know, so a misspelt setting or server hook would do
    # nothing silently. Every public name except the module's own imports counts, functions
    # included, because gunicorn's server hooks (post_fork and the like) are functions.
    imports = {
        "os",
        "Any",
        "resolve_port",
        "configure_logging",
        "run_migrations",
        "run_admin_bootstrap",
        "get_settings",
        "log_event",
        "prepare_scan_environment",
        "wait_for_database",
    }
    defined = {
        name
        for name in load_settings(monkeypatch, None)
        if not name.startswith("_") and name not in imports
    }
    assert defined == {"bind", "worker_class", "workers", "control_socket_disable", "on_starting"}
    assert defined <= set(Config().settings)


def test_the_worker_class_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    module_name, _, class_name = load_settings(monkeypatch, None)["worker_class"].rpartition(".")
    assert hasattr(importlib.import_module(module_name), class_name)
