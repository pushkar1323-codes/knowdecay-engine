"""
app/schemas/retention.py
─────────────────────────
Pydantic v2 schemas for retention prediction API.

Three schema groups:
  1. Request  — inputs for retention computation
  2. Response — full retention result with explainability breakdown
  3. Batch    — multi-topic prediction in a single call
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Request Schemas ───────────────────────────────────────────────────────────

class RetentionPredictRequest(BaseModel):
    """Request to predict current retention for a single user × topic."""

    user_id: uuid.UUID
    topic_id: uuid.UUID

    # Optional overrides — if omitted, the service pulls from memory_state/topic
    study_duration_minutes: float | None = Field(default=None, ge=0.0)
    quiz_score: float | None = Field(default=None, ge=0.0, le=1.0)
    quiz_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    elapsed_days: float | None = Field(default=None, ge=0.0)


class RetentionBatchRequest(BaseModel):
    """Predict retention for multiple topics at once."""

    user_id: uuid.UUID
    topic_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


# ── Response Schemas ──────────────────────────────────────────────────────────

class RetentionBreakdown(BaseModel):
    """
    Explainability breakdown — shows HOW the retention score was computed.
    Consumers can display this to learners or use it for debugging.
    """

    base_strength: float = Field(description="Contribution from study duration")
    revision_reinforcement: float = Field(description="Bonus from repeated revisions")
    quiz_boost: float = Field(description="Boost from latest quiz performance")
    time_decay: float = Field(description="Penalty from elapsed time (forgetting)")
    difficulty_penalty: float = Field(description="Penalty for topic difficulty")


class RetentionPredictResponse(BaseModel):
    """Full retention prediction result for one user × topic."""

    user_id: uuid.UUID
    topic_id: uuid.UUID
    topic_name: str | None = None

    # Core scores
    retention_score: float = Field(ge=0.0, le=1.0)
    stability_score: float = Field(ge=0.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    forgetting_probability: float = Field(ge=0.0, le=1.0)
    decay_rate: float = Field(ge=0.0)

    # Context
    revision_count: int = Field(ge=0)
    last_revision_at: datetime | None = None

    # Explainability
    breakdown: RetentionBreakdown

    model_config = {"from_attributes": True}


class RetentionBatchResponse(BaseModel):
    """Batch prediction results."""

    user_id: uuid.UUID
    predictions: list[RetentionPredictResponse]
    total: int
