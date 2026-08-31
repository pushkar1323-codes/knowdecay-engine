"""
app/services/retention_service.py
──────────────────────────────────
Orchestration layer between the API and the retention engine.

Responsibilities:
  1. Load memory state + topic metadata from DB
  2. Build RetentionInput from persisted data + request overrides
  3. Call the pure retention engine
  4. Persist updated scores back to memory_state (incremental update)
  5. Return response schemas

This module DOES access the database (via memory_service).
The retention_engine module does NOT.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.engine.retention_engine import (
    RetentionInput,
    RetentionOutput,
    compute_retention,
)
from app.models.hierarchy import Topic
from app.schemas.memory import MemoryStateUpdate
from app.schemas.retention import (
    RetentionBreakdown,
    RetentionPredictResponse,
)
from app.services import memory_service
from app.utils.time_utils import utcnow

logger = logging.getLogger(__name__)


def predict_retention(
    db: Session,
    user_id: uuid.UUID,
    topic_id: uuid.UUID,
    *,
    study_duration_override: float | None = None,
    quiz_score_override: float | None = None,
    quiz_confidence_override: float | None = None,
    elapsed_days_override: float | None = None,
    persist: bool = True,
) -> RetentionPredictResponse:
    """
    Predict current retention for a user × topic pair.

    Steps:
      1. Fetch (or create) memory state
      2. Fetch topic metadata (difficulty, importance_weight)
      3. Build RetentionInput with DB data + optional overrides
      4. Run the pure engine computation
      5. Persist updated scores to memory_state (if persist=True)
      6. Return the full response with explainability breakdown

    The `persist` flag defaults to True so that every prediction also
    updates the stored state. Set to False for "what-if" simulations.
    """
    # ── 1. Memory state ───────────────────────────────────────────────────────
    state, _created = memory_service.get_or_create_memory_state(db, user_id, topic_id)

    # ── 2. Topic metadata ─────────────────────────────────────────────────────
    topic = db.get(Topic, topic_id)
    difficulty = topic.difficulty if topic else 0.5
    importance = topic.importance_weight if topic else 1.0
    topic_name = topic.name if topic else None

    # ── 3. Build input ────────────────────────────────────────────────────────
    # Compute elapsed_days from last_revision_at
    now = utcnow()
    if elapsed_days_override is not None:
        elapsed = elapsed_days_override
    elif state.last_revision_at is not None:
        delta = now - state.last_revision_at
        elapsed = delta.total_seconds() / 86400.0
    else:
        elapsed = 0.0

    has_quiz = (quiz_score_override is not None) or (state.revision_count > 0)
    quiz_score = quiz_score_override if quiz_score_override is not None else 0.0
    quiz_conf = quiz_confidence_override if quiz_confidence_override is not None else state.confidence_score

    inp = RetentionInput(
        study_duration_minutes=study_duration_override or 0.0,
        quiz_score=quiz_score,
        quiz_confidence=quiz_conf,
        has_quiz=has_quiz,
        revision_count=state.revision_count,
        revision_strength=state.revision_strength,
        elapsed_days=elapsed,
        decay_rate=state.decay_rate,
        difficulty=difficulty,
        importance_weight=importance,
    )

    # ── 4. Run engine ─────────────────────────────────────────────────────────
    result: RetentionOutput = compute_retention(inp)

    # ── 5. Persist ────────────────────────────────────────────────────────────
    if persist:
        update = MemoryStateUpdate(
            retention_score=result.retention_score,
            stability_score=result.stability_score,
            confidence_score=result.confidence_score,
            forgetting_probability=result.forgetting_probability,
            decay_rate=result.decay_rate,
        )
        memory_service.update_incremental(db, user_id, topic_id, update)
        db.flush()

    # ── 6. Build response ─────────────────────────────────────────────────────
    return RetentionPredictResponse(
        user_id=user_id,
        topic_id=topic_id,
        topic_name=topic_name,
        retention_score=result.retention_score,
        stability_score=result.stability_score,
        confidence_score=result.confidence_score,
        forgetting_probability=result.forgetting_probability,
        decay_rate=result.decay_rate,
        revision_count=state.revision_count,
        last_revision_at=state.last_revision_at,
        breakdown=RetentionBreakdown(
            base_strength=result.base_strength,
            revision_reinforcement=result.revision_reinforcement,
            quiz_boost=result.quiz_boost,
            time_decay=result.time_decay,
            difficulty_penalty=result.difficulty_penalty,
        ),
    )


def predict_retention_batch(
    db: Session,
    user_id: uuid.UUID,
    topic_ids: list[uuid.UUID],
    *,
    persist: bool = True,
) -> list[RetentionPredictResponse]:
    """
    Predict retention for multiple topics in one call.
    Each topic is computed independently — no cross-topic dependencies.
    """
    results = []
    for tid in topic_ids:
        try:
            result = predict_retention(db, user_id, tid, persist=persist)
            results.append(result)
        except Exception:
            logger.warning(
                "Failed to predict retention for user=%s topic=%s",
                user_id, tid, exc_info=True,
            )
    return results
