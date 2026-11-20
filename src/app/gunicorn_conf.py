"""gunicorn settings for the container (gunicorn --config python:app.gunicorn_conf).

The bind comes from the same validated PORT parser as the dev server, so a malformed PORT
stops the container at boot instead of listening on a port the platform does not probe.

A refusal to start is written as one FATAL line in the logging standard's form on stdout, then
the process exits 1. gunicorn would otherwise print a bare "Error: <message>" to stderr, which
the standard does not allow.
"""

import logging
import os
from collections.abc import Callable, Mapping
from typing import Any, NoReturn

from app.admin_bootstrap import run_admin_bootstrap
from app.config import get_settings, resolve_port
from app.core.logging import GUNICORN_LOGCONFIG, configure_logging, log_event
from app.dast_scan import prepare_scan_environment
from app.migrate import run_migrations, wait_for_database


def _refuse(error: Exception) -> NoReturn:
    log_event(
        "refused",
        level=logging.CRITICAL,
        exc_info=(type(error), error, error.__traceback__),
        reason=str(error),
    )
    raise SystemExit(1) from error


def _refusing_on_error[T](step: Callable[[], T]) -> T:
    try:
        return step()
    # Every refusal is logged the same way and then exits.
    except Exception as error:  # noqa: BLE001
        _refuse(error)


def _port(environ: Mapping[str, str]) -> int:
    return _refusing_on_error(lambda: resolve_port(environ))


# The App Store contract binds every interface.
bind = f"0.0.0.0:{_port(os.environ)}"
worker_class = "uvicorn_worker.UvicornWorker"
# Exactly one worker: the background refresh loops (UDL, Mattermost, the assistant) run inside
# the worker, so a second worker would pull and bill everything twice. The rate limits and the
# daily assistant cap also count in this one process.
workers = 1
# gunicorn 25.1 and later open an admin control socket under $HOME by default. Holly needs no
# runtime admin interface, and the non-root user has no home directory to hold one.
control_socket_disable = True
# gunicorn's own lines, and the uvicorn worker's, as JSON on stdout like the application's.
logconfig_dict = GUNICORN_LOGCONFIG


def on_starting(server: Any) -> None:
    """In the master, before the worker starts: fill in what the App Store's DAST scan leaves
    out (only under its flag), wait for the database, apply pending migrations, then create the
    first admin from the environment if no account exists, logging in the same JSON form as the
    application. With no database at all, which the settings allow only under the scan flag,
    there is nothing to migrate or bootstrap. Any failure is a logged refusal."""
    configure_logging()
    _refusing_on_error(lambda: _start(server))


def _start(server: Any) -> None:
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
