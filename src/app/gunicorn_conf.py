"""gunicorn settings for the container (gunicorn --config python:app.gunicorn_conf).

The bind comes from the same validated PORT parser as the dev server, so a malformed PORT
stops the container at boot instead of listening on a port the platform does not probe.
"""

import os

from app.config import resolve_port

# The App Store contract binds every interface.
bind = f"0.0.0.0:{resolve_port(os.environ)}"
worker_class = "uvicorn_worker.UvicornWorker"
# gunicorn 25.1 and later open an admin control socket under $HOME by default. Holly needs no
# runtime admin interface, and the non-root user has no home directory to hold one.
control_socket_disable = True
