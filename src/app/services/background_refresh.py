"""Per-surface background refresh loops.

Three independent asyncio tasks, each owning one external surface on its own cadence:

● notifications: hourly, a 5-day window from UDL. After each pull, Claude evaluates the
  notifications that have no evaluation yet, and the three-sentence event narratives are
  refreshed. Only notices whose classification marking is cleared for the assistant are sent
  (services/disclosure.py), and each sending is written to the audit chain.
● maneuvers: every 10 minutes, a 48-hour window from UDL. Pull only.
● mattermost: every 60 seconds (MATTERMOST_INTERVAL_SECONDS), a sweep of the channels the bot
  can read, then a pull of the followed open ones (ADR-015). It writes to Mattermost nothing,
  and the messages reach the assistant's prompt at evaluation time. A cycle that polled or
  failed a channel, or changed the channel list, writes one audit row: up to 1,440 a day at
  the default cadence while a channel is followed. Single-flight, like the notification cycle.

Element-set auto-pulling was removed because operators were not using the data; the route,
model and table remain for recoverability.

Each loop opens its own session per phase, and logs and survives any failure, so a transient
outage never kills it. The notification and Mattermost cycles are single-flight: a manual
refresh during a running cycle joins it instead of starting a second.
"""

import asyncio
import logging
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.single_flight import SingleFlight
from app.db.session import get_session_factory
from app.models.assistant_evaluation import AssistantEvaluation
from app.models.event_summary import EventSummary
from app.models.notification import Notification
from app.services.assistant import EvaluationRun, evaluate_once, write_evaluation_audit
from app.services.audit import write_audit
from app.services.disclosure import cleared_condition, cleared_markings
from app.services.event_summary import (
    compute_event_key,
    generate_event_summary,
    publication_order,
)
from app.services.maneuver_ingest import ingest_maneuvers
from app.services.mattermost_ingest import MattermostIngestResult, ingest_mattermost_messages
from app.services.notification_ingest import ingest_notifications
from app.services.notification_query import (
    aliased_deduped_notifications,
    notification_group_key,
)
from app.services.udl_client import UDLAuthError, UDLClient, UDLClientError

logger = logging.getLogger(__name__)

_CYCLE: SingleFlight[None] = SingleFlight()


# Notifications -------------------------------------------------


async def _pull_notifications_once() -> None:
    window_hours = get_settings().background_notification_window_hours
    window_start = datetime.now(UTC) - timedelta(hours=window_hours)
    try:
        async with UDLClient() as client, get_session_factory()() as db:
            await ingest_notifications(
                db,
                client,
                msg_type="TACREP_NOTSO",
                created_at_gte=window_start,
                data_mode="REAL",
                source="JCO",
            )
        logger.info("Notification ingest complete (window: last %sh)", window_hours)
    except UDLAuthError as exc:
        logger.warning("Notification ingest skipped: UDL auth failed (%s)", exc)
    except UDLClientError as exc:
        logger.warning("Notification ingest failed: %s", exc)
    except Exception:
        logger.exception("Notification ingest crashed unexpectedly")


async def _unevaluated_notification_ids(window_start: datetime, limit: int) -> list[uuid.UUID]:
    # Only the latest version of each logical notice: UDL re-publishes notices, and a
    # duplicate is not worth an assistant call.
    async with get_session_factory()() as db:
        notif_alias, _dedup_subq = aliased_deduped_notifications(
            [Notification.udl_created_at >= window_start]
        )
        stmt = (
            select(notif_alias.id)
            .outerjoin(
                AssistantEvaluation,
                AssistantEvaluation.notification_id == notif_alias.id,
            )
            .where(AssistantEvaluation.id.is_(None))
            # Only a notice whose latest publication is cleared; an older cleared one would be
            # evaluated while the dashboard shows the newer one as not sent.
            .where(notif_alias.classification_marking.in_(cleared_markings()))
            .order_by(notif_alias.udl_created_at.desc())
            .limit(limit)
        )
        return [row[0] for row in (await db.execute(stmt)).all()]


