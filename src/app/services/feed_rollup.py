"""The urgency the dashboard shows for a notification: the most urgent next action its latest
evaluation names. The feed and the activity overview share it."""

from collections.abc import Iterable
from uuid import UUID

from app.models.assistant_evaluation import AssistantEvaluation

URGENCY_RANK = {"high": 3, "medium": 2, "low": 1, "none": 0, "pending": -1}
UNRANKED = -2


def rollup_urgency(evaluation: AssistantEvaluation | None) -> tuple[str, str | None]:
    """(urgency, top action) for the dashboard: the most urgent next action, if any."""
    if evaluation is None or evaluation.error:
        return "pending", None
    actions = [
        a for a in (evaluation.structured or {}).get("next_actions") or [] if isinstance(a, dict)
    ]
    if not actions:
        return "none", None
    best_rank, best, top_action = UNRANKED, "none", None
    for action in actions:
        urgency = str(action.get("urgency", "")).lower() or "low"
        rank = URGENCY_RANK.get(urgency, 0)
        if rank > best_rank:
            best_rank, best = rank, urgency
            text = action.get("action")
            top_action = text if isinstance(text, str) else None
    return best, top_action


def latest_by_notification(
    rows: Iterable[AssistantEvaluation],
) -> dict[UUID, AssistantEvaluation]:
    latest: dict[UUID, AssistantEvaluation] = {}
    for row in rows:
        existing = latest.get(row.notification_id)
        if existing is None or row.evaluated_at > existing.evaluated_at:
            latest[row.notification_id] = row
    return latest
