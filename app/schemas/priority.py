"""
app/schemas/priority.py
────────────────────────
Pydantic v2 schemas for priority ranking API.

Schema groups:
  1. Request  — single topic or batch ranking
  2. Response — priority result with full explainability
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Request Schemas ───────────────────────────────────────────────────────────

class PriorityRankRequest(BaseModel):
    """Request to compute priority for a single user × topic."""

    user_id: uuid.UUID
    topic_id: uuid.UUID

    # Optional context overrides
    days_until_exam: float | None = Field(default=None, ge=0.0)
    importance_weight: float | None = Field(default=None, ge=0.0)


class PriorityBatchRequest(BaseModel):
    """Rank multiple topics by revision priority."""

    user_id: uuid.UUID
    topic_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    limit: int | None = Field(default=None, ge=1, le=500)

    # Optional global exam context
    days_until_exam: float | None = Field(default=None, ge=0.0)


# ── Response Schemas ──────────────────────────────────────────────────────────

class PriorityBreakdown(BaseModel):
    """Component breakdown — shows HOW priority was computed."""

    urgency_component: float = Field(description="(1−retention) × difficulty boost")
    weakness_component: float = Field(description="Forgetting prob × weakness trend")
    delay_component: float = Field(description="Log-scaled revision delay")
    exam_component: float = Field(description="Exam proximity multiplier")


class PriorityReasonResponse(BaseModel):
    """Human-readable reasons for prioritisation decision."""

    urgency_reason: str
    weakness_reason: str
    delay_reason: str
    exam_reason: str
    summary: str


class PriorityRankResponse(BaseModel):
    """Full priority result for one user × topic."""

    user_id: uuid.UUID
    topic_id: uuid.UUID
    topic_name: str | None = None

    # Scores
    priority_score: float = Field(ge=0.0)
    normalised_score: float = Field(ge=0.0, le=1.0)
    tier: str = Field(description="critical | high | medium | low | minimal")

    # Context
    retention_score: float = Field(ge=0.0, le=1.0)
    forgetting_probability: float = Field(ge=0.0, le=1.0)
    revision_count: int = Field(ge=0)
    last_revision_at: datetime | None = None

    # Explainability
    breakdown: PriorityBreakdown
    reason: PriorityReasonResponse

    # Ranking position (set by batch endpoint)
    rank: int | None = None

    model_config = {"from_attributes": True}


class PriorityBatchResponse(BaseModel):
    """Batch ranking results — topics sorted by priority."""

    user_id: uuid.UUID
    rankings: list[PriorityRankResponse]
    total: int
