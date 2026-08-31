"""
app/engine/stability_engine.py
────────────────────────────────
Adaptive Memory Stability Engine.

Computes S_adaptive — the dynamic memory stability that governs how
fast a learner forgets a specific topic.  This value is the denominator
in the Ebbinghaus forgetting curve: R(t) = e^(−t / S_adaptive).

Higher S_adaptive → slower forgetting → longer intervals between revisions.

Stability Evolution Model
═════════════════════════
  S_adaptive = base_stability
               × reinforcement_factor
               × quiz_performance_factor
               × confidence_factor
               − difficulty_penalty

Component Definitions
═════════════════════
  base_stability          — starting stability in days, evolves with each event
  reinforcement_factor    — accumulated learning reinforcement (diminishing returns)
  quiz_performance_factor — how well quizzes indicate mastery
  confidence_factor       — learner's own confidence signal
  difficulty_penalty      — harder topics have inherently lower stability

After each successful event, base_stability grows:
  base_new = base_old × (1 + growth × quality)

Design principles:
  • All functions are PURE — no DB, no I/O
  • Stability is always ≥ minimum bound (0.1 days)
  • Every component is individually computable and testable
  • Growth is sublinear to prevent stability explosion
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════════════════════
#  Data Transfer Objects
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class StabilityInput:
    """All inputs needed to compute adaptive stability."""

    # Current state
    base_stability: float = 1.0         # starting stability (days), evolves over time
    revision_count: int = 0             # total revision events
    revision_quality: float = 0.5       # average quality of revisions (0–1)

    # Performance signals
    quiz_score: float = 0.0             # latest quiz score (0–1)
    confidence_score: float = 0.5       # blended confidence (0–1)
    performance_trend: float = 0.0      # recent trajectory: −1 (declining) to +1 (improving)

    # Topic properties
    difficulty: float = 0.5             # 0.0 (easy) → 1.0 (hard)


@dataclass(frozen=True, slots=True)
class StabilityOutput:
    """Complete stability computation result with component breakdown."""

    adaptive_stability: float           # S_adaptive — the final value
    reinforcement_factor: float         # how reinforcement scaled stability
    quiz_performance_factor: float      # how quiz performance scaled stability
    confidence_factor: float            # how confidence scaled stability
    difficulty_penalty: float           # how much difficulty subtracted


@dataclass(frozen=True, slots=True)
class StabilityEvolution:
    """Result of evolving base_stability after a learning event."""

    new_base_stability: float           # updated base stability
    growth_applied: float               # how much growth was added
    new_revision_quality: float         # updated running quality average
    new_performance_trend: float        # updated trend indicator


# ═══════════════════════════════════════════════════════════════════════════════
#  Default Parameters
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_MIN_STABILITY: float = 0.1          # minimum S_adaptive (days)
DEFAULT_MAX_STABILITY: float = 365.0        # maximum S_adaptive (days)
DEFAULT_REINFORCEMENT_ALPHA: float = 0.4    # reinforcement log scaling
DEFAULT_DIFFICULTY_BETA: float = 0.3        # difficulty penalty scaling
DEFAULT_GROWTH_RATE: float = 0.15           # base stability growth rate per event
DEFAULT_MAX_GROWTH_PER_EVENT: float = 0.5   # cap growth per event
DEFAULT_TREND_SMOOTHING: float = 0.3        # EMA alpha for performance trend


# ═══════════════════════════════════════════════════════════════════════════════
#  Component Functions
# ═══════════════════════════════════════════════════════════════════════════════

def compute_reinforcement_factor(
    revision_count: int,
    revision_quality: float,
    *,
    alpha: float = DEFAULT_REINFORCEMENT_ALPHA,
) -> float:
    """
    Reinforcement factor — how much repeated, quality revision strengthens memory.

    Formula:
        factor = 1 + α × ln(1 + revision_count) × quality_weight

    Where quality_weight = 0.5 + 0.5 × revision_quality (so bad revisions
    still contribute half).

    Range: [1.0, ~3.5] for typical inputs
    Properties:
        0 revisions → factor = 1.0 (no reinforcement)
        Many good revisions → grows logarithmically (diminishing returns)
    """
    count = max(revision_count, 0)
    quality = _clamp01(revision_quality)
    quality_weight = 0.5 + 0.5 * quality
    return round(1.0 + alpha * math.log(1 + count) * quality_weight, 4)


def compute_quiz_performance_factor(
    quiz_score: float,
    performance_trend: float = 0.0,
) -> float:
    """
    Quiz performance factor — how quiz mastery affects stability.

    Formula:
        factor = 0.5 + 0.5 × score + 0.1 × trend

    Range: [0.4, 1.1]
    Properties:
        score=0, trend=-1 → 0.4 (worst case — unstable memory)
        score=1, trend=+1 → 1.1 (best case — very stable memory)
    """
    score = _clamp01(quiz_score)
    trend = max(-1.0, min(1.0, performance_trend))
    return round(max(0.4, min(1.1, 0.5 + 0.5 * score + 0.1 * trend)), 4)


def compute_confidence_factor(
    confidence_score: float,
) -> float:
    """
    Confidence factor — learner's self-assessed mastery signal.

    Formula:
        factor = 0.7 + 0.3 × confidence

    Range: [0.7, 1.0]
    Properties:
        Confidence is a weak but directional signal.
        Low confidence lowers stability (even if quiz is good — signals fragility).
    """
    conf = _clamp01(confidence_score)
    return round(0.7 + 0.3 * conf, 4)


def compute_difficulty_penalty(
    difficulty: float,
    *,
    beta: float = DEFAULT_DIFFICULTY_BETA,
) -> float:
    """
    Difficulty penalty — harder topics have inherently lower stability.

    Formula:
        penalty = β × difficulty^1.2

    The exponent > 1 means very hard topics are penalised disproportionately.

    Range: [0.0, β]
    """
    diff = _clamp01(difficulty)
    return round(beta * math.pow(diff, 1.2), 4)


# ═══════════════════════════════════════════════════════════════════════════════
#  Master Computation
# ═══════════════════════════════════════════════════════════════════════════════

def compute_adaptive_stability(
    inp: StabilityInput,
    *,
    min_stability: float = DEFAULT_MIN_STABILITY,
    max_stability: float = DEFAULT_MAX_STABILITY,
) -> StabilityOutput:
    """
    Master stability computation.

    Formula:
        S_adaptive = base_stability × reinforcement × quiz_perf × confidence − difficulty_penalty

    All components are computed independently, then combined multiplicatively
    (except difficulty which is subtractive — it removes days of stability).
    """
    reinf = compute_reinforcement_factor(inp.revision_count, inp.revision_quality)
    quiz = compute_quiz_performance_factor(inp.quiz_score, inp.performance_trend)
    conf = compute_confidence_factor(inp.confidence_score)
    diff_pen = compute_difficulty_penalty(inp.difficulty)

    raw = inp.base_stability * reinf * quiz * conf - diff_pen
    adaptive = max(min(raw, max_stability), min_stability)

    return StabilityOutput(
        adaptive_stability=round(adaptive, 4),
        reinforcement_factor=reinf,
        quiz_performance_factor=quiz,
        confidence_factor=conf,
        difficulty_penalty=diff_pen,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Stability Evolution — After Learning Events
# ═══════════════════════════════════════════════════════════════════════════════

def evolve_stability(
    current_base: float,
    event_quality: float,
    revision_count: int,
    current_quality_avg: float,
    current_trend: float,
    *,
    growth_rate: float = DEFAULT_GROWTH_RATE,
    max_growth: float = DEFAULT_MAX_GROWTH_PER_EVENT,
    trend_alpha: float = DEFAULT_TREND_SMOOTHING,
) -> StabilityEvolution:
    """
    Evolve base_stability after a learning event.

    Growth:
        growth = growth_rate × event_quality / (1 + 0.05 × revision_count)
        base_new = base_old × (1 + min(growth, max_growth))

    The growth rate diminishes with revision count — early revisions
    grow stability faster than late ones.

    Revision quality is a running average:
        quality_new = (quality_old × count + event_quality) / (count + 1)

    Performance trend uses EMA:
        trend_new = α × event_quality + (1 − α) × trend_old
        Then normalized to [−1, +1] centered at 0.5
    """
    quality = _clamp01(event_quality)
    count = max(revision_count, 0)

    # Growth (sublinear, capped)
    raw_growth = growth_rate * quality / (1.0 + 0.05 * count)
    growth = min(raw_growth, max_growth)
    new_base = current_base * (1.0 + growth)

    # Running quality average
    if count > 0:
        new_quality = (current_quality_avg * count + quality) / (count + 1)
    else:
        new_quality = quality

    # Performance trend (EMA, then shift so 0.5 → 0.0)
    ema = trend_alpha * quality + (1.0 - trend_alpha) * ((current_trend + 1.0) / 2.0)
    new_trend = max(-1.0, min(1.0, 2.0 * ema - 1.0))

    return StabilityEvolution(
        new_base_stability=round(new_base, 4),
        growth_applied=round(growth, 4),
        new_revision_quality=round(new_quality, 4),
        new_performance_trend=round(new_trend, 4),
    )


def degrade_stability(
    current_base: float,
    days_inactive: float,
    *,
    onset_days: float = 7.0,
    degradation_rate: float = 0.02,
    min_base: float = 0.5,
) -> float:
    """
    Degrade base_stability due to inactivity.

    After the onset period, stability shrinks gradually.

    Formula:
        loss_factor = 1 − degradation_rate × (days − onset)^0.8
        new_base = max(base × loss_factor, min_base)
    """
    if days_inactive <= onset_days:
        return current_base

    excess = days_inactive - onset_days
    loss_factor = max(0.0, 1.0 - degradation_rate * math.pow(excess, 0.8))
    return round(max(current_base * loss_factor, min_base), 4)


# ═══════════════════════════════════════════════════════════════════════════════
#  Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
