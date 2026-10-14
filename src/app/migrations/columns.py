"""Column groups the migrations share.

Frozen: migrations that have already run import these, so changing one would change the
history those migrations describe. A table that needs a different shape gets a new function.
"""

from typing import Any

import sqlalchemy as sa


def timestamp_columns() -> list[sa.Column[Any]]:
    """created_at and updated_at, both set by the database when a row is written."""
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
        for name in ("created_at", "updated_at")
    ]
