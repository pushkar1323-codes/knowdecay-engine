"""
app/schemas/recalibration.py
──────────────────────────────
Pydantic v2 schemas for recalibration API.

Schema groups:
  1. Request  — event submission (quiz, revision, study, inactivity)
  2. Response — recalibration result with deltas + audit trail
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Request Schemas ───────────────────────────────────────────────────────────

class RecalibrationEventRequest(BaseModel):
    """Submit a learning event to trigger recalibration."""

    user_id: uuid.UUID
    topic_id: uuid.UUID
    event_type: Literal["quiz_submitted", "revision_completed", "study_session", "inactivity_decay"] = Field(
        description="quiz_submitted | revision_completed | study_session | inactivity_decay"
    )

    # Quiz fields (required for quiz_submitted)
    quiz_score: float | None = Field(default=None, ge=0.0, le=1.0)
    quiz_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    # Study/revision fields
    study_duration_minutes: float = Field(default=0.0, ge=0.0)

    # Inactivity
    days_inactive: float = Field(default=0.0, ge=0.0)

    # Optional context
    days_until_exam: float | None = Field(default=None, ge=0.0)


class BatchRecalibrationRequest(BaseModel):
    """Submit multiple recalibration events at once."""

    events: list[RecalibrationEventRequest] = Field(min_length=1, max_length=200)


# ── Response Schemas ──────────────────────────────────────────────────────────

class StateChangeDetail(BaseModel):
    """Single field change in the audit trail."""

    field: str
    old_value: float
    new_value: float
    reason: str


class StateDeltaResponse(BaseModel):
    """Incremental deltas that were applied."""

    retention_delta: float
    stability_delta: float
    decay_rate_new: float | None
    confidence_delta: float
    revision_strength_delta: float
    revision_count_delta: int
    forgetting_probability_new: float | None
    urgency_delta: float

    # Phase 8.5 — adaptive forgetting curve deltas
    base_stability_new: float | None = None
    revision_quality_new: float | None = None
    difficulty_factor_new: float | None = None
    performance_trend_new: float | None = None

    # Adaptive stability deltas
    adaptive_stability_new: float | None = None
    stability_growth_rate_new: float | None = None
    half_life_days_new: float | None = None

    # Decay parameter deltas
    effective_decay_rate_new: float | None = None
    time_to_critical_new: float | None = None
    days_until_target_new: float | None = None

    # Reinforcement behaviour deltas
    quality_variance_new: float | None = None
    effective_revision_count_delta: int = 0
    revision_effectiveness_ratio_new: float | None = None
    time_pattern_regularity_new: float | None = None
    confidence_calibration_error_new: float | None = None

    # Retention history deltas
    peak_retention_new: float | None = None
    retention_at_last_revision_new: float | None = None
    total_forgetting_events_delta: int = 0


class RecalibrationResponse(BaseModel):
    """Full recalibration result for one event."""

    user_id: uuid.UUID
    topic_id: uuid.UUID
    event_type: str

    # New state values — core
    new_retention: float = Field(ge=0.0, le=1.0)
    new_stability: float = Field(ge=0.0)
    new_decay_rate: float = Field(ge=0.0)
    new_confidence: float = Field(ge=0.0, le=1.0)
    new_revision_strength: float = Field(ge=0.0)
    new_revision_count: int = Field(ge=0)
    new_forgetting_probability: float = Field(ge=0.0, le=1.0)
    new_urgency: float = Field(ge=0.0, le=1.0)

    # New state values — Phase 8.5
    new_base_stability: float = Field(default=1.0, ge=0.0)
    new_revision_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    new_difficulty_factor: float = Field(default=1.0, ge=0.0)
    new_performance_trend: float = 0.0

    # New state values — adaptive stability
    new_adaptive_stability: float = Field(default=1.0, ge=0.0)
    new_stability_growth_rate: float = 0.0
    new_half_life_days: float = Field(default=0.0, ge=0.0)

    # New state values — decay parameters
    new_effective_decay_rate: float = Field(default=0.1, ge=0.0)
    new_time_to_critical: float = Field(default=0.0, ge=0.0)
    new_days_until_target: float = Field(default=0.0, ge=0.0)

    # New state values — reinforcement behaviour
    new_quality_variance: float = Field(default=0.0, ge=0.0)
    new_effective_revision_count: int = Field(default=0, ge=0)
    new_revision_effectiveness_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    new_time_pattern_regularity: float = Field(default=0.5, ge=0.0, le=1.0)
    new_confidence_calibration_error: float = Field(default=0.0, ge=0.0)

    # New state values — retention history
    new_peak_retention: float = Field(default=0.0, ge=0.0, le=1.0)
    new_retention_at_last_revision: float = Field(default=0.0, ge=0.0, le=1.0)
    new_total_forgetting_events: int = Field(default=0, ge=0)

    # Deltas
    delta: StateDeltaResponse

    # Audit trail
    changes: list[StateChangeDetail]
    summary: str

    # Scheduling — updated next_revision_at
    next_revision_at: datetime | None = None

    model_config = {"from_attributes": True}


class BatchRecalibrationResponse(BaseModel):
    """Batch recalibration results."""

    results: list[RecalibrationResponse]
    total_processed: int
    total_errors: int = 0
