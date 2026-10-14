"""Runtime configuration, read from the environment only and validated at the boundary."""

from collections.abc import Mapping

DEFAULT_PORT = 8080
MAX_PORT = 65535
_MAX_PORT_DIGITS = len(str(MAX_PORT))


def resolve_port(environ: Mapping[str, str]) -> int:
    """Return the port to listen on: PORT when set, otherwise 8080 (the App Store contract).

    PORT must be a canonical whole number from 1 to 65535: ASCII digits only, no sign and no
    leading zero. Surrounding whitespace is ignored. Anything else fails closed with a clear
    message instead of falling back quietly, because a silent fallback would listen on a port
    the platform is not probing.
    """
    raw = environ.get("PORT", "").strip()
    if not raw:
        return DEFAULT_PORT
    if (
        raw.isascii()
        and raw.isdigit()
        and not raw.startswith("0")
        and len(raw) <= _MAX_PORT_DIGITS
        and int(raw) <= MAX_PORT
    ):
        return int(raw)
    msg = f"PORT must be a whole number from 1 to {MAX_PORT}, got {raw[:16]!r}"
    raise ValueError(msg)
