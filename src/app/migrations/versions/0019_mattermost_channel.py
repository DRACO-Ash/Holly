"""create mattermost_channel

Holly now finds the Mattermost channels its bot can read, instead of reading a fixed list from
MATTERMOST_CHANNEL_IDS (ADR-015). Each row is a public or private channel as the latest sweep
found it: open or closed, followed or not, new until someone reviews it. The messages table is
unchanged.

Revision ID: 0019_mattermost_channel
Revises: 0018_user_password_state
Create Date: 2026-10-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_mattermost_channel"
down_revision: str | None = "0018_user_password_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mattermost_channel",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("mm_channel_id", sa.String(64), nullable=False),
        sa.Column("team_id", sa.String(64), nullable=True),
        sa.Column("team_name", sa.String(200), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("channel_type", sa.String(8), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accessible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("following", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("following_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "following_changed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("mm_channel_id", name="uq_mattermost_channel_mm_channel_id"),
    )


def downgrade() -> None:
    op.drop_table("mattermost_channel")
