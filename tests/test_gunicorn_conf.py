"""The container's gunicorn settings bind through the validated PORT parser."""

import importlib
import runpy
from typing import Any

import pytest
from gunicorn.config import Config


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


def test_control_socket_is_off_and_the_worker_is_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings(monkeypatch, None)
    assert settings["control_socket_disable"] is True
    assert settings["worker_class"] == "uvicorn_worker.UvicornWorker"


def test_gunicorn_knows_every_setting_and_the_worker_class_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # gunicorn ignores a name it does not know, so a misspelt setting would do nothing silently.
    settings = load_settings(monkeypatch, None)
    assert {"bind", "worker_class", "control_socket_disable"} <= set(Config().settings)
    module_name, _, class_name = settings["worker_class"].rpartition(".")
    assert hasattr(importlib.import_module(module_name), class_name)
