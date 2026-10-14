from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.notification import NotificationRead

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


class AssistantFeed(BaseModel):
    items: list[AssistantFeedItem]
    window_hours: int
