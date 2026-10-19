"""Guard the root Node project. It exists only for the App Store's node job, which runs npm ci at
the upload's root and, as the node template does (TBC, re-verify), its test and build commands: it
holds no packages of its own, and hands each command to the dashboard in frontend/, which installs
from its own lockfile with install scripts off, so no package's install script runs in the
platform's job. Both files are held whole, so no field, script or package can be added unseen."""

import json
from pathlib import Path
from typing import Any

from app import __version__

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str) -> Any:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_root_manifest_is_the_delegate_and_nothing_else() -> None:
    assert _load("package.json") == {
        "name": "holly",
        "version": __version__,
        "private": True,
        "description": (
            "The App Store's node job runs npm ci at the upload's root, then (TBC, re-verify) "
            "the node template's test and build commands: this installs the dashboard in "
            "frontend/ from its own lockfile, install scripts off, and runs its tests and build "
            "there."
        ),
        "scripts": {
            "postinstall": "npm ci --prefix frontend --ignore-scripts --no-audit --no-fund",
            "test": "npm test --prefix frontend --",
            "build": "npm run build --prefix frontend",
        },
    }


def test_root_lock_holds_the_root_project_alone() -> None:
    assert _load("package-lock.json") == {
        "name": "holly",
        "version": __version__,
        "lockfileVersion": 3,
        "requires": True,
        "packages": {"": {"name": "holly", "version": __version__, "hasInstallScript": True}},
    }
