"""Structured logging: one JSON object per line on stdout, each carrying the request id.

Two writers share the format. log_event records a named event (boot, shutdown, an assistant
call) with its fields; the standard logging module, configured here, carries everything else.
Neither is ever given a secret value.
"""

import json
import logging
import sys
from datetime import UTC, datetime

from app.core.request_id import current_request_id

SERVICE_NAME = "holly"


def log_event(event: str, **fields: object) -> None:
    """Write one structured JSON log line to stdout. Never pass a secret value."""
    line = {"event": event, "service": SERVICE_NAME, "request_id": current_request_id(), **fields}
    sys.stdout.write(json.dumps(line, default=str) + "\n")
    sys.stdout.flush()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": SERVICE_NAME,
            "request_id": current_request_id(),
            "message": record.getMessage(),
        }
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str)


class StdoutHandler(logging.Handler):
    """Writes each record to whatever sys.stdout is when the record is emitted, as log_event
    does, so a replaced stdout (a test's capture, say) never leaves a handler on a closed one."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            sys.stdout.write(self.format(record) + "\n")
            sys.stdout.flush()
        except Exception:  # noqa: BLE001  logging must never raise into the caller
            self.handleError(record)


def configure_logging() -> None:
    handler = StdoutHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
