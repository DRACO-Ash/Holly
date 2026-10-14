"""PORT resolution: default to 8080, honour a canonical value, fail closed on anything else.

Expected values are literals, never the module's own constants, so a changed bound fails here.
"""

import pytest

from app.config import resolve_port

# Non-ASCII digits, built from code points so the source stays plain ASCII.
# str.isdigit() is true for both, so the ASCII check is what must refuse them.
FULL_WIDTH_8080 = "".join(chr(code) for code in (0xFF18, 0xFF10, 0xFF18, 0xFF10))
SUPERSCRIPT_TWO = chr(0x00B2)


def test_port_defaults_to_8080_when_absent() -> None:
    assert resolve_port({}) == 8080


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
def test_blank_port_falls_back_to_8080(raw: str) -> None:
    assert resolve_port({"PORT": raw}) == 8080


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", 1), ("8080", 8080), (" 3000\n", 3000), ("65535", 65535)],
)
def test_canonical_port_is_honoured(raw: str, expected: int) -> None:
    assert resolve_port({"PORT": raw}) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "0",
        "00001",
        "08080",
        "65536",
        "99999",
        "100000",
        "-1",
        "+80",
        "8_080",
        "80.0",
        "abc",
        '"8080"',
        "8080 --check-config",
        FULL_WIDTH_8080,
        SUPERSCRIPT_TWO,
        # Past Python's 4,300-digit int() limit: only the length guard keeps this message ours.
        "1" * 5000,
    ],
)
def test_malformed_port_fails_closed(raw: str) -> None:
    with pytest.raises(ValueError, match="PORT must be a whole number"):
        resolve_port({"PORT": raw})
