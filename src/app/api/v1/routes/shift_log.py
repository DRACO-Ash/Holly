"""The ops-floor shift log: notes polished by the assistant, an end-of-shift narrative, and an
export of either as Markdown or HTML.

Polishing a note, re-polishing it and generating the summary each call the assistant, so each
counts against the caller's assistant limit (core/rate_limit.py).
"""

import html
from datetime import UTC, datetime, timedelta
from datetime import date as date_t
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.common import get_or_404
from app.core.net import client_ip
from app.core.rate_limit import ASSISTANT_LIMIT
from app.dependencies import CurrentUser, DbSession
from app.models.shift_note import ShiftNote
from app.models.shift_summary import ShiftSummary
from app.models.user import User
from app.schemas.shift import (
    ShiftDateList,
    ShiftDateSummary,
    ShiftNoteCreate,
    ShiftNoteList,
    ShiftNoteRead,
    ShiftNoteUpdate,
    ShiftSummaryRead,
)
from app.services.audit import write_audit
from app.services.shift_log import polish_text, summarise_shift

router = APIRouter(prefix="/shift-log", tags=["shift-log"])

ExportFormat = Literal["md", "html"]
_TITLE = "Daily Operations Shift Log"


def _today_utc() -> date_t:
    return datetime.now(UTC).date()


