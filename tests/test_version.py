"""Guard the drift: the version stamp in code, in pyproject.toml, and in the manifest and lockfile
of the dashboard and of the root Node project the platform's node job installs, is one value."""

import json
import tomllib
from pathlib import Path

from app import __version__

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
DASHBOARD = Path(__file__).resolve().parent.parent / "frontend"
ROOT = Path(__file__).resolve().parent.parent


def test_version_stamp_matches_pyproject() -> None:
    with PYPROJECT.open("rb") as handle:
        assert tomllib.load(handle)["project"]["version"] == __version__


def _assert_node_project_version(directory: Path) -> None:
    manifest = json.loads((directory / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((directory / "package-lock.json").read_text(encoding="utf-8"))
    assert manifest["version"] == __version__
    assert lock["version"] == __version__
    assert lock["packages"][""]["version"] == __version__


def test_dashboard_carries_the_same_version() -> None:
    _assert_node_project_version(DASHBOARD)


def test_root_node_project_carries_the_same_version() -> None:
    _assert_node_project_version(ROOT)
