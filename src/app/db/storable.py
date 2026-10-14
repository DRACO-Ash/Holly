"""What PostgreSQL can store, checked before a value from outside Holly is written.

PostgreSQL text and JSON hold no NUL character, and only text that encodes as UTF-8, which a
lone surrogate does not. Its JSON holds no NaN or infinity either: json.dumps writes them as
tokens PostgreSQL refuses. A value that breaks these rules fails its whole statement, so UDL
records and model replies are checked first and refused one at a time instead.
"""

import math
from typing import Any

UNSTORABLE_TEXT = "holds a character PostgreSQL cannot store"
UNSTORABLE_NUMBER = "holds a number PostgreSQL JSON cannot store"


def storable_text(text: str) -> bool:
    if "\x00" in text:
        return False
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:  # a lone surrogate
        return False
    return True


def json_problem(value: Any) -> str | None:
    """Why PostgreSQL cannot store `value` as JSON, or None when it can. Every string, keys
    included, must be storable text and every number finite. The value is walked without
    recursion, so no depth of nesting can raise."""
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str) and not storable_text(item):
            return UNSTORABLE_TEXT
        if isinstance(item, float) and not math.isfinite(item):
            return UNSTORABLE_NUMBER
        if isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list | tuple):
            pending.extend(item)
    return None