async def _notes_for(db: AsyncSession, shift_date: date_t) -> list[ShiftNote]:
    stmt = (
        select(ShiftNote)
        .where(ShiftNote.shift_date == shift_date)
        .order_by(ShiftNote.created_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def _latest_summary(db: AsyncSession, shift_date: date_t) -> ShiftSummary | None:
    """The newest narrative that was generated, so a failed attempt never hides an earlier good
    one; the newest failed attempt only when none succeeded."""
    stmt = (
        select(ShiftSummary)
        .where(ShiftSummary.shift_date == shift_date)
        .order_by(ShiftSummary.error.is_not(None), desc(ShiftSummary.created_at))
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _audit_note(
    db: AsyncSession,
    request: Request,
    user: User,
    action_type: str,
    note_id: UUID,
    detail: dict[str, object],
) -> None:
    await write_audit(
        db,
        action_type=action_type,
        entity_type="shift_note",
        entity_id=str(note_id),
        user_id=user.id,
        ip_address=client_ip(request),
        detail=detail,
    )


# Dates ----------------------------------------------------------


@router.get("/dates")
async def list_shift_dates(
    db: DbSession,
    _current_user: CurrentUser,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> ShiftDateList:
    """Dates in the last `days` with at least one note, newest first.

    Each entry carries its note count and whether an end-of-shift summary exists, so the
    operator can pick out the shifts with content without stepping through the date picker.
    """
    cutoff = _today_utc() - timedelta(days=days)
    counts_stmt = (
        select(
            ShiftNote.shift_date.label("shift_date"),
            func.count(ShiftNote.id).label("note_count"),
        )
        .where(ShiftNote.shift_date >= cutoff)
        .group_by(ShiftNote.shift_date)
        .order_by(desc(ShiftNote.shift_date))
    )
    rows = (await db.execute(counts_stmt)).all()
    summary_dates_stmt = (
        select(ShiftSummary.shift_date).where(ShiftSummary.shift_date >= cutoff).distinct()
    )
    summary_dates = {row[0] for row in (await db.execute(summary_dates_stmt)).all()}
    return ShiftDateList(
        items=[
            ShiftDateSummary(
                shift_date=row.shift_date,
                note_count=row.note_count,
                has_summary=row.shift_date in summary_dates,
            )
            for row in rows
        ]
    )


# Notes ----------------------------------------------------------


@router.get("/notes")
async def list_notes(
    db: DbSession, _current_user: CurrentUser, shift_date: date_t | None = None
) -> ShiftNoteList:
    target = shift_date or _today_utc()
    notes = await _notes_for(db, target)
    return ShiftNoteList(items=[ShiftNoteRead.model_validate(n) for n in notes], shift_date=target)


@router.post("/notes", status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: ShiftNoteCreate, request: Request, db: DbSession, current_user: CurrentUser
) -> ShiftNoteRead:
    raw = payload.raw_text.strip()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Note text cannot be empty."
        )
    # The note is the analyst's own record and is always kept: when the assistant limit is
    # spent, only the polishing waits, and the note can be re-polished later.
    wait = ASSISTANT_LIMIT.retry_after(str(current_user.id))
    if wait:
        polished, model = None, None
        error: str | None = (
            f"Not polished: the assistant limit is reached. Re-polish in {wait} seconds."
        )
    else:
        polished, model, error = await polish_text(raw)
    note = ShiftNote(
        author_id=current_user.id,
        shift_date=payload.shift_date or _today_utc(),
        raw_text=raw,
        polished_text=polished,
        polish_error=error,
        model=model,
    )
    db.add(note)
    await db.flush()
    await _audit_note(
        db,
        request,
        current_user,
        "shift_log.note.create",
        note.id,
        {"shift_date": note.shift_date.isoformat(), "had_error": error is not None},
    )
    await db.commit()
    await db.refresh(note)
    return ShiftNoteRead.model_validate(note)


@router.patch("/notes/{note_id}")
async def update_note(
    note_id: UUID,
    payload: ShiftNoteUpdate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> ShiftNoteRead:
    note: ShiftNote = await get_or_404(db, ShiftNote, note_id, "Note")
    if payload.polished_text is not None:
        note.polished_text = payload.polished_text.strip() or None
        note.polish_error = None
    await db.flush()
    await _audit_note(
        db,
        request,
        current_user,
        "shift_log.note.update",
        note.id,
        {"shift_date": note.shift_date.isoformat()},
    )
    await db.commit()
    await db.refresh(note)
    return ShiftNoteRead.model_validate(note)


@router.post("/notes/{note_id}/repolish")
async def repolish_note(
    note_id: UUID, request: Request, db: DbSession, current_user: CurrentUser
) -> ShiftNoteRead:
    note: ShiftNote = await get_or_404(db, ShiftNote, note_id, "Note")
    ASSISTANT_LIMIT.check(str(current_user.id))
    polished, model, error = await polish_text(note.raw_text)
    # A failed attempt keeps the text the note already had, an analyst's own edit included.
    if error is None:
        note.polished_text, note.model = polished, model
    note.polish_error = error
    await db.flush()
    await _audit_note(
        db,
        request,
        current_user,
        "shift_log.note.repolish",
        note.id,
        {"had_error": note.polish_error is not None},
    )
    await db.commit()
    await db.refresh(note)
    return ShiftNoteRead.model_validate(note)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: UUID, request: Request, db: DbSession, current_user: CurrentUser
) -> None:
    note: ShiftNote = await get_or_404(db, ShiftNote, note_id, "Note")
    shift_date = note.shift_date
    await db.delete(note)
    await _audit_note(
        db,
        request,
        current_user,
        "shift_log.note.delete",
        note_id,
        {"shift_date": shift_date.isoformat()},
    )
    await db.commit()


# Summary --------------------------------------------------------


@router.get("/summary")
async def get_summary(
    db: DbSession, _current_user: CurrentUser, shift_date: date_t | None = None
) -> ShiftSummaryRead | None:
    row = await _latest_summary(db, shift_date or _today_utc())
    return ShiftSummaryRead.model_validate(row) if row is not None else None


@router.post("/summary")
async def generate_summary(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    shift_date: date_t | None = None,
) -> ShiftSummaryRead:
    target = shift_date or _today_utc()
    notes = await _notes_for(db, target)
    if not notes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No notes recorded for {target.isoformat()}.",
        )
    ASSISTANT_LIMIT.check(str(current_user.id))
    narrative, model, error = await summarise_shift(notes)
    summary = ShiftSummary(
        shift_date=target,
        generated_by=current_user.id,
        narrative=narrative or "Summary could not be generated.",
        source_note_ids=[str(n.id) for n in notes],
        model=model,
        error=error,
    )
    db.add(summary)
    await db.flush()
    await write_audit(
        db,
        action_type="shift_log.summary.generate",
        entity_type="shift_summary",
        entity_id=str(summary.id),
        user_id=current_user.id,
        ip_address=client_ip(request),
        detail={
            "shift_date": target.isoformat(),
            "note_count": len(notes),
            "had_error": error is not None,
        },
    )
    await db.commit()
    await db.refresh(summary)
    return ShiftSummaryRead.model_validate(summary)


# Export ---------------------------------------------------------


def _timestamp(note: ShiftNote) -> str:
    return note.created_at.strftime("%Y-%m-%d %H:%M:%SZ") if note.created_at else "?"


def _body(note: ShiftNote) -> str:
    return (note.polished_text or note.raw_text).strip()


def build_markdown(shift_date: date_t, notes: list[ShiftNote], summary: ShiftSummary | None) -> str:
    parts = [f"# {_TITLE}: {shift_date.isoformat()}", ""]
    if summary is not None:
        parts += ["## End-of-shift narrative", "", summary.narrative.strip(), ""]
    parts += ["## Timeline", ""]
    for note in notes:
        parts += [f"**{_timestamp(note)}**", "", _body(note), ""]
    return "\n".join(parts).rstrip() + "\n"


_EXPORT_STYLE = """\
    body { font-family: 'Segoe UI', system-ui, sans-serif; max-width: 820px;
           margin: 40px auto; padding: 0 24px; color: #1f2937; line-height: 1.55; }
    h1 { font-weight: 300; font-size: 1.8rem; border-bottom: 2px solid #385FAF;
         padding-bottom: 8px; }
    h2 { color: #162646; margin-top: 32px; font-weight: 500; }
    .timeline-entry { margin-bottom: 18px; padding: 10px 14px;
                      border-left: 3px solid #385FAF; background: #f6f8fc; }
    .timeline-ts { font-size: 0.8rem; color: #6b7785; letter-spacing: 0.06em;
                   text-transform: uppercase; margin-bottom: 4px; }
    .narrative { padding: 16px; background: #f6f8fc; border-radius: 6px;
                 white-space: pre-wrap; }
    @media print {
      body { max-width: none; margin: 0; }
      .timeline-entry { page-break-inside: avoid; }
    }
    """


def build_html(shift_date: date_t, notes: list[ShiftNote], summary: ShiftSummary | None) -> str:
    """A standalone HTML export. Every stored value is escaped (html.escape)."""
    date_text = html.escape(shift_date.isoformat())
    body = [f"<h1>{html.escape(_TITLE)}: {date_text}</h1>"]
    if summary is not None:
        body.append("<h2>End-of-shift narrative</h2>")
        body.append(f'<div class="narrative">{html.escape(summary.narrative.strip())}</div>')
    body.append("<h2>Timeline</h2>")
    body.extend(
        '<div class="timeline-entry">'
        f'<div class="timeline-ts">{html.escape(_timestamp(note))}</div>'
        f"<div>{html.escape(_body(note))}</div>"
        "</div>"
        for note in notes
    )
    return (
        "<!doctype html>\n<html><head><meta charset='utf-8'>"
        f"<title>Shift log {date_text}</title>"
        f"<style>{_EXPORT_STYLE}</style></head><body>" + "\n".join(body) + "</body></html>"
    )


@router.get("/export")
async def export_shift(
    db: DbSession,
    _current_user: CurrentUser,
    shift_date: date_t | None = None,
    fmt: Annotated[ExportFormat, Query(alias="format")] = "md",
) -> Response:
    target = shift_date or _today_utc()
    notes = await _notes_for(db, target)
    summary = await _latest_summary(db, target)
    if fmt == "html":
        content, media_type = build_html(target, notes, summary), "text/html"
    else:
        content, media_type = build_markdown(target, notes, summary), "text/markdown"
    filename = f"shift-log-{target.isoformat()}.{fmt}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
