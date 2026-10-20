"""gunicorn settings for the container (gunicorn --config python:app.gunicorn_conf).

The bind comes from the same validated PORT parser as the dev server, so a malformed PORT
stops the container at boot instead of listening on a port the platform does not probe.
"""

import os
from typing import Any

from app.admin_bootstrap import run_admin_bootstrap
from app.config import get_settings, resolve_port
from app.core.logging import configure_logging, log_event
from app.dast_scan import prepare_scan_environment
from app.migrate import run_migrations, wait_for_database

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


def on_starting(server: Any) -> None:
    """In the master, before the worker starts: fill in what the App Store's DAST scan leaves
    out (only under its flag), wait for the database, apply pending migrations, then create the
    first admin from the environment if no account exists, logging in the same JSON form as the
    application. With no database at all, which the settings allow only under the scan flag,
    there is nothing to migrate or bootstrap."""
    configure_logging()
    prepare_scan_environment(os.environ)
    settings = get_settings()
    if settings.has_database():
        wait_for_database(settings.sqlalchemy_url())
        run_migrations()
        run_admin_bootstrap(os.environ)
    else:
        log_event("migrations", status="skipped", reason="no database in this DAST scan")
    # The worker forks from the master next. Its os.environ lacks the admin password, and so
    # does gunicorn's copy of the starting environment (cfg.env_orig), which the worker inherits
    # and a re-exec would start from. /proc/<pid>/environ still shows the block each process
    # started with: removing the variable from the platform, then restarting, is what clears it.
    os.environ.pop("ADMIN_PASSWORD", None)
    server.cfg.env_orig.pop("ADMIN_PASSWORD", None)
