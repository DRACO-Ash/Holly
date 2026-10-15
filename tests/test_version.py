"""Guard the drift: the version stamp in code, in pyproject.toml and in the dashboard's manifest
and lockfile are one value."""

import json
import tomllib
from pathlib import Path

from app import __version__

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
DASHBOARD = Path(__file__).resolve().parent.parent / "frontend"


def test_version_stamp_matches_pyproject() -> None:
    with PYPROJECT.open("rb") as handle:
        assert tomllib.load(handle)["project"]["version"] == __version__


def test_dashboard_carries_the_same_version() -> None:
    manifest = json.loads((DASHBOARD / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((DASHBOARD / "package-lock.json").read_text(encoding="utf-8"))
    assert manifest["version"] == __version__
    assert lock["version"] == __version__
    assert lock["packages"][""]["version"] == __version__
