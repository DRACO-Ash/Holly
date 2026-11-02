"""What a stored UDL maneuver record says, read from its raw payload at read time.

Holly's typed maneuver columns read `mnvrType`, `deltaV` and `eventStopTime`, which the fusion
providers' records do not carry (fact, from the app owner's Maneuvers page on 2 November 2026:
every KBR and NorthStar row showed n/a for all three). The keys below are those of the UDL
Maneuver schema as Holly's authors know it (TBC, re-verify against a stored KBR or NorthStar
record), read from `raw` so every record already stored benefits with no migration. A key that
is absent, or holds anything but the expected kind of value, gives None: nothing here is
guessed, and the raw record stays available on the detail route to check any value against.

Every value is untrusted. Text is kept only when PostgreSQL could store it, trimmed and capped;
a number only when it is finite and of a plausible size; a time only when it parses.
"""

import math
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from app.db.storable import storable_text
from app.services.udl_records import parse_datetime

TEXT_CAP = 200
# No physical quantity in a maneuver record comes near this; a larger number is not data.
NUMBER_CAP = 1e9

# (raw key, fact name) for each text fact.
_TEXT_KEYS = (
    ("status", "status"),
    ("characterization", "characterization"),
    ("eventId", "event_id"),
    ("origObjectId", "orig_object_id"),
)
# (raw key, fact name) for each time fact.
_TIME_KEYS = (
    ("eventEndTime", "event_end_time"),
    ("reportTime", "report_time"),
)
# (raw key, fact name) for each number fact. The names carry the unit the UDL schema states for
# the key (TBC, re-verify): km and km/s for the position and velocity changes, kg for mass,
# seconds for the burn, degrees and degrees per day for the geostationary longitude and drift,
# km for apogee, perigee and semi-major axis, minutes for the period.
_NUMBER_KEYS = (
    ("deltaVel", "delta_vel_kms"),
    ("deltaPos", "delta_pos_km"),
    ("deltaMass", "delta_mass_kg"),
    ("totalBurnTime", "total_burn_time_s"),
    ("preGeoLongitude", "pre_geo_longitude_deg"),
    ("postGeoLongitude", "post_geo_longitude_deg"),
    ("preDriftRate", "pre_drift_rate_deg_day"),
    ("postDriftRate", "post_drift_rate_deg_day"),
    ("preApogee", "pre_apogee_km"),
    ("postApogee", "post_apogee_km"),
    ("prePerigee", "pre_perigee_km"),
    ("postPerigee", "post_perigee_km"),
    ("preInclination", "pre_inclination_deg"),
    ("postInclination", "post_inclination_deg"),
    ("prePeriod", "pre_period_min"),
    ("postPeriod", "post_period_min"),
    ("preSemiMajorAxis", "pre_semi_major_axis_km"),
    ("postSemiMajorAxis", "post_semi_major_axis_km"),
    ("preEccentricity", "pre_eccentricity"),
    ("postEccentricity", "post_eccentricity"),
)

FACT_NAMES: tuple[str, ...] = (
    *(name for _key, name in _TEXT_KEYS),
    *(name for _key, name in _TIME_KEYS),
    *(name for _key, name in _NUMBER_KEYS),
    "uct",
)


def fact_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or not storable_text(text):
        return None
    return text[:TEXT_CAP]


def fact_number(value: Any) -> float | None:
    # A bool is an int in Python, but true is not a measurement.
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    if not math.isfinite(number) or abs(number) > NUMBER_CAP:
        return None
    return number


def fact_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return parse_datetime(value)
    except ValueError:
        return None


def maneuver_facts(raw: Any) -> dict[str, Any]:
    """Every fact name, with its value from `raw` or None."""
    record: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
    facts: dict[str, Any] = {}
    for key, name in _TEXT_KEYS:
        facts[name] = fact_text(record.get(key))
    for key, name in _TIME_KEYS:
        facts[name] = fact_time(record.get(key))
    for key, name in _NUMBER_KEYS:
        facts[name] = fact_number(record.get(key))
    uct = record.get("uct")
    facts["uct"] = uct if isinstance(uct, bool) else None
    return facts
