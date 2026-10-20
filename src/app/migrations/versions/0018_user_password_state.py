"""add must_change_password and token_version to app_user

An admin now creates accounts and resets passwords from the Users page (ADR-014). An account an
admin set a password for must choose its own before it can do anything else, and every token
carries the version it was issued under, so a password change, a reset or a deactivation ends
every session that came before. Existing accounts keep their passwords and their sessions.

Revision ID: 0018_user_password_state
Revises: 0017_audit_append_only
Create Date: 2026-10-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_user_password_state"
down_revision: str | None = "0017_audit_append_only"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_user",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "app_user",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("app_user", "token_version")
    op.drop_column("app_user", "must_change_password")
