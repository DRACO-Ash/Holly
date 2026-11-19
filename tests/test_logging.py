"""The App Store's logging standard: one JSON object per line on stdout, with exactly the
standard's top-level fields, flat attributes, the request id and the gateway's email on every
line written for a request, exceptions in the attributes, and no query string, header value or
service name anywhere. gunicorn's and uvicorn's own lines are held to it too."""

import json
import logging
import re
import sys
import warnings
from logging.config import dictConfig
from typing import Any

import httpx2
import pytest
from fastapi import FastAPI
from gunicorn.config import Config
from gunicorn.glogging import Logger

from app.core.logging import (
    GUNICORN_LOGCONFIG,
    JsonFormatter,
    StdoutHandler,
    configure_logging,
    log_event,
    log_line,
    severity,
    without_query,
)
from app.core.request_id import EMAIL_HEADER, REQUEST_ID_HEADER, request_attributes
from fakes import FakeSession, log_lines

TOP_LEVEL = {"timestamp", "severity_text", "severity_number", "body", "attributes"}
UTC_MILLISECONDS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")
# Values that must never reach a log line: a query string's and two request headers'.
QUERY_MARK = "query-mark-7"
AUTH_MARK = "auth-mark-7"
COOKIE_MARK = "cookie-mark-7"
HOLLY_MARK = "holly-mark-7"


def held_to_the_standard(line: dict[str, Any]) -> None:
    assert set(line) == TOP_LEVEL
    assert UTC_MILLISECONDS.fullmatch(line["timestamp"])
    assert isinstance(line["body"], str)
    assert not any(isinstance(value, dict) for value in line["attributes"].values())
    assert "service" not in json.dumps(line["attributes"])


@pytest.mark.parametrize(
    ("level", "pair"),
    [
        (1, ("TRACE", 1)),
        (logging.DEBUG, ("DEBUG", 5)),
        (logging.INFO, ("INFO", 9)),
        (logging.WARNING, ("WARN", 13)),
        (logging.ERROR, ("ERROR", 17)),
        (logging.CRITICAL, ("FATAL", 21)),
    ],
)
def test_each_level_takes_the_standards_severity_pair(level: int, pair: tuple[str, int]) -> None:
    assert severity(level) == pair
    line = json.loads(log_line("x", level=level))
    assert (line["severity_text"], line["severity_number"]) == pair


def test_a_line_has_exactly_the_standards_fields_with_flat_attributes() -> None:
    line = json.loads(
        log_line(
            "an event",
            created=0.5,
            attributes={"a": {"b": 1, "c": {"d": True}}, "names": ("x", 2), "none": None},
        )
    )
    held_to_the_standard(line)
    assert line["timestamp"] == "1970-01-01T00:00:00.500Z"
    assert line["attributes"] == {"a.b": 1, "a.c.d": True, "names": ["x", 2], "none": None}


def test_a_query_string_is_cut_from_every_part_of_a_line() -> None:
    url = f"https://udl.example/api?search={QUERY_MARK}&page=2"
    try:
        raise ValueError(url)
    except ValueError as error:
        exc_info = (ValueError, error, error.__traceback__)
    line = log_line(f"fetching {url}", attributes={"url": url}, exc_info=exc_info)
    assert QUERY_MARK not in line
    parsed = json.loads(line)
    cut = "https://udl.example/api?[query removed]"
    assert parsed["body"] == f"fetching {cut}"
    assert parsed["attributes"]["url"] == cut
    assert parsed["attributes"]["exception.type"] == "ValueError"
    assert parsed["attributes"]["exception.message"] == cut
    assert "Traceback" in parsed["attributes"]["exception.stacktrace"]


@pytest.mark.parametrize(
    ("text", "cut"),
    [
        (f"HTTPS://H/P?KEY={QUERY_MARK}", "HTTPS://H/P?[query removed]"),
        (f"GET /x?search={QUERY_MARK} 200", "GET /x?[query removed] 200"),
        (
            f"postgresql://holly:{QUERY_MARK}@db:5432/holly?sslmode=require",
            "postgresql://[userinfo removed]@db:5432/holly?[query removed]",
        ),
        (f"https://user:{QUERY_MARK}@host/p", "https://[userinfo removed]@host/p"),
        ("and/or? either way", "and/or? either way"),
        ("https://host/p", "https://host/p"),
    ],
)
def test_a_credential_or_query_in_any_url_or_path_is_cut(text: str, cut: str) -> None:
    assert without_query(text) == cut


