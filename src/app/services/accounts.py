"""A user's row read again to change it, locked until the change commits (ADR-014).

A request reads its user when it starts, then spends a bcrypt round or two before it writes. A
write worked out from that first read would undo a change committed meanwhile: a password change
in flight would put back the token version and the password an admin had just reset. So every
change to a password, a role or a status reads the rows it decides on again under a lock, and
decides on what it reads there.

The lock is FOR NO KEY UPDATE: two such changes wait for each other, but a row that merely names
the user, such as a shift note, does not wait, its foreign-key check taking only a KEY SHARE
lock. The rows are locked in one statement, in id order, so two requests locking the same rows
wait in turn rather than deadlock.
"""

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def lock_users(db: AsyncSession, *which: ColumnElement[bool]) -> list[User]:
    """The users matching any of `which`, locked and read afresh, in id order."""
    statement = (
        select(User)
        .where(or_(*which))
        .order_by(User.id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )
    return list((await db.execute(statement)).scalars().all())
