"""The ASGI entry point the container serves: gunicorn loads app.main:app."""

from app.core.logging import configure_logging
from app.factory import create_app

configure_logging()
app = create_app()
