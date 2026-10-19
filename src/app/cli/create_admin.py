"""Create or update an admin user, and record it in the audit chain.

Inside the container (or any environment with the database settings):

    python -m app.cli.create_admin --username alice

The password comes from the ADMIN_PASSWORD environment variable, or is prompted for. It is
never accepted as a command-line argument, which would leave it in the shell history and the
process list. Running it again for an existing username resets the password and the admin role.
"""

import argparse
import asyncio
import os
import sys
from getpass import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.db.storable import storable_text
from app.models.user import User, UserRole
from app.services.audit import write_audit

MIN_PASSWORD_LENGTH = 12
MAX_USERNAME_LENGTH = 50
MAX_EMAIL_LENGTH = 255


CLI_PROBLEMS = {
    "password": "The admin password holds a character that is not valid UTF-8 text.",
    "username": f"The admin username must be 1 to {MAX_USERNAME_LENGTH} printable characters.",
    "email": f"The admin email must be at most {MAX_EMAIL_LENGTH} printable characters.",
}


def _fits(value: str, limit: int) -> bool:
    return 0 < len(value) <= limit and storable_text(value) and value.isprintable()


def unstorable_field(username: str, password: str, email: str | None) -> str | None:
    """The field ("password", "username" or "email") that cannot be hashed or stored, or None.

    Checked before any query: bcrypt names a character that will not encode, and the database's
    refusal of a value would print the statement that carried it."""
    if not storable_text(password):
        return "password"
    if not _fits(username, MAX_USERNAME_LENGTH):
        return "username"
    if email is not None and not _fits(email, MAX_EMAIL_LENGTH):
        return "email"
    return None


async def upsert_admin(username: str, password: str, email: str | None = None) -> str:
    async with get_session_factory()() as session:
        username = username.strip().lower()
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        action = "updated"
        if user is None:
            user = User(username=username, email=email)
            session.add(user)
            action = "created"
        user.password_hash = hash_password(password)
        user.role = UserRole.ADMIN.value
        user.is_active = True
        if email is not None:
            user.email = email
        await session.flush()
        await write_audit(
            session,
            action_type="auth.user.admin_upsert",
            entity_type="user",
            entity_id=str(user.id),
            detail={"username": username, "action": action},
        )
        await session.commit()
    return action


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or update an admin user.")
    parser.add_argument("--username", default=os.environ.get("ADMIN_USERNAME"))
    parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL"))
    args = parser.parse_args(argv)

    username = (args.username or input("Username (admin): ")).strip()
    password = os.environ.get("ADMIN_PASSWORD") or getpass("Admin password (hidden): ")
    if not username or not password.strip():
        sys.stderr.write("A username and a password are both required.\n")
        return 2
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.stderr.write(f"Use at least {MIN_PASSWORD_LENGTH} characters for the admin password.\n")
        return 2
    email = args.email.strip() if args.email and args.email.strip() else None
    field = unstorable_field(username.lower(), password, email)
    if field is not None:
        sys.stderr.write(f"{CLI_PROBLEMS[field]}\n")
        return 2

    action = asyncio.run(upsert_admin(username, password, email))
    sys.stdout.write(f"Admin user '{username.lower()}' {action}.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
