"""
app/schemas/event.py
────────────────────
Pydantic schemas for event tracking endpoints.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    event_type: str = Field(..., description="Type of event")
    topic_id: uuid.UUID | None = Field(default=None, description="Topic ID")
    ref_id: uuid.UUID | None = Field(default=None, description="Reference ID")
    ref_type: str | None = Field(default=None, description="Reference type")
    payload: dict = Field(default_factory=dict, description="Event payload data")
    occurred_at: datetime | None = Field(default=None, description="When the event occurred")


class EventResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Event ID")
    user_id: uuid.UUID = Field(..., description="User ID")
    event_type: str = Field(..., description="Type of event")
    topic_id: uuid.UUID | None = Field(default=None, description="Topic ID")
    ref_id: uuid.UUID | None = Field(default=None, description="Reference ID")
    ref_type: str | None = Field(default=None, description="Reference type")
    payload: dict = Field(..., description="Event payload data")
    occurred_at: datetime | None = Field(default=None, description="When the event occurred")
    created_at: datetime = Field(..., description="Creation time")

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    events: list[EventResponse] = Field(..., description="List of events")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")


class EventTimelineResponse(BaseModel):
    events: list[EventResponse] = Field(..., description="List of events")
    date_range_start: datetime = Field(..., description="Start of date range")
    date_range_end: datetime = Field(..., description="End of date range")
    total: int = Field(..., description="Total count")
