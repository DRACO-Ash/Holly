"""The activity overview: one window of notices, maneuvers and the latest element set of each
satellite they name, compact enough for the console views to draw and link in the browser."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.maneuver import ManeuverFacts


class ActivityNotice(BaseModel):
    """One logical notice: its latest publication, and the urgency of its latest evaluation."""

    id: UUID
    notice: str | None
    event_class: str | None
    event_type: str | None
    status: str | None
    region: str | None
    udl_created_at: datetime | None
    sat_ids: list[str]
    urgency: str
    top_action: str | None


class ActivityManeuver(BaseModel):
    id: UUID
    sat_no: int | None
    source: str | None
    event_start_time: datetime | None
    event_stop_time: datetime | None
    mnvr_type: str | None
    maneuver_status: str | None
    delta_v: float | None
    facts: ManeuverFacts


class ActivityElset(BaseModel):
    """The latest element set Holly holds for a satellite."""

    model_config = ConfigDict(from_attributes=True)

    sat_no: int
    epoch: datetime
    period: float | None
    inclination: float | None
    eccentricity: float | None
    apogee: float | None
    perigee: float | None
    mean_motion: float | None


class ActivityTruncated(BaseModel):
    """True where the window held more than the overview carries: the newest are kept."""

    notices: bool
    maneuvers: bool
    elsets: bool


class ActivityOverview(BaseModel):
    window_hours: int
    window_start: datetime
    generated_at: datetime
    notices: list[ActivityNotice]
    maneuvers: list[ActivityManeuver]
    elsets: list[ActivityElset]
    truncated: ActivityTruncated
