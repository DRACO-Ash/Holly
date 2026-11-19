"""Structured logging to the App Store's logging standard: one JSON object per line on stdout.

Every line has exactly these top-level fields: timestamp (UTC, milliseconds), severity_text,
severity_number, body and attributes, a flat object holding everything else. A line written
while a request is handled carries the request's id (and the signed-in email the platform's
gateway names, when it sends one) in its attributes. An exception goes into the attributes as
exception.type, exception.message and exception.stacktrace.

Two writers share the format. log_event records a named event (boot, shutdown, an assistant
call) with its fields; the standard logging module, configured here, carries everything else,
gunicorn's and uvicorn's own lines included (app/gunicorn_conf.py). Neither is ever given a
secret value, and a query string in any URL is cut before the line is written.
"""

import json
import logging
import re
import sys
import traceback
from collections.abc import Mapping
from datetime import UTC, datetime
from types import TracebackType
from typing import Any

from app.core.request_id import current_request_attributes

SERVICE_NAME = "holly"

# The standard's severity pairs, from the record's level.
_SEVERITIES: tuple[tuple[int, str, int], ...] = (
    (logging.CRITICAL, "FATAL", 21),
    (logging.ERROR, "ERROR", 17),
    (logging.WARNING, "WARN", 13),
    (logging.INFO, "INFO", 9),
    (logging.DEBUG, "DEBUG", 5),
)

# A URL's query string, cut wherever it appears in a line: it can carry a key or a search.
_QUERY = re.compile(r"(\bhttps?://[^\s?#\"'<>]+)\?[^\s#\"'<>]*")

ExcInfo = tuple[type[BaseException], BaseException, TracebackType | None]


def severity(level: int) -> tuple[str, int]:
    for floor, text, number in _SEVERITIES:
        if level >= floor:
            return text, number
    return "TRACE", 1


def without_query(text: str) -> str:
    return _QUERY.sub(r"\1?[query removed]", text)


def _scalar(value: object) -> object:
    if value is None or isinstance(value, bool | int | float):
        return value
    return without_query(str(value))


def _flatten(fields: Mapping[str, object], prefix: str = "") -> dict[str, object]:
    """Nested mappings become dotted keys, so the attributes stay one flat object. A list or
    tuple stays a list of plain values."""
    flat: dict[str, object] = {}
    for key, value in fields.items():
        name = f"{prefix}{key}"
        if isinstance(value, Mapping):
            flat.update(_flatten(value, f"{name}."))
        elif isinstance(value, list | tuple):
            flat[name] = [_scalar(item) for item in value]
        else:
            flat[name] = _scalar(value)
    return flat


def _exception(exc_info: ExcInfo) -> dict[str, object]:
    kind, error, trace = exc_info
    return {
        "exception.type": kind.__name__,
        "exception.message": str(error),
        "exception.stacktrace": "".join(traceback.format_exception(kind, error, trace)),
    }


def log_line(
    body: str,
    *,
    level: int = logging.INFO,
    created: float | None = None,
    attributes: Mapping[str, object] | None = None,
    exc_info: ExcInfo | None = None,
) -> str:
    """One line in the standard's form, the request's attributes added to the caller's."""
    when = datetime.now(UTC) if created is None else datetime.fromtimestamp(created, UTC)
    text, number = severity(level)
    merged: dict[str, object] = _flatten(attributes or {})
    if exc_info is not None:
        merged.update(_flatten(_exception(exc_info)))
    merged.update(current_request_attributes())
    return json.dumps(
        {
            "timestamp": when.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "severity_text": text,
            "severity_number": number,
            "body": without_query(body),
            "attributes": merged,
        }
    )


def _write(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def log_event(event: str, *, level: int = logging.INFO, **fields: object) -> None:
    """Write one named event to stdout, its fields in the attributes. Never pass a secret."""
    _write(log_line(event, level=level, attributes={"event": event, **fields}))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        exc_info = record.exc_info if record.exc_info and record.exc_info[0] else None
        return log_line(
            record.getMessage(),
            level=record.levelno,
            created=record.created,
            attributes={"logger.name": record.name, **getattr(record, "attributes", {})},
            exc_info=exc_info,
        )


class StdoutHandler(logging.Handler):
    """Writes each record to whatever sys.stdout is when the record is emitted, as log_event
    does, so a replaced stdout (a test's capture, say) never leaves a handler on a closed one."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            _write(self.format(record))
        except Exception:  # noqa: BLE001  logging must never raise into the caller
            self.handleError(record)


def _uncaught(kind: type[BaseException], error: BaseException, trace: TracebackType | None) -> None:
    _write(log_line("uncaught exception", level=logging.CRITICAL, exc_info=(kind, error, trace)))


def _stdout_handler() -> dict[str, str]:
    return {"class": "app.core.logging.StdoutHandler", "formatter": "json"}


def _logger(level: str, handler: str, *, propagate: bool = False) -> dict[str, Any]:
    return {"level": level, "handlers": [handler], "propagate": propagate}


# gunicorn's logging, in its logconfig_dict form, so its own lines and those of the uvicorn
# worker (which takes gunicorn's handlers) are written here too, on stdout, in the same form.
# gunicorn's defaults name the two handlers console and error_console.
GUNICORN_LOGCONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "app.core.logging.JsonFormatter"}},
    "handlers": {"console": _stdout_handler(), "error_console": _stdout_handler()},
    "root": _logger("INFO", "console", propagate=True),
    "loggers": {
        "gunicorn.error": _logger("INFO", "error_console"),
        # Holly writes its own request line (app/core/request_id.py), without the query string.
        "gunicorn.access": _logger("WARNING", "console"),
    },
}


def configure_logging() -> None:
    handler = StdoutHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    logging.captureWarnings(True)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    sys.excepthook = _uncaught
