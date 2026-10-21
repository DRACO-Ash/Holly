from pydantic import BaseModel


class ManualSummary(BaseModel):
    slug: str
    title: str


class ManualRead(ManualSummary):
    markdown: str
