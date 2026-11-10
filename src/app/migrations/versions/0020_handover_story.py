"""handover story: thread ids on chat posts, thread links, object notes

V0.19's Handover tab tells each object's story from what Holly already holds (the Handover
proposal, docs/roadmap/handover-module.md). Four changes:

- `mattermost_message.root_id`, the Mattermost thread a reply belongs to, so posts group into
  threads. It was only inside `raw`; posts already held get it from there when it is a plain id.
- A GIN index on `notification.sat_ids`, so an object's notices are found by containment, and an
  index on `notification.event_id`, so a link decision finds its notice without a scan.
- `handover_thread_link`: a mission lead's decision that a chat thread is, or is not, about a
  logical notice (its group key). Holly only suggests a link; only a confirmed one is used.
- `handover_note`: an analyst's free-text note on an object, by catalogue number.

Revision ID: 0020_handover_story
Revises: 0019_mattermost_channel
Create Date: 2026-11-10

"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_handover_story"
down_revision: str | None = "0019_mattermost_channel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[Any]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _user(name: str) -> sa.Column[Any]:
    return sa.Column(
        name,
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("app_user.id", ondelete="SET NULL"),
        nullable=True,
    )


def upgrade() -> None:
    op.add_column("mattermost_message", sa.Column("root_id", sa.String(64), nullable=True))
    # The same plain-id rule the ingest applies to every id it stores (PLAIN_ID).
    op.execute(
        "UPDATE mattermost_message SET root_id = raw->>'root_id' "
        "WHERE raw->>'root_id' ~ '^[A-Za-z0-9_-]{1,64}$'"
    )
    op.create_index("ix_mattermost_message_root_id", "mattermost_message", ["root_id"])
    op.create_index(
        "ix_notification_sat_ids",
        "notification",
        ["sat_ids"],
        postgresql_using="gin",
        postgresql_ops={"sat_ids": "jsonb_path_ops"},
    )
    op.create_index("ix_notification_event_id", "notification", ["event_id"])
    op.create_table(
        "handover_thread_link",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", sa.String(64), nullable=False),
        sa.Column("event_key", sa.String(200), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        _user("decided_by"),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("thread_id", "event_key", name="uq_handover_thread_link"),
        sa.CheckConstraint(
            "decision IN ('confirmed', 'rejected')", name="ck_handover_thread_link_decision"
        ),
    )
    op.create_index("ix_handover_thread_link_event_key", "handover_thread_link", ["event_key"])
    op.create_table(
        "handover_note",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sat_no", sa.Integer(), nullable=False),
        _user("author_id"),
        sa.Column("text", sa.Text(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_handover_note_sat_no", "handover_note", ["sat_no"])


def downgrade() -> None:
    op.drop_index("ix_handover_note_sat_no", table_name="handover_note")
    op.drop_table("handover_note")
    op.drop_index("ix_handover_thread_link_event_key", table_name="handover_thread_link")
    op.drop_table("handover_thread_link")
    op.drop_index("ix_notification_event_id", table_name="notification")
    op.drop_index("ix_notification_sat_ids", table_name="notification")
    op.drop_index("ix_mattermost_message_root_id", table_name="mattermost_message")
    op.drop_column("mattermost_message", "root_id")
