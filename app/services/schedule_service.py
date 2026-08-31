"""
app/services/schedule_service.py
─────────────────────────────────
Orchestration layer between the API and the scheduling engine.

Responsibilities:
  1. Load memory state + topic metadata from DB
  2. Compute real-time retention via adaptive forgetting engine
  3. Build ScheduleInput with pre-computed retention + adaptive stability
  4. Call the pure scheduling engine (which never estimates retention itself)
  5. Persist next_revision_at back to memory_state
  6. Return response schemas
"""

import logging
import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.engine.adaptive_forgetting import (
    ForgettingInput,
    compute_adaptive_forgetting,
)
from app.engine.scheduling_engine import (
    ScheduleInput,
    ScheduleOutput,
    compute_schedule,
    generate_schedule,
    select_mode,
)
from app.models.hierarchy import Topic
from app.schemas.schedule import (
    ScheduleBreakdown,
    ScheduleGenerateResponse,
    ScheduleSingleResponse,
    ScheduleSlotResponse,
)
from app.services import memory_service
from app.services.ml_feature_builder import build_ml_features
from app.utils.time_utils import utcnow

logger = logging.getLogger(__name__)


def _build_schedule_input(
    state,
    topic,
    *,
    days_until_exam: float | None = None,
) -> ScheduleInput:
    """
    Construct ScheduleInput from memory_state + topic metadata.

    Real-time retention is computed HERE using the adaptive forgetting engine
    (R = e^(-t/S_adaptive)), ensuring the scheduling engine always receives
    fresh retention values — never stale persisted scores.
    """
    now = utcnow()

    if state.last_revision_at is not None:
        elapsed = (now - state.last_revision_at).total_seconds() / 86400.0
    else:
        elapsed = 0.0

    difficulty = topic.difficulty if topic else 0.5
    importance = topic.importance_weight if topic else 1.0

    # ── Compute real-time retention from adaptive forgetting curve ─────────
    # The service layer is responsible for retention estimation.
    # The scheduling engine CONSUMES these values — it never calls the
    # forgetting engine itself. This preserves separation of concerns.
    base_stability = getattr(state, 'base_stability', None)
    adaptive_stability_value = None

    if base_stability is not None and elapsed > 0:
        ml = build_ml_features(state, difficulty=difficulty)
        forg_out = compute_adaptive_forgetting(ForgettingInput(
            elapsed_days=elapsed,
            base_stability=base_stability,
            revision_count=state.revision_count,
            revision_quality=getattr(state, 'revision_quality', 0.5),
            quiz_score=0.0,
            confidence_score=state.confidence_score,
            performance_trend=getattr(state, 'performance_trend', 0.0),
            difficulty=difficulty,
            ml_stability_correction=ml.stability_correction,
            ml_decay_modifier=ml.decay_modifier,
            ml_blend_weight=ml.blend_weight,
        ))
        realtime_retention = forg_out.retention
        realtime_forgetting = forg_out.forgetting_probability
        adaptive_stability_value = forg_out.adaptive_stability
    else:
        # Fallback: use persisted values (pre-Phase-8.5 or zero elapsed)
        realtime_retention = state.retention_score
        realtime_forgetting = state.forgetting_probability

    return ScheduleInput(
        retention_score=realtime_retention,
        stability_score=state.stability_score,
        decay_rate=state.decay_rate,
        urgency_score=state.urgency_score,
        revision_count=state.revision_count,
        forgetting_probability=realtime_forgetting,
        difficulty=difficulty,
        importance_weight=importance,
        days_until_exam=days_until_exam,
        days_since_last_revision=elapsed,
        adaptive_stability=adaptive_stability_value,
    )


def schedule_single(
    db: Session,
    user_id: uuid.UUID,
    topic_id: uuid.UUID,
    *,
    days_until_exam: float | None = None,
    persist: bool = True,
) -> ScheduleSingleResponse:
    """
    Compute the next revision time for a single topic.

    Loads memory state, runs the scheduling engine,
    persists next_revision_at, and returns the full response.
    """
    state, _ = memory_service.get_or_create_memory_state(db, user_id, topic_id)
    topic = db.get(Topic, topic_id)
    topic_name = topic.name if topic else None

    inp = _build_schedule_input(state, topic, days_until_exam=days_until_exam)
    out: ScheduleOutput = compute_schedule(inp)

    now = utcnow()
    next_at = now + timedelta(days=out.next_revision_days)

    if persist:
        state.next_revision_at = next_at
        db.flush()

    return ScheduleSingleResponse(
        user_id=user_id,
        topic_id=topic_id,
        topic_name=topic_name,
        next_revision_days=out.next_revision_days,
        next_revision_at=next_at,
        mode=out.mode.value,
        schedule_priority=out.schedule_priority,
        retention_score=state.retention_score,
        revision_count=state.revision_count,
        breakdown=ScheduleBreakdown(
            base_interval=out.base_interval,
            adjusted_interval=out.adjusted_interval,
            retention_factor=out.retention_factor,
            difficulty_modifier=out.difficulty_modifier,
            exam_compression=out.exam_compression,
        ),
        recommendation=out.recommendation,
    )


def schedule_batch(
    db: Session,
    user_id: uuid.UUID,
    topic_ids: list[uuid.UUID],
    *,
    days_until_exam: float | None = None,
    max_per_day: int = 10,
    persist: bool = True,
) -> ScheduleGenerateResponse:
    """
    Generate a full revision schedule across multiple topics.

    Loads all memory states, runs the multi-topic scheduler,
    persists all next_revision_at timestamps, and returns the plan.
    """
    inputs: list[tuple[uuid.UUID, ScheduleInput]] = []
    states: dict[uuid.UUID, object] = {}
    topics: dict[uuid.UUID, Topic | None] = {}

    for tid in topic_ids:
        try:
            state, _ = memory_service.get_or_create_memory_state(db, user_id, tid)
            topic = db.get(Topic, tid)
            states[tid] = state
            topics[tid] = topic

            inp = _build_schedule_input(state, topic, days_until_exam=days_until_exam)
            inputs.append((tid, inp))
        except Exception:
            logger.warning("Failed to build schedule input for topic=%s", tid, exc_info=True)

    slots = generate_schedule(inputs, max_per_day=max_per_day)

    now = utcnow()
    mode = select_mode(days_until_exam)
    day_buckets: set[int] = set()
    response_slots: list[ScheduleSlotResponse] = []

    for slot in slots:
        tid = slot.topic_id
        topic = topics.get(tid)
        topic_name = topic.name if topic else None
        day_buckets.add(int(slot.day))

        if persist and tid in states:
            next_at = now + timedelta(days=slot.day)
            states[tid].next_revision_at = next_at

        response_slots.append(ScheduleSlotResponse(
            topic_id=tid,
            topic_name=topic_name,
            day=slot.day,
            priority=slot.priority,
            mode=slot.mode.value,
            recommendation=slot.recommendation,
        ))

    if persist:
        db.flush()

    return ScheduleGenerateResponse(
        user_id=user_id,
        schedule=response_slots,
        mode=mode.value,
        total_topics=len(response_slots),
        total_days=len(day_buckets),
    )
