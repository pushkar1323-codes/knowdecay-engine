"""
app/services/memory_service.py
───────────────────────────────
Core memory state management service.

This is the PERSISTENCE + RETRIEVAL + AGGREGATION layer for memory_states.
All engine modules (retention, decay, priority, scheduler, recalibration)
write to memory_states through this service.

Architecture principles:
  • get_or_create: lazily initialises memory state on first access
  • update_incremental: applies partial field updates WITHOUT full recalculation
  • aggregate_*: computes hierarchical retention rollups from topic → subject
  • All writes go through a single code path for consistency and audit logging

This module does NOT contain retention formulas — those live in app/engine/.
This module ONLY manages state persistence, retrieval, and aggregation.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.hierarchy import Chapter, Module, Subject, Topic
from app.models.memory_state import MemoryState
from app.schemas.memory import (
    MemoryStateInit,
    MemoryStateSummary,
    MemoryStateUpdate,
    RetentionAggregate,
    UserRetentionOverview,
)
from app.utils.time_utils import utcnow

logger = logging.getLogger(__name__)

# Topics with retention below this threshold are considered "at risk"
AT_RISK_THRESHOLD = 0.4


# ═══════════════════════════════════════════════════════════════════════════════
#  CRUD — Create / Read
# ═══════════════════════════════════════════════════════════════════════════════

def get_memory_state(
    db: Session,
    user_id: uuid.UUID,
    topic_id: uuid.UUID,
) -> MemoryState | None:
    """
    Fetch the current memory state for a user × topic pair.
    Returns None if no state exists yet.
    """
    stmt = select(MemoryState).where(
        MemoryState.user_id == user_id,
        MemoryState.topic_id == topic_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_or_create_memory_state(
    db: Session,
    user_id: uuid.UUID,
    topic_id: uuid.UUID,
) -> tuple[MemoryState, bool]:
    """
    Return existing memory state or create a fresh one with default values.
    Returns (state, created) where created=True if a new row was inserted.

    This is the primary entry point — engine modules call this to ensure
    a state row exists before applying updates.
    """
    state = get_memory_state(db, user_id, topic_id)
    if state is not None:
        return state, False

    state = MemoryState(
        user_id=user_id,
        topic_id=topic_id,
        retention_score=0.0,
        stability_score=1.0,
        decay_rate=0.1,
        confidence_score=0.5,
        revision_strength=0.0,
        revision_count=0,
        forgetting_probability=1.0,
        urgency_score=0.0,
        last_revision_at=None,
        next_revision_at=None,
    )
    db.add(state)
    db.flush()

    logger.info(
        "Created memory state: user=%s topic=%s",
        user_id, topic_id,
    )
    return state, True


def init_memory_state(
    db: Session,
    payload: MemoryStateInit,
) -> MemoryState:
    """
    Explicitly initialise a memory state with caller-provided values.
    Used when a platform registers a topic for a user with known priors
    (e.g., a placement quiz already set initial retention).
    """
    state, created = get_or_create_memory_state(db, payload.user_id, payload.topic_id)
    if created:
        state.retention_score = payload.retention_score
        state.stability_score = payload.stability_score
        state.decay_rate = payload.decay_rate
        state.confidence_score = payload.confidence_score
        db.flush()
    db.commit()
    db.refresh(state)
    return state


# ═══════════════════════════════════════════════════════════════════════════════
#  INCREMENTAL UPDATE — The core evolution mechanism
# ═══════════════════════════════════════════════════════════════════════════════

def update_incremental(
    db: Session,
    user_id: uuid.UUID,
    topic_id: uuid.UUID,
    update: MemoryStateUpdate,
) -> MemoryState:
    """
    Apply a partial, incremental update to an existing memory state.

    ONLY the fields present in `update` (non-None) are modified.
    All other fields remain untouched.

    This is the ONLY write path for engine modules:
      retention_engine  → update retention_score, stability_score
      decay_engine      → update decay_rate, forgetting_probability
      priority_engine   → update urgency_score
      scheduler         → update next_revision_at
      recalibration     → update multiple fields after events

    The function guarantees:
      1. State row is created if missing (get_or_create)
      2. Only provided fields are written (no clobbering)
      3. updated_at is auto-bumped by ORM onupdate
    """
    state, _created = get_or_create_memory_state(db, user_id, topic_id)

    update_data = update.model_dump(exclude_none=True)
    if not update_data:
        return state

    for field, value in update_data.items():
        setattr(state, field, value)

    db.flush()

    logger.debug(
        "Updated memory state: user=%s topic=%s fields=%s",
        user_id, topic_id, list(update_data.keys()),
    )
    return state


def increment_revision(
    db: Session,
    user_id: uuid.UUID,
    topic_id: uuid.UUID,
    revision_timestamp: datetime | None = None,
) -> MemoryState:
    """
    Convenience method: bump revision_count by 1 and set last_revision_at.
    Called by recalibration_engine after any revision event.
    """
    state, _ = get_or_create_memory_state(db, user_id, topic_id)
    state.revision_count += 1
    state.last_revision_at = revision_timestamp or utcnow()
    db.flush()
    return state


# ═══════════════════════════════════════════════════════════════════════════════
#  RETRIEVAL — List / Filter / Batch
# ═══════════════════════════════════════════════════════════════════════════════

def list_memory_states(
    db: Session,
    user_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[MemoryState]:
    """List all memory states for a user, ordered by urgency DESC."""
    stmt = (
        select(MemoryState)
        .where(MemoryState.user_id == user_id)
        .order_by(MemoryState.urgency_score.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars().all())


def list_overdue(
    db: Session,
    user_id: uuid.UUID,
    as_of: datetime | None = None,
) -> list[MemoryState]:
    """
    Return all memory states where next_revision_at is in the past.
    Items that have never been scheduled (next_revision_at IS NULL)
    are included — they are always considered overdue.
    """
    now = as_of or utcnow()
    stmt = (
        select(MemoryState)
        .where(
            MemoryState.user_id == user_id,
            (MemoryState.next_revision_at <= now)
            | (MemoryState.next_revision_at.is_(None)),
        )
        .order_by(MemoryState.urgency_score.desc())
    )
    return list(db.execute(stmt).scalars().all())


def list_at_risk(
    db: Session,
    user_id: uuid.UUID,
    threshold: float = AT_RISK_THRESHOLD,
) -> list[MemoryState]:
    """Return memory states where retention is below the risk threshold."""
    stmt = (
        select(MemoryState)
        .where(
            MemoryState.user_id == user_id,
            MemoryState.retention_score < threshold,
        )
        .order_by(MemoryState.retention_score.asc())
    )
    return list(db.execute(stmt).scalars().all())


def batch_get(
    db: Session,
    user_id: uuid.UUID,
    topic_ids: list[uuid.UUID],
) -> list[MemoryState]:
    """Fetch memory states for a specific set of topics."""
    stmt = (
        select(MemoryState)
        .where(
            MemoryState.user_id == user_id,
            MemoryState.topic_id.in_(topic_ids),
        )
    )
    return list(db.execute(stmt).scalars().all())


def count_user_states(db: Session, user_id: uuid.UUID) -> int:
    """Count total memory states for a user."""
    stmt = select(func.count()).where(MemoryState.user_id == user_id)
    return db.execute(stmt).scalar() or 0


# ═══════════════════════════════════════════════════════════════════════════════
#  AGGREGATION — Hierarchical retention rollups
# ═══════════════════════════════════════════════════════════════════════════════
#
#  Architecture principle from the master spec:
#    Retention is calculated at the TOPIC level
#    and AGGREGATED UPWARD:
#      Topic → Chapter → Module → Subject
#
#  These functions compute averages from memory_states rows.
#  They do NOT recalculate retention formulas — they aggregate existing scores.

def _aggregate_states(
    states: list[MemoryState],
) -> dict:
    """
    Compute aggregate metrics from a list of memory states.
    Pure function — no DB access.
    """
    if not states:
        return {
            "retention_avg": 0.0,
            "stability_avg": 0.0,
            "urgency_avg": 0.0,
            "topics_total": 0,
            "topics_at_risk": 0,
        }

    n = len(states)
    return {
        "retention_avg": round(sum(s.retention_score for s in states) / n, 4),
        "stability_avg": round(sum(s.stability_score for s in states) / n, 4),
        "urgency_avg": round(sum(s.urgency_score for s in states) / n, 4),
        "topics_total": n,
        "topics_at_risk": sum(
            1 for s in states if s.retention_score < AT_RISK_THRESHOLD
        ),
    }


def _state_to_summary(state: MemoryState, topic_name: str = "") -> MemoryStateSummary:
    """Convert a MemoryState ORM object to a compact summary schema."""
    return MemoryStateSummary(
        topic_id=state.topic_id,
        topic_name=topic_name,
        retention_score=state.retention_score,
        stability_score=state.stability_score,
        forgetting_probability=state.forgetting_probability,
        urgency_score=state.urgency_score,
        revision_count=state.revision_count,
        last_revision_at=state.last_revision_at,
        next_revision_at=state.next_revision_at,
        # Adaptive stability
        adaptive_stability=state.adaptive_stability,
        stability_growth_rate=state.stability_growth_rate,
        half_life_days=state.half_life_days,
        # Decay parameters
        effective_decay_rate=state.effective_decay_rate,
        time_to_critical=state.time_to_critical,
        days_until_target=state.days_until_target,
        # Reinforcement behaviour
        quality_variance=state.quality_variance,
        effective_revision_count=state.effective_revision_count,
        revision_effectiveness_ratio=state.revision_effectiveness_ratio,
        time_pattern_regularity=state.time_pattern_regularity,
        confidence_calibration_error=state.confidence_calibration_error,
        # Retention history
        peak_retention=state.peak_retention,
        retention_at_last_revision=state.retention_at_last_revision,
        total_forgetting_events=state.total_forgetting_events,
    )


def aggregate_for_chapter(
    db: Session,
    user_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> RetentionAggregate:
    """
    Aggregate retention across all topics in a chapter.
    Chapter retention = mean of topic-level memory states.
    """
    chapter = db.get(Chapter, chapter_id)
    chapter_name = chapter.name if chapter else "Unknown"

    # Get topic_ids that belong to this chapter
    topic_ids_stmt = select(Topic.id).where(Topic.chapter_id == chapter_id)
    topic_ids = list(db.execute(topic_ids_stmt).scalars().all())

    if not topic_ids:
        return RetentionAggregate(
            level="chapter", ref_id=chapter_id, name=chapter_name,
            retention_avg=0.0, stability_avg=0.0, urgency_avg=0.0,
            topics_total=0, topics_at_risk=0,
        )

    states = batch_get(db, user_id, topic_ids)
    agg = _aggregate_states(states)

    # Find weakest topics (bottom 5 by retention)
    weakest = sorted(states, key=lambda s: s.retention_score)[:5]
    weakest_summaries = []
    for s in weakest:
        topic = db.get(Topic, s.topic_id)
        weakest_summaries.append(
            _state_to_summary(s, topic.name if topic else "")
        )

    return RetentionAggregate(
        level="chapter",
        ref_id=chapter_id,
        name=chapter_name,
        weakest_topics=weakest_summaries,
        **agg,
    )


def aggregate_for_module(
    db: Session,
    user_id: uuid.UUID,
    module_id: uuid.UUID,
) -> RetentionAggregate:
    """
    Aggregate retention across all topics in all chapters of a module.
    Module retention = mean of ALL topic-level states under this module.
    """
    module = db.get(Module, module_id)
    module_name = module.name if module else "Unknown"

    # chapters → topics
    topic_ids_stmt = (
        select(Topic.id)
        .join(Chapter, Topic.chapter_id == Chapter.id)
        .where(Chapter.module_id == module_id)
    )
    topic_ids = list(db.execute(topic_ids_stmt).scalars().all())

    states = batch_get(db, user_id, topic_ids) if topic_ids else []
    agg = _aggregate_states(states)

    weakest = sorted(states, key=lambda s: s.retention_score)[:5]
    weakest_summaries = []
    for s in weakest:
        topic = db.get(Topic, s.topic_id)
        weakest_summaries.append(
            _state_to_summary(s, topic.name if topic else "")
        )

    return RetentionAggregate(
        level="module",
        ref_id=module_id,
        name=module_name,
        weakest_topics=weakest_summaries,
        **agg,
    )


def aggregate_for_subject(
    db: Session,
    user_id: uuid.UUID,
    subject_id: uuid.UUID,
) -> RetentionAggregate:
    """
    Aggregate retention across all topics under a subject.
    Subject retention = mean of ALL topic-level states under this subject.
    This traverses: Subject → Module → Chapter → Topic → MemoryState.
    """
    subject = db.get(Subject, subject_id)
    subject_name = subject.name if subject else "Unknown"

    topic_ids_stmt = (
        select(Topic.id)
        .join(Chapter, Topic.chapter_id == Chapter.id)
        .join(Module, Chapter.module_id == Module.id)
        .where(Module.subject_id == subject_id)
    )
    topic_ids = list(db.execute(topic_ids_stmt).scalars().all())

    states = batch_get(db, user_id, topic_ids) if topic_ids else []
    agg = _aggregate_states(states)

    weakest = sorted(states, key=lambda s: s.retention_score)[:5]
    weakest_summaries = []
    for s in weakest:
        topic = db.get(Topic, s.topic_id)
        weakest_summaries.append(
            _state_to_summary(s, topic.name if topic else "")
        )

    return RetentionAggregate(
        level="subject",
        ref_id=subject_id,
        name=subject_name,
        weakest_topics=weakest_summaries,
        **agg,
    )


def get_user_overview(
    db: Session,
    user_id: uuid.UUID,
) -> UserRetentionOverview:
    """
    Build a complete retention overview for a user across all subjects.
    This is the top-level aggregation: user → all subjects → all topics.
    """
    # All memory states for this user
    all_states = list_memory_states(db, user_id, limit=10_000, offset=0)
    global_agg = _aggregate_states(all_states)

    # Total topics in the system (not just tracked ones)
    total_topics_stmt = select(func.count()).select_from(Topic)
    total_topics = db.execute(total_topics_stmt).scalar() or 0

    # Per-subject aggregation
    subject_ids_stmt = select(Subject.id)
    subject_ids = list(db.execute(subject_ids_stmt).scalars().all())
    subject_aggs = [
        aggregate_for_subject(db, user_id, sid) for sid in subject_ids
    ]

    return UserRetentionOverview(
        user_id=user_id,
        total_topics=total_topics,
        topics_tracked=global_agg["topics_total"],
        topics_at_risk=global_agg["topics_at_risk"],
        global_retention_avg=global_agg["retention_avg"],
        global_stability_avg=global_agg["stability_avg"],
        global_urgency_avg=global_agg["urgency_avg"],
        subjects=subject_aggs,
    )
