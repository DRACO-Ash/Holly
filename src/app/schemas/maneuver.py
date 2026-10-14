from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import UDLEnvelopeRead


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


class ManeuverDetail(ManeuverRead):
    raw: dict[str, Any]


class ManeuverPage(BaseModel):
    items: list[ManeuverRead]
    total: int
    limit: int
    offset: int
