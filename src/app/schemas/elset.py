from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ElsetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    udl_id: str | None = None
    sat_no: int
    epoch: datetime
    mean_motion: float | None = None
    eccentricity: float | None = None
    inclination: float | None = None
    raan: float | None = None
    arg_of_perigee: float | None = None
    mean_anomaly: float | None = None
    rev_no: int | None = None
    bstar: float | None = None
    mean_motion_dot: float | None = None
    mean_motion_ddot: float | None = None
    semi_major_axis: float | None = None
    period: float | None = None
    apogee: float | None = None
    perigee: float | None = None
    line1: str | None = None
    line2: str | None = None
    classification_marking: str | None = None
    data_mode: str | None = None
    source: str | None = None
    created_at: datetime
    updated_at: datetime


class ElsetDetail(ElsetRead):
    raw: dict[str, Any]


class ElsetPage(BaseModel):
    items: list[ElsetRead]
    total: int
    limit: int
    offset: int


class ElsetIngestRequest(BaseModel):
    epoch_gte: datetime
    sat_no: int | None = None
    # Holly's own cap on what one manual pull may ask for. A request that names no limit asks
    # for none, and UDL applies its own default page size (TBC, re-verify: its value).
    max_results: int | None = Field(default=None, ge=1, le=10_000)


class ElsetIngestResponse(BaseModel):
    pulled: int
    inserted: int
    updated: int
    skipped: int
