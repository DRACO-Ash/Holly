"""make audit.audit_log append-only

ADR-005 records the audit log as INSERT-only, but no migration enforced it. A statement-level
trigger now refuses every UPDATE, DELETE and TRUNCATE on the table, whether it would touch rows
or not. The database owner can still disable the trigger deliberately; the hash chain
(python -m app.cli.verify_audit) detects any change made that way.

Revision ID: 0017_audit_append_only
Revises: 0016_timer_recurrence_anchor
Create Date: 2026-10-14

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017_audit_append_only"
down_revision: str | None = "0016_timer_recurrence_anchor"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION audit.refuse_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit.audit_log is append-only';
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER audit_log_append_only "
        "BEFORE UPDATE OR DELETE OR TRUNCATE ON audit.audit_log "
        "FOR EACH STATEMENT EXECUTE FUNCTION audit.refuse_change()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_log_append_only ON audit.audit_log")
    op.execute("DROP FUNCTION audit.refuse_change()")
