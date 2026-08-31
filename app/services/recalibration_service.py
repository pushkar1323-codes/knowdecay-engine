"""
app/services/recalibration_service.py
──────────────────────────────────────
Orchestration layer between the API and the recalibration engine.

Pipeline (KnowDecay Intelligence Backbone):
  1. MemoryState        — load current state from DB
  2. Adaptive Stability — compute S_adaptive from current state
  3. Decay + Retention  — recalibrate via pure engine (uses S_adaptive)
  4. Priority           — (deferred to priority_service)
  5. Scheduling         — compute next revision interval
  6. Analytics          — (deferred to analytics_service)
  7. Return response schema with full audit trail
"""

import logging
import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.engine.recalibration_engine import (
    CurrentState,
    EventData,
    EventType,
    RecalibrationOutput,
    recalibrate,
)
from app.engine.scheduling_engine import (
    ScheduleInput,
    compute_schedule,
)
from app.engine.stability_engine import (
    StabilityInput,
    compute_adaptive_stability,
)
from app.models.hierarchy import Topic
from app.schemas.recalibration import (
    BatchRecalibrationResponse,
    RecalibrationEventRequest,
    RecalibrationResponse,
    StateChangeDetail,
    StateDeltaResponse,
)
from app.services import memory_service
from app.utils.time_utils import utcnow

logger = logging.getLogger(__name__)


