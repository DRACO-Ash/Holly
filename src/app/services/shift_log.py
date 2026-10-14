"""Claude's polish and end-of-shift narrative for the ops-floor log.

Two prompts:

● polish: the operator types a raw observation (often a rant); Claude rewrites it as a
  professional, factual single paragraph stripped of opinion or controversy.

● summarise: at the end of a shift, Claude reads the day's polished notes in order and
  composes a handover narrative for the incoming crew.

Either may fail; the caller stores the note or summary anyway, with the error, so the raw
observation is never lost.
"""

import logging

from app.config import get_settings
from app.models.shift_note import ShiftNote
from app.services.claude import AssistantError, call_claude

logger = logging.getLogger(__name__)

_POLISH_SYSTEM_PROMPT = """\
You are an editor for a Daily Space Operations team's shift log.

The operator types raw observations from the ops floor. They may be
informal, opinionated, ranty, or contain controversy and blame.

Rewrite each input as a single short paragraph that:
● Preserves every operationally relevant fact (times, satellite
  numbers, event identifiers, named systems, actions taken, decisions
  made, people involved by role rather than by personal attack).
● Removes opinion, blame, sarcasm, profanity, and personal attacks.
● Reads as something appropriate for an end-of-shift log and any
  follow-on hand-over.

Return only the rewritten paragraph as plain text. No headings, no
"the operator said", no commentary on what you changed.
"""

_SUMMARY_SYSTEM_PROMPT = """\
You are writing the end-of-shift handover narrative for a Daily Space
Operations team.

You will receive a chronological list of polished shift notes from a
single shift. Produce a short markdown document with:

1. A single opening line that names the date and headlines the shift
   (e.g. "Quiet shift dominated by routine maneuver tracking" or
   "Multi-event shift led by a Soyuz launch and follow-on conjunction
   work").
2. 2-4 short narrative paragraphs telling the story of the shift in
   roughly chronological order, grouping related notes where it helps
   readability.
3. A final "**Handover items**" markdown bullet list of anything that
   is unresolved and needs the incoming shift's attention. If nothing
   is outstanding, write "**Handover items**: none.".

Plain markdown only. No HTML, no code fences, no preamble before
section 1.
"""

ClaudeText = tuple[str | None, str | None, str | None]


async def polish_text(raw: str) -> ClaudeText:
    """Return (polished_text, model, error): (text, model, None), or (None, model, message)."""
    settings = get_settings()
    try:
        reply = await call_claude(
            _POLISH_SYSTEM_PROMPT,
            raw.strip(),
            max_tokens=settings.anthropic_max_tokens,
            purpose="shift_log.polish",
        )
    except AssistantError as exc:
        logger.warning("Shift-note polish failed: %s", exc)
        return None, settings.anthropic_model, str(exc)
    return reply.text, reply.model, None


def _format_notes_for_summary(notes: list[ShiftNote]) -> str:
    lines: list[str] = []
    for note in notes:
        ts = note.created_at.isoformat() if note.created_at else "?"
        body = (note.polished_text or note.raw_text).strip()
        lines.append(f"- {ts}: {body}")
    return "\n".join(lines)


async def summarise_shift(notes: list[ShiftNote]) -> ClaudeText:
    """Return (narrative_markdown, model, error)."""
    settings = get_settings()
    if not notes:
        return None, settings.anthropic_model, "Cannot summarise an empty shift."
    try:
        reply = await call_claude(
            _SUMMARY_SYSTEM_PROMPT,
            _format_notes_for_summary(notes),
            max_tokens=settings.anthropic_max_tokens,
            purpose="shift_log.summary",
        )
    except AssistantError as exc:
        logger.warning("Shift summary generation failed: %s", exc)
        return None, settings.anthropic_model, str(exc)
    return reply.text, reply.model, None
