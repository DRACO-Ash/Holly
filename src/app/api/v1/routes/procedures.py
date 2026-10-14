"""Operator-uploaded procedures: stored on the procedure volume, indexed in the database, and
read by the assistant when it evaluates a notification.

Uploads are capped at 10 MB (and the whole request body at core/body_limit.py's limit). Every
download is an attachment of type application/octet-stream, whatever type the uploader
claimed, so a stored file can never render as a page in Holly's origin.
"""

import hashlib
import logging
import re
import uuid
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.common import get_or_404
from app.core.net import client_ip
from app.dependencies import CurrentUser, DbSession
from app.models.procedure import Procedure
from app.models.user import User
from app.schemas.procedure import ProcedureContent, ProcedurePage, ProcedureRead
from app.services.audit import write_audit
from app.services.procedure_storage import (
    delete_file,
    read_file_bytes,
    read_preview,
    write_file,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/procedures", tags=["procedures"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_MAX_FILENAME_CHARS = 255
_MAX_CONTENT_TYPE_CHARS = 100
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def _attachment_disposition(filename: str) -> str:
    """An attachment header that names the file safely: a plain ASCII fallback, plus the
    exact name percent-encoded (RFC 6266), so no uploaded name can break the header."""
    fallback = _UNSAFE_FILENAME_CHARS.sub("_", filename)[:100] or "procedure"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"


@router.get("")
async def list_procedures(db: DbSession, _current_user: CurrentUser) -> ProcedurePage:
    items = (await db.execute(select(Procedure).order_by(Procedure.created_at.desc()))).scalars()
    total = (await db.execute(select(func.count()).select_from(Procedure))).scalar_one()
    return ProcedurePage(items=[ProcedureRead.model_validate(p) for p in items.all()], total=total)


@router.get("/{procedure_id}")
async def get_procedure(
    procedure_id: UUID, db: DbSession, _current_user: CurrentUser
) -> ProcedureContent:
    procedure: Procedure = await get_or_404(db, Procedure, procedure_id, "Procedure")
    content, truncated = read_preview(procedure.id, procedure.filename, procedure.content_type)
    return ProcedureContent(
        **ProcedureRead.model_validate(procedure).model_dump(),
        content=content,
        content_truncated=truncated,
    )


@router.get("/{procedure_id}/download")
async def download_procedure(
    procedure_id: UUID, db: DbSession, _current_user: CurrentUser
) -> Response:
    procedure: Procedure = await get_or_404(db, Procedure, procedure_id, "Procedure")
    try:
        content = read_file_bytes(procedure.id, procedure.filename)
    except FileNotFoundError:
        # A row whose file is gone: one uploaded before V0.2, when every upload was written to
        # the same file, or a store that was replaced. The row stays; the file must be re-uploaded.
        logger.warning("Procedure %s has no file in the store", procedure.id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The file for this procedure is missing; upload it again.",
        ) from None
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": _attachment_disposition(procedure.filename)},
    )


async def _store(
    db: AsyncSession, procedure: Procedure, user: User, ip_address: str | None
) -> None:
    """Insert the procedure's row and its audit entry, and commit; 409 for a duplicate file."""
    db.add(procedure)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A procedure with identical content already exists",
        ) from None
    await write_audit(
        db,
        action_type="procedure.upload",
        entity_type="procedure",
        entity_id=str(procedure.id),
        user_id=user.id,
        ip_address=ip_address,
        detail={
            "name": procedure.name,
            "filename": procedure.filename,
            "size_bytes": procedure.size_bytes,
        },
    )
    await db.commit()


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_procedure(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    # At least one character that is not whitespace: the name is stored stripped.
    name: Annotated[str, Form(min_length=1, max_length=200, pattern=r"\S")],
    file: Annotated[UploadFile, File()],
    description: Annotated[str | None, Form(max_length=4000)] = None,
) -> ProcedureRead:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty"
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit",
        )
    filename = (file.filename or "procedure")[:_MAX_FILENAME_CHARS]
    content_type = (file.content_type or "application/octet-stream")[:_MAX_CONTENT_TYPE_CHARS]

    # The id is set here, not left to the INSERT, because the stored file is named after it:
    # without it every upload was written to the same "None" file.
    procedure = Procedure(
        id=uuid.uuid4(),
        name=name.strip(),
        description=(description.strip() or None) if description else None,
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        file_hash=hashlib.sha256(data).hexdigest(),
        uploaded_by=current_user.id,
    )
    write_file(procedure.id, filename, data)
    try:
        await _store(db, procedure, current_user, client_ip(request))
    except Exception:
        # Whatever stopped the row being stored, a duplicate included, its file goes too.
        delete_file(procedure.id, filename)
        raise
    await db.refresh(procedure)
    return ProcedureRead.model_validate(procedure)


@router.delete("/{procedure_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_procedure(
    procedure_id: UUID, request: Request, db: DbSession, current_user: CurrentUser
) -> None:
    procedure: Procedure = await get_or_404(db, Procedure, procedure_id, "Procedure")
    await db.delete(procedure)
    await write_audit(
        db,
        action_type="procedure.delete",
        entity_type="procedure",
        entity_id=str(procedure.id),
        user_id=current_user.id,
        ip_address=client_ip(request),
        detail={"name": procedure.name, "filename": procedure.filename},
    )
    await db.commit()
    # The file goes only once the row is gone: a failed commit leaves both in place.
    delete_file(procedure.id, procedure.filename)
