"""LIKE patterns built from untrusted text."""


def contains_pattern(text: str) -> str:
    """A LIKE pattern matching `text` anywhere, its own wildcards taken literally; use it with a
    backslash as the escape character."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
