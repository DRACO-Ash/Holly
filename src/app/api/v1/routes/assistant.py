"""The assistant's dashboard feed and on-demand evaluations.

An evaluation calls Claude, so it counts against the caller's assistant limit; two requests
for the same notification at once share one run (services/assistant.py).
"""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select

from app.config import get_settings
from app.core.net import client_ip
from app.core.rate_limit import ASSISTANT_LIMIT
from app.dependencies import CurrentUser, DbSession
from app.models.assistant_evaluation import AssistantEvaluation
from app.models.event_summary import EventSummary
from app.models.notification import Notification
from app.schemas.assistant import (
    AssistantEvaluationRead,
    AssistantFeed,
    AssistantFeedItem,
)
from app.schemas.notification import NotificationRead
from app.services.assistant import (
    NotificationNotFoundError,
    evaluate_once,
    get_latest_evaluation,
)
from app.services.audit import write_audit
from app.services.disclosure import is_cleared
from app.services.event_summary import compute_event_key
from app.services.notification_query import aliased_deduped_notifications

router = APIRouter(prefix="/assistant", tags=["assistant"])

_URGENCY_RANK = {"high": 3, "medium": 2, "low": 1, "none": 0, "pending": -1}
_UNRANKED = -2


def _rollup_urgency(evaluation: AssistantEvaluation | None) -> tuple[str, str | None]:
    """(urgency, top action) for the dashboard: the most urgent next action, if any."""
    if evaluation is None or evaluation.error:
        return "pending", None
    actions = [
        a for a in (evaluation.structured or {}).get("next_actions") or [] if isinstance(a, dict)
    ]
    if not actions:
        return "none", None
    best_rank, best, top_action = _UNRANKED, "none", None
    for action in actions:
        urgency = str(action.get("urgency", "")).lower() or "low"
        rank = _URGENCY_RANK.get(urgency, 0)
        if rank > best_rank:
            best_rank, best = rank, urgency
            text = action.get("action")
            top_action = text if isinstance(text, str) else None
    return best, top_action


def _latest_by_notification(
    rows: Iterable[AssistantEvaluation],
) -> dict[UUID, AssistantEvaluation]:
    latest: dict[UUID, AssistantEvaluation] = {}
    for row in rows:
        existing = latest.get(row.notification_id)
        if existing is None or row.evaluated_at > existing.evaluated_at:
            latest[row.notification_id] = row
    return latest


def _feed_item(
    notification: Notification,
    evaluation: AssistantEvaluation | None,
    event_key: str,
    summary: EventSummary | None,
) -> AssistantFeedItem:
    urgency, top_action = _rollup_urgency(evaluation)
    return AssistantFeedItem(
        notification=NotificationRead.model_validate(notification),
        evaluation=AssistantEvaluationRead.model_validate(evaluation) if evaluation else None,
        urgency=urgency,
        top_action=top_action,
        event_summary=summary.narrative if summary and not summary.error else None,
        event_publication_count=summary.publication_count if summary else None,
        event_key=event_key,
        assistant_cleared=is_cleared(notification),
    )


def _feed_order(item: AssistantFeedItem) -> tuple[int, datetime]:
    created = item.notification.udl_created_at or datetime.min.replace(tzinfo=UTC)
    return _URGENCY_RANK.get(item.urgency, _UNRANKED), created


@router.get("/feed")
async def feed(
    db: DbSession,
    _current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    hours: Annotated[int | None, Query(ge=1, le=720)] = None,
) -> AssistantFeed:
    window_hours = hours or get_settings().background_notification_window_hours
    window_start = datetime.now(UTC) - timedelta(hours=window_hours)
    notification, _subquery = aliased_deduped_notifications(
        [Notification.udl_created_at >= window_start]
    )
    stmt = select(notification).order_by(notification.udl_created_at.desc()).limit(limit)
    notifications: list[Any] = list((await db.execute(stmt)).scalars().all())
    if not notifications:
        return AssistantFeed(items=[], window_hours=window_hours)

    eval_stmt = select(AssistantEvaluation).where(
        AssistantEvaluation.notification_id.in_([n.id for n in notifications])
    )
    latest = _latest_by_notification((await db.execute(eval_stmt)).scalars().all())
    event_keys = {n.id: compute_event_key(n) for n in notifications}
    summary_stmt = select(EventSummary).where(EventSummary.event_key.in_(set(event_keys.values())))
    summaries = {row.event_key: row for row in (await db.execute(summary_stmt)).scalars().all()}

    items = [
        _feed_item(n, latest.get(n.id), event_keys[n.id], summaries.get(event_keys[n.id]))
        for n in notifications
    ]
    items.sort(key=_feed_order, reverse=True)
    return AssistantFeed(items=items, window_hours=window_hours)


@router.get("/evaluation/{notification_id}")
async def get_evaluation(
    notification_id: UUID, db: DbSession, _current_user: CurrentUser
) -> AssistantEvaluationRead:
    evaluation = await get_latest_evaluation(db, notification_id)
    if evaluation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No evaluation exists for this notification yet. POST to /evaluate to create one."
            ),
        )
    return AssistantEvaluationRead.model_validate(evaluation)


@router.post("/evaluate/{notification_id}")
async def evaluate(
    notification_id: UUID, request: Request, db: DbSession, current_user: CurrentUser
) -> AssistantEvaluationRead:
    ASSISTANT_LIMIT.check(str(current_user.id))
    try:
        run = await evaluate_once(notification_id)
    except NotificationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        ) from exc
    evaluation = run.evaluation
    await write_audit(
        db,
        action_type="assistant.evaluate",
        entity_type="notification",
        entity_id=str(notification_id),
        user_id=current_user.id,
        ip_address=client_ip(request),
        detail={
            "evaluation_id": str(evaluation.id),
            "model": evaluation.model,
            "procedures_used": evaluation.procedures_used,
            "had_error": evaluation.error is not None,
        },
    )
    await db.commit()
    return evaluation
