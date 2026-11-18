"""object watch: each analyst's watch list and when they last looked at an object

V0.20's Object Lens (docs/roadmap/object-lens-proposal.html) keeps, per analyst and object,
whether the object is on their watch strip and when they last looked at it in the lens, so the
lens can mark what is new. One row per analyst and object; deleting the analyst deletes the rows.

Revision ID: 0021_object_watch
Revises: 0020_handover_story
Create Date: 2026-11-18

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_object_watch"
down_revision: str | None = "0020_handover_story"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "object_watch",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sat_no", sa.Integer(), nullable=False),
        sa.Column("pinned", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "sat_no", name="uq_object_watch_user_sat"),
    )


def downgrade() -> None:
    op.drop_table("object_watch")
