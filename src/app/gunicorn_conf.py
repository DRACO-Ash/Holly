"""gunicorn settings for the container (gunicorn --config python:app.gunicorn_conf).

The bind comes from the same validated PORT parser as the dev server, so a malformed PORT
stops the container at boot instead of listening on a port the platform does not probe.
"""

import os

from app.config import resolve_port
from app.core.logging import configure_logging
from app.migrate import run_migrations

# The App Store contract binds every interface.
bind = f"0.0.0.0:{resolve_port(os.environ)}"
worker_class = "uvicorn_worker.UvicornWorker"
# Exactly one worker: the background refresh loops (UDL, Mattermost, the assistant) run inside
# the worker, so a second worker would pull and bill everything twice. The rate limits and the
# daily assistant cap also count in this one process.
workers = 1
# gunicorn 25.1 and later open an admin control socket under $HOME by default. Holly needs no
# runtime admin interface, and the non-root user has no home directory to hold one.
control_socket_disable = True


def on_starting(_server: object) -> None:
    """Apply pending database migrations in the master, before the worker starts, logging in
    the same JSON form as the application."""
    configure_logging()
    run_migrations()
