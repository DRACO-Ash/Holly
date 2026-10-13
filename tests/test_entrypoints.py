"""The two ways Holly starts: the container's ASGI object and `python -m app`."""

import runpy
from typing import Any

import pytest
import uvicorn
from fastapi import FastAPI

from app import main


def test_container_entry_point_is_the_factory_built_app() -> None:
    assert isinstance(main.app, FastAPI)


@pytest.mark.parametrize(("port_env", "expected_port"), [(None, 8080), ("9000", 9000)])
def test_dev_server_binds_all_interfaces_on_the_resolved_port(
    monkeypatch: pytest.MonkeyPatch, port_env: str | None, expected_port: int
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(app: str, **kwargs: Any) -> None:
        calls.append({"app": app, **kwargs})

    monkeypatch.setattr(uvicorn, "run", fake_run)
    if port_env is None:
        monkeypatch.delenv("PORT", raising=False)
    else:
        monkeypatch.setenv("PORT", port_env)
    runpy.run_module("app", run_name="__main__")
    assert calls == [{"app": "app.main:app", "host": "0.0.0.0", "port": expected_port}]
