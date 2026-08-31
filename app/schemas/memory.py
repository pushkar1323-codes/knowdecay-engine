"""
app/schemas/memory.py
──────────────────────
Pydantic v2 schemas for memory state operations.

Three schema categories:
  1. Response schemas — what the API returns
  2. Update schemas  — incremental field updates from engine modules
  3. Aggregation schemas — hierarchical retention summaries
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Response Schemas ──────────────────────────────────────────────────────────

class MemoryStateResponse(BaseModel):
    """Full memory state for a single user × topic pair."""

    id: uuid.UUID
    user_id: uuid.UUID
    topic_id: uuid.UUID

    # Retention intelligence fields
    retention_score: float = Field(ge=0.0, le=1.0)
    stability_score: float = Field(ge=0.0)
    decay_rate: float = Field(ge=0.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    revision_strength: float = Field(ge=0.0)
    revision_count: int = Field(ge=0)
    forgetting_probability: float = Field(ge=0.0, le=1.0)
    urgency_score: float = Field(ge=0.0)

    # Phase 8.5 — adaptive forgetting curve
    base_stability: float = Field(default=1.0, ge=0.0)
    revision_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    difficulty_factor: float = Field(default=1.0, ge=0.0)
    performance_trend: float = 0.0

    # Adaptive stability persistence
    adaptive_stability: float = Field(default=1.0, ge=0.0)
    stability_growth_rate: float = 0.0
    half_life_days: float = Field(default=0.0, ge=0.0)

    # Decay parameters
    effective_decay_rate: float = Field(default=0.1, ge=0.0)
    time_to_critical: float = Field(default=0.0, ge=0.0)
    days_until_target: float = Field(default=0.0, ge=0.0)

    # Reinforcement behaviour
    quality_variance: float = Field(default=0.0, ge=0.0)
    effective_revision_count: int = Field(default=0, ge=0)
    revision_effectiveness_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    time_pattern_regularity: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence_calibration_error: float = Field(default=0.0, ge=0.0)

    # Retention history
    peak_retention: float = Field(default=0.0, ge=0.0, le=1.0)
    retention_at_last_revision: float = Field(default=0.0, ge=0.0, le=1.0)
    total_forgetting_events: int = Field(default=0, ge=0)
    last_forgetting_event_at: datetime | None = None

    # Scheduling timestamps
    last_revision_at: datetime | None = None
    next_revision_at: datetime | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class MemoryStateSummary(BaseModel):
    """Compact memory state — used in list responses and batch operations."""

    topic_id: uuid.UUID
    topic_name: str | None = None
    retention_score: float
    stability_score: float
    forgetting_probability: float
    urgency_score: float
    revision_count: int
    last_revision_at: datetime | None = None
    next_revision_at: datetime | None = None

    # Adaptive stability persistence
    adaptive_stability: float = 1.0
    stability_growth_rate: float = 0.0
    half_life_days: float = 0.0

    # Decay parameters
    effective_decay_rate: float = 0.1
    time_to_critical: float = 0.0
    days_until_target: float = 0.0

    # Reinforcement behaviour
    quality_variance: float = 0.0
    effective_revision_count: int = 0
    revision_effectiveness_ratio: float = 0.0
    time_pattern_regularity: float = 0.5
    confidence_calibration_error: float = 0.0

    # Retention history
    peak_retention: float = 0.0
    retention_at_last_revision: float = 0.0
    total_forgetting_events: int = 0

    model_config = {"from_attributes": True}


# ── Update Schemas ────────────────────────────────────────────────────────────

class MemoryStateUpdate(BaseModel):
    """
    Incremental update payload for a memory state.
    Only provided fields are applied — everything else stays unchanged.
    This is how engine modules evolve memory state WITHOUT full recalculation.
    """

    retention_score: float | None = Field(default=None, ge=0.0, le=1.0)
    stability_score: float | None = Field(default=None, ge=0.0)
    decay_rate: float | None = Field(default=None, ge=0.0)
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    revision_strength: float | None = Field(default=None, ge=0.0)
    revision_count: int | None = Field(default=None, ge=0)
    forgetting_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    urgency_score: float | None = Field(default=None, ge=0.0)
    last_revision_at: datetime | None = None
    next_revision_at: datetime | None = None


class MemoryStateInit(BaseModel):
    """
    Explicit initialization payload for creating a new memory state.
    Used when a topic is first registered for a user.
    """

    user_id: uuid.UUID
    topic_id: uuid.UUID
    retention_score: float = Field(default=0.0, ge=0.0, le=1.0)
    stability_score: float = Field(default=1.0, ge=0.0)
    decay_rate: float = Field(default=0.1, ge=0.0)
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)


# ── Aggregation Schemas ───────────────────────────────────────────────────────

class RetentionAggregate(BaseModel):
    """
    Aggregated retention at any hierarchy level.
    Used for: topic → chapter → module → subject rollups.
    """

    level: str               # 'topic' | 'chapter' | 'module' | 'subject'
    ref_id: uuid.UUID        # UUID of the entity at this level
    name: str                # human-readable name
    retention_avg: float     # mean retention across children
    stability_avg: float     # mean stability across children
    urgency_avg: float       # mean urgency across children
    topics_total: int        # how many topic-level states contribute
    topics_at_risk: int      # topics where retention < 0.4
    weakest_topics: list[MemoryStateSummary] = Field(default_factory=list)


class UserRetentionOverview(BaseModel):
    """Top-level retention overview for a single user across all subjects."""

    user_id: uuid.UUID
    total_topics: int
    topics_tracked: int          # topics that have memory_states
    topics_at_risk: int          # retention < 0.4
    global_retention_avg: float
    global_stability_avg: float
    global_urgency_avg: float
    subjects: list[RetentionAggregate] = Field(default_factory=list)


class BatchMemoryStateRequest(BaseModel):
    """Request to get memory states for multiple topics at once."""

    user_id: uuid.UUID
    topic_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class BatchMemoryStateResponse(BaseModel):
    """Response containing memory states for multiple topics."""

    user_id: uuid.UUID
    states: list[MemoryStateSummary]
    total: int
