"""The manuals Holly shows on its Help page, read from the documents the release carries.

The analyst training manual is for every signed-in user; the operator manual, which names the
settings, commands and recovery steps, for operators and admins alone. The role is checked on
the server, never in the browser. Each manual is the Markdown file kept under docs/, copied into
the image at the same place relative to the source, so there is one copy to keep up to date.
"""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

from app.models.user import UserRole

# src/app/services/manuals.py -> the repository root, or /app in the image.
_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Manual:
    slug: str
    title: str
    path: str
    roles: frozenset[str]


_EVERYONE = frozenset(role.value for role in UserRole)
_OPERATORS = frozenset({UserRole.OPERATOR.value, UserRole.ADMIN.value})

MANUALS = (
    Manual(
        "training", "Analyst training manual", "docs/user-handbook/training-manual.md", _EVERYONE
    ),
    Manual("operator", "Operator manual", "docs/runbook/operator-manual.md", _OPERATORS),
)


def manuals_for(role: str) -> list[Manual]:
    return [manual for manual in MANUALS if role in manual.roles]


def find_manual(slug: str) -> Manual | None:
    return next((manual for manual in MANUALS if manual.slug == slug), None)


@cache
def manual_text(manual: Manual) -> str | None:
    """The manual's Markdown, read once a process; None when the release lacks the file."""
    try:
        return (_ROOT / manual.path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
