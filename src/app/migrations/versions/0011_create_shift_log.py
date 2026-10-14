"""create shift_note and shift_summary tables

Revision ID: 0011_shift_log
Revises: 0010_create_maneuver
Create Date: 2026-06-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.migrations.columns import timestamp_columns

revision: str = "0011_shift_log"
down_revision: str | None = "0010_create_maneuver"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shift_note",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("shift_date", sa.Date(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("polished_text", sa.Text(), nullable=True),
        sa.Column("polish_error", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["author_id"], ["app_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shift_note_shift_date", "shift_note", ["shift_date"])
    op.create_index("ix_shift_note_author_id", "shift_note", ["author_id"])

    op.create_table(
        "shift_summary",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shift_date", sa.Date(), nullable=False),
        sa.Column("generated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("source_note_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["generated_by"], ["app_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shift_summary_shift_date", "shift_summary", ["shift_date"])


def downgrade() -> None:
    op.drop_index("ix_shift_summary_shift_date", table_name="shift_summary")
    op.drop_table("shift_summary")
    op.drop_index("ix_shift_note_author_id", table_name="shift_note")
    op.drop_index("ix_shift_note_shift_date", table_name="shift_note")
    op.drop_table("shift_note")
