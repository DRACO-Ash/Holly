"""Claude's evaluation of a notification against the team's procedures.

Loads a notification with the related maneuvers, recent team chat and every uploaded
procedure, asks Claude for a strict JSON evaluation, validates it (schemas/assistant.py) and
stores it in assistant_evaluation. A reply that is not valid JSON of the right shape is retried
once; a second failure is stored as the error, with no advice (llm-integration). Concurrent
requests for the same notification share one run (core/single_flight.py).
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.single_flight import SingleFlight
from app.db.session import get_session_factory
from app.models.assistant_evaluation import AssistantEvaluation
from app.models.maneuver import Maneuver
from app.models.mattermost_message import MattermostMessage
from app.models.notification import Notification
from app.models.procedure import Procedure
from app.schemas.assistant import AssistantEvaluationRead, StructuredEvaluation
from app.services.claude import AssistantError, call_claude, extract_json_object
from app.services.procedure_storage import read_preview

logger = logging.getLogger(__name__)

_MANEUVER_LOOKBACK_DAYS = 30
_MANEUVER_MAX_PER_PROMPT = 10
_CHAT_MESSAGE_MAX_CHARS = 500

_SYSTEM_PROMPT = """\
You are an expert space operations analyst supporting a Daily Space
Operations team. You assist the operator by reading UDL notifications
(NOTSOs / TACREPs) alongside related maneuver records from fusion
providers, recent team chat from Mattermost, and the team's own
uploaded operational procedures, then recommending concrete next
steps.

Maneuver records describe historical or in-progress thrust events for
the same satellites referenced in the notification. Use them to spot
patterns (e.g. recent maneuver may explain a new conjunction) and to
contextualise the notification.

The TEAM CHAT section is recent shop-talk from the ops floor. Treat
it as soft context, useful for spotting decisions the team has
already made, escalations in flight, or open threads, not as
authoritative source data. Operators may speculate or revise.

You must respond with a single JSON object and nothing else. No prose
before or after the JSON. Use this schema exactly:

{
  "summary": "One short paragraph in plain operational English. What
              is happening, who/what is involved, when.",
  "applicable_procedures": [
    {
      "procedure_id": "<the id provided>",
      "name": "<procedure name>",
      "reason": "Why this procedure applies to this notification"
    }
  ],
  "next_actions": [
    {
      "action": "Imperative description of what the operator should do",
      "urgency": "high" | "medium" | "low",
      "deadline": "ISO 8601 timestamp or null",
      "rationale": "Why; cite the procedure step or orbital trigger"
    }
  ],
  "open_questions": [
    "Question the operator must answer using judgement or external info"
  ]
}

Rules:
- Be specific. "Release a NOTSO" is weak; "Release follow-up NOTSO
  referencing this event 24h before re-entry" is good.
- Empty arrays are fine. If no procedure applies, return
  applicable_procedures: [].
- Do not invent procedure ids. Use only the ids supplied in the prompt.
- If the notification is informational only and no action is required,
  say so in summary and return next_actions: [].
