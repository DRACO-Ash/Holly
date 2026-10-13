"""The ASGI entry point the container serves: gunicorn loads app.main:app."""

from app.factory import create_app

app = create_app()
