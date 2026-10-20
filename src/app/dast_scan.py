"""Start under the App Store's DAST scan, which gives the container none of Holly's settings.

The scan runs the image with APPSTORE_DAST_SCAN=true and none of the app's variables or secrets,
then probes HTTP on port 8080 (the platform's scan log, 19 October 2026). Holly refuses to start
without a signing key, a database or a writable store, so the gunicorn master calls
prepare_scan_environment first, before anything reads the settings. With the scan flag set,
and only then, it:

  - generates a throwaway APP_SECRET_KEY when none is set, never logged; every token signed
    with it dies with the container;
  - turns the background pulls off, so the scan makes no call to UDL, Mattermost or the
    assistant;
  - points the procedure store at a new temporary directory when no store is configured.

The database is left as the scan provides it. With none at all, Holly serves without one
(config.Settings allows that under the flag alone), and each request that needs one answers
503. The master logs one `dast_scan` line naming what it set, never a value, so a container
started with the flag by mistake says so at once.
"""

import secrets
import tempfile
from collections.abc import MutableMapping

from pydantic import TypeAdapter, ValidationError

from app.core.logging import log_event

SCAN_FLAG = "APPSTORE_DAST_SCAN"
_BOOL = TypeAdapter(bool)


def _flag_value(env: MutableMapping[str, str]) -> str | None:
    # The settings match a variable's name in any letter case, so the flag is read the same way.
    for name, value in env.items():
        if name.upper() == SCAN_FLAG:
            return value
    return None


def scan_requested(env: MutableMapping[str, str]) -> bool:
    """Whether the flag is set to a true value, read as the settings read it. A value that is
    not a boolean is left for the settings to refuse."""
    value = _flag_value(env)
    if value is None:
        return False
    try:
        return _BOOL.validate_python(value)
    except ValidationError:
        return False


def prepare_scan_environment(env: MutableMapping[str, str]) -> bool:
    """Fill in what the scan leaves out, as the module says; True when the scan flag is set."""
    if not scan_requested(env):
        return False
    generated_key = not env.get("APP_SECRET_KEY", "").strip()
    if generated_key:
        env["APP_SECRET_KEY"] = secrets.token_urlsafe(48)
    env["BACKGROUND_REFRESH_ENABLED"] = "false"
    temporary_store = not (env.get("PROCEDURE_STORAGE_PATH") or env.get("STORAGE_MOUNT_PATH"))
    if temporary_store:
        env["PROCEDURE_STORAGE_PATH"] = tempfile.mkdtemp(prefix="holly-dast-")
    database = any(env.get(name, "").strip() for name in ("DATABASE_URL", "POSTGRES_HOST"))
    log_event(
        "dast_scan",
        status="active",
        generated_secret_key=generated_key,
        temporary_store=temporary_store,
        database=database,
        background_refresh=False,
    )
    return True