def test_a_logged_exception_goes_into_the_attributes(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    try:
        1 / 0  # noqa: B018
    except ZeroDivisionError:
        logging.getLogger("app.test").exception("it failed")
    [line] = log_lines(capsys.readouterr().out)
    held_to_the_standard(line)
    assert (line["severity_text"], line["body"]) == ("ERROR", "it failed")
    assert line["attributes"]["logger.name"] == "app.test"
    assert line["attributes"]["exception.type"] == "ZeroDivisionError"
    assert "1 / 0" in line["attributes"]["exception.stacktrace"]


def test_an_event_keeps_its_name_and_fields_and_takes_a_level(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_event("database_wait", level=logging.WARNING, status="retrying", attempt=2)
    [line] = log_lines(capsys.readouterr().out)
    held_to_the_standard(line)
    assert (line["severity_text"], line["body"]) == ("WARN", "database_wait")
    assert line["attributes"] == {"event": "database_wait", "status": "retrying", "attempt": 2}


def test_warnings_and_uncaught_errors_are_written_to_stdout_too(
    capsys: pytest.CaptureFixture[str],
) -> None:
    logging.captureWarnings(False)
    configure_logging()
    # pytest records warnings.warn itself and restores the display hook between tests, so the
    # capture starts afresh here and the test calls the hook captureWarnings replaced.
    warnings.showwarning("old call", DeprecationWarning, __file__, 1)
    try:
        msg = "boom"
        raise RuntimeError(msg)
    except RuntimeError as error:
        sys.excepthook(RuntimeError, error, error.__traceback__)
    captured = capsys.readouterr()
    assert captured.err == ""
    warned, crashed = log_lines(captured.out)
    assert warned["severity_text"] == "WARN"
    assert "old call" in warned["body"]
    assert (crashed["severity_text"], crashed["severity_number"]) == ("FATAL", 21)
    assert crashed["attributes"]["exception.message"] == "boom"


def test_gunicorn_and_its_uvicorn_worker_write_their_lines_to_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = Config()
    config.set("logconfig_dict", GUNICORN_LOGCONFIG)
    log = Logger(config)
    log.info("Listening at: %s", "http://0.0.0.0:8080")
    log.error("Worker failed to boot")
    # The worker hands uvicorn gunicorn's handlers, as uvicorn_worker does.
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.handlers = log.error_log.handlers
    uvicorn_error.propagate = False
    uvicorn_error.info("Application startup complete.")
    logging.getLogger("gunicorn.access").info("GET /?search=%s 200", QUERY_MARK)
    captured = capsys.readouterr()
    assert captured.err == ""
    assert QUERY_MARK not in captured.out
    lines = log_lines(captured.out)
    for line in lines:
        held_to_the_standard(line)
    assert [(line["severity_text"], line["body"]) for line in lines] == [
        ("INFO", "Listening at: http://0.0.0.0:8080"),
        ("ERROR", "Worker failed to boot"),
        ("INFO", "Application startup complete."),
    ]
    dictConfig({"version": 1, "disable_existing_loggers": False})


@pytest.mark.parametrize(
    ("email", "kept"),
    [
        ("analyst@example.com", True),
        ("first.last+watch@sub.example.co.uk", True),
        ("not an email", False),
        ('a"b@example.com', False),
        ("x" * 65 + "@example.com", False),
        ("", False),
        (None, False),
    ],
)
def test_only_a_plain_email_is_kept(email: str | None, kept: bool) -> None:
    attributes = request_attributes("rid-1", email)
    assert attributes["http.request.header.x-request-id"] == "rid-1"
    assert ("user.email" in attributes) is kept
    if kept:
        assert attributes["user.email"] == email


async def test_every_line_of_a_request_carries_its_id_and_email_and_no_header_value(
    api_app: FastAPI,
    api: httpx2.AsyncClient,
    use_session: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging()
    use_session(FakeSession([None]))

    def logs_twice() -> dict[str, str]:
        log_event("probe.event")
        logging.getLogger("app.probe").warning("and a warning")
        return {"status": "ok"}

    api_app.add_api_route("/logs-twice", logs_twice, methods=["GET"])
    await api.get(
        f"/logs-twice?search={QUERY_MARK}",
        headers={
            REQUEST_ID_HEADER: "req-41",
            EMAIL_HEADER: "analyst@example.com",
            "Authorization": f"Bearer {AUTH_MARK}",
            "Cookie": f"holly={COOKIE_MARK}",
            "X-Holly-Token": HOLLY_MARK,
        },
    )
    captured = capsys.readouterr()
    assert captured.err == ""
    for mark in (QUERY_MARK, AUTH_MARK, COOKIE_MARK, HOLLY_MARK):
        assert mark not in captured.out
    # The test's own HTTP client logs too; only the app's lines count here.
    lines = [
        line
        for line in log_lines(captured.out)
        if not line["attributes"].get("logger.name", "").startswith("httpx")
    ]
    assert len(lines) == 3
    for line in lines:
        held_to_the_standard(line)
        assert line["attributes"]["http.request.header.x-request-id"] == "req-41"
        assert line["attributes"]["user.email"] == "analyst@example.com"
    request_line = lines[-1]
    assert request_line["body"] == "GET /logs-twice 200"
    assert request_line["attributes"]["http.request.method"] == "GET"
    assert request_line["attributes"]["url.path"] == "/logs-twice"
    assert request_line["attributes"]["http.response.status_code"] == 200
    assert isinstance(request_line["attributes"]["http.server.request.duration_ms"], int)


async def test_an_unhandled_error_is_logged_once_with_its_request_id(
    api_app: FastAPI, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging()
    raised: list[RuntimeError] = []

    def fails() -> None:
        error = RuntimeError("kaput")
        raised.append(error)
        raise error

    api_app.add_api_route("/fails", fails, methods=["GET"])
    transport = httpx2.ASGITransport(app=api_app, raise_app_exceptions=False)
    async with httpx2.AsyncClient(transport=transport, base_url="http://holly.test") as client:
        response = await client.get("/fails", headers={REQUEST_ID_HEADER: "req-500"})
    assert response.status_code == 500
    # The server then logs the same exception again, outside the request, as uvicorn does:
    # that line is dropped, as the handler's line already holds it with the request's id.
    [error] = raised
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.error("Exception in ASGI application\n", exc_info=error)
    # Any other exception the server logs is still written.
    uvicorn_error.error("Exception in ASGI application\n", exc_info=RuntimeError("other"))
    lines = [
        line
        for line in log_lines(capsys.readouterr().out)
        if not line["attributes"].get("logger.name", "").startswith("httpx")
    ]
    request_line = next(line for line in lines if line["body"] == "GET /fails 500")
    assert request_line["attributes"]["http.request.header.x-request-id"] == "req-500"
    kaput = [line for line in lines if line["attributes"].get("exception.message") == "kaput"]
    [logged] = kaput
    held_to_the_standard(logged)
    assert (logged["severity_text"], logged["body"]) == ("ERROR", "unhandled error")
    assert logged["attributes"]["http.request.header.x-request-id"] == "req-500"
    assert [line["attributes"].get("exception.message") for line in lines][-1] == "other"


def test_a_record_that_cannot_be_formatted_is_reported_on_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    handler = StdoutHandler()
    handler.setFormatter(JsonFormatter())
    record = logging.LogRecord("lib", logging.INFO, __file__, 1, "%s and %s", ("one",), None)
    handler.emit(record)
    captured = capsys.readouterr()
    assert captured.err == ""
    [line] = log_lines(captured.out)
    assert (line["severity_text"], line["body"]) == ("ERROR", "a log line could not be written")
    assert line["attributes"]["logger.name"] == "lib"
    assert line["attributes"]["exception.type"] == "TypeError"
