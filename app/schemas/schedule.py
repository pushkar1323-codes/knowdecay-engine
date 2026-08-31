"""
app/schemas/schedule.py
────────────────────────
Pydantic v2 schemas for scheduling API.

Schema groups:
  1. Request  — single topic or batch schedule generation
  2. Response — schedule result with interval breakdown
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Request Schemas ───────────────────────────────────────────────────────────

class ScheduleSingleRequest(BaseModel):
    """Request to compute the next revision time for a single topic."""

    user_id: uuid.UUID
    topic_id: uuid.UUID
    days_until_exam: float | None = Field(default=None, ge=0.0)


class ScheduleGenerateRequest(BaseModel):
    """Generate a full revision schedule across multiple topics."""

    user_id: uuid.UUID
    topic_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    days_until_exam: float | None = Field(default=None, ge=0.0)
    max_per_day: int = Field(default=10, ge=1, le=50)


# ── Response Schemas ──────────────────────────────────────────────────────────

class ScheduleBreakdown(BaseModel):
    """Interval computation breakdown for explainability."""

    base_interval: float = Field(description="Raw spaced-repetition interval in days")
    adjusted_interval: float = Field(description="After difficulty + exam compression")
    retention_factor: float = Field(description="How retention affected interval")
    difficulty_modifier: float = Field(description="Difficulty scaling factor")
    exam_compression: float = Field(description="Exam proximity compression divisor")


class ScheduleSingleResponse(BaseModel):
    """Full schedule result for one user × topic."""

    user_id: uuid.UUID
    topic_id: uuid.UUID
    topic_name: str | None = None

    next_revision_days: float = Field(ge=0.0)
    next_revision_at: datetime | None = None
    mode: str = Field(description="exam_tomorrow | exam_week | exam_month | long_term")
    schedule_priority: float = Field(ge=0.0, le=1.0)

    # Context
    retention_score: float = Field(ge=0.0, le=1.0)
    revision_count: int = Field(ge=0)

    # Explainability
    breakdown: ScheduleBreakdown
    recommendation: str

    model_config = {"from_attributes": True}


class ScheduleSlotResponse(BaseModel):
    """A single slot in a multi-topic schedule."""

    topic_id: uuid.UUID
    topic_name: str | None = None
    day: float
    priority: float
    mode: str
    recommendation: str


class ScheduleGenerateResponse(BaseModel):
    """Full generated schedule across multiple topics."""

    user_id: uuid.UUID
    schedule: list[ScheduleSlotResponse]
    mode: str
    total_topics: int
    total_days: int = Field(description="Number of distinct revision days in schedule")
