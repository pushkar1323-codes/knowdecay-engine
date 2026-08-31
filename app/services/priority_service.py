"""
app/services/priority_service.py
──────────────────────────────────
Orchestration layer between the API and the priority engine.

Responsibilities:
  1. Load memory state + topic metadata from DB
  2. Compute real-time retention via adaptive forgetting engine
  3. Build PriorityInput with pre-computed retention values
  4. Call the pure priority engine (which never estimates retention itself)
  5. Persist updated urgency_score back to memory_state
  6. Return response schemas with rank positions
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.engine.adaptive_forgetting import (
    ForgettingInput,
    compute_adaptive_forgetting,
)
from app.engine.priority_engine import (
    PriorityInput,
    PriorityOutput,
    compute_priority,
    rank_topics,
)
from app.models.hierarchy import Topic
from app.schemas.priority import (
    PriorityBreakdown,
    PriorityBatchResponse,
    PriorityRankResponse,
    PriorityReasonResponse,
)
from app.services import memory_service
from app.services.ml_feature_builder import build_ml_features
from app.utils.time_utils import utcnow

logger = logging.getLogger(__name__)


def _build_priority_input(
    state,
    topic,
    *,
    days_until_exam: float | None = None,
    importance_override: float | None = None,
) -> PriorityInput:
    """
    Construct PriorityInput from a memory_state ORM object + topic metadata.

    Real-time retention is computed HERE using the adaptive forgetting engine
    (R = e^(-t/S_adaptive)), ensuring the priority engine always receives
    fresh retention values — never stale persisted scores.
    """
    now = utcnow()

    # Elapsed days since last revision
    if state.last_revision_at is not None:
        elapsed = (now - state.last_revision_at).total_seconds() / 86400.0
    else:
        elapsed = 0.0

    # Days overdue: positive if past next_revision_at
    days_overdue = 0.0
    if state.next_revision_at is not None and now > state.next_revision_at:
        days_overdue = (now - state.next_revision_at).total_seconds() / 86400.0

    difficulty = topic.difficulty if topic else 0.5
    importance = importance_override or (topic.importance_weight if topic else 1.0)

    # ── Compute real-time retention from adaptive forgetting curve ─────────
    # The service layer is responsible for retention estimation.
    # The priority engine CONSUMES these values — it never calls the
    # forgetting engine itself. This preserves separation of concerns.
    base_stability = getattr(state, 'base_stability', None)
    if base_stability is not None and elapsed > 0:
        ml = build_ml_features(state, difficulty=difficulty)
        forg_out = compute_adaptive_forgetting(ForgettingInput(
            elapsed_days=elapsed,
            base_stability=base_stability,
            revision_count=state.revision_count,
            revision_quality=getattr(state, 'revision_quality', 0.5),
            quiz_score=0.0,  # not available at priority query time
            confidence_score=state.confidence_score,
            performance_trend=getattr(state, 'performance_trend', 0.0),
            difficulty=difficulty,
            ml_stability_correction=ml.stability_correction,
            ml_decay_modifier=ml.decay_modifier,
            ml_blend_weight=ml.blend_weight,
        ))
        realtime_retention = forg_out.retention
        realtime_forgetting = forg_out.forgetting_probability
    else:
        # Fallback: use persisted values (pre-Phase-8.5 or zero elapsed)
        realtime_retention = state.retention_score
        realtime_forgetting = state.forgetting_probability

    return PriorityInput(
        retention_score=realtime_retention,
        forgetting_probability=realtime_forgetting,
        stability_score=state.stability_score,
        decay_rate=state.decay_rate,
        revision_count=state.revision_count,
        days_since_last_revision=elapsed,
        days_overdue=days_overdue,
        difficulty=difficulty,
        importance_weight=importance,
        days_until_exam=days_until_exam,
        weakness_trend=0.0,         # Phase 7 recalibration will populate this
        recent_quiz_score=None,     # Phase 7 recalibration will populate this
    )


def _build_response(
    user_id: uuid.UUID,
    topic_id: uuid.UUID,
    topic_name: str | None,
    state,
    out: PriorityOutput,
    rank: int | None = None,
) -> PriorityRankResponse:
    """Convert engine output + state into API response schema."""
    return PriorityRankResponse(
        user_id=user_id,
        topic_id=topic_id,
        topic_name=topic_name,
        priority_score=out.priority_score,
        normalised_score=out.normalised_score,
        tier=out.tier.value,
        retention_score=state.retention_score,
        forgetting_probability=state.forgetting_probability,
        revision_count=state.revision_count,
        last_revision_at=state.last_revision_at,
        breakdown=PriorityBreakdown(
            urgency_component=out.urgency_component,
            weakness_component=out.weakness_component,
            delay_component=out.delay_component,
            exam_component=out.exam_component,
        ),
        reason=PriorityReasonResponse(
            urgency_reason=out.reason.urgency_reason,
            weakness_reason=out.reason.weakness_reason,
            delay_reason=out.reason.delay_reason,
            exam_reason=out.reason.exam_reason,
            summary=out.reason.summary,
        ),
        rank=rank,
    )


def rank_single(
    db: Session,
    user_id: uuid.UUID,
    topic_id: uuid.UUID,
    *,
    days_until_exam: float | None = None,
    importance_override: float | None = None,
    persist: bool = True,
) -> PriorityRankResponse:
    """
    Compute priority for a single user × topic.

    Loads memory state, runs the engine, optionally persists
    the urgency_score back to memory_state.
    """
    state, _ = memory_service.get_or_create_memory_state(db, user_id, topic_id)
    topic = db.get(Topic, topic_id)
    topic_name = topic.name if topic else None

    inp = _build_priority_input(
        state, topic,
        days_until_exam=days_until_exam,
        importance_override=importance_override,
    )
    out = compute_priority(inp)

    # Persist urgency score back to memory state
    if persist:
        state.urgency_score = out.normalised_score
        db.flush()

    return _build_response(user_id, topic_id, topic_name, state, out)


def rank_batch(
    db: Session,
    user_id: uuid.UUID,
    topic_ids: list[uuid.UUID],
    *,
    days_until_exam: float | None = None,
    limit: int | None = None,
    persist: bool = True,
) -> PriorityBatchResponse:
    """
    Rank multiple topics by priority (descending).

    Steps:
      1. Load all memory states and topics
      2. Build PriorityInput for each
      3. Call rank_topics (batch computation + sort)
      4. Persist updated urgency scores
      5. Return ranked list with positions
    """
    # Pre-load states and topics
    inputs: list[tuple[uuid.UUID, PriorityInput]] = []
    states: dict[uuid.UUID, object] = {}
    topics: dict[uuid.UUID, Topic | None] = {}

    for tid in topic_ids:
        try:
            state, _ = memory_service.get_or_create_memory_state(db, user_id, tid)
            topic = db.get(Topic, tid)
            states[tid] = state
            topics[tid] = topic

            inp = _build_priority_input(
                state, topic, days_until_exam=days_until_exam,
            )
            inputs.append((tid, inp))
        except Exception:
            logger.warning("Failed to build input for topic=%s", tid, exc_info=True)

    # Rank
    ranked = rank_topics(inputs, limit=limit)

    # Build responses with rank positions
    results: list[PriorityRankResponse] = []
    for position, (tid, out) in enumerate(ranked, start=1):
        state = states[tid]
        topic = topics.get(tid)
        topic_name = topic.name if topic else None

        if persist:
            state.urgency_score = out.normalised_score

        results.append(_build_response(
            user_id, tid, topic_name, state, out, rank=position,
        ))

    if persist:
        db.flush()

    return PriorityBatchResponse(
        user_id=user_id,
        rankings=results,
        total=len(results),
    )