def _build_current_state(state) -> CurrentState:
    """
    Extract CurrentState from ORM MemoryState object.

    Maps ALL 26 fields — MemoryState is the single source of truth
    for the intelligence backbone.
    """
    return CurrentState(
        # Core retention intelligence
        retention_score=state.retention_score,
        stability_score=state.stability_score,
        decay_rate=state.decay_rate,
        confidence_score=state.confidence_score,
        revision_strength=state.revision_strength,
        revision_count=state.revision_count,
        forgetting_probability=state.forgetting_probability,
        urgency_score=state.urgency_score,
        # Adaptive forgetting curve (Phase 8.5)
        base_stability=state.base_stability,
        revision_quality=state.revision_quality,
        difficulty_factor=state.difficulty_factor,
        performance_trend=state.performance_trend,
        # Adaptive stability persistence
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


def _build_event_data(req: RecalibrationEventRequest, state, topic) -> EventData:
    """Build EventData from the API request + topic metadata."""
    now = utcnow()

    # Calculate elapsed days since last revision
    elapsed = 0.0
    if state.last_revision_at is not None:
        elapsed = (now - state.last_revision_at).total_seconds() / 86400.0

    difficulty = topic.difficulty if topic else 0.5
    importance = topic.importance_weight if topic else 1.0

    return EventData(
        event_type=EventType(req.event_type),
        quiz_score=req.quiz_score or 0.0,
        quiz_confidence=req.quiz_confidence or 0.5,
        study_duration_minutes=req.study_duration_minutes,
        elapsed_days=elapsed,
        days_inactive=req.days_inactive or elapsed,  # fallback to elapsed
        difficulty=difficulty,
        importance_weight=importance,
    )


def _apply_to_orm(state, out: RecalibrationOutput) -> None:
    """
    Apply recalibration output to the ORM memory state object.

    Maps ALL evolution fields — keeps MemoryState as the single
    source of truth for the intelligence backbone.
    """
    # Core retention intelligence
    state.retention_score = out.new_retention
    state.stability_score = out.new_stability
    state.decay_rate = out.new_decay_rate
    state.confidence_score = out.new_confidence
    state.revision_strength = out.new_revision_strength
    state.revision_count = out.new_revision_count
    state.forgetting_probability = out.new_forgetting_probability
    state.urgency_score = out.new_urgency
    # Adaptive forgetting curve (Phase 8.5)
    state.base_stability = out.new_base_stability
    state.revision_quality = out.new_revision_quality
    state.difficulty_factor = out.new_difficulty_factor
    state.performance_trend = out.new_performance_trend
    # Adaptive stability persistence
    state.adaptive_stability = out.new_adaptive_stability
    state.stability_growth_rate = out.new_stability_growth_rate
    state.half_life_days = out.new_half_life_days
    # Decay parameters
    state.effective_decay_rate = out.new_effective_decay_rate
    state.time_to_critical = out.new_time_to_critical
    state.days_until_target = out.new_days_until_target
    # Reinforcement behaviour
    state.quality_variance = out.new_quality_variance
    state.effective_revision_count = out.new_effective_revision_count
    state.revision_effectiveness_ratio = out.new_revision_effectiveness_ratio
    state.time_pattern_regularity = out.new_time_pattern_regularity
    state.confidence_calibration_error = out.new_confidence_calibration_error
    # Retention history
    state.peak_retention = out.new_peak_retention
    state.retention_at_last_revision = out.new_retention_at_last_revision
    state.total_forgetting_events = out.new_total_forgetting_events


def _compute_pre_stability(
    current: CurrentState,
    event: EventData,
) -> "StabilityOutput":
    """
    Backbone Stage 2: Compute adaptive stability BEFORE recalibration.

    This feeds S_adaptive into the decay/retention computation,
    ensuring the pipeline flows:
      MemoryState → Stability → Decay → Retention → ...
    """
    from app.engine.stability_engine import StabilityOutput  # noqa: F811

    stab_input = StabilityInput(
        base_stability=current.base_stability,
        revision_count=current.revision_count,
        revision_quality=current.revision_quality,
        quiz_score=event.quiz_score,
        confidence_score=current.confidence_score,
        performance_trend=current.performance_trend,
        difficulty=event.difficulty,
    )
    return compute_adaptive_stability(stab_input)


def _reschedule(
    state,
    out: RecalibrationOutput,
    days_until_exam: float | None,
    stab_adaptive: float,
) -> None:
    """
    Backbone Stage 6: Scheduling — compute next revision interval.

    Uses the pre-computed S_adaptive from the stability stage,
    NOT a redundant recomputation.
    """
    now = utcnow()

    sched_input = ScheduleInput(
        retention_score=out.new_retention,
        stability_score=out.new_stability,
        decay_rate=out.new_decay_rate,
        urgency_score=out.new_urgency,
        revision_count=out.new_revision_count,
        forgetting_probability=out.new_forgetting_probability,
        difficulty=out.new_difficulty_factor,
        days_until_exam=days_until_exam,
        adaptive_stability=stab_adaptive,
    )
    sched_out = compute_schedule(sched_input)
    state.next_revision_at = now + timedelta(days=sched_out.next_revision_days)

    # Persist S_adaptive to ORM (backbone persistence)
    state.adaptive_stability = stab_adaptive

    # Update last_revision_at for revision/quiz events
    if out.event_type in (EventType.QUIZ_SUBMITTED, EventType.REVISION_COMPLETED):
        state.last_revision_at = now


def _build_response(
    user_id: uuid.UUID,
    topic_id: uuid.UUID,
    out: RecalibrationOutput,
    next_revision_at,
) -> RecalibrationResponse:
    """Convert engine output to API response schema."""
    return RecalibrationResponse(
        user_id=user_id,
        topic_id=topic_id,
        event_type=out.event_type.value,
        new_retention=out.new_retention,
        new_stability=out.new_stability,
        new_decay_rate=out.new_decay_rate,
        new_confidence=out.new_confidence,
        new_revision_strength=out.new_revision_strength,
        new_revision_count=out.new_revision_count,
        new_forgetting_probability=out.new_forgetting_probability,
        new_urgency=out.new_urgency,
        delta=StateDeltaResponse(
            retention_delta=out.delta.retention_delta,
            stability_delta=out.delta.stability_delta,
            decay_rate_new=out.delta.decay_rate_new,
            confidence_delta=out.delta.confidence_delta,
            revision_strength_delta=out.delta.revision_strength_delta,
            revision_count_delta=out.delta.revision_count_delta,
            forgetting_probability_new=out.delta.forgetting_probability_new,
            urgency_delta=out.delta.urgency_delta,
        ),
        changes=[
            StateChangeDetail(
                field=c.field,
                old_value=c.old_value,
                new_value=c.new_value,
                reason=c.reason,
            )
            for c in out.changes
        ],
        summary=out.summary,
        next_revision_at=next_revision_at,
    )


def process_event(
    db: Session,
    req: RecalibrationEventRequest,
    *,
    persist: bool = True,
) -> RecalibrationResponse:
    """
    Process a single recalibration event.

    KnowDecay Intelligence Backbone:
      1. MemoryState        → load/create from DB
      2. Adaptive Stability → compute S_adaptive from current state
      3. Decay + Retention  → recalibrate (uses S_adaptive)
      4. Apply to ORM       → persist new values
      5. Scheduling         → compute next revision interval
      6. Return response    → full audit trail
    """
    # Stage 1: MemoryState
    state, _ = memory_service.get_or_create_memory_state(db, req.user_id, req.topic_id)
    topic = db.get(Topic, req.topic_id)

    current = _build_current_state(state)
    event = _build_event_data(req, state, topic)

    # Stage 2: Adaptive Stability (BEFORE decay/retention)
    stab_out = _compute_pre_stability(current, event)

    # Inject S_adaptive into current state for decay computation
    current = CurrentState(**{
        **{f: getattr(current, f) for f in CurrentState.__dataclass_fields__},
        "adaptive_stability": stab_out.adaptive_stability,
    })

    # Stage 3+4: Decay → Retention (inside recalibrate)
    out: RecalibrationOutput = recalibrate(current, event)

    if persist:
        _apply_to_orm(state, out)
        # Stage 5: Scheduling (uses pre-computed S_adaptive)
        _reschedule(state, out, req.days_until_exam, stab_out.adaptive_stability)
        db.flush()

    return _build_response(req.user_id, req.topic_id, out, state.next_revision_at)


def process_batch(
    db: Session,
    events: list[RecalibrationEventRequest],
    *,
    persist: bool = True,
) -> BatchRecalibrationResponse:
    """
    Process multiple recalibration events sequentially.

    Events are processed in order — later events for the same
    user×topic see the results of earlier events in the batch.
    """
    results: list[RecalibrationResponse] = []
    errors = 0

    for req in events:
        try:
            result = process_event(db, req, persist=persist)
            results.append(result)
        except Exception:
            logger.warning(
                "Recalibration failed for user=%s topic=%s event=%s",
                req.user_id, req.topic_id, req.event_type,
                exc_info=True,
            )
            errors += 1

    return BatchRecalibrationResponse(
        results=results,
        total_processed=len(results),
        total_errors=errors,
    )
