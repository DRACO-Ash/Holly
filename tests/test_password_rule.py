"""Guard the drift: Holly's rule for a password it sets is written twice, by the server
(app/schemas/auth.py) and by the dashboard (frontend/src/utils/passwords.ts), which checks first
to say why in plain words. If the two disagree, the dashboard sends a password the server
refuses, or refuses one the server would take (ADR-014)."""

import codecs
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.cli.create_admin import MIN_PASSWORD_LENGTH
from app.schemas.auth import MAX_PASSWORD_LENGTH, PasswordChangeRequest

RULE = Path(__file__).resolve().parent.parent / "frontend" / "src" / "utils" / "passwords.ts"


def _constant(name: str) -> str:
    source = RULE.read_text(encoding="utf-8")
    [value] = re.findall(rf'^(?:export )?const {name} =\s*"?([^";]*)"?;$', source, re.MULTILINE)
    return str(value)


def test_the_dashboard_holds_the_server_s_lengths() -> None:
    assert int(_constant("MIN_PASSWORD_LENGTH")) == MIN_PASSWORD_LENGTH
    assert int(_constant("MAX_PASSWORD_LENGTH")) == MAX_PASSWORD_LENGTH


def test_the_dashboard_counts_as_spaces_what_the_server_strips() -> None:
    spaces = set(codecs.decode(_constant("PYTHON_SPACES"), "unicode_escape"))
    assert spaces == {chr(code) for code in range(0x110000) if chr(code).isspace()}


# What the user typed as their current password: any text; the rule is about the new one.
TYPED = "now"


def _accepted(password: str) -> bool:
    try:
        PasswordChangeRequest(current_password=TYPED, new_password=password)
    except ValidationError:
        return False
    return True


@pytest.mark.parametrize(
    ("password", "accepted"),
    [
        # The edges the dashboard's tests check (passwords.test.ts), as the server decides them.
        ("\U0001f680" * 6, False),
        ("\U0001f680" * MIN_PASSWORD_LENGTH, True),
        ("\u00a0" * MIN_PASSWORD_LENGTH, False),
        ("\u001c" * MIN_PASSWORD_LENGTH, False),
        ("\ufeff" * MIN_PASSWORD_LENGTH, True),
        ("x" * MAX_PASSWORD_LENGTH, True),
        ("x" * (MAX_PASSWORD_LENGTH + 1), False),
    ],
)
def test_the_server_decides_the_edges_as_the_dashboard_does(password: str, accepted: bool) -> None:
    assert _accepted(password) is accepted
