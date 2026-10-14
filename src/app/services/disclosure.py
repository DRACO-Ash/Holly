"""Which notifications may be shown to the assistant (Anthropic).

A notification's content goes to the assistant only when its UDL classification marking is one
the data owner has cleared (ASSISTANT_CLEARED_MARKINGS, exactly U by default). A notice with
any other marking, or none, never leaves Holly: a control that cannot be verified is treated as
failed. The evaluation path checks each notice, and the background cycle selects only cleared
ones, so a notice that is not cleared is never sent, never retried and never billed.
"""

from sqlalchemy import ColumnElement

from app.config import get_settings
from app.models.notification import Notification

NOT_CLEARED = (
    "Not sent to the assistant: this notice's classification marking is not cleared for it "
    "(ASSISTANT_CLEARED_MARKINGS)."
)


def cleared_markings() -> list[str]:
    return [marking.strip() for marking in get_settings().assistant_cleared_markings]


def is_cleared(notification: Notification) -> bool:
    return notification.classification_marking in cleared_markings()


def cleared_condition() -> ColumnElement[bool]:
    """is_cleared as SQL, for the queries that choose what the assistant sees."""
    return Notification.classification_marking.in_(cleared_markings())
