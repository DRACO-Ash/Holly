"""Guard the drift: the version stamp in code and in pyproject.toml are one value."""

import tomllib
from pathlib import Path

from app import __version__

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_version_stamp_matches_pyproject() -> None:
    with PYPROJECT.open("rb") as handle:
        assert tomllib.load(handle)["project"]["version"] == __version__
