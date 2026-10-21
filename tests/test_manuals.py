"""The Help page's manuals (app/api/v1/routes/manuals.py): every signed-in user reads the training
manual, and only operators and admins the operator manual, refused on the server."""

from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest

from app.models.user import User, UserRole
from app.services import manuals
from fakes import make_user

SignIn = Callable[[User], User]
MANUALS = "/api/v1/manuals"
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def fresh_cache() -> None:
    manuals.manual_text.cache_clear()


async def test_it_requires_sign_in(api: httpx2.AsyncClient) -> None:
    assert (await api.get(MANUALS)).status_code == 401
    assert (await api.get(f"{MANUALS}/training")).status_code == 401


async def test_an_analyst_is_offered_and_reads_only_the_training_manual(
    api: httpx2.AsyncClient, sign_in: SignIn
) -> None:
    sign_in(make_user(role=UserRole.ANALYST))
    assert (await api.get(MANUALS)).json() == [
        {"slug": "training", "title": "Analyst training manual"}
    ]
    training = await api.get(f"{MANUALS}/training")
    assert training.status_code == 200
    expected = (ROOT / "docs/user-handbook/training-manual.md").read_text(encoding="utf-8")
    assert training.json()["markdown"] == expected
    refused = await api.get(f"{MANUALS}/operator")
    assert refused.status_code == 403
    assert "markdown" not in refused.json()


@pytest.mark.parametrize("role", [UserRole.OPERATOR, UserRole.ADMIN])
async def test_operators_and_admins_read_both(
    api: httpx2.AsyncClient, sign_in: SignIn, role: UserRole
) -> None:
    sign_in(make_user(role=role))
    assert [m["slug"] for m in (await api.get(MANUALS)).json()] == ["training", "operator"]
    operator = await api.get(f"{MANUALS}/operator")
    assert operator.status_code == 200
    assert operator.json()["title"] == "Operator manual"
    assert operator.json()["markdown"].startswith("**BLUESTAQ LIMITED** | Operator Manual")


@pytest.mark.parametrize("slug", ["nothing", "Training", "../etc", "a" * 33])
async def test_an_unknown_or_malformed_manual_is_refused(
    api: httpx2.AsyncClient, sign_in: SignIn, slug: str
) -> None:
    sign_in(make_user(role=UserRole.ADMIN))
    assert (await api.get(f"{MANUALS}/{slug}")).status_code in {404, 422}


async def test_a_release_without_the_file_says_so(
    api: httpx2.AsyncClient, sign_in: SignIn, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(manuals, "_ROOT", tmp_path)
    sign_in(make_user())
    response = await api.get(f"{MANUALS}/training")
    assert response.status_code == 503
    assert response.json() == {"detail": "This release does not carry the manual."}


def test_each_manual_is_read_once_a_process(monkeypatch: pytest.MonkeyPatch) -> None:
    [training, _operator] = manuals.MANUALS
    first = manuals.manual_text(training)
    monkeypatch.setattr(manuals, "_ROOT", Path("/nonexistent"))
    assert manuals.manual_text(training) == first
