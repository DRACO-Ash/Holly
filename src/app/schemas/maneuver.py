from datetime import datetime
from typing import Any

from pydantic import BaseModel, model_validator

from app.schemas.common import UDLEnvelopeRead
from app.services.maneuver_facts import maneuver_facts


class ManeuverFacts(BaseModel):
    """What the stored UDL record says beyond the typed columns (services/maneuver_facts.py).
    Each name carries the unit the UDL schema states for its key (TBC, re-verify)."""

    status: str | None = None
    characterization: str | None = None
    event_id: str | None = None
    orig_object_id: str | None = None
    event_end_time: datetime | None = None
    report_time: datetime | None = None
    delta_vel_kms: float | None = None
    delta_pos_km: float | None = None
    delta_mass_kg: float | None = None
    total_burn_time_s: float | None = None
    pre_geo_longitude_deg: float | None = None
    post_geo_longitude_deg: float | None = None
    pre_drift_rate_deg_day: float | None = None
    post_drift_rate_deg_day: float | None = None
    pre_apogee_km: float | None = None
    post_apogee_km: float | None = None
    pre_perigee_km: float | None = None
    post_perigee_km: float | None = None
    pre_inclination_deg: float | None = None
    post_inclination_deg: float | None = None
    pre_period_min: float | None = None
    post_period_min: float | None = None
    pre_semi_major_axis_km: float | None = None
    post_semi_major_axis_km: float | None = None
    pre_eccentricity: float | None = None
    post_eccentricity: float | None = None
    uct: bool | None = None


class ManeuverRead(UDLEnvelopeRead):
    origin: str | None = None

    sat_no: int | None = None
    event_start_time: datetime | None = None
    event_stop_time: datetime | None = None
    mnvr_type: str | None = None
    description: str | None = None
    delta_v: float | None = None
    thrust_magnitude: float | None = None
    thrust_duration: float | None = None
    propulsion_type: str | None = None
    maneuver_status: str | None = None
    responsible_nation: str | None = None

    created_at: datetime
    updated_at: datetime

    facts: ManeuverFacts = ManeuverFacts()

    @model_validator(mode="before")
    @classmethod
    def _read_facts(cls, data: Any) -> Any:
        """A row read from the database carries its raw record: its facts are read from it."""
        if isinstance(data, dict) or not hasattr(data, "raw"):
            return data
        fields = {name: getattr(data, name) for name in cls.model_fields if hasattr(data, name)}
        return {**fields, "facts": ManeuverFacts(**maneuver_facts(data.raw))}


class ManeuverDetail(ManeuverRead):
    raw: dict[str, Any]


class ManeuverPage(BaseModel):
    items: list[ManeuverRead]
    total: int
    limit: int
    offset: int
