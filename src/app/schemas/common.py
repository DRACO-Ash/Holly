"""Read models several API responses share."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UDLEnvelopeRead(BaseModel):
    """The UDL identity and envelope fields of a notification or maneuver."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    udl_id: str | None = None
    data_mode: str | None = None
    source: str | None = None
    classification_marking: str | None = None
    created_by: str | None = None
    orig_network: str | None = None
    udl_created_at: datetime | None = None
