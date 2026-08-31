"""
app/engine/decay_engine.py
────────────────────────────
Forgetting progression analysis engine.

This module models HOW memory decays over time — complementary to
retention_engine.py which computes a point-in-time score.

Responsibilities:
  • Estimate forgetting progression over a time window
  • Calculate time-based decay using Ebbinghaus-inspired curves
  • Estimate forgetting probability at any future point
  • Predict retention drop over configurable horizons
  • Apply inactivity penalties for prolonged non-revision
  • Compute memory half-life

Mathematical Foundations
════════════════════════
All formulas derive from the Ebbinghaus Forgetting Curve:

  R(t) = R₀ × e^(−λt)

Where:
  R(t) = retention at time t
  R₀   = initial retention (at t=0, i.e., right after learning)
  λ    = decay rate (per day)
  t    = elapsed time in days

Modifications to the classic model:
  1. Difficulty-adjusted λ  — harder topics have higher λ
  2. Reinforcement damping  — more revisions lower λ
  3. Inactivity acceleration — prolonged absence raises λ super-linearly
  4. Retention floor         — retention never drops to true zero
  5. Half-life computation  — days until retention reaches 50% of R₀

Design principles:
  • All functions are PURE — no DB, no I/O, no side effects
  • All inputs are explicit — no globals
  • All parameters have sensible defaults with keyword-only overrides
  • Outputs are clamped to valid mathematical ranges
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════════════════════
#  Data Transfer Objects
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class DecayInput:
    """
    All inputs for forgetting analysis of a single user × topic.
    """

    # Current state
    current_retention: float = 1.0      # R₀ — retention at measurement time
    current_decay_rate: float = 0.1     # λ — current per-day decay rate

    # Topic properties
    difficulty: float = 0.5             # 0.0 (easy) → 1.0 (very hard)

    # Revision history
    revision_count: int = 0             # total lifetime revisions
    days_since_last_revision: float = 0.0  # elapsed since most recent revision

    # Analysis window
    projection_days: float = 7.0        # how far into the future to project


@dataclass(frozen=True, slots=True)
class DecayOutput:
    """
    Complete forgetting analysis result.
    """

    # Core outputs
    effective_decay_rate: float         # λ_eff — after difficulty + reinforcement + inactivity adjustments
    forgetting_probability: float       # P(forgotten) at current time
    predicted_retention: float          # R(t) at end of projection window
    predicted_retention_drop: float     # ΔR = R₀ − R(t) — how much retention will fall

    # Time metrics
    half_life_days: float               # days until retention reaches 50% of R₀
    time_to_threshold_days: float       # days until retention drops below threshold

    # Inactivity
    inactivity_penalty: float           # additional decay from prolonged inactivity
    is_critically_decayed: bool         # True if retention will drop below 0.2 in window

    # Forgetting curve projection (sampled points)
    curve: list[CurvePoint] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CurvePoint:
    """A single point on the projected forgetting curve."""

    day: float
    retention: float
    forgetting_probability: float


# ═══════════════════════════════════════════════════════════════════════════════
#  Default Parameters
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_RETENTION_THRESHOLD: float = 0.4    # below this = "at risk"
DEFAULT_CRITICAL_THRESHOLD: float = 0.2     # below this = "critically decayed"
DEFAULT_RETENTION_FLOOR: float = 0.02       # absolute minimum — never true zero
DEFAULT_INACTIVITY_ONSET_DAYS: float = 7.0  # inactivity penalty starts after this
DEFAULT_INACTIVITY_SCALE: float = 0.02      # how aggressively inactivity raises λ
DEFAULT_CURVE_POINTS: int = 10              # number of sample points on projection curve


# ═══════════════════════════════════════════════════════════════════════════════
#  Core Decay Functions
# ═══════════════════════════════════════════════════════════════════════════════

def compute_effective_decay_rate(
    base_rate: float,
    difficulty: float,
    revision_count: int,
    days_since_last_revision: float,
    *,
    inactivity_onset: float = DEFAULT_INACTIVITY_ONSET_DAYS,
    inactivity_scale: float = DEFAULT_INACTIVITY_SCALE,
    min_rate: float = 0.005,
    max_rate: float = 1.0,
) -> float:
    """
    Compute the effective decay rate after all adjustments.

    Three modifiers applied to the base rate:
      1. Difficulty multiplier     — harder topics decay faster
         factor: (1 + 0.5 × difficulty)

      2. Reinforcement damping     — more revisions slow decay
         factor: 1 / (1 + 0.15 × revision_count)

      3. Inactivity acceleration   — prolonged absence speeds decay
         penalty added when days_since_last_revision > onset threshold
         penalty: scale × (excess_days)^1.3  (super-linear — accelerates)

    Formula:
        λ_eff = base_rate × (1 + 0.5 × difficulty) / (1 + 0.15 × revisions) + inactivity_penalty

    Range: [min_rate, max_rate]
    """
    diff = _clamp01(difficulty)
    revisions = max(revision_count, 0)

    # Difficulty makes forgetting faster
    difficulty_factor = 1.0 + 0.5 * diff

    # Revisions slow forgetting (diminishing returns)
    reinforcement_factor = 1.0 / (1.0 + 0.15 * revisions)

    adjusted = base_rate * difficulty_factor * reinforcement_factor

    # Inactivity penalty — super-linear growth after onset
    inactivity = compute_inactivity_penalty(
        days_since_last_revision,
        onset=inactivity_onset,
        scale=inactivity_scale,
    )
    adjusted += inactivity

    return round(max(min(adjusted, max_rate), min_rate), 6)


def compute_inactivity_penalty(
    days_since_last_revision: float,
    *,
    onset: float = DEFAULT_INACTIVITY_ONSET_DAYS,
    scale: float = DEFAULT_INACTIVITY_SCALE,
) -> float:
    """
    Inactivity decay acceleration.

    No penalty for the first `onset` days after last revision.
    After that, penalty grows super-linearly (exponent 1.3).

    This models the observation that forgetting accelerates when
    a learner completely abandons a topic for extended periods.

    Formula:
        if days <= onset: penalty = 0
        else: penalty = scale × (days − onset)^1.3

    Range: [0.0, ∞)  — but clamped by caller in effective rate
    """
    if days_since_last_revision <= onset:
        return 0.0
    excess = days_since_last_revision - onset
    return scale * math.pow(excess, 1.3)


def compute_retention_at_time(
    initial_retention: float,
    decay_rate: float,
    elapsed_days: float,
    *,
    floor: float = DEFAULT_RETENTION_FLOOR,
) -> float:
    """
    Predict retention at a future time point using the Ebbinghaus model.

    Formula:  R(t) = max(R₀ × e^(−λt), floor)

    Properties:
      t=0  → R(0) = R₀     (no forgetting yet)
      t→∞  → R(∞) → floor  (approaches but never reaches zero)

    Range: [floor, R₀]
    """
    if elapsed_days <= 0:
        return _clamp01(initial_retention)
    if decay_rate <= 0:
        return _clamp01(initial_retention)

    r = initial_retention * math.exp(-decay_rate * elapsed_days)
    return max(r, floor)


def compute_forgetting_probability(
    initial_retention: float,
    decay_rate: float,
    elapsed_days: float,
    *,
    threshold: float = DEFAULT_RETENTION_THRESHOLD,
) -> float:
    """
    Probability that the topic has been substantially forgotten.

    Uses a soft sigmoid transition around the retention threshold
    rather than a hard binary cutoff. This gives smoother prioritisation.

    Formula:
        R(t) = R₀ × e^(−λt)
        ratio = R(t) / threshold
        P(forgotten) = 1 / (1 + e^(5 × (ratio − 1)))

    When R(t) == threshold: P ≈ 0.5
    When R(t) >> threshold: P → 0  (well retained)
    When R(t) << threshold: P → 1  (substantially forgotten)

    The steepness parameter (5) controls transition sharpness.
    Range: [0.0, 1.0]
    """
    r_t = compute_retention_at_time(initial_retention, decay_rate, elapsed_days)

    if threshold <= 0:
        return 0.0

    ratio = r_t / threshold
    # Sigmoid centred at ratio=1 with steepness=5
    exponent = 5.0 * (ratio - 1.0)
    # Clamp exponent to prevent overflow
    exponent = max(-20.0, min(20.0, exponent))
    p = 1.0 / (1.0 + math.exp(exponent))

    return round(_clamp01(p), 4)


def compute_half_life(
    decay_rate: float,
) -> float:
    """
    Memory half-life — days until retention drops to 50% of initial value.

    From R(t) = R₀ × e^(−λt), solving for R(t) = 0.5 × R₀:
        0.5 = e^(−λ × t_half)
        t_half = ln(2) / λ

    Range: [0.69 / max_rate, ∞)  — always positive when λ > 0
    """
    if decay_rate <= 0:
        return float("inf")   # no decay → infinite half-life
    return round(math.log(2) / decay_rate, 4)


def compute_time_to_threshold(
    initial_retention: float,
    decay_rate: float,
    *,
    threshold: float = DEFAULT_RETENTION_THRESHOLD,
    floor: float = DEFAULT_RETENTION_FLOOR,
) -> float:
    """
    Days until retention drops below the given threshold.

    From R(t) = R₀ × e^(−λt), solving for R(t) = threshold:
        t = −ln(threshold / R₀) / λ

    Returns float('inf') if retention is already below threshold
    or if decay rate is zero.

    Range: [0.0, ∞)
    """
    if decay_rate <= 0:
        return float("inf")
    if initial_retention <= threshold:
        return 0.0   # already below threshold
    if threshold <= floor:
        return float("inf")

    t = -math.log(threshold / initial_retention) / decay_rate
    return round(max(t, 0.0), 4)


def compute_predicted_retention_drop(
    initial_retention: float,
    decay_rate: float,
    projection_days: float,
    *,
    floor: float = DEFAULT_RETENTION_FLOOR,
) -> float:
    """
    How much retention will decrease over the projection window.

    Formula: ΔR = R₀ − R(t_end)
    Range:   [0.0, R₀ − floor]
    """
    if projection_days <= 0:
        return 0.0
    r_end = compute_retention_at_time(initial_retention, decay_rate, projection_days, floor=floor)
    drop = initial_retention - r_end
    return round(max(drop, 0.0), 4)


# ═══════════════════════════════════════════════════════════════════════════════
#  Forgetting Curve Projection
# ═══════════════════════════════════════════════════════════════════════════════

def project_forgetting_curve(
    initial_retention: float,
    decay_rate: float,
    projection_days: float,
    *,
    num_points: int = DEFAULT_CURVE_POINTS,
    threshold: float = DEFAULT_RETENTION_THRESHOLD,
    floor: float = DEFAULT_RETENTION_FLOOR,
) -> list[CurvePoint]:
    """
    Generate a sampled forgetting curve over the projection window.

    Returns `num_points` evenly-spaced points from day 0 to day projection_days,
    each with retention and forgetting probability.

    Used by analytics and visualisation consumers.
    """
    if num_points < 2:
        num_points = 2
    if projection_days <= 0:
        return [CurvePoint(day=0.0, retention=_clamp01(initial_retention), forgetting_probability=0.0)]

    step = projection_days / (num_points - 1)
    points = []
    for i in range(num_points):
        day = round(i * step, 2)
        r = compute_retention_at_time(initial_retention, decay_rate, day, floor=floor)
        fp = compute_forgetting_probability(initial_retention, decay_rate, day, threshold=threshold)
        points.append(CurvePoint(
            day=day,
            retention=round(r, 4),
            forgetting_probability=fp,
        ))
    return points


# ═══════════════════════════════════════════════════════════════════════════════
#  Master Computation — Single Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_decay(
    inp: DecayInput,
    *,
    threshold: float = DEFAULT_RETENTION_THRESHOLD,
    critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
    floor: float = DEFAULT_RETENTION_FLOOR,
    inactivity_onset: float = DEFAULT_INACTIVITY_ONSET_DAYS,
    inactivity_scale: float = DEFAULT_INACTIVITY_SCALE,
    curve_points: int = DEFAULT_CURVE_POINTS,
) -> DecayOutput:
    """
    Master forgetting analysis.

    Combines all decay functions into a complete analysis:
      1. Compute effective decay rate (with difficulty, reinforcement, inactivity)
      2. Predict retention at end of projection window
      3. Compute forgetting probability
      4. Calculate half-life and time-to-threshold
      5. Generate forgetting curve projection

    This is the ONLY function the service layer needs to call.
    """
    # ── 1. Effective decay rate ───────────────────────────────────────────────
    effective_rate = compute_effective_decay_rate(
        inp.current_decay_rate,
        inp.difficulty,
        inp.revision_count,
        inp.days_since_last_revision,
        inactivity_onset=inactivity_onset,
        inactivity_scale=inactivity_scale,
    )

    inactivity = compute_inactivity_penalty(
        inp.days_since_last_revision,
        onset=inactivity_onset,
        scale=inactivity_scale,
    )

    # ── 2. Predicted retention at end of window ───────────────────────────────
    predicted_retention = compute_retention_at_time(
        inp.current_retention, effective_rate, inp.projection_days, floor=floor,
    )
    predicted_drop = compute_predicted_retention_drop(
        inp.current_retention, effective_rate, inp.projection_days, floor=floor,
    )

    # ── 3. Forgetting probability (at current time) ───────────────────────────
    forgetting_prob = compute_forgetting_probability(
        inp.current_retention, effective_rate, inp.days_since_last_revision,
        threshold=threshold,
    )

    # ── 4. Time metrics ───────────────────────────────────────────────────────
    half_life = compute_half_life(effective_rate)
    time_to_thresh = compute_time_to_threshold(
        inp.current_retention, effective_rate, threshold=threshold, floor=floor,
    )

    # ── 5. Critical decay check ───────────────────────────────────────────────
    retention_at_window_end = predicted_retention
    is_critical = retention_at_window_end < critical_threshold

    # ── 6. Curve projection ───────────────────────────────────────────────────
    curve = project_forgetting_curve(
        inp.current_retention, effective_rate, inp.projection_days,
        num_points=curve_points, threshold=threshold, floor=floor,
    )

    return DecayOutput(
        effective_decay_rate=effective_rate,
        forgetting_probability=forgetting_prob,
        predicted_retention=round(predicted_retention, 4),
        predicted_retention_drop=predicted_drop,
        half_life_days=half_life,
        time_to_threshold_days=time_to_thresh,
        inactivity_penalty=round(inactivity, 6),
        is_critically_decayed=is_critical,
        curve=curve,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def _clamp01(value: float) -> float:
    """Clamp a value to the [0.0, 1.0] range."""
    return max(0.0, min(1.0, value))
