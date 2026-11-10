"""What a notice's event class says: its kind as written, the objects it names and the regime.

The Python twin of the dashboard's `parseEventClass` (frontend/src/utils/ops.ts), so the server
can tell which objects a notice is about. Every input is untrusted UDL text: a part that does not
fit a pattern is kept as an object's name, never guessed at, and a catalogue number is only ever
digits in the last brackets of a part.
"""

import re
from dataclasses import dataclass

REGIMES = frozenset({"LEO", "MEO", "HEO", "GEO", "XGEO"})
_VS = re.compile(r"\svs\.?\s", re.IGNORECASE)
_CATALOGUE = re.compile(r"\d{1,9}")
NAME_CAP = 120


@dataclass(frozen=True)
class EventObject:
    name: str
    catalogue_number: int | None


@dataclass(frozen=True)
class ParsedEvent:
    kind_label: str
    objects: tuple[EventObject, ...]
    regime: str | None


def _tidy(text: str) -> str:
    return " ".join(text.split())


def event_object(text: str) -> EventObject:
    """`CHINASAT 3B (64062)` to its name and catalogue number."""
    trimmed = _tidy(text)
    open_at = trimmed.rfind("(")
    if open_at != -1 and trimmed.endswith(")"):
        inside = trimmed[open_at + 1 : -1].strip()
        if inside.isascii() and _CATALOGUE.fullmatch(inside):
            name = trimmed[:open_at].strip() or inside
            return EventObject(name[:NAME_CAP], int(inside))
    return EventObject(trimmed[:NAME_CAP], None)


def parse_event_class(event_class: str | None) -> ParsedEvent | None:
    """`Maneuver / CHINASAT 3B (64062) / GEO`, or an RPO's `A (1) vs B (2)`, read apart."""
    if not event_class:
        return None
    parts = [p for p in (_tidy(part) for part in event_class.split("/")) if p]
    if not parts:
        return None
    rest = parts[1:]
    regime = rest[-1].upper() if rest and rest[-1].upper() in REGIMES else None
    if regime:
        rest = rest[:-1]
    objects = tuple(
        obj
        for part in rest
        for obj in (event_object(piece) for piece in _VS.split(part))
        if obj.name
    )
    return ParsedEvent(kind_label=parts[0][:NAME_CAP], objects=objects, regime=regime)
