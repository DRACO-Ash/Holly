"""add recurrence_anchor to event_timer

A recurring timer now counts each occurrence from its first one, so a monthly timer set for the
31st returns to the 31st after a shorter month instead of drifting to the 28th. Existing
recurring timers take their current target as the anchor: a timer that has already drifted
keeps its drifted day.

Revision ID: 0016_timer_recurrence_anchor
Revises: 0015_mattermost
Create Date: 2026-10-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_timer_recurrence_anchor"
down_revision: str | None = "0015_mattermost"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "event_timer",
        sa.Column("recurrence_anchor", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE event_timer SET recurrence_anchor = target_time WHERE recurrence <> 'none'")


def downgrade() -> None:
    op.drop_column("event_timer", "recurrence_anchor")
