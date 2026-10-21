from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.schemas.notification import NotificationRead
from app.services.disclosure import NOT_CLEARED

# The assistant's reply is untrusted input (llm-integration). These models are the boundary
# validator: an unknown urgency, a missing field or an oversized value fails validation, and
# the reply is retried once, then refused.
Urgency = Literal["high", "medium", "low"]


class ApplicableProcedure(BaseModel):
    procedure_id: str | None = Field(default=None, max_length=64)
    name: str = Field(max_length=300)
    reason: str = Field(max_length=2000)


class NextAction(BaseModel):
    action: str = Field(max_length=1000)
    urgency: Urgency
    deadline: str | None = Field(default=None, max_length=64)
    rationale: str = Field(max_length=2000)

    @field_validator("urgency", mode="before")
    @classmethod
    def _normalise_urgency(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("deadline")
    @classmethod
    def _deadline_is_a_timestamp(cls, value: str | None) -> str | None:
        # The prompt asks for an ISO 8601 timestamp or null. What Python's fromisoformat reads,
        # a bare date or a compact form included, is kept as sent, but a time of day only with
        # its UTC offset: without one, every browser would read it in its own zone. Anything
        # else ("by end of shift") is dropped here rather than stored, so no reader has to
        # guess what it means.
        if value is None:
            return None
        text = value.strip()
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        has_time = len(text) > len("2026-01-02")
        if has_time and parsed.tzinfo is None:
            return None
        return text


class StructuredEvaluation(BaseModel):
    summary: str = Field(max_length=4000)
    applicable_procedures: list[ApplicableProcedure] = Field(default_factory=list, max_length=20)
    next_actions: list[NextAction] = Field(default_factory=list, max_length=20)
    open_questions: list[Annotated[str, Field(max_length=1000)]] = Field(
        default_factory=list, max_length=20
    )


class AssistantEvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    notification_id: UUID
    summary: str
    structured: dict[str, Any]
    procedures_used: list[str]
    model: str
    error: str | None = None
    evaluated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def withheld(self) -> bool:
        """Kept from the assistant by the disclosure control: a decision, not a failure, which
        the panel shows as a note rather than an error."""
        return self.error == NOT_CLEARED


class AssistantFeedItem(BaseModel):
    """Dashboard row: a notification, its latest evaluation, the cross-version
    event summary, and a precomputed urgency rollup."""

    notification: NotificationRead
    evaluation: AssistantEvaluationRead | None = None
    urgency: str
    top_action: str | None = None
    event_summary: str | None = None
    event_publication_count: int | None = None
    event_key: str | None = None
    # False when the notice's classification marking keeps it from the assistant.
    assistant_cleared: bool = True


class AssistantFeed(BaseModel):
    items: list[AssistantFeedItem]
    window_hours: int
