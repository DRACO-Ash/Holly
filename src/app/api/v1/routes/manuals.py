"""The Help page's manuals: which the caller may read, and each one's Markdown. The operator
manual is for operators and admins; anyone else is refused here, on the server."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from app.dependencies import CurrentUser
from app.schemas.manuals import ManualRead, ManualSummary
from app.services.manuals import find_manual, manual_text, manuals_for

router = APIRouter(prefix="/manuals", tags=["manuals"])

Slug = Annotated[str, Path(pattern=r"^[a-z]{1,32}$")]


@router.get("")
async def list_manuals(user: CurrentUser) -> list[ManualSummary]:
    """The manuals this user may read, in the order the Help page shows them."""
    return [ManualSummary(slug=m.slug, title=m.title) for m in manuals_for(user.role)]


@router.get("/{slug}")
async def read_manual(slug: Slug, user: CurrentUser) -> ManualRead:
    manual = find_manual(slug)
    if manual is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manual not found")
    if user.role not in manual.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges for this action"
        )
    text = manual_text(manual)
    if text is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="This release does not carry the manual.",
        )
    return ManualRead(slug=manual.slug, title=manual.title, markdown=text)