async def _auto_evaluate_phase() -> None:
    settings = get_settings()
    if not settings.background_auto_evaluate:
        return
    window_start = datetime.now(UTC) - timedelta(
        hours=settings.background_notification_window_hours
    )
    ids = await _unevaluated_notification_ids(
        window_start, settings.background_max_evaluations_per_cycle
    )
    if not ids:
        return
    logger.info("Auto-evaluating %s un-analysed notification(s)", len(ids))
    for notification_id in ids:
        try:
            run = await evaluate_once(notification_id)
            await _audit_background_evaluation(notification_id, run)
        except Exception:
            # Fail closed: once the notice may have been sent, a failure to store or audit the
            # evaluation means sendings may go unrecorded, so nothing more is sent this cycle.
            logger.exception("Auto-evaluate of notification %s failed; stopping", notification_id)
            return
        if run.persistent_failure:
            logger.warning("Stopping auto-evaluate cycle early: %s", run.evaluation.error)
            return


async def _audit_background_evaluation(notification_id: uuid.UUID, run: EvaluationRun) -> None:
    """The background cycle's counterpart of the evaluate route's audit row: which notice the
    assistant was shown, by no user."""
    async with get_session_factory()() as db:
        await write_evaluation_audit(db, notification_id, run.evaluation, trigger="background")
        await db.commit()


async def _publications_by_event(window_start: datetime) -> dict[str, list[Notification]]:
    # Grouped in Python, so the key is the same COALESCE event_key the rest of the system
    # uses, without a lateral join.
    async with get_session_factory()() as db:
        stmt = (
            select(Notification)
            .where(Notification.udl_created_at >= window_start, cleared_condition())
            .order_by(Notification.udl_created_at.asc(), Notification.id.asc())
        )
        publications = list((await db.execute(stmt)).scalars().all())
    grouped: dict[str, list[Notification]] = defaultdict(list)
    for publication in publications:
        grouped[compute_event_key(publication)].append(publication)
    return grouped


def _summary_is_stale(existing: EventSummary | None, publications: list[Notification]) -> bool:
    """Stale when there is no summary, when the stored one records a failure (the Daily
    Operations Dashboard wrote such rows), or when the window holds a publication the summary
    has not seen. A publication that has aged out of the window never makes a summary stale,
    so no summary ever shrinks."""
    if existing is None or existing.error:
        return True
    seen = set(existing.source_notification_ids or ())
    return any(str(publication.id) not in seen for publication in publications)


async def _event_history(db: AsyncSession, event_key: str) -> list[Notification]:
    """Every stored publication of one logical event that may be sent to the assistant, the
    ones older than the window too."""
    stmt = select(Notification).where(notification_group_key() == event_key, cleared_condition())
    return list((await db.execute(stmt)).scalars().all())


async def _stale_event_keys(grouped: dict[str, list[Notification]]) -> list[str]:
    async with get_session_factory()() as db:
        stmt = select(EventSummary).where(EventSummary.event_key.in_(grouped.keys()))
        existing = {row.event_key: row for row in (await db.execute(stmt)).scalars().all()}
    return [
        key
        for key, publications in grouped.items()
        if publications and _summary_is_stale(existing.get(key), publications)
    ]


async def _event_summary_phase() -> None:
    """Refresh the narrative of every logical event in the window that holds a publication its
    summary has not seen, newest events first, up to the per-cycle cap."""
    settings = get_settings()
    window_start = datetime.now(UTC) - timedelta(
        hours=settings.background_notification_window_hours
    )
    grouped = await _publications_by_event(window_start)
    if not grouped:
        return
    # Newest events first, so the per-cycle cap never leaves the current picture waiting.
    stale = sorted(
        await _stale_event_keys(grouped),
        key=lambda key: max(map(publication_order, grouped[key])),
        reverse=True,
    )
    stale_keys = stale[: settings.background_max_event_summaries_per_cycle]
    if not stale_keys:
        return
    logger.info("Refreshing %s event summary/summaries", len(stale_keys))
    for key in stale_keys:
        async with get_session_factory()() as db:
            try:
                history = await _event_history(db, key)
            except Exception:
                # Nothing has been sent for this event yet, so the next one may still run.
                logger.exception("Event summary failed for %s", key)
                await db.rollback()
                continue
            try:
                outcome = await generate_event_summary(db, key, history)
                await write_audit(db, **_summary_audit(key, history, outcome.summary is None))
                await db.commit()
            except Exception:
                # Fail closed: the publications may have been sent, and the narrative or its
                # audit row not stored, so nothing more is sent this cycle.
                logger.exception("Event summary for %s failed; stopping", key)
                await db.rollback()
                return
        if outcome.persistent_failure:
            logger.warning("Stopping event summary cycle early: %s", outcome.error)
            return


