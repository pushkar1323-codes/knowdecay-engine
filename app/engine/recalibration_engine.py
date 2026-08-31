"""
app/engine/recalibration_engine.py
────────────────────────────────────
Event-driven memory state evolution engine.

This module is the NERVOUS SYSTEM of KnowDecay — it processes learning
events and produces incremental state deltas. It does NOT reset or
fully recompute memory states. It EVOLVES them.

Trigger Events
══════════════
  QUIZ_SUBMITTED        — learner took a quiz → strongest signal
  REVISION_COMPLETED    — learner finished a revision session
  STUDY_SESSION         — learner studied (no quiz)
  INACTIVITY_DETECTED   — system detected prolonged absence

Architecture
════════════
  event + current_state → recalibration_engine → StateDeltas
                                                    ↓
                                           service layer applies
                                           deltas incrementally

Each event type has a DIFFERENT recalibration pathway:
  • Quiz     → recomputes retention, stability, confidence, decay_rate
  • Revision → reinforces retention, bumps revision_count, extends stability
  • Study    → modest retention boost, updates study duration
  • Inactivity → degrades retention, increases urgency, shortens stability

Design principles:
  • All functions are PURE — no DB, no I/O
  • Deltas are INCREMENTAL — add/subtract from current state
  • No state is ever RESET — only evolved
  • Every recalibration produces an audit trail of what changed and why
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from app.engine.retention_engine import (
    RetentionInput,
    RetentionOutput,
    compute_retention,
    compute_updated_decay_rate,
)
from app.engine.decay_engine import (
    compute_effective_decay_rate,
    compute_forgetting_probability,
    compute_inactivity_penalty,
)
from app.engine.stability_engine import (
    evolve_stability,
    degrade_stability,
)
from app.engine.adaptive_forgetting import (
    estimate_retention_after_event,
    compute_optimal_revision_time,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Enums
# ═══════════════════════════════════════════════════════════════════════════════

class EventType(str, Enum):
    """Learning events that trigger recalibration."""

    QUIZ_SUBMITTED = "quiz_submitted"
    REVISION_COMPLETED = "revision_completed"
    STUDY_SESSION = "study_session"
    INACTIVITY_DETECTED = "inactivity_detected"


# ═══════════════════════════════════════════════════════════════════════════════
#  Data Transfer Objects
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class CurrentState:
    """
    Snapshot of the current memory state before recalibration.
    Maps directly to MemoryState model fields.
    """

    retention_score: float = 0.0
    stability_score: float = 1.0
    decay_rate: float = 0.1
    confidence_score: float = 0.5
    revision_strength: float = 0.0
    revision_count: int = 0
    forgetting_probability: float = 1.0
    urgency_score: float = 0.0

    # Adaptive forgetting curve fields (Phase 8.5)
    base_stability: float = 1.0
    revision_quality: float = 0.5
    difficulty_factor: float = 0.5
    performance_trend: float = 0.0

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


@dataclass(frozen=True, slots=True)
class EventData:
    """
    Event-specific data attached to a trigger.
    Not all fields apply to every event type.
    """

    event_type: EventType

    # Quiz event fields
    quiz_score: float = 0.0             # 0.0–1.0
    quiz_confidence: float = 0.5        # 0.0–1.0 self-reported

    # Study/revision fields
    study_duration_minutes: float = 0.0
    topics_covered: int = 1

    # Time context
    elapsed_days: float = 0.0           # days since last revision/study
    days_inactive: float = 0.0          # for inactivity events

    # Topic context
    difficulty: float = 0.5
    importance_weight: float = 1.0


@dataclass(frozen=True, slots=True)
class StateDelta:
    """
    Incremental changes to apply to the memory state.
    Positive values = increase, negative values = decrease.
    None = no change to that field.
    """

    retention_delta: float = 0.0
    stability_delta: float = 0.0
    decay_rate_new: float | None = None     # absolute replacement (not delta)
    confidence_delta: float = 0.0
    revision_strength_delta: float = 0.0
    revision_count_delta: int = 0
    forgetting_probability_new: float | None = None  # absolute replacement
    urgency_delta: float = 0.0

    # Adaptive forgetting curve deltas (Phase 8.5)
    base_stability_new: float | None = None         # absolute replacement
    revision_quality_new: float | None = None        # absolute replacement
    difficulty_factor_new: float | None = None       # absolute replacement
    performance_trend_new: float | None = None       # absolute replacement

    # Adaptive stability persistence
    adaptive_stability_new: float | None = None
    stability_growth_rate_new: float | None = None
    half_life_days_new: float | None = None

    # Decay parameters
    effective_decay_rate_new: float | None = None
    time_to_critical_new: float | None = None
    days_until_target_new: float | None = None

    # Reinforcement behaviour
    quality_variance_new: float | None = None
    effective_revision_count_delta: int = 0
    revision_effectiveness_ratio_new: float | None = None
    time_pattern_regularity_new: float | None = None
    confidence_calibration_error_new: float | None = None

    # Retention history
    peak_retention_new: float | None = None
    retention_at_last_revision_new: float | None = None
    total_forgetting_events_delta: int = 0


@dataclass(frozen=True, slots=True)
class ChangeReason:
    """What changed and why — audit trail for every recalibration."""

    field: str
    old_value: float
    new_value: float
    reason: str


@dataclass(frozen=True, slots=True)
class RecalibrationOutput:
    """
    Complete result of a recalibration event.
    """

    event_type: EventType

    # New absolute state values (after applying deltas)
    new_retention: float
    new_stability: float
    new_decay_rate: float
    new_confidence: float
    new_revision_strength: float
    new_revision_count: int
    new_forgetting_probability: float
    new_urgency: float

    # The delta that was applied
    delta: StateDelta

    # Explainability
    changes: list[ChangeReason]
    summary: str

    # Adaptive forgetting curve values (Phase 8.5) — defaults last
    new_base_stability: float = 1.0
    new_revision_quality: float = 0.5
    new_difficulty_factor: float = 0.5
    new_performance_trend: float = 0.0

    # Adaptive stability persistence
    new_adaptive_stability: float = 1.0
    new_stability_growth_rate: float = 0.0
    new_half_life_days: float = 0.0

    # Decay parameters
    new_effective_decay_rate: float = 0.1
    new_time_to_critical: float = 0.0
    new_days_until_target: float = 0.0

    # Reinforcement behaviour
    new_quality_variance: float = 0.0
    new_effective_revision_count: int = 0
    new_revision_effectiveness_ratio: float = 0.0
    new_time_pattern_regularity: float = 0.5
    new_confidence_calibration_error: float = 0.0

    # Retention history
    new_peak_retention: float = 0.0
    new_retention_at_last_revision: float = 0.0
    new_total_forgetting_events: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
#  Default Parameters
# ═══════════════════════════════════════════════════════════════════════════════

# Revision reinforcement
REVISION_STRENGTH_GAIN: float = 0.1         # strength gain per revision
REVISION_RETENTION_BOOST: float = 0.05      # retention boost per revision (diminishing)
REVISION_STABILITY_BOOST: float = 0.15      # stability extension per revision

# Quiz recalibration
QUIZ_SCORE_WEIGHT: float = 0.6              # how much quiz moves retention
QUIZ_CONFIDENCE_WEIGHT: float = 0.3         # quiz-inferred vs self-reported blend

# Study session
STUDY_RETENTION_RATE: float = 0.002         # retention gain per minute studied
STUDY_SATURATION: float = 60.0              # minutes after which gain plateaus
STUDY_STRENGTH_GAIN: float = 0.03           # strength gain per study session

# Inactivity
INACTIVITY_RETENTION_LOSS_RATE: float = 0.01  # retention loss per day inactive (beyond onset)
INACTIVITY_URGENCY_GAIN: float = 0.02         # urgency gain per inactive day
INACTIVITY_ONSET_DAYS: float = 7.0             # days before inactivity penalty kicks in

# General
RETENTION_FLOOR: float = 0.05
RETENTION_CEILING: float = 1.0


# ═══════════════════════════════════════════════════════════════════════════════
#  Event-Specific Recalibration Functions
# ═══════════════════════════════════════════════════════════════════════════════

def recalibrate_quiz(
    state: CurrentState,
    event: EventData,
) -> tuple[StateDelta, list[ChangeReason]]:
    """
    Recalibrate after a quiz submission — the STRONGEST signal.

    What happens:
      1. Retention is recalculated using the retention engine
      2. Decay rate is updated based on quiz performance
      3. Confidence is blended from quiz score + self-report
      4. Stability extends for good performance, contracts for poor
      5. Revision count and strength are incremented
      6. Forgetting probability is recomputed
      7. Urgency adjusts inversely to performance

    The quiz score drives the magnitude:
      High score → reinforce (↑retention, ↑stability, ↓decay, ↓urgency)
      Low score  → alert     (↓retention modestly, ↑urgency, ↓stability)
    """
    changes: list[ChangeReason] = []
    qs = _clamp01(event.quiz_score)
    qc = _clamp01(event.quiz_confidence)

    # ── Use retention engine for full recomputation ───────────────────────────
    ret_input = RetentionInput(
        study_duration_minutes=event.study_duration_minutes,
        quiz_score=qs,
        quiz_confidence=qc,
        has_quiz=True,
        revision_count=state.revision_count + 1,
        revision_strength=state.revision_strength,
        elapsed_days=event.elapsed_days,
        decay_rate=state.decay_rate,
        difficulty=event.difficulty,
        importance_weight=event.importance_weight,
    )
    ret_out: RetentionOutput = compute_retention(ret_input)

    # ── Compute deltas (blend, don't replace) ─────────────────────────────────
    # Retention: for good quizzes, always boost. For poor quizzes, allow decay.
    # A good quiz score PROVES the learner knows the material — state must improve.
    engine_ret = ret_out.retention_score
    if qs >= 0.5:
        # Good quiz: direct performance-proportional boost on top of current state.
        # Boost scales with quiz score: 0.5 → +0.02, 1.0 → +0.06
        quiz_boost = 0.02 + 0.04 * (qs - 0.5) / 0.5
        # Also blend in engine result if it's higher than current
        engine_lift = max(engine_ret - state.retention_score, 0.0) * QUIZ_SCORE_WEIGHT
        blended_retention = state.retention_score + quiz_boost + engine_lift
    else:
        # Poor quiz: allow degradation via standard blend
        blended_retention = QUIZ_SCORE_WEIGHT * engine_ret + (1 - QUIZ_SCORE_WEIGHT) * state.retention_score
    blended_retention = _clamp(blended_retention, RETENTION_FLOOR, RETENTION_CEILING)
    ret_delta = blended_retention - state.retention_score

    # Stability: quiz performance moves stability
    if qs >= 0.7:
        stab_delta = REVISION_STABILITY_BOOST * (1 + qs)  # good quiz extends
    elif qs >= 0.4:
        stab_delta = REVISION_STABILITY_BOOST * 0.3       # mediocre — small gain
    else:
        stab_delta = -REVISION_STABILITY_BOOST * (1 - qs) # poor quiz contracts

    # Confidence: blend quiz-inferred and self-reported
    quiz_inferred_conf = qs * 0.9  # slightly below quiz score
    new_conf = QUIZ_CONFIDENCE_WEIGHT * quiz_inferred_conf + (1 - QUIZ_CONFIDENCE_WEIGHT) * qc
    conf_delta = new_conf - state.confidence_score

    # Urgency: inversely proportional to quiz score
    urgency_delta = -0.1 * qs + 0.05 * (1 - qs)  # good quiz ↓urgency, bad quiz ↑urgency

    # ── Adaptive stability evolution (Phase 8.5) ──────────────────────────────
    stab_evo = evolve_stability(
        current_base=state.base_stability,
        event_quality=qs,
        revision_count=state.revision_count,
        current_quality_avg=state.revision_quality,
        current_trend=state.performance_trend,
    )
    # Difficulty factor: blend topic difficulty with learner-specific adjustment
    new_diff_factor = 0.7 * event.difficulty + 0.3 * state.difficulty_factor

    # ── Compute retention evolution fields ─────────────────────────────────────
    # Adaptive stability: use forgetting engine for real-time S_adaptive
    new_adaptive_s = stab_evo.new_base_stability  # initial approx; service layer recomputes
    # Stability growth rate: EMA of growth per event
    growth = stab_evo.growth_applied
    alpha_g = 0.2  # EMA smoothing
    new_growth_rate = alpha_g * growth + (1 - alpha_g) * state.stability_growth_rate

    # Quality variance: online Welford-style EMA update
    alpha_v = 0.15
    new_qvar = alpha_v * (qs - state.revision_quality) ** 2 + (1 - alpha_v) * state.quality_variance

    # Confidence calibration error: EMA of |confidence - performance|
    cal_err = abs(state.confidence_score - qs)
    alpha_c = 0.2
    new_cal_err = alpha_c * cal_err + (1 - alpha_c) * state.confidence_calibration_error

    # Effective revision tracking
    revision_improved = 1 if ret_delta > 0.001 else 0
    new_eff_count = state.effective_revision_count + revision_improved
    new_total_revs = state.revision_count + 1
    new_eff_ratio = new_eff_count / new_total_revs if new_total_revs > 0 else 0.0

    # Retention history
    new_peak = max(state.peak_retention, blended_retention)
    # Forgetting event detection: retention dropped below 0.3
    forgetting_event = 1 if blended_retention < 0.3 and state.retention_score >= 0.3 else 0

    # ── Build delta ───────────────────────────────────────────────────────────
    delta = StateDelta(
        retention_delta=round(ret_delta, 4),
        stability_delta=round(stab_delta, 4),
        decay_rate_new=ret_out.decay_rate,
        confidence_delta=round(conf_delta, 4),
        revision_strength_delta=REVISION_STRENGTH_GAIN,
        revision_count_delta=1,
        forgetting_probability_new=round(1.0 - blended_retention, 4),
        urgency_delta=round(urgency_delta, 4),
        base_stability_new=stab_evo.new_base_stability,
        revision_quality_new=stab_evo.new_revision_quality,
        difficulty_factor_new=round(new_diff_factor, 4),
        performance_trend_new=stab_evo.new_performance_trend,
        # Retention evolution fields
        adaptive_stability_new=round(new_adaptive_s, 4),
        stability_growth_rate_new=round(new_growth_rate, 4),
        effective_decay_rate_new=ret_out.decay_rate,
        quality_variance_new=round(new_qvar, 4),
        effective_revision_count_delta=revision_improved,
        revision_effectiveness_ratio_new=round(new_eff_ratio, 4),
        confidence_calibration_error_new=round(new_cal_err, 4),
        peak_retention_new=round(new_peak, 4),
        retention_at_last_revision_new=round(state.retention_score, 4),
        total_forgetting_events_delta=forgetting_event,
    )

    # ── Audit trail ───────────────────────────────────────────────────────────
    if abs(ret_delta) > 0.001:
        direction = "improved" if ret_delta > 0 else "declined"
        changes.append(ChangeReason("retention_score", state.retention_score,
                                     blended_retention, f"Quiz score {qs:.0%} — retention {direction}"))
    changes.append(ChangeReason("decay_rate", state.decay_rate, ret_out.decay_rate,
                                 f"Decay rate updated from quiz (score={qs:.0%}, difficulty={event.difficulty:.0%})"))
    changes.append(ChangeReason("revision_count", state.revision_count, state.revision_count + 1,
                                 "Quiz counts as revision event"))
    changes.append(ChangeReason("base_stability", state.base_stability, stab_evo.new_base_stability,
                                 f"Adaptive stability evolved: growth +{stab_evo.growth_applied:.4f}"))

    return delta, changes


def recalibrate_revision(
    state: CurrentState,
    event: EventData,
) -> tuple[StateDelta, list[ChangeReason]]:
    """
    Recalibrate after a revision session — reinforcement signal.

    What happens:
      1. Retention gets a diminishing boost
      2. Stability extends
      3. Revision count and strength increment
      4. Decay rate slightly decreases (more resistant to forgetting)
      5. Urgency decreases
      6. Forgetting probability recomputed

    The boost diminishes with more revisions — 10th revision helps less than 1st.
    """
    changes: list[ChangeReason] = []
    count = state.revision_count

    # Diminishing retention boost: 0.05 / (1 + 0.1 × count)
    boost = REVISION_RETENTION_BOOST / (1.0 + 0.1 * count)
    new_ret = _clamp(state.retention_score + boost, RETENTION_FLOOR, RETENTION_CEILING)
    ret_delta = new_ret - state.retention_score

    # Stability extension: grows less with more revisions
    stab_boost = REVISION_STABILITY_BOOST / (1.0 + 0.05 * count)

    # Decay rate: slight decrease from reinforcement
    damping = 1.0 / (1.0 + 0.1 * (count + 1))
    new_decay = _clamp(state.decay_rate * (1.0 - 0.05 * damping), 0.005, 1.0)

    # Urgency decrease
    urgency_delta = -0.05

    # Forgetting probability
    new_fp = round(1.0 - new_ret, 4)

    # ── Adaptive stability evolution (Phase 8.5) ──────────────────────────────
    # Revision quality: use a moderate quality signal (0.6 for completing revision)
    rev_quality_signal = 0.6
    stab_evo = evolve_stability(
        current_base=state.base_stability,
        event_quality=rev_quality_signal,
        revision_count=state.revision_count,
        current_quality_avg=state.revision_quality,
        current_trend=state.performance_trend,
    )

    # ── Retention evolution fields ──────────────────────────────────────────────
    growth = stab_evo.growth_applied
    alpha_g = 0.2
    new_growth_rate = alpha_g * growth + (1 - alpha_g) * state.stability_growth_rate

    # Quality variance: revision quality signal vs running average
    alpha_v = 0.15
    new_qvar = alpha_v * (rev_quality_signal - state.revision_quality) ** 2 + (1 - alpha_v) * state.quality_variance

    # Effective revision: did this revision improve retention?
    revision_improved = 1 if ret_delta > 0.001 else 0
    new_eff_count = state.effective_revision_count + revision_improved
    new_total_revs = count + 1
    new_eff_ratio = new_eff_count / new_total_revs if new_total_revs > 0 else 0.0

    # Time pattern regularity: EMA of timing consistency
    # Uses elapsed_days — regular intervals → regularity stays high
    if count > 0 and event.elapsed_days > 0:
        expected_gap = state.half_life_days if state.half_life_days > 0 else 1.0
        gap_deviation = abs(event.elapsed_days - expected_gap) / max(expected_gap, 0.1)
        gap_regularity = max(0.0, 1.0 - gap_deviation)
        alpha_r = 0.25
        new_regularity = alpha_r * gap_regularity + (1 - alpha_r) * state.time_pattern_regularity
    else:
        new_regularity = state.time_pattern_regularity

    # Confidence calibration
    alpha_c = 0.2
    cal_err = abs(state.confidence_score - rev_quality_signal)
    new_cal_err = alpha_c * cal_err + (1 - alpha_c) * state.confidence_calibration_error

    # Retention history
    new_peak = max(state.peak_retention, new_ret)
    forgetting_event = 1 if new_ret < 0.3 and state.retention_score >= 0.3 else 0

    delta = StateDelta(
        retention_delta=round(ret_delta, 4),
        stability_delta=round(stab_boost, 4),
        decay_rate_new=round(new_decay, 6),
        confidence_delta=0.02,  # slight confidence boost from practice
        revision_strength_delta=REVISION_STRENGTH_GAIN,
        revision_count_delta=1,
        forgetting_probability_new=new_fp,
        urgency_delta=urgency_delta,
        base_stability_new=stab_evo.new_base_stability,
        revision_quality_new=stab_evo.new_revision_quality,
        performance_trend_new=stab_evo.new_performance_trend,
        # Retention evolution fields
        adaptive_stability_new=round(stab_evo.new_base_stability, 4),
        stability_growth_rate_new=round(new_growth_rate, 4),
        effective_decay_rate_new=round(new_decay, 6),
        quality_variance_new=round(new_qvar, 4),
        effective_revision_count_delta=revision_improved,
        revision_effectiveness_ratio_new=round(new_eff_ratio, 4),
        time_pattern_regularity_new=round(new_regularity, 4),
        confidence_calibration_error_new=round(new_cal_err, 4),
        peak_retention_new=round(new_peak, 4),
        retention_at_last_revision_new=round(state.retention_score, 4),
        total_forgetting_events_delta=forgetting_event,
    )

    changes.append(ChangeReason("retention_score", state.retention_score, new_ret,
                                 f"Revision #{count+1} — diminishing retention boost (+{boost:.4f})"))
    changes.append(ChangeReason("stability_score", state.stability_score,
                                 state.stability_score + stab_boost,
                                 f"Stability extended by {stab_boost:.3f} days"))
    changes.append(ChangeReason("revision_count", count, count + 1,
                                 "Revision event recorded"))
    changes.append(ChangeReason("base_stability", state.base_stability, stab_evo.new_base_stability,
                                 f"Adaptive base stability evolved: +{stab_evo.growth_applied:.4f}"))

    return delta, changes


def recalibrate_study(
    state: CurrentState,
    event: EventData,
) -> tuple[StateDelta, list[ChangeReason]]:
    """
    Recalibrate after a study session — modest reinforcement.

    Study sessions provide a smaller signal than quizzes or revisions
    because passive study is less effective than active recall.

    The gain saturates at STUDY_SATURATION minutes (diminishing returns).
    """
    changes: list[ChangeReason] = []
    minutes = max(event.study_duration_minutes, 0.0)

    # Saturating study gain: rate × min(duration, saturation)
    effective_minutes = min(minutes, STUDY_SATURATION)
    gain = STUDY_RETENTION_RATE * effective_minutes
    new_ret = _clamp(state.retention_score + gain, RETENTION_FLOOR, RETENTION_CEILING)
    ret_delta = new_ret - state.retention_score

    # Small stability boost
    stab_delta = 0.05 * (effective_minutes / STUDY_SATURATION)

    # Strength gain
    strength_gain = STUDY_STRENGTH_GAIN * (effective_minutes / STUDY_SATURATION)

    # ── Adaptive stability evolution (Phase 8.5) ──────────────────────────────
    # Study is weaker than revision — quality signal = 0.4
    study_quality_signal = 0.4 * (effective_minutes / STUDY_SATURATION)
    stab_evo = evolve_stability(
        current_base=state.base_stability,
        event_quality=study_quality_signal,
        revision_count=state.revision_count,
        current_quality_avg=state.revision_quality,
        current_trend=state.performance_trend,
    )

    # ── Retention evolution (study is lighter than revision) ───────────────────
    new_peak = max(state.peak_retention, new_ret)

    delta = StateDelta(
        retention_delta=round(ret_delta, 4),
        stability_delta=round(stab_delta, 4),
        confidence_delta=0.01,
        revision_strength_delta=round(strength_gain, 4),
        revision_count_delta=0,  # study is NOT a revision
        urgency_delta=-0.02,
        forgetting_probability_new=round(1.0 - new_ret, 4),
        base_stability_new=stab_evo.new_base_stability,
        revision_quality_new=stab_evo.new_revision_quality,
        performance_trend_new=stab_evo.new_performance_trend,
        # Retention evolution fields (study: lightweight updates)
        adaptive_stability_new=round(stab_evo.new_base_stability, 4),
        peak_retention_new=round(new_peak, 4),
    )

    changes.append(ChangeReason("retention_score", state.retention_score, new_ret,
                                 f"Studied {minutes:.0f} min — retention gain +{gain:.4f}"))
    if stab_delta > 0.001:
        changes.append(ChangeReason("stability_score", state.stability_score,
                                     state.stability_score + stab_delta,
                                     f"Stability slightly extended from study"))

    return delta, changes


def recalibrate_inactivity(
    state: CurrentState,
    event: EventData,
) -> tuple[StateDelta, list[ChangeReason]]:
    """
    Recalibrate after inactivity detection — degradation signal.

    What happens:
      1. Retention degrades based on days inactive
      2. Stability contracts
      3. Urgency increases
      4. Forgetting probability increases
      5. Decay rate worsens

    Uses the decay engine's inactivity penalty for consistency.
    Degradation is GRADUAL, not a hard reset.
    """
    changes: list[ChangeReason] = []
    days = max(event.days_inactive, 0.0)

    if days <= INACTIVITY_ONSET_DAYS:
        # Within grace period — no degradation
        delta = StateDelta()
        changes.append(ChangeReason("retention_score", state.retention_score,
                                     state.retention_score,
                                     f"Inactive {days:.0f} days — within grace period ({INACTIVITY_ONSET_DAYS:.0f}d), no change"))
        return delta, changes

    # Days beyond onset
    excess = days - INACTIVITY_ONSET_DAYS

    # Retention loss: gradual, capped
    loss = INACTIVITY_RETENTION_LOSS_RATE * excess
    loss = min(loss, state.retention_score - RETENTION_FLOOR)  # never below floor
    loss = max(loss, 0.0)
    new_ret = state.retention_score - loss

    # Stability contraction
    stab_loss = 0.1 * math.log(1 + excess)
    stab_loss = min(stab_loss, state.stability_score - 0.1)
    stab_loss = max(stab_loss, 0.0)

    # Decay rate worsens
    inactivity_pen = compute_inactivity_penalty(days, onset=INACTIVITY_ONSET_DAYS)
    new_decay = _clamp(state.decay_rate + inactivity_pen * 0.1, 0.005, 1.0)

    # Urgency increases
    urgency_gain = INACTIVITY_URGENCY_GAIN * excess
    urgency_gain = min(urgency_gain, 1.0 - state.urgency_score)

    # Forgetting probability
    new_fp = round(1.0 - new_ret, 4)

    # ── Adaptive stability degradation (Phase 8.5) ────────────────────────────
    new_base_stab = degrade_stability(
        current_base=state.base_stability,
        days_inactive=days,
    )
    # Shift performance trend downward during inactivity
    trend_decay = min(0.1 * (excess / 7.0), 0.5)  # max −0.5 trend shift
    new_trend = max(-1.0, state.performance_trend - trend_decay)

    # ── Retention evolution: inactivity degradation ────────────────────────────
    forgetting_event = 1 if new_ret < 0.3 and state.retention_score >= 0.3 else 0
    # Regularity degrades during inactivity
    reg_decay = min(0.1 * (excess / 7.0), 0.3)
    new_regularity = max(0.0, state.time_pattern_regularity - reg_decay)

    delta = StateDelta(
        retention_delta=round(-loss, 4),
        stability_delta=round(-stab_loss, 4),
        decay_rate_new=round(new_decay, 6),
        confidence_delta=round(-0.01 * excess, 4),  # confidence erodes
        revision_strength_delta=0.0,
        revision_count_delta=0,
        forgetting_probability_new=new_fp,
        urgency_delta=round(urgency_gain, 4),
        base_stability_new=round(new_base_stab, 4),
        performance_trend_new=round(new_trend, 4),
        # Retention evolution fields
        adaptive_stability_new=round(new_base_stab, 4),
        effective_decay_rate_new=round(new_decay, 6),
        time_pattern_regularity_new=round(new_regularity, 4),
        total_forgetting_events_delta=forgetting_event,
    )

    changes.append(ChangeReason("retention_score", state.retention_score, new_ret,
                                 f"Inactive {days:.0f} days ({excess:.0f} beyond grace) — retention loss −{loss:.4f}"))
    if urgency_gain > 0.001:
        changes.append(ChangeReason("urgency_score", state.urgency_score,
                                     state.urgency_score + urgency_gain,
                                     f"Urgency increased due to {excess:.0f} days of inactivity"))
    if new_base_stab < state.base_stability:
        changes.append(ChangeReason("base_stability", state.base_stability, new_base_stab,
                                     f"Adaptive stability degraded from {days:.0f} days of inactivity"))

    return delta, changes


# ═══════════════════════════════════════════════════════════════════════════════
#  Apply Deltas — State Evolution
# ═══════════════════════════════════════════════════════════════════════════════

def apply_delta(state: CurrentState, delta: StateDelta) -> dict[str, float | int]:
    """
    Apply a StateDelta to a CurrentState and return new absolute values.

    This is the ONLY place where state actually changes.
    All values are clamped to valid ranges.

    Returns a dict of field_name → new_value suitable for ORM update.
    """
    new_ret = _clamp(state.retention_score + delta.retention_delta, RETENTION_FLOOR, RETENTION_CEILING)
    new_stab = max(state.stability_score + delta.stability_delta, 0.1)
    new_decay = delta.decay_rate_new if delta.decay_rate_new is not None else state.decay_rate
    new_decay = _clamp(new_decay, 0.005, 1.0)
    new_conf = _clamp01(state.confidence_score + delta.confidence_delta)
    new_strength = max(state.revision_strength + delta.revision_strength_delta, 0.0)
    new_count = max(state.revision_count + delta.revision_count_delta, 0)
    new_fp = delta.forgetting_probability_new if delta.forgetting_probability_new is not None else round(1.0 - new_ret, 4)
    new_fp = _clamp01(new_fp)
    new_urgency = _clamp01(state.urgency_score + delta.urgency_delta)

    # Adaptive forgetting curve fields (Phase 8.5)
    new_base_stab = delta.base_stability_new if delta.base_stability_new is not None else state.base_stability
    new_base_stab = max(new_base_stab, 0.1)
    new_rev_quality = delta.revision_quality_new if delta.revision_quality_new is not None else state.revision_quality
    new_rev_quality = _clamp01(new_rev_quality)
    new_diff_factor = delta.difficulty_factor_new if delta.difficulty_factor_new is not None else state.difficulty_factor
    new_diff_factor = _clamp01(new_diff_factor)
    new_perf_trend = delta.performance_trend_new if delta.performance_trend_new is not None else state.performance_trend
    new_perf_trend = max(-1.0, min(1.0, new_perf_trend))

    # Adaptive stability persistence
    new_adaptive_stab = delta.adaptive_stability_new if delta.adaptive_stability_new is not None else state.adaptive_stability
    new_adaptive_stab = max(new_adaptive_stab, 0.1)
    new_stab_growth = delta.stability_growth_rate_new if delta.stability_growth_rate_new is not None else state.stability_growth_rate
    new_half_life = delta.half_life_days_new if delta.half_life_days_new is not None else state.half_life_days
    new_half_life = max(new_half_life, 0.0)

    # Decay parameters
    new_eff_decay = delta.effective_decay_rate_new if delta.effective_decay_rate_new is not None else state.effective_decay_rate
    new_eff_decay = _clamp(new_eff_decay, 0.005, 1.0)
    new_time_crit = delta.time_to_critical_new if delta.time_to_critical_new is not None else state.time_to_critical
    new_time_crit = max(new_time_crit, 0.0)
    new_days_tgt = delta.days_until_target_new if delta.days_until_target_new is not None else state.days_until_target
    new_days_tgt = max(new_days_tgt, 0.0)

    # Reinforcement behaviour
    new_qvar = delta.quality_variance_new if delta.quality_variance_new is not None else state.quality_variance
    new_qvar = max(new_qvar, 0.0)
    new_eff_rev_count = max(state.effective_revision_count + delta.effective_revision_count_delta, 0)
    new_rev_eff_ratio = delta.revision_effectiveness_ratio_new if delta.revision_effectiveness_ratio_new is not None else state.revision_effectiveness_ratio
    new_rev_eff_ratio = _clamp01(new_rev_eff_ratio)
    new_time_reg = delta.time_pattern_regularity_new if delta.time_pattern_regularity_new is not None else state.time_pattern_regularity
    new_time_reg = _clamp01(new_time_reg)
    new_conf_cal_err = delta.confidence_calibration_error_new if delta.confidence_calibration_error_new is not None else state.confidence_calibration_error
    new_conf_cal_err = max(new_conf_cal_err, 0.0)

    # Retention history
    new_peak_ret = delta.peak_retention_new if delta.peak_retention_new is not None else state.peak_retention
    new_peak_ret = max(new_peak_ret, round(new_ret, 4))  # always track peak
    new_peak_ret = _clamp01(new_peak_ret)
    new_ret_at_rev = delta.retention_at_last_revision_new if delta.retention_at_last_revision_new is not None else state.retention_at_last_revision
    new_ret_at_rev = _clamp01(new_ret_at_rev)
    new_total_forg = max(state.total_forgetting_events + delta.total_forgetting_events_delta, 0)

    return {
        "retention_score": round(new_ret, 4),
        "stability_score": round(new_stab, 4),
        "decay_rate": round(new_decay, 6),
        "confidence_score": round(new_conf, 4),
        "revision_strength": round(new_strength, 4),
        "revision_count": new_count,
        "forgetting_probability": round(new_fp, 4),
        "urgency_score": round(new_urgency, 4),
        "base_stability": round(new_base_stab, 4),
        "revision_quality": round(new_rev_quality, 4),
        "difficulty_factor": round(new_diff_factor, 4),
        "performance_trend": round(new_perf_trend, 4),
        "adaptive_stability": round(new_adaptive_stab, 4),
        "stability_growth_rate": round(new_stab_growth, 4),
        "half_life_days": round(new_half_life, 4),
        "effective_decay_rate": round(new_eff_decay, 6),
        "time_to_critical": round(new_time_crit, 4),
        "days_until_target": round(new_days_tgt, 4),
        "quality_variance": round(new_qvar, 4),
        "effective_revision_count": new_eff_rev_count,
        "revision_effectiveness_ratio": round(new_rev_eff_ratio, 4),
        "time_pattern_regularity": round(new_time_reg, 4),
        "confidence_calibration_error": round(new_conf_cal_err, 4),
        "peak_retention": round(new_peak_ret, 4),
        "retention_at_last_revision": round(new_ret_at_rev, 4),
        "total_forgetting_events": new_total_forg,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Master Function
# ═══════════════════════════════════════════════════════════════════════════════

def recalibrate(
    state: CurrentState,
    event: EventData,
) -> RecalibrationOutput:
    """
    Master recalibration function — routes event to the correct pathway.

    Steps:
      1. Select recalibration pathway based on event type
      2. Compute incremental deltas
      3. Apply deltas to produce new absolute state
      4. Generate explainability summary

    This is the ONLY function the service layer needs to call.
    """
    # ── Route to pathway ──────────────────────────────────────────────────────
    dispatch = {
        EventType.QUIZ_SUBMITTED: recalibrate_quiz,
        EventType.REVISION_COMPLETED: recalibrate_revision,
        EventType.STUDY_SESSION: recalibrate_study,
        EventType.INACTIVITY_DETECTED: recalibrate_inactivity,
    }

    handler = dispatch[event.event_type]
    delta, changes = handler(state, event)

    # ── Apply deltas ──────────────────────────────────────────────────────────
    new_values = apply_delta(state, delta)

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = _generate_summary(event.event_type, state, new_values, changes)

    return RecalibrationOutput(
        event_type=event.event_type,
        new_retention=new_values["retention_score"],
        new_stability=new_values["stability_score"],
        new_decay_rate=new_values["decay_rate"],
        new_confidence=new_values["confidence_score"],
        new_revision_strength=new_values["revision_strength"],
        new_revision_count=new_values["revision_count"],
        new_forgetting_probability=new_values["forgetting_probability"],
        new_urgency=new_values["urgency_score"],
        new_base_stability=new_values["base_stability"],
        new_revision_quality=new_values["revision_quality"],
        new_difficulty_factor=new_values["difficulty_factor"],
        new_performance_trend=new_values["performance_trend"],
        new_adaptive_stability=new_values["adaptive_stability"],
        new_stability_growth_rate=new_values["stability_growth_rate"],
        new_half_life_days=new_values["half_life_days"],
        new_effective_decay_rate=new_values["effective_decay_rate"],
        new_time_to_critical=new_values["time_to_critical"],
        new_days_until_target=new_values["days_until_target"],
        new_quality_variance=new_values["quality_variance"],
        new_effective_revision_count=new_values["effective_revision_count"],
        new_revision_effectiveness_ratio=new_values["revision_effectiveness_ratio"],
        new_time_pattern_regularity=new_values["time_pattern_regularity"],
        new_confidence_calibration_error=new_values["confidence_calibration_error"],
        new_peak_retention=new_values["peak_retention"],
        new_retention_at_last_revision=new_values["retention_at_last_revision"],
        new_total_forgetting_events=new_values["total_forgetting_events"],
        delta=delta,
        changes=changes,
        summary=summary,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Summary Generation
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_summary(
    event_type: EventType,
    old: CurrentState,
    new: dict[str, float | int],
    changes: list[ChangeReason],
) -> str:
    """Generate one-line summary of what the recalibration did."""
    ret_delta = new["retention_score"] - old.retention_score
    direction = "↑" if ret_delta > 0 else "↓" if ret_delta < 0 else "→"

    if event_type == EventType.QUIZ_SUBMITTED:
        return (f"Quiz recalibration: retention {old.retention_score:.0%} {direction} "
                f"{new['retention_score']:.0%}, rev #{new['revision_count']}")
    elif event_type == EventType.REVISION_COMPLETED:
        return (f"Revision #{new['revision_count']}: retention {old.retention_score:.0%} {direction} "
                f"{new['retention_score']:.0%}")
    elif event_type == EventType.STUDY_SESSION:
        return f"Study session: retention {old.retention_score:.0%} {direction} {new['retention_score']:.0%}"
    elif event_type == EventType.INACTIVITY_DETECTED:
        if ret_delta == 0:
            return "Inactivity check: within grace period, no change"
        return (f"Inactivity detected: retention {old.retention_score:.0%} {direction} "
                f"{new['retention_score']:.0%}, urgency {direction} {new['urgency_score']:.0%}")
    return f"Recalibration: {len(changes)} fields updated"


# ═══════════════════════════════════════════════════════════════════════════════
#  Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))

def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
