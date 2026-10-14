"""Claude's three-sentence narrative of how a single logical event evolved.

A "logical event" is the grouping used everywhere else: every UDL re-publication of the same
notice shares a group key (event_id, then notso_identifier, then udl_id). This service feeds
every publication of one event to Claude in chronological order and asks for a strict
three-sentence summary of the evolution.

Stored in event_summary keyed on event_key, so the dashboard renders the narrative without
paying for Claude on every load.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_summary import EventSummary
from app.models.notification import Notification
from app.services.assistant import display_value
from app.services.claude import AssistantError, call_claude

logger = logging.getLogger(__name__)

# Three sentences fit comfortably under 400 tokens.
_MAX_TOKENS = 400
_MAX_SENTENCES = 3
# A long-lived event can gather many publications. Claude is shown the first and the newest, at
# most this many in all; the stored summary still lists every publication it covers.
_MAX_PROMPT_PUBLICATIONS = 20

_SYSTEM_PROMPT = """\
You are summarising the evolution of a single space-operations event
across multiple UDL publications.

You will receive a chronological list of publications that all
reference the same logical event. Each publication is the operator
community's snapshot of the event at that moment.

Write a STRICT 3-sentence maximum paragraph in plain operational
English that tells the reader how the event evolved: what happened
first, what changed across publications, what the current status is.

Rules:
- HARD CAP: no more than 3 sentences.
- Plain text only. No markdown, no bullet list, no headings.
- Operational tone. Name the satellite(s), event class, key timing.
- If only one publication exists, just describe that publication in
  at most 3 sentences.
- Do not quote the source publications.
"""

_HEAD_FIELDS = (
    ("udl_created", "udl_created_at"),
    ("status", "status"),
    ("event_type", "event_type"),
)


@dataclass(frozen=True)
class SummaryOutcome:
    """The stored summary; or, when the assistant failed, no summary and the error."""

    summary: EventSummary | None
    error: str | None = None
    persistent_failure: bool = False


def publication_order(n: Notification) -> tuple[datetime, str]:
    """Oldest first by UDL time, the id breaking a tie, so every reader agrees which
    publication is the latest."""
    return (n.udl_created_at or n.created_at, str(n.id))


def compute_event_key(n: Notification) -> str:
    """Python mirror of the SQL COALESCE in notification_query.

    The SQL groups on COALESCE(event_id, notso_identifier, udl_id). The same key is computed
    here, so the summariser can group publications and the dashboard can join notifications
    to their summary.
    """
    for value in (n.event_id, n.notso_identifier, n.udl_id):
        if value:
            return str(value)
    return str(n.id)


def _format_publication(index: int, n: Notification) -> str:
    head = [f"Publication {index + 1}"]
    for label, attribute in _HEAD_FIELDS:
        value = getattr(n, attribute)
        if value:
            head.append(f"{label}={display_value(value)}")
    body: dict[str, object] = {
        "event_class": n.event_class,
        "subject": n.subject if n.subject != n.event_class else None,
        "region": n.region,
        "sat_no": n.sat_no,
        "sat_ids": ", ".join(str(sat) for sat in n.sat_ids) if n.sat_ids else None,
        "description": n.description.strip() if n.description else None,
        "effective_from": n.effective_from,
        "effective_until": n.effective_until,
    }
    lines = [
        f"  {name}: {display_value(value)}"
        for name, value in body.items()
        if value is not None and value != ""
    ]
    return " | ".join(head) + "\n" + "\n".join(lines)


def _build_user_message(publications: list[Notification]) -> str:
    numbered = list(enumerate(publications))
    heading = "EVENT PUBLICATIONS (oldest to newest"
    if len(numbered) > _MAX_PROMPT_PUBLICATIONS:
        # How the event began, then where it stands now.
        numbered = [numbered[0], *numbered[1 - _MAX_PROMPT_PUBLICATIONS :]]
        heading += f"; the first and the newest {len(numbered) - 1} of {len(publications)}"
    blocks = [_format_publication(i, p) for i, p in numbered]
    return heading + "):\n\n" + "\n\n".join(blocks)


def _enforce_three_sentences(text: str) -> str:
    """Belt and braces: keep the first three sentences if Claude overshoots the cap."""
    pieces = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(pieces[:_MAX_SENTENCES]).strip()


async def _narrate(publications: list[Notification]) -> tuple[str, str]:
    reply = await call_claude(
        _SYSTEM_PROMPT,
        _build_user_message(publications),
        max_tokens=_MAX_TOKENS,
        purpose="assistant.event_summary",
    )
    return _enforce_three_sentences(reply.text), reply.model


async def generate_event_summary(
    db: AsyncSession,
    event_key: str,
    publications: list[Notification],
) -> SummaryOutcome:
    """Generate or replace the summary for one logical event (the caller commits).

    The caller passes the event's publications; they are sorted oldest first here. The row is
    upserted on event_key, so a re-run replaces the earlier text. When the assistant fails,
    nothing is written: an earlier narrative stays as it was, and the publications it has not
    seen keep the event stale, so the next cycle tries again.
    """
    if not publications:
        msg = "Cannot summarise an empty publication list"
        raise AssistantError(msg)
    publications = sorted(publications, key=publication_order)

    try:
        narrative, model = await _narrate(publications)
    except AssistantError as exc:
        logger.warning("Event summary failed for %s: %s", event_key, exc)
        return SummaryOutcome(summary=None, error=str(exc), persistent_failure=exc.persistent)

    values: dict[str, Any] = {
        "event_key": event_key,
        "narrative": narrative,
        "source_notification_ids": [str(p.id) for p in publications],
        "latest_notification_id": publications[-1].id,
        "publication_count": len(publications),
        "model": model,
        "error": None,
    }
    stmt = pg_insert(EventSummary).values(values)
    replaced = {
        column: getattr(stmt.excluded, column) for column in values if column != "event_key"
    }
    stmt = stmt.on_conflict_do_update(
        constraint="uq_event_summary_event_key",
        set_={**replaced, "updated_at": func.now()},
    )
    await db.execute(stmt)
    summary = (
        await db.execute(select(EventSummary).where(EventSummary.event_key == event_key))
    ).scalar_one()
    return SummaryOutcome(summary=summary)
