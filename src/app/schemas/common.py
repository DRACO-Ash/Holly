"""Read models several API responses share, and the text type every request field uses."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict

from app.db.storable import storable_text


def _storable(value: str) -> str:
    if not storable_text(value):
        msg = "holds a character Holly cannot store"
        raise ValueError(msg)
    return value


# Text from a request. PostgreSQL can neither store nor compare a NUL, and stores only text
# that encodes as UTF-8, so such text is refused here, with a 422, before any query, write or
# assistant call.
StorableText = Annotated[str, AfterValidator(_storable)]


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
