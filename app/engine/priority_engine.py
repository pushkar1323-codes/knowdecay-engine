"""
app/engine/priority_engine.py
───────────────────────────────
THE MOST IMPORTANT MODULE IN THE SYSTEM.

Answers the question: "What should the learner revise RIGHT NOW?"

This module computes a composite urgency score for each topic and produces
an ordered priority ranking with explainable reasons for every decision.

Master Formula
══════════════
    priority = urgency × weakness × delay_factor × exam_importance

Component breakdown:
────────────────────
  urgency          = (1 − retention) × difficulty_boost
                     The service layer provides real-time R(t) = e^(-t/S_adaptive)
                     from the adaptive forgetting engine. The priority engine
                     consumes this value — it never computes retention itself.
                     High when retention has decayed and topic is hard.

  weakness         = forgetting_prob × (1 + weakness_trend)
                     The service layer provides 1 − R(t) as forgetting_probability.
                     High when the topic is actively being forgotten
                     and the learner has shown a pattern of struggle.

  delay_factor     = 1 + log(1 + overdue_days)
                     Grows logarithmically with how overdue the revision is.
                     Never punishes freshly-revised topics.

  exam_importance  = importance_weight × exam_proximity_multiplier
                     Scales priority when an exam is near.

Each component generates a human-readable reason string, so consumers
can display WHY a topic was ranked highly.

Design principles:
  • Every function is PURE — no DB, no I/O
  • All weights configurable via keyword-only params
  • All outputs clamped to valid ranges
  • Reasons are always generated — no black-box decisions
  • Batch ranking uses a stable sort (ties preserve insertion order)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
#  Enums
# ═══════════════════════════════════════════════════════════════════════════════

class PriorityTier(str, Enum):
    """Human-readable urgency tier for UI consumers."""

    CRITICAL = "critical"       # score >= 0.8
    HIGH = "high"               # score >= 0.5
    MEDIUM = "medium"           # score >= 0.25
    LOW = "low"                 # score >= 0.1
    MINIMAL = "minimal"         # score < 0.1


# ═══════════════════════════════════════════════════════════════════════════════
#  Data Transfer Objects
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class PriorityInput:
    """
    All inputs needed to compute priority for a single user × topic.

    Fields map directly to memory_state + topic metadata.
    Every field has a sensible default — missing data degrades gracefully.

    IMPORTANT: retention_score and forgetting_probability should be
    pre-computed by the service layer using the adaptive forgetting
    engine (R = e^(-t/S_adaptive)). The priority engine CONSUMES these
    values — it never estimates retention itself.
    """

    # ── From adaptive forgetting engine (via service layer) ───────────────────
    retention_score: float = 0.0            # 0.0–1.0 real-time R(t) from forgetting curve
    forgetting_probability: float = 1.0     # 0.0–1.0 = 1 − R(t)
    stability_score: float = 1.0            # S_adaptive (days)
    decay_rate: float = 0.1                 # λ
    revision_count: int = 0                 # total revisions

    # ── Time context ──────────────────────────────────────────────────────────
    days_since_last_revision: float = 0.0   # elapsed since last revision
    days_overdue: float = 0.0               # days past next_revision_at (0 if not overdue)

    # ── Topic properties ──────────────────────────────────────────────────────
    difficulty: float = 0.5                 # 0.0–1.0
    importance_weight: float = 1.0          # exam weight multiplier

    # ── Exam context ──────────────────────────────────────────────────────────
    days_until_exam: float | None = None    # None = no exam scheduled
    exam_weight: float = 1.0               # base exam multiplier from config

    # ── Weakness signal ───────────────────────────────────────────────────────
    weakness_trend: float = 0.0             # 0.0–1.0 (historical weakness pattern)
    recent_quiz_score: float | None = None  # latest quiz score (None = no quiz)


@dataclass(frozen=True, slots=True)
class PriorityReason:
    """
    Explainability — WHY this topic was prioritised.
    Each component has a human-readable reason string.
    """

    urgency_reason: str
    weakness_reason: str
    delay_reason: str
    exam_reason: str
    summary: str              # one-line overall recommendation


@dataclass(frozen=True, slots=True)
class PriorityOutput:
    """
    Complete priority result for a single topic.
    """

    # Composite score
    priority_score: float           # 0.0–∞ (higher = more urgent)
    normalised_score: float         # 0.0–1.0 (clamped for API responses)
    tier: PriorityTier              # human-readable urgency bucket

    # Component breakdown
    urgency_component: float
    weakness_component: float
    delay_component: float
    exam_component: float

    # Explainability
    reason: PriorityReason


# ═══════════════════════════════════════════════════════════════════════════════
#  Default Weight Constants
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_URGENCY_WEIGHT: float = 1.0
DEFAULT_DIFFICULTY_WEIGHT: float = 1.2
DEFAULT_EXAM_WEIGHT: float = 1.5
DEFAULT_WEAKNESS_WEIGHT: float = 1.0
DEFAULT_DELAY_WEIGHT: float = 1.0
DEFAULT_EXAM_PROXIMITY_DAYS: float = 30.0   # exam within 30 days = maximum urgency
DEFAULT_NORMALISATION_CAP: float = 5.0      # raw scores above this map to 1.0




# ═══════════════════════════════════════════════════════════════════════════════
#  Component Functions
# ═══════════════════════════════════════════════════════════════════════════════

def compute_urgency(
    retention_score: float,
    difficulty: float,
    *,
    urgency_weight: float = DEFAULT_URGENCY_WEIGHT,
    difficulty_weight: float = DEFAULT_DIFFICULTY_WEIGHT,
) -> tuple[float, str]:
    """
    Core urgency signal: how badly does this topic need revision?

    Formula:
        urgency = (1 − retention) × (1 + difficulty × difficulty_weight) × urgency_weight

    When retention=0: urgency is maximal (topic is completely forgotten)
    When retention=1: urgency is 0 (topic is perfectly retained)
    Difficulty amplifies urgency — harder forgotten topics get higher priority.

    Returns: (score, reason_string)
    """
    retention = _clamp01(retention_score)
    diff = _clamp01(difficulty)

    gap = 1.0 - retention
    difficulty_boost = 1.0 + diff * difficulty_weight
    score = gap * difficulty_boost * urgency_weight

    # Generate reason
    if gap > 0.7:
        reason = f"Retention critically low ({retention:.0%}), urgent revision needed"
    elif gap > 0.4:
        reason = f"Retention declining ({retention:.0%}), revision recommended"
    elif gap > 0.15:
        reason = f"Retention moderately low ({retention:.0%})"
    else:
        reason = f"Retention healthy ({retention:.0%})"

    return round(score, 4), reason


def compute_weakness(
    forgetting_probability: float,
    weakness_trend: float,
    recent_quiz_score: float | None,
    *,
    weight: float = DEFAULT_WEAKNESS_WEIGHT,
) -> tuple[float, str]:
    """
    Weakness signal: is the learner struggling with this topic?

    Formula:
        weakness = forgetting_prob × (1 + weakness_trend + quiz_penalty) × weight

    Three signals feed weakness:
      1. forgetting_probability — from decay engine
      2. weakness_trend — historical pattern (0.0=strong, 1.0=consistently weak)
      3. recent_quiz_score — low quiz score = recent failure signal

    Returns: (score, reason_string)
    """
    fp = _clamp01(forgetting_probability)
    trend = _clamp01(weakness_trend)

    # Quiz penalty: low recent score amplifies weakness
    quiz_penalty = 0.0
    quiz_note = ""
    if recent_quiz_score is not None:
        qs = _clamp01(recent_quiz_score)
        if qs < 0.5:
            quiz_penalty = 0.5 * (1.0 - qs)  # max 0.25 at score=0.5, max 0.5 at score=0
            quiz_note = f", recent quiz poor ({qs:.0%})"
        elif qs < 0.7:
            quiz_penalty = 0.2 * (0.7 - qs)  # small penalty for borderline
            quiz_note = f", recent quiz borderline ({qs:.0%})"

    score = fp * (1.0 + trend + quiz_penalty) * weight

    # Generate reason
    if trend > 0.6:
        reason = f"Persistent weakness pattern (trend={trend:.0%}){quiz_note}"
    elif fp > 0.7:
        reason = f"High forgetting probability ({fp:.0%}){quiz_note}"
    elif quiz_penalty > 0:
        reason = f"Recent quiz underperformance{quiz_note}"
    elif fp > 0.3:
        reason = f"Moderate forgetting risk ({fp:.0%})"
    else:
        reason = "No significant weakness detected"

    return round(score, 4), reason


def compute_delay_factor(
    days_overdue: float,
    days_since_last_revision: float,
    *,
    weight: float = DEFAULT_DELAY_WEIGHT,
) -> tuple[float, str]:
    """
    Revision delay signal: how overdue is this topic?

    Formula:
        delay = (1 + log(1 + overdue_days)) × inactivity_bonus × weight

    Uses log to prevent explosion — a topic 100 days overdue shouldn't
    be 100× more urgent than one 1 day overdue.

    Inactivity bonus: if no revision has ever happened (days_since_last=0 and
    overdue>0), adds a flat 0.5 bonus.

    Returns: (score, reason_string)
    """
    overdue = max(days_overdue, 0.0)
    since_last = max(days_since_last_revision, 0.0)

    delay = (1.0 + math.log(1.0 + overdue)) * weight

    # Bonus for topics that have never been revised
    never_revised_bonus = 0.0
    if since_last == 0.0 and overdue > 0:
        never_revised_bonus = 0.5
        delay += never_revised_bonus

    # Generate reason
    if overdue > 14:
        reason = f"Severely overdue ({overdue:.0f} days past schedule)"
    elif overdue > 3:
        reason = f"Overdue by {overdue:.0f} days"
    elif overdue > 0:
        reason = f"Slightly overdue ({overdue:.1f} days)"
    elif since_last > 14:
        reason = f"Not revised in {since_last:.0f} days"
    else:
        reason = "Revision is on schedule"

    return round(delay, 4), reason


def compute_exam_importance(
    importance_weight: float,
    days_until_exam: float | None,
    *,
    exam_weight: float = DEFAULT_EXAM_WEIGHT,
    proximity_window: float = DEFAULT_EXAM_PROXIMITY_DAYS,
) -> tuple[float, str]:
    """
    Exam importance signal: how much does exam proximity amplify priority?

    Formula:
        if no exam: importance = importance_weight (baseline)
        if exam in window:
            proximity = 1 − (days_until_exam / proximity_window)
            importance = importance_weight × (1 + proximity × exam_weight)

    Closer exam → higher multiplier (up to importance × (1 + exam_weight)).

    Returns: (score, reason_string)
    """
    base = max(importance_weight, 0.1)  # never zero

    if days_until_exam is None:
        return round(base, 4), "No exam scheduled"

    days = max(days_until_exam, 0.0)

    if days >= proximity_window:
        return round(base, 4), f"Exam in {days:.0f} days (not yet urgent)"

    # Proximity factor: 0 at edge of window → 1 at exam day
    proximity = 1.0 - (days / proximity_window)
    multiplier = 1.0 + proximity * exam_weight

    score = base * multiplier

    # Generate reason
    if days <= 1:
        reason = "Exam TOMORROW — maximum priority"
    elif days <= 3:
        reason = f"Exam in {days:.0f} days — critical priority"
    elif days <= 7:
        reason = f"Exam in {days:.0f} days — high priority"
    elif days <= 14:
        reason = f"Exam in {days:.0f} days — elevated priority"
    else:
        reason = f"Exam in {days:.0f} days — moderate boost"

    return round(score, 4), reason


# ═══════════════════════════════════════════════════════════════════════════════
#  Priority Tier Classification
# ═══════════════════════════════════════════════════════════════════════════════

def classify_tier(normalised_score: float) -> PriorityTier:
    """Map a 0.0–1.0 normalised score to a human-readable tier."""
    if normalised_score >= 0.8:
        return PriorityTier.CRITICAL
    elif normalised_score >= 0.5:
        return PriorityTier.HIGH
    elif normalised_score >= 0.25:
        return PriorityTier.MEDIUM
    elif normalised_score >= 0.1:
        return PriorityTier.LOW
    else:
        return PriorityTier.MINIMAL


def generate_summary(
    tier: PriorityTier,
    urgency_reason: str,
    weakness_reason: str,
    delay_reason: str,
    exam_reason: str,
) -> str:
    """
    Generate a one-line recommendation summary.
    Picks the most actionable reason based on tier.
    """
    if tier == PriorityTier.CRITICAL:
        parts = [r for r in [urgency_reason, exam_reason] if "critical" in r.lower() or "urgent" in r.lower() or "tomorrow" in r.lower()]
        if parts:
            return f"REVISE NOW: {parts[0]}"
        return f"REVISE NOW: {urgency_reason}"
    elif tier == PriorityTier.HIGH:
        return f"Recommended: {urgency_reason}. {delay_reason}"
    elif tier == PriorityTier.MEDIUM:
        return f"Consider revising: {urgency_reason}"
    elif tier == PriorityTier.LOW:
        return f"Low priority: {urgency_reason}"
    else:
        return "No immediate revision needed"


# ═══════════════════════════════════════════════════════════════════════════════
#  Master Computation — Single Topic
# ═══════════════════════════════════════════════════════════════════════════════

def compute_priority(
    inp: PriorityInput,
    *,
    urgency_weight: float = DEFAULT_URGENCY_WEIGHT,
    difficulty_weight: float = DEFAULT_DIFFICULTY_WEIGHT,
    exam_weight: float = DEFAULT_EXAM_WEIGHT,
    weakness_weight: float = DEFAULT_WEAKNESS_WEIGHT,
    delay_weight: float = DEFAULT_DELAY_WEIGHT,
    normalisation_cap: float = DEFAULT_NORMALISATION_CAP,
) -> PriorityOutput:
    """
    Master priority computation for a single topic.

    Combines all four components multiplicatively:
        priority = urgency × weakness × delay × exam_importance

    Multiplicative (not additive) because:
      - A topic with 0 urgency should have 0 priority regardless of delay
      - A topic with no weakness has reduced priority even if overdue
      - Exam importance scales everything proportionally

    The raw score is normalised to [0, 1] for API responses using:
        normalised = min(raw / cap, 1.0)
    """
    # ── Components ────────────────────────────────────────────────────────────
    # retention_score and forgetting_probability arrive pre-computed from
    # the adaptive forgetting engine via the service layer.
    urgency, urgency_reason = compute_urgency(
        inp.retention_score, inp.difficulty,
        urgency_weight=urgency_weight, difficulty_weight=difficulty_weight,
    )

    weakness, weakness_reason = compute_weakness(
        inp.forgetting_probability, inp.weakness_trend, inp.recent_quiz_score,
        weight=weakness_weight,
    )

    delay, delay_reason = compute_delay_factor(
        inp.days_overdue, inp.days_since_last_revision,
        weight=delay_weight,
    )

    exam, exam_reason = compute_exam_importance(
        inp.importance_weight, inp.days_until_exam,
        exam_weight=exam_weight,
    )

    # ── Composite score ───────────────────────────────────────────────────────
    raw = urgency * weakness * delay * exam
    normalised = min(raw / normalisation_cap, 1.0) if normalisation_cap > 0 else 0.0

    tier = classify_tier(normalised)
    summary = generate_summary(tier, urgency_reason, weakness_reason, delay_reason, exam_reason)

    reason = PriorityReason(
        urgency_reason=urgency_reason,
        weakness_reason=weakness_reason,
        delay_reason=delay_reason,
        exam_reason=exam_reason,
        summary=summary,
    )

    return PriorityOutput(
        priority_score=round(raw, 4),
        normalised_score=round(normalised, 4),
        tier=tier,
        urgency_component=urgency,
        weakness_component=weakness,
        delay_component=delay,
        exam_component=exam,
        reason=reason,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Batch Ranking
# ═══════════════════════════════════════════════════════════════════════════════

def rank_topics(
    inputs: list[tuple[object, PriorityInput]],
    *,
    limit: int | None = None,
    **kwargs,
) -> list[tuple[object, PriorityOutput]]:
    """
    Rank multiple topics by priority score (descending).

    Args:
        inputs: list of (topic_id, PriorityInput) tuples.
                topic_id can be any hashable identifier.
        limit:  if set, return only the top-N topics.
        **kwargs: forwarded to compute_priority (weight overrides).

    Returns:
        Sorted list of (topic_id, PriorityOutput) tuples,
        highest priority first.

    The sort is STABLE — topics with equal scores preserve their
    original order (no random tie-breaking).
    """
    scored = [
        (tid, compute_priority(inp, **kwargs))
        for tid, inp in inputs
    ]

    # Stable sort by raw priority_score descending
    scored.sort(key=lambda x: x[1].priority_score, reverse=True)

    if limit is not None and limit > 0:
        scored = scored[:limit]

    return scored


# ═══════════════════════════════════════════════════════════════════════════════
#  Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def _clamp01(value: float) -> float:
    """Clamp a value to the [0.0, 1.0] range."""
    return max(0.0, min(1.0, value))