- Use UTC for any timestamps.
"""

_JSON_RETRY_NUDGE = (
    "Your previous reply could not be used. Return only the JSON object described in the "
    "instructions, with every required field, and no text before or after it."
)


def _empty_evaluation() -> dict[str, Any]:
    return {
        "summary": "Assistant evaluation could not be generated.",
        "applicable_procedures": [],
        "next_actions": [],
        "open_questions": [],
    }


# (label, attribute) for each notification field the prompt shows, in order.
_NOTIFICATION_FIELDS = (
    ("Notice", "notso_identifier"),
    ("Message type", "msg_type"),
    ("Event type", "event_type"),
    ("Event class", "event_class"),
    ("Status", "status"),
    ("Subject", "subject"),
    ("Description", "description"),
    ("Region", "region"),
    ("Company", "company_name"),
    ("Published", "publish_date"),
    ("Effective from", "effective_from"),
    ("Effective until", "effective_until"),
    ("UDL created", "udl_created_at"),
)
_MANEUVER_FIELDS = (
    ("start", "event_start_time"),
    ("stop", "event_stop_time"),
    ("type", "mnvr_type"),
    ("status", "maneuver_status"),
    ("deltaV", "delta_v"),
    ("source", "source"),
)


class NotificationNotFoundError(LookupError):
    """The notification asked about does not exist."""


@dataclass(frozen=True)
class EvaluationOutcome:
    evaluation: AssistantEvaluation
    persistent_failure: bool


@dataclass(frozen=True)
class EvaluationRun:
    evaluation: AssistantEvaluationRead
    persistent_failure: bool


_IN_FLIGHT: SingleFlight[EvaluationRun] = SingleFlight()


def display_value(value: object) -> str:
    """A prompt-ready rendering: datetimes in ISO 8601, everything else as text."""
    return value.isoformat() if isinstance(value, datetime) else str(value)


def _shown(value: object) -> bool:
    return value is not None and value != ""


def _format_notification(n: Notification) -> str:
    lines = ["NOTIFICATION:"]
    for label, attribute in _NOTIFICATION_FIELDS:
        value = getattr(n, attribute)
        if _shown(value):
            lines.append(f"  {label}: {display_value(value)}")
    if n.sat_no is not None:
        lines.append(f"  Satellite: {n.sat_no}")
    if n.sat_ids:
        lines.append(f"  Satellites: {', '.join(str(sat) for sat in n.sat_ids)}")
    if n.notso_link:
        lines.append(f"  Source link: {n.notso_link}")
    return "\n".join(lines)


def _format_maneuver(m: Maneuver) -> str:
    parts = [f"  - Sat {m.sat_no if m.sat_no is not None else '?'}"]
    for label, attribute in _MANEUVER_FIELDS:
        value = getattr(m, attribute)
        if _shown(value):
            parts.append(f"{label}={display_value(value)}")
    head = " | ".join(parts)
    if m.description:
        return f"{head}\n    {m.description.strip()}"
    return head


def _extract_sat_nos(notification: Notification) -> list[int]:
    numbers: list[int] = []
    if notification.sat_no is not None:
        numbers.append(notification.sat_no)
    for value in notification.sat_ids or []:
        try:
            numbers.append(int(value))
        except (TypeError, ValueError):
            continue
    return list(dict.fromkeys(numbers))  # de-duplicated, order kept


async def _load_relevant_maneuvers(db: AsyncSession, notification: Notification) -> list[Maneuver]:
    sat_nos = _extract_sat_nos(notification)
    if not sat_nos:
        return []
    window_start = datetime.now(UTC) - timedelta(days=_MANEUVER_LOOKBACK_DAYS)
    stmt = (
        select(Maneuver)
        .where(Maneuver.sat_no.in_(sat_nos))
        .where(
            or_(
                Maneuver.event_start_time.is_(None),
                Maneuver.event_start_time >= window_start,
            )
        )
        .order_by(Maneuver.event_start_time.desc().nullslast())
        .limit(_MANEUVER_MAX_PER_PROMPT)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _load_recent_chat(db: AsyncSession) -> list[MattermostMessage]:
    """The latest chat from the configured channels, oldest first, as the operator reads it."""
    settings = get_settings()
    window_hours = settings.mattermost_prompt_window_hours
    limit = settings.mattermost_max_messages_in_prompt
    if window_hours <= 0 or limit <= 0:
        return []
    window_start = datetime.now(UTC) - timedelta(hours=window_hours)
    stmt = (
        select(MattermostMessage)
        .where(MattermostMessage.posted_at >= window_start)
        .order_by(MattermostMessage.posted_at.desc())
        .limit(limit)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    rows.reverse()
    return rows


def _format_chat(messages: list[MattermostMessage]) -> str:
    if not messages:
        return ""
    lines = [f"TEAM CHAT (last {get_settings().mattermost_prompt_window_hours} hours):"]
    for m in messages:
        ts = m.posted_at.strftime("%Y-%m-%d %H:%M")
        author = m.user_display_name or m.user_id
        channel = m.channel_name or m.channel_id
        body = m.message.replace("\n", " ").strip()
        if len(body) > _CHAT_MESSAGE_MAX_CHARS:
            body = body[:_CHAT_MESSAGE_MAX_CHARS] + "..."
        lines.append(f"- [{ts}] #{channel} @{author}: {body}")
    return "\n".join(lines)


def _format_procedure(p: Procedure) -> str:
    content, truncated = read_preview(p.id, p.filename, p.content_type)
    block = [f"PROCEDURE id={p.id} name={p.name!r}"]
    if p.description:
        block.append(f"  Description: {p.description}")
    if content is None:
        block.append("  Content: <binary or unsupported preview type; operator should view file>")
    else:
        block.append("  Content:")
        block.append(content)
        if truncated:
            block.append("  ... (truncated)")
    return "\n".join(block)


def _build_user_message(
    notification: Notification,
    procedures: list[Procedure],
    maneuvers: list[Maneuver],
    chat: list[MattermostMessage],
) -> str:
    parts = [_format_notification(notification), ""]
    if maneuvers:
        lines = [f"RELATED MANEUVERS (same satellite, last {_MANEUVER_LOOKBACK_DAYS} days):"]
        lines.extend(_format_maneuver(m) for m in maneuvers)
        parts.append("\n".join(lines))
    else:
        parts.append("RELATED MANEUVERS: (none for the satellite(s) in this notification)")
    chat_block = _format_chat(chat)
    if chat_block:
        parts.append(chat_block)
    if procedures:
        parts.append("AVAILABLE PROCEDURES:")
        parts.extend(_format_procedure(p) for p in procedures)
    else:
        parts.append("AVAILABLE PROCEDURES: (none uploaded)")
    parts.append("")
    parts.append("Return the JSON object as specified. No text before or after the JSON.")
    return "\n\n".join(parts)


def parse_evaluation(text: str, procedure_ids: set[str]) -> StructuredEvaluation:
    """Validate a reply as an evaluation. Raises AssistantError when it is not one."""
    try:
        evaluation = StructuredEvaluation.model_validate(extract_json_object(text))
    except ValidationError as exc:
        msg = f"Model response did not match the evaluation schema ({exc.error_count()} errors)"
        raise AssistantError(msg) from exc
    # The model may cite only the procedures it was given; any other id is dropped.
    for procedure in evaluation.applicable_procedures:
        if procedure.procedure_id not in procedure_ids:
            procedure.procedure_id = None
    return evaluation


async def _ask(user_message: str) -> tuple[str, str]:
    max_tokens = get_settings().anthropic_max_tokens
    reply = await call_claude(
        _SYSTEM_PROMPT, user_message, max_tokens=max_tokens, purpose="assistant.evaluate"
    )
    if reply.truncated:
        # A truncated reply cannot hold the complete JSON; a retry would truncate again.
        msg = (
            f"Model response was truncated at {max_tokens} tokens before completing the JSON. "
            "Raise ANTHROPIC_MAX_TOKENS."
        )
        raise AssistantError(msg)
    return reply.text, reply.model


async def _evaluate(user_message: str, procedure_ids: set[str]) -> tuple[StructuredEvaluation, str]:
    text, model = await _ask(user_message)
    try:
        return parse_evaluation(text, procedure_ids), model
    except AssistantError as exc:
        logger.info("Evaluation reply unusable (%s); retrying once for JSON only", exc)
    text, model = await _ask(f"{user_message}\n\n{_JSON_RETRY_NUDGE}")
    return parse_evaluation(text, procedure_ids), model


async def evaluate_notification(db: AsyncSession, notification_id: uuid.UUID) -> EvaluationOutcome:
    """Evaluate one notification and add the result to the session (the caller commits)."""
    notification = (
        await db.execute(select(Notification).where(Notification.id == notification_id))
    ).scalar_one_or_none()
    if notification is None:
        raise NotificationNotFoundError(str(notification_id))

    procedures = list(
        (await db.execute(select(Procedure).order_by(Procedure.created_at))).scalars().all()
    )
    maneuvers = await _load_relevant_maneuvers(db, notification)
    chat = await _load_recent_chat(db)
    user_message = _build_user_message(notification, procedures, maneuvers, chat)
    procedure_ids = {str(p.id) for p in procedures}

    error: str | None = None
    persistent = False
    structured = _empty_evaluation()
    model = get_settings().anthropic_model
    try:
        evaluation, model = await _evaluate(user_message, procedure_ids)
        structured = evaluation.model_dump()
    except AssistantError as exc:
        logger.warning("Assistant evaluation failed for %s: %s", notification_id, exc)
        error, persistent = str(exc), exc.persistent

    row = AssistantEvaluation(
        notification_id=notification.id,
        summary=str(structured.get("summary") or "No summary returned."),
        structured=structured,
        procedures_used=[str(p.id) for p in procedures],
        model=model,
        error=error,
    )
    db.add(row)
    await db.flush()
    return EvaluationOutcome(evaluation=row, persistent_failure=persistent)


async def _evaluate_and_store(notification_id: uuid.UUID) -> EvaluationRun:
    async with get_session_factory()() as db:
        outcome = await evaluate_notification(db, notification_id)
        await db.commit()
        await db.refresh(outcome.evaluation)
        return EvaluationRun(
            evaluation=AssistantEvaluationRead.model_validate(outcome.evaluation),
            persistent_failure=outcome.persistent_failure,
        )


async def evaluate_once(notification_id: uuid.UUID) -> EvaluationRun:
    """Evaluate and store, in a session of its own. A caller asking for a notification already
    being evaluated joins that run instead of starting another."""
    return await _IN_FLIGHT.run(str(notification_id), lambda: _evaluate_and_store(notification_id))


async def get_latest_evaluation(
    db: AsyncSession,
    notification_id: uuid.UUID,
) -> AssistantEvaluation | None:
    stmt = (
        select(AssistantEvaluation)
        .where(AssistantEvaluation.notification_id == notification_id)
        .order_by(AssistantEvaluation.evaluated_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()