def _summary_audit(event_key: str, history: list[Notification], failed: bool) -> dict[str, Any]:
    """The audit row for one event's publications shown to the assistant, written in the same
    transaction as the narrative."""
    return {
        "action_type": "assistant.event_summary",
        "entity_type": "event",
        "entity_id": event_key,
        "detail": {"trigger": "background", "publications": len(history), "had_error": failed},
    }


async def _notification_cycle() -> None:
    await _pull_notifications_once()
    await _auto_evaluate_phase()
    await _event_summary_phase()


async def run_pull_notifications_now() -> None:
    """Run the notification cycle now (UDL pull, auto-evaluate, event summaries). A call made
    while a cycle is already running joins that cycle."""
    await _CYCLE.run("notifications", _notification_cycle)


# Mattermost ------------------------------------------------------


_MATTERMOST: SingleFlight[MattermostIngestResult] = SingleFlight()


async def _mattermost_cycle(actor: Any, ip_address: str | None) -> MattermostIngestResult:
    async with get_session_factory()() as db:
        return await ingest_mattermost_messages(db, user_id_actor=actor, ip_address=ip_address)


async def run_mattermost_now(
    actor: Any = None, ip_address: str | None = None
) -> MattermostIngestResult:
    """Sweep the channels and pull them now. A call made while a cycle is running joins it,
    and its audit row carries whoever started that cycle."""
    return await _MATTERMOST.run("mattermost", lambda: _mattermost_cycle(actor, ip_address))


async def _pull_mattermost_once() -> None:
    try:
        await run_mattermost_now()
    except Exception:
        logger.exception("Mattermost ingest crashed unexpectedly")


# Maneuvers ------------------------------------------------------


async def _pull_maneuvers_once() -> None:
    window_hours = get_settings().background_maneuver_window_hours
    window_start = datetime.now(UTC) - timedelta(hours=window_hours)
    try:
        async with UDLClient() as client, get_session_factory()() as db:
            await ingest_maneuvers(
                db,
                client,
                event_start_time_gte=window_start,
                data_mode="REAL",
            )
        logger.info("Maneuver ingest complete (window: last %sh)", window_hours)
    except UDLAuthError as exc:
        logger.warning("Maneuver ingest skipped: UDL auth failed (%s)", exc)
    except UDLClientError as exc:
        logger.warning("Maneuver ingest failed: %s", exc)
    except Exception:
        logger.exception("Maneuver ingest crashed unexpectedly")


# Loops ----------------------------------------------------------


async def run_forever(name: str, work: Callable[[], Awaitable[None]], interval: int) -> None:
    """Run `work` every `interval` seconds until cancelled, surviving any failure."""
    logger.info("Background %s loop enabled: every %ss", name, interval)
    while True:
        try:
            await work()
        except asyncio.CancelledError:
            # A cycle joined from another caller is cancelled when that caller is; only a
            # cancellation of this loop itself (shutdown) may end it.
            task = asyncio.current_task()
            if task is None or task.cancelling():
                raise
            logger.warning("Background %s cycle was cancelled by another caller (continuing)", name)
        except Exception:
            logger.exception("Background %s cycle crashed (continuing)", name)
        await asyncio.sleep(interval)


def start_background_loops() -> list[asyncio.Task[None]]:
    settings = get_settings()
    loops = (
        (
            "notifications",
            run_pull_notifications_now,
            settings.background_notification_interval_seconds,
        ),
        ("maneuvers", _pull_maneuvers_once, settings.background_maneuver_interval_seconds),
        ("mattermost", _pull_mattermost_once, settings.mattermost_interval_seconds),
    )
    return [asyncio.create_task(run_forever(*loop), name=f"holly-{loop[0]}") for loop in loops]


async def stop_background_loops(tasks: list[asyncio.Task[None]]) -> None:
    """Cancel the loops and wait for them. A cancellation of the caller itself still reaches
    the caller; a loop that ended with an error is logged."""
    for task in tasks:
        task.cancel()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for task, result in zip(tasks, results, strict=True):
        if isinstance(result, Exception):
            logger.error("Background task %s exited with error", task.get_name(), exc_info=result)
