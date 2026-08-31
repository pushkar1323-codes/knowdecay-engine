"""
app/engine/scheduling_engine.py
─────────────────────────────────
Adaptive revision scheduling engine.

Answers the question: "WHEN should the learner revise each topic?"

This module generates optimal revision times using spaced repetition
principles, adapted for exam proximity and individual learner state.

Scheduling Modes
════════════════
  EXAM_TOMORROW   — cram mode: compress everything into hours
  EXAM_WEEK       — intensive: daily revision of weak topics
  EXAM_MONTH      — balanced: spaced intervals with exam ramp-up
  LONG_TERM       — maintenance: pure spaced repetition for retention

Core Algorithm
══════════════
  base_interval = stability_score × retention_factor
  adjusted      = base_interval × difficulty_modifier / exam_compression
  next_revision = now + adjusted

  Where:
    retention_factor   = max(0.3, retention^0.5)  — lower retention → shorter interval
    difficulty_modifier = 1 / (1 + 0.3 × difficulty)  — harder → sooner
    exam_compression   = depends on mode (1.0 for long-term, up to 10× for cram)

Spaced Repetition Intervals
════════════════════════════
  Revision 1: base_interval × 1.0
  Revision 2: base_interval × 1.5
  Revision 3: base_interval × 2.0
  Revision n: base_interval × min(n^0.6, 5.0)  — capped growth

Design principles:
  • All functions are PURE — no DB, no I/O
  • Schedule mode selection is deterministic based on exam distance
  • Intervals always respect minimum and maximum bounds
  • Multi-topic schedules avoid time slot conflicts
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
#  Enums
# ═══════════════════════════════════════════════════════════════════════════════

class ScheduleMode(str, Enum):
    """Scheduling strategy based on exam proximity."""

    EXAM_TOMORROW = "exam_tomorrow"     # < 1 day
    EXAM_WEEK = "exam_week"             # 1–7 days
    EXAM_MONTH = "exam_month"           # 7–30 days
    LONG_TERM = "long_term"             # > 30 days or no exam


# ═══════════════════════════════════════════════════════════════════════════════
#  Data Transfer Objects
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class ScheduleInput:
    """
    All inputs for computing the next revision time for a single topic.
    """

    # From memory_state
    retention_score: float = 0.5
    stability_score: float = 1.0        # days until retention drops to threshold
    decay_rate: float = 0.1
    urgency_score: float = 0.0          # from priority engine
    revision_count: int = 0
    forgetting_probability: float = 0.5

    # Topic properties
    difficulty: float = 0.5
    importance_weight: float = 1.0

    # Exam context
    days_until_exam: float | None = None

    # Time context
    days_since_last_revision: float = 0.0

    # Adaptive forgetting curve (Phase 8.5) — used in place of
    # stability_score when available for cognitively grounded intervals
    adaptive_stability: float | None = None


@dataclass(frozen=True, slots=True)
class ScheduleOutput:
    """
    Complete scheduling result for a single topic.
    """

    # Core output
    next_revision_days: float           # days from now to next revision
    mode: ScheduleMode                  # which scheduling strategy was used
    schedule_priority: float            # 0.0–1.0, higher = revise sooner within a session

    # Interval breakdown
    base_interval: float                # raw spaced repetition interval
    adjusted_interval: float            # after difficulty + exam compression
    retention_factor: float             # how retention affected the interval
    difficulty_modifier: float          # difficulty scaling
    exam_compression: float             # how much exam proximity compressed the interval

    # Recommendation
    recommendation: str                 # human-readable scheduling advice


@dataclass(frozen=True, slots=True)
class ScheduleSlot:
    """A single slot in a multi-topic schedule."""

    topic_id: object                    # any hashable identifier
    day: float                          # days from now
    priority: float                     # schedule_priority for ordering within a day
    mode: ScheduleMode
    recommendation: str


# ═══════════════════════════════════════════════════════════════════════════════
#  Default Parameters
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_MIN_INTERVAL: float = 0.04      # ~1 hour minimum between revisions
DEFAULT_MAX_INTERVAL: float = 90.0      # 90 day maximum gap
DEFAULT_RETENTION_EXPONENT: float = 0.5 # sqrt scaling for retention factor
DEFAULT_DIFFICULTY_SCALE: float = 0.3   # how much difficulty shortens intervals
DEFAULT_INTERVAL_GROWTH_CAP: float = 5.0  # max revision multiplier


# ═══════════════════════════════════════════════════════════════════════════════
#  Schedule Mode Selection
# ═══════════════════════════════════════════════════════════════════════════════

def select_mode(days_until_exam: float | None) -> ScheduleMode:
    """
    Select scheduling strategy based on exam proximity.

    Rules:
      None or > 30 days → LONG_TERM (pure spaced repetition)
      7–30 days         → EXAM_MONTH (balanced with exam ramp-up)
      1–7 days          → EXAM_WEEK (intensive daily revision)
      < 1 day           → EXAM_TOMORROW (cram — hours, not days)
    """
    if days_until_exam is None or days_until_exam > 30:
        return ScheduleMode.LONG_TERM
    if days_until_exam > 7:
        return ScheduleMode.EXAM_MONTH
    if days_until_exam > 1:
        return ScheduleMode.EXAM_WEEK
    return ScheduleMode.EXAM_TOMORROW


# ═══════════════════════════════════════════════════════════════════════════════
#  Core Scheduling Functions
# ═══════════════════════════════════════════════════════════════════════════════

def compute_base_interval(
    stability_score: float,
    retention_score: float,
    revision_count: int,
    *,
    retention_exponent: float = DEFAULT_RETENTION_EXPONENT,
    growth_cap: float = DEFAULT_INTERVAL_GROWTH_CAP,
) -> tuple[float, float]:
    """
    Compute the base spaced-repetition interval.

    Formula:
        retention_factor = max(0.3, retention^exponent)
        revision_mult    = min(revision_count^0.6, growth_cap) if count > 0 else 1.0
        base_interval    = stability × retention_factor × revision_mult

    Higher retention → longer interval (topic is well-remembered).
    More revisions  → longer interval (spaced repetition working).
    Higher stability → longer interval (slower decay).

    Returns: (base_interval_days, retention_factor)
    """
    stability = max(stability_score, 0.1)
    retention = _clamp01(retention_score)

    # Retention factor: sqrt scaling — low retention shortens interval
    ret_factor = max(0.3, math.pow(retention, retention_exponent))

    # Revision multiplier: more revisions → longer gaps (diminishing)
    if revision_count > 0:
        rev_mult = min(math.pow(revision_count, 0.6), growth_cap)
    else:
        rev_mult = 1.0

    interval = stability * ret_factor * rev_mult
    return round(interval, 4), round(ret_factor, 4)


def compute_difficulty_modifier(
    difficulty: float,
    *,
    scale: float = DEFAULT_DIFFICULTY_SCALE,
) -> float:
    """
    Difficulty shortens the revision interval.

    Formula: 1 / (1 + scale × difficulty)

    Easy topic (0.0) → modifier = 1.0 (no change)
    Hard topic (1.0) → modifier ≈ 0.77 (23% shorter interval)

    Range: (1/(1+scale), 1.0]
    """
    diff = _clamp01(difficulty)
    return round(1.0 / (1.0 + scale * diff), 4)


def compute_exam_compression(
    mode: ScheduleMode,
    days_until_exam: float | None,
) -> float:
    """
    Exam proximity compression factor — how much to shrink intervals.

    LONG_TERM:      1.0  (no compression)
    EXAM_MONTH:     1.5–2.5 (moderate compression, ramps up as exam nears)
    EXAM_WEEK:      3.0–5.0 (aggressive compression)
    EXAM_TOMORROW:  8.0–10.0 (maximum compression — cram mode)

    Returns a divisor: interval / compression = compressed_interval
    """
    if mode == ScheduleMode.LONG_TERM:
        return 1.0

    days = max(days_until_exam or 0, 0.01)

    if mode == ScheduleMode.EXAM_TOMORROW:
        # Cram mode: compress to hours
        return 10.0

    if mode == ScheduleMode.EXAM_WEEK:
        # 1–7 days: linear ramp from 3.0 (7 days) to 5.0 (1 day)
        t = (7.0 - days) / 6.0  # 0 at 7 days, 1 at 1 day
        return 3.0 + 2.0 * _clamp01(t)

    if mode == ScheduleMode.EXAM_MONTH:
        # 7–30 days: linear ramp from 1.5 (30 days) to 2.5 (7 days)
        t = (30.0 - days) / 23.0  # 0 at 30 days, 1 at 7 days
        return 1.5 + 1.0 * _clamp01(t)

    return 1.0


def compute_schedule_priority(
    urgency_score: float,
    retention_score: float,
    forgetting_probability: float,
) -> float:
    """
    Priority within a scheduling session — which topics to revise first.

    Combines urgency from the priority engine with retention state.

    Formula:
        priority = 0.5 × urgency + 0.3 × (1 − retention) + 0.2 × forgetting_prob

    Range: [0.0, 1.0]
    """
    u = _clamp01(urgency_score)
    r_gap = 1.0 - _clamp01(retention_score)
    fp = _clamp01(forgetting_probability)
    return round(_clamp01(0.5 * u + 0.3 * r_gap + 0.2 * fp), 4)


def generate_recommendation(
    mode: ScheduleMode,
    next_revision_days: float,
    retention_score: float,
    urgency_score: float,
) -> str:
    """
    Generate human-readable scheduling advice.
    """
    retention = _clamp01(retention_score)

    if mode == ScheduleMode.EXAM_TOMORROW:
        if urgency_score > 0.5:
            return "CRAM: Revise this topic in the next few hours — high urgency before exam"
        return "CRAM: Quick review recommended before exam"

    if mode == ScheduleMode.EXAM_WEEK:
        if retention < 0.4:
            return f"INTENSIVE: Revise within {next_revision_days:.1f} days — retention is low before exam"
        return f"INTENSIVE: Schedule revision in {next_revision_days:.1f} days before exam"

    if mode == ScheduleMode.EXAM_MONTH:
        if retention < 0.5:
            return f"BALANCED: Revise in {next_revision_days:.1f} days — build retention before exam"
        return f"BALANCED: Next revision in {next_revision_days:.1f} days"

    # LONG_TERM
    if next_revision_days < 1:
        return "SPACED: Revise today for optimal retention"
    elif next_revision_days < 7:
        return f"SPACED: Revise in {next_revision_days:.1f} days for optimal spacing"
    else:
        return f"SPACED: Well-retained — next revision in {next_revision_days:.0f} days"


# ═══════════════════════════════════════════════════════════════════════════════
#  Master Computation — Single Topic
# ═══════════════════════════════════════════════════════════════════════════════

def compute_schedule(
    inp: ScheduleInput,
    *,
    min_interval: float = DEFAULT_MIN_INTERVAL,
    max_interval: float = DEFAULT_MAX_INTERVAL,
) -> ScheduleOutput:
    """
    Master scheduling computation for a single topic.

    Steps:
      1. Select scheduling mode based on exam proximity
      2. Compute base spaced-repetition interval
      3. Apply difficulty modifier
      4. Apply exam compression
      5. Clamp to [min, max] bounds
      6. Compute schedule priority for session ordering
      7. Generate recommendation

    The final interval is further capped by days_until_exam when an exam
    is scheduled — we never schedule a revision AFTER the exam.
    """
    # ── 1. Mode ───────────────────────────────────────────────────────────────
    mode = select_mode(inp.days_until_exam)

    # ── 2. Base interval ──────────────────────────────────────────────────────────
    # Use adaptive_stability from forgetting curve when available (Phase 8.5)
    effective_stability = inp.adaptive_stability if inp.adaptive_stability is not None else inp.stability_score
    base, ret_factor = compute_base_interval(
        effective_stability, inp.retention_score, inp.revision_count,
    )

    # ── 3. Difficulty modifier ────────────────────────────────────────────────
    diff_mod = compute_difficulty_modifier(inp.difficulty)

    # ── 4. Exam compression ───────────────────────────────────────────────────
    compression = compute_exam_compression(mode, inp.days_until_exam)

    # ── 5. Adjusted interval ──────────────────────────────────────────────────
    adjusted = (base * diff_mod) / compression
    adjusted = max(min(adjusted, max_interval), min_interval)

    # Never schedule past the exam
    if inp.days_until_exam is not None and inp.days_until_exam > 0:
        adjusted = min(adjusted, inp.days_until_exam * 0.9)  # 10% buffer before exam
        adjusted = max(adjusted, min_interval)

    next_days = round(adjusted, 4)

    # ── 6. Schedule priority ──────────────────────────────────────────────────
    sched_priority = compute_schedule_priority(
        inp.urgency_score, inp.retention_score, inp.forgetting_probability,
    )

    # ── 7. Recommendation ─────────────────────────────────────────────────────
    rec = generate_recommendation(mode, next_days, inp.retention_score, inp.urgency_score)

    return ScheduleOutput(
        next_revision_days=next_days,
        mode=mode,
        schedule_priority=sched_priority,
        base_interval=base,
        adjusted_interval=round(adjusted, 4),
        retention_factor=ret_factor,
        difficulty_modifier=diff_mod,
        exam_compression=compression,
        recommendation=rec,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Multi-Topic Schedule Generation
# ═══════════════════════════════════════════════════════════════════════════════

def generate_schedule(
    inputs: list[tuple[object, ScheduleInput]],
    *,
    max_per_day: int = 10,
    **kwargs,
) -> list[ScheduleSlot]:
    """
    Generate a unified revision schedule across multiple topics.

    Steps:
      1. Compute schedule for each topic independently
      2. Sort by next_revision_days (soonest first)
      3. Within the same day, sort by schedule_priority (highest first)
      4. Cap at max_per_day topics per day-bucket

    Returns: list of ScheduleSlot sorted chronologically.
    """
    # Compute individual schedules
    computed: list[tuple[object, ScheduleOutput]] = []
    for tid, inp in inputs:
        out = compute_schedule(inp, **kwargs)
        computed.append((tid, out))

    # Sort: primary by day (soonest), secondary by priority (highest)
    computed.sort(key=lambda x: (x[1].next_revision_days, -x[1].schedule_priority))

    # Build slots with per-day cap
    slots: list[ScheduleSlot] = []
    day_counts: dict[int, int] = {}  # day_bucket → count

    for tid, out in computed:
        day_bucket = int(out.next_revision_days)
        count = day_counts.get(day_bucket, 0)

        if count >= max_per_day:
            # Push to next available day
            day_bucket += 1
            while day_counts.get(day_bucket, 0) >= max_per_day:
                day_bucket += 1

        day_counts[day_bucket] = day_counts.get(day_bucket, 0) + 1

        slots.append(ScheduleSlot(
            topic_id=tid,
            day=round(max(out.next_revision_days, float(day_bucket)), 4),
            priority=out.schedule_priority,
            mode=out.mode,
            recommendation=out.recommendation,
        ))

    return slots


# ═══════════════════════════════════════════════════════════════════════════════
#  Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def _clamp01(value: float) -> float:
    """Clamp a value to the [0.0, 1.0] range."""
    return max(0.0, min(1.0, value))
