"""Guard the drift: the header that carries Holly's access token is named once on each side of the
wire, by the server (app/dependencies.py) and by the dashboard (frontend/src/api/client.ts). If the
two differ, every signed-in request fails, with every other suite still green (ADR-013)."""

import re
from pathlib import Path

from app.dependencies import TOKEN_HEADER

CLIENT = Path(__file__).resolve().parent.parent / "frontend" / "src" / "api" / "client.ts"


def test_the_server_reads_the_header_the_docs_and_the_smoke_rung_name() -> None:
    # A header's name, not a secret.
    assert TOKEN_HEADER == "X-Holly-Token"  # noqa: S105


def test_the_dashboard_sends_the_header_the_server_reads() -> None:
    source = CLIENT.read_text(encoding="utf-8")
    names = re.findall(r'^export const TOKEN_HEADER = "([^"]*)";$', source, re.MULTILINE)
    assert names == [TOKEN_HEADER]
