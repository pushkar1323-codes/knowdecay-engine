"""
app/engine/retention_engine.py
────────────────────────────────
Deterministic retention intelligence — the core scoring engine.

This module contains PURE FUNCTIONS with no database access, no side effects,
and no I/O. All state is passed in, all results are returned. This makes
every function trivially unit-testable.

Master Formula
══════════════
    retention = clamp(
        base_strength
        + revision_reinforcement
        + quiz_performance_boost
        − time_decay
        − difficulty_penalty,
        floor, 1.0
    )

Component breakdown:
────────────────────
  base_strength           = sigmoid of normalised study duration
  revision_reinforcement  = log(1 + revision_count) × revision_factor  (diminishing returns)
  quiz_performance_boost  = score × quiz_weight                        (latest quiz performance)
  time_decay              = 1 − e^(−λt)                                (Ebbinghaus forgetting curve)
  difficulty_penalty      = difficulty × difficulty_factor              (harder → faster decay)

Stability
═════════
  stability = base_interval × (1 + revision_count)^growth_rate / (1 + difficulty)
  Represents: how many DAYS before retention drops to the threshold.

Confidence
══════════
  blended_confidence = quiz_weight × quiz_inferred + self_weight × self_reported
  quiz_inferred      = score × consistency_factor
  Falls back gracefully when no quiz data exists.

Design principles:
  • Every function receives explicit inputs — no globals, no singletons
  • All weights are keyword-only with sensible defaults
  • All outputs are clamped to valid ranges
  • Config overrides come from app.config.Settings via the service layer
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════════════════════
#  Data Transfer Objects
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class RetentionInput:
    """
    All inputs needed to compute retention for a single user × topic.

    Every field has a sensible default so callers can provide only what
    they have — missing data degrades gracefully, never crashes.
    """

    # ── Study signal ──────────────────────────────────────────────────────────
    study_duration_minutes: float = 0.0     # cumulative study time

    # ── Quiz signal (latest quiz) ─────────────────────────────────────────────
    quiz_score: float = 0.0                 # 0.0–1.0 (objective recall quality)
    quiz_confidence: float = 0.5            # 0.0–1.0 (self-reported certainty)
    has_quiz: bool = False                  # whether any quiz data exists

    # ── Revision history ──────────────────────────────────────────────────────
    revision_count: int = 0                 # total revision events
    revision_strength: float = 0.0          # accumulated strength from past updates

    # ── Time context ──────────────────────────────────────────────────────────
    elapsed_days: float = 0.0               # days since last revision
    decay_rate: float = 0.1                 # λ — current forgetting rate

    # ── Topic properties ──────────────────────────────────────────────────────
    difficulty: float = 0.5                 # 0.0 (easy) → 1.0 (very hard)
    importance_weight: float = 1.0          # exam urgency multiplier


@dataclass(frozen=True, slots=True)
class RetentionOutput:
    """
    All computed retention metrics returned by the engine.
    """

    retention_score: float      # 0.0–1.0  overall recall probability
    stability_score: float      # days until retention drops to threshold
    confidence_score: float     # 0.0–1.0  blended confidence
    forgetting_probability: float  # 0.0–1.0  probability of substantial forgetting
    decay_rate: float           # λ — updated decay rate for this topic

    # Component breakdown for explainability
    base_strength: float
    revision_reinforcement: float
    quiz_boost: float
    time_decay: float
    difficulty_penalty: float


# ═══════════════════════════════════════════════════════════════════════════════
#  Default Weight Constants
# ═══════════════════════════════════════════════════════════════════════════════
# These defaults are used when the caller does not override.
# In production, the service layer passes values from app.config.Settings.

DEFAULT_STUDY_WEIGHT: float = 0.20          # how much study duration contributes
DEFAULT_STUDY_SATURATION: float = 60.0      # minutes at which study benefit plateaus
DEFAULT_REVISION_FACTOR: float = 0.15       # per-revision reinforcement scale
DEFAULT_QUIZ_WEIGHT: float = 0.30           # quiz score contribution to retention
DEFAULT_DIFFICULTY_FACTOR: float = 0.15     # difficulty penalty scale
DEFAULT_MIN_FLOOR: float = 0.05            # retention never drops below this
DEFAULT_BASE_INTERVAL: float = 1.0          # starting stability in days
DEFAULT_GROWTH_RATE: float = 0.5            # how fast stability grows with revisions
DEFAULT_CONFIDENCE_QUIZ_WEIGHT: float = 0.7 # weight of quiz-inferred confidence
DEFAULT_CONFIDENCE_SELF_WEIGHT: float = 0.3 # weight of self-reported confidence


# ═══════════════════════════════════════════════════════════════════════════════
#  Component Functions (each computes one additive term)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_base_strength(
    study_duration_minutes: float,
    *,
    weight: float = DEFAULT_STUDY_WEIGHT,
    saturation: float = DEFAULT_STUDY_SATURATION,
) -> float:
    """
    Base memory strength from study exposure.

    Uses a sigmoid-like saturation curve: studying 60+ minutes gives
    diminishing returns — cramming doesn't help linearly.

    Formula: weight × (duration / (duration + saturation))
    Range:   [0.0, weight)  — approaches but never exceeds `weight`
    """
    if study_duration_minutes <= 0:
        return 0.0
    normalised = study_duration_minutes / (study_duration_minutes + saturation)
    return weight * normalised


def compute_revision_reinforcement(
    revision_count: int,
    *,
    factor: float = DEFAULT_REVISION_FACTOR,
) -> float:
    """
    Reinforcement bonus from repeated revisions.

    Uses log(1 + n) for diminishing returns: the 1st revision helps a lot,
    the 10th revision helps much less.

    Formula: factor × log(1 + revision_count)
    Range:   [0.0, ∞)  — grows slowly without bound
    """
    if revision_count <= 0:
        return 0.0
    return factor * math.log(1 + revision_count)


def compute_quiz_boost(
    quiz_score: float,
    has_quiz: bool,
    *,
    weight: float = DEFAULT_QUIZ_WEIGHT,
) -> float:
    """
    Performance boost from the most recent quiz.

    Direct linear scaling: a perfect score gives the full weight,
    a score of 0.5 gives half the weight, etc.

    Formula: weight × quiz_score  (only if has_quiz is True)
    Range:   [0.0, weight]
    """
    if not has_quiz:
        return 0.0
    return weight * _clamp01(quiz_score)


def compute_time_decay(
    elapsed_days: float,
    decay_rate: float,
) -> float:
    """
    Memory decay from the Ebbinghaus forgetting curve.

    Formula: 1 − e^(−λt)
    Where:   λ = decay_rate, t = elapsed_days

    Properties:
      t=0  → decay=0  (just revised, no forgetting)
      t→∞  → decay→1  (complete forgetting)

    Range: [0.0, 1.0)
    """
    if elapsed_days <= 0 or decay_rate <= 0:
        return 0.0
    return 1.0 - math.exp(-decay_rate * elapsed_days)


def compute_difficulty_penalty(
    difficulty: float,
    *,
    factor: float = DEFAULT_DIFFICULTY_FACTOR,
) -> float:
    """
    Penalty for harder topics — difficult material is forgotten faster.

    Formula: factor × difficulty
    Range:   [0.0, factor]
    """
    return factor * _clamp01(difficulty)


# ═══════════════════════════════════════════════════════════════════════════════
#  Stability Calculation
# ═══════════════════════════════════════════════════════════════════════════════

def compute_stability(
    revision_count: int,
    quiz_score: float,
    difficulty: float,
    *,
    base_interval: float = DEFAULT_BASE_INTERVAL,
    growth_rate: float = DEFAULT_GROWTH_RATE,
) -> float:
    """
    Memory stability — estimated days until retention drops to threshold.

    More revisions and higher quiz scores extend stability.
    Higher difficulty reduces stability.

    Formula: base_interval × (1 + revision_count)^growth_rate × (1 + quiz_bonus) / (1 + difficulty)
    Where:   quiz_bonus = 0.5 × quiz_score  (capped contribution)

    Range: [base_interval / 2, ∞)  — always positive
    """
    revision_multiplier = math.pow(1 + revision_count, growth_rate)
    quiz_bonus = 1.0 + 0.5 * _clamp01(quiz_score)
    difficulty_divisor = 1.0 + _clamp01(difficulty)

    stability = base_interval * revision_multiplier * quiz_bonus / difficulty_divisor
    return round(max(stability, 0.1), 4)  # never less than 0.1 days


# ═══════════════════════════════════════════════════════════════════════════════
#  Confidence Blending
# ═══════════════════════════════════════════════════════════════════════════════

def compute_confidence(
    quiz_score: float,
    quiz_confidence: float,
    has_quiz: bool,
    *,
    quiz_weight: float = DEFAULT_CONFIDENCE_QUIZ_WEIGHT,
    self_weight: float = DEFAULT_CONFIDENCE_SELF_WEIGHT,
) -> float:
    """
    Blended confidence score.

    If quiz data exists:
        confidence = quiz_weight × (score × consistency) + self_weight × self_reported
        where consistency = 1 − |score − self_reported|  (penalises overconfidence)

    If no quiz data:
        confidence = self_reported × 0.6  (discounted — unverified self-report)

    Range: [0.0, 1.0]
    """
    if not has_quiz:
        return round(_clamp01(quiz_confidence * 0.6), 4)

    score = _clamp01(quiz_score)
    self_reported = _clamp01(quiz_confidence)

    # Consistency factor: penalise mismatch between score and self-report
    consistency = 1.0 - abs(score - self_reported)
    quiz_inferred = score * consistency

    blended = quiz_weight * quiz_inferred + self_weight * self_reported
    return round(_clamp01(blended), 4)


# ═══════════════════════════════════════════════════════════════════════════════
#  Decay Rate Update
# ═══════════════════════════════════════════════════════════════════════════════

def compute_updated_decay_rate(
    current_decay_rate: float,
    quiz_score: float,
    difficulty: float,
    revision_count: int,
    *,
    base_rate: float = 0.1,
    min_rate: float = 0.01,
    max_rate: float = 0.5,
) -> float:
    """
    Adapt the decay rate based on performance.

    Good quiz scores LOWER the decay rate (learner retains better).
    High difficulty RAISES the decay rate.
    More revisions LOWER the decay rate (spaced repetition working).

    Formula:
        adjusted = base_rate × (1 + difficulty) × (1 − 0.3 × score) / (1 + 0.1 × revision_count)

    Range: [min_rate, max_rate]
    """
    score = _clamp01(quiz_score)
    diff = _clamp01(difficulty)

    adjusted = base_rate * (1.0 + diff) * (1.0 - 0.3 * score)
    revision_damping = 1.0 + 0.1 * max(revision_count, 0)
    adjusted /= revision_damping

    return round(max(min(adjusted, max_rate), min_rate), 6)


# ═══════════════════════════════════════════════════════════════════════════════
#  Master Computation — Single Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def compute_retention(
    inp: RetentionInput,
    *,
    study_weight: float = DEFAULT_STUDY_WEIGHT,
    study_saturation: float = DEFAULT_STUDY_SATURATION,
    revision_factor: float = DEFAULT_REVISION_FACTOR,
    quiz_weight: float = DEFAULT_QUIZ_WEIGHT,
    difficulty_factor: float = DEFAULT_DIFFICULTY_FACTOR,
    min_floor: float = DEFAULT_MIN_FLOOR,
    base_interval: float = DEFAULT_BASE_INTERVAL,
    growth_rate: float = DEFAULT_GROWTH_RATE,
) -> RetentionOutput:
    """
    Master retention computation.

    Combines all component functions into a single retention score,
    plus stability, confidence, forgetting probability, and updated decay rate.

    This is the ONLY function the service layer needs to call.
    """
    # ── Component scores ──────────────────────────────────────────────────────
    base = compute_base_strength(
        inp.study_duration_minutes, weight=study_weight, saturation=study_saturation,
    )
    reinforcement = compute_revision_reinforcement(
        inp.revision_count, factor=revision_factor,
    )
    quiz = compute_quiz_boost(
        inp.quiz_score, inp.has_quiz, weight=quiz_weight,
    )
    decay = compute_time_decay(inp.elapsed_days, inp.decay_rate)
    penalty = compute_difficulty_penalty(inp.difficulty, factor=difficulty_factor)

    # ── Composite retention ───────────────────────────────────────────────────
    raw = base + reinforcement + quiz - decay - penalty
    retention = _clamp(raw, min_floor, 1.0)

    # ── Stability ─────────────────────────────────────────────────────────────
    stability = compute_stability(
        inp.revision_count, inp.quiz_score, inp.difficulty,
        base_interval=base_interval, growth_rate=growth_rate,
    )

    # ── Confidence ────────────────────────────────────────────────────────────
    confidence = compute_confidence(
        inp.quiz_score, inp.quiz_confidence, inp.has_quiz,
    )

    # ── Forgetting probability ────────────────────────────────────────────────
    # Inverse of retention: how likely is it that the topic is forgotten?
    forgetting = round(1.0 - retention, 4)

    # ── Updated decay rate ────────────────────────────────────────────────────
    updated_decay = compute_updated_decay_rate(
        inp.decay_rate, inp.quiz_score, inp.difficulty, inp.revision_count,
    )

    return RetentionOutput(
        retention_score=round(retention, 4),
        stability_score=stability,
        confidence_score=confidence,
        forgetting_probability=forgetting,
        decay_rate=updated_decay,
        base_strength=round(base, 4),
        revision_reinforcement=round(reinforcement, 4),
        quiz_boost=round(quiz, 4),
        time_decay=round(decay, 4),
        difficulty_penalty=round(penalty, 4),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def _clamp01(value: float) -> float:
    """Clamp a value to the [0.0, 1.0] range."""
    return max(0.0, min(1.0, value))


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp a value to the [low, high] range."""
    return max(low, min(high, value))
