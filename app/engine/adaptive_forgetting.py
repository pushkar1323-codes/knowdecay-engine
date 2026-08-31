"""
app/engine/adaptive_forgetting.py
───────────────────────────────────
Adaptive Forgetting Curve Engine.

This is the COGNITIVE FOUNDATION of KnowDecay — the Ebbinghaus forgetting
curve with dynamic memory stability.

Core Formula
════════════
  R(t) = e^(−t / S_adaptive)

Where:
  R(t)       = retention estimate at elapsed time t
  t          = days since last meaningful revision
  S_adaptive = adaptive memory stability (from stability_engine)

This module does NOT use a fixed forgetting rate. Instead, S_adaptive
is computed dynamically by the stability engine using learner behavior,
quiz performance, confidence, difficulty, and reinforcement patterns.

Integration Architecture
════════════════════════
  stability_engine → S_adaptive
  adaptive_forgetting → R(t) = e^(−t/S)
  recalibration_engine → uses both for state evolution
  scheduling_engine → consumes R(t) for next_revision_at

Design principles:
  • All functions are PURE — no DB, no I/O
  • The forgetting curve is a continuous mathematical model
  • Retention is always in [floor, 1.0]
  • Every function accepts explicit parameters — no globals
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.engine.stability_engine import (
    StabilityInput,
    StabilityOutput,
    StabilityEvolution,
    compute_adaptive_stability,
    evolve_stability,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Data Transfer Objects
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class ForgettingInput:
    """All inputs for adaptive forgetting curve computation."""

    # Time context
    elapsed_days: float = 0.0           # t — days since last revision

    # Stability inputs (forwarded to stability_engine)
    base_stability: float = 1.0
    revision_count: int = 0
    revision_quality: float = 0.5
    quiz_score: float = 0.0
    confidence_score: float = 0.5
    performance_trend: float = 0.0
    difficulty: float = 0.5

    # ML augmentation (optional — None = pure deterministic)
    ml_stability_correction: float | None = None    # from ml_augmentor
    ml_decay_modifier: float | None = None          # from ml_augmentor
    ml_blend_weight: float = 0.0                    # 0.0 = deterministic only


@dataclass(frozen=True, slots=True)
class ForgettingOutput:
    """Complete adaptive forgetting analysis."""

    # Core output
    retention: float                    # R(t) — current retention estimate
    adaptive_stability: float           # S_adaptive used in the computation
    forgetting_probability: float       # 1 − R(t)

    # Time metrics
    half_life_days: float               # days until R drops to 50%
    time_to_critical: float             # days until R drops to critical threshold (0.3)
    days_until_target: float            # days until R drops to revision threshold (0.7)

    # Stability breakdown (from stability_engine)
    stability_breakdown: StabilityOutput

    # Curve projection (multiple time points)
    curve: list[CurvePoint] = field(default_factory=list)

    # ML augmentation metadata (for audit / explainability)
    ml_applied: bool = False
    ml_stability_correction: float = 0.0
    ml_decay_modifier: float = 1.0
    s_before_ml: float = 0.0            # S_deterministic before ML blending


@dataclass(frozen=True, slots=True)
class CurvePoint:
    """A point on the adaptive forgetting curve."""

    day: float
    retention: float
    forgetting_probability: float


# ═══════════════════════════════════════════════════════════════════════════════
#  Default Parameters
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_RETENTION_FLOOR: float = 0.02       # retention never reaches true zero
DEFAULT_REVISION_THRESHOLD: float = 0.7     # below this → schedule revision
DEFAULT_CRITICAL_THRESHOLD: float = 0.3     # below this → urgent revision
DEFAULT_CURVE_POINTS: int = 10              # number of projection points


# ═══════════════════════════════════════════════════════════════════════════════
#  Core Forgetting Curve Functions
# ═══════════════════════════════════════════════════════════════════════════════

def compute_retention(
    elapsed_days: float,
    adaptive_stability: float,
    *,
    floor: float = DEFAULT_RETENTION_FLOOR,
) -> float:
    """
    Core Ebbinghaus forgetting curve with adaptive stability.

    Formula:
        R(t) = max(e^(−t / S), floor)

    Properties:
        t=0  → R = 1.0 (perfect recall immediately after learning)
        t→∞  → R → floor (approaches but never reaches zero)
        Higher S → slower decay (better memory stability)
    """
    if elapsed_days <= 0:
        return 1.0
    if adaptive_stability <= 0:
        return floor

    r = math.exp(-elapsed_days / adaptive_stability)
    return max(r, floor)


def compute_half_life(
    adaptive_stability: float,
) -> float:
    """
    Time until retention drops to 50%.

    From R(t) = e^(−t/S), solving for R = 0.5:
        0.5 = e^(−t/S)
        t = S × ln(2)
    """
    return round(max(adaptive_stability, 0.1) * math.log(2), 4)


def compute_time_to_threshold(
    adaptive_stability: float,
    threshold: float = DEFAULT_REVISION_THRESHOLD,
    *,
    floor: float = DEFAULT_RETENTION_FLOOR,
) -> float:
    """
    Days until retention drops to a specific threshold.

    From R(t) = e^(−t/S):
        t = −S × ln(threshold)
    """
    threshold = max(threshold, floor + 0.01)
    if threshold >= 1.0:
        return 0.0
    return round(max(adaptive_stability, 0.1) * (-math.log(threshold)), 4)


def project_curve(
    adaptive_stability: float,
    projection_days: float = 30.0,
    *,
    num_points: int = DEFAULT_CURVE_POINTS,
    floor: float = DEFAULT_RETENTION_FLOOR,
) -> list[CurvePoint]:
    """
    Project the forgetting curve into the future.

    Returns evenly-spaced sample points from day 0 to projection_days.
    """
    if num_points < 2:
        num_points = 2

    points: list[CurvePoint] = []
    for i in range(num_points):
        day = (projection_days * i) / (num_points - 1)
        r = compute_retention(day, adaptive_stability, floor=floor)
        points.append(CurvePoint(
            day=round(day, 2),
            retention=round(r, 4),
            forgetting_probability=round(1.0 - r, 4),
        ))
    return points


# ═══════════════════════════════════════════════════════════════════════════════
#  Master Computation — Full Adaptive Forgetting Analysis
# ═══════════════════════════════════════════════════════════════════════════════

def compute_adaptive_forgetting(
    inp: ForgettingInput,
    *,
    floor: float = DEFAULT_RETENTION_FLOOR,
    revision_threshold: float = DEFAULT_REVISION_THRESHOLD,
    critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
    curve_points: int = DEFAULT_CURVE_POINTS,
    projection_days: float = 30.0,
) -> ForgettingOutput:
    """
    Master function: compute adaptive forgetting for a single user × topic.

    Steps:
      1. Compute S_adaptive from learner state (via stability_engine)
      2. Compute R(t) = e^(−t / S_adaptive)
      3. Derive half-life, time-to-critical, time-to-revision
      4. Project the forgetting curve

    This is the ONLY function the service layer needs for full analysis.
    """
    # ── 1. Compute adaptive stability (DETERMINISTIC — never modified) ────────
    stab_input = StabilityInput(
        base_stability=inp.base_stability,
        revision_count=inp.revision_count,
        revision_quality=inp.revision_quality,
        quiz_score=inp.quiz_score,
        confidence_score=inp.confidence_score,
        performance_trend=inp.performance_trend,
        difficulty=inp.difficulty,
    )
    stab_out = compute_adaptive_stability(stab_input)
    s = stab_out.adaptive_stability
    s_before_ml = s

    # ── 1b. ML augmentation (optional — blend weight gates all ML effects) ───
    ml_applied = False
    ml_corr_used = 0.0
    ml_decay_used = 1.0

    if inp.ml_blend_weight > 0:
        # Stability correction: S_aug = S_det × (1 + α × correction)
        if inp.ml_stability_correction is not None:
            corr = max(-0.3, min(0.3, inp.ml_stability_correction))
            s = s * (1.0 + inp.ml_blend_weight * corr)
            s = max(min(s, 365.0), 0.1)  # enforce global bounds
            ml_corr_used = round(corr, 4)
            ml_applied = True

        # Decay modifier: applied to effective stability for R(t) only
        if inp.ml_decay_modifier is not None:
            dm = max(0.7, min(1.3, inp.ml_decay_modifier))
            ml_decay_used = round(1.0 + inp.ml_blend_weight * (dm - 1.0), 4)
            ml_applied = True

    # ── 2. Core forgetting curve ──────────────────────────────────────────────
    effective_s = s * ml_decay_used   # decay modifier only affects R(t)
    retention = compute_retention(inp.elapsed_days, effective_s, floor=floor)
    fp = round(1.0 - retention, 4)

    # ── 3. Time metrics (use effective stability for consistency) ─────────────
    half_life = compute_half_life(effective_s)
    time_critical = compute_time_to_threshold(effective_s, critical_threshold, floor=floor)
    time_target = compute_time_to_threshold(effective_s, revision_threshold, floor=floor)

    # ── 4. Curve projection ───────────────────────────────────────────────────
    curve = project_curve(effective_s, projection_days, num_points=curve_points, floor=floor)

    return ForgettingOutput(
        retention=round(retention, 4),
        adaptive_stability=round(effective_s, 4),
        forgetting_probability=fp,
        half_life_days=half_life,
        time_to_critical=time_critical,
        days_until_target=time_target,
        stability_breakdown=stab_out,
        curve=curve,
        ml_applied=ml_applied,
        ml_stability_correction=ml_corr_used,
        ml_decay_modifier=ml_decay_used,
        s_before_ml=round(s_before_ml, 4),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Retention Estimation — For Recalibration Integration
# ═══════════════════════════════════════════════════════════════════════════════

def estimate_retention_after_event(
    current_retention: float,
    adaptive_stability: float,
    event_quality: float,
    elapsed_days: float,
    *,
    floor: float = DEFAULT_RETENTION_FLOOR,
) -> float:
    """
    Estimate new retention after a learning event.

    The event partially "resets" the forgetting clock:
      1. Compute how much was forgotten: R_decayed = e^(−t/S)
      2. The event quality lifts retention: R_new = R_decayed + boost
      3. boost = event_quality × (1 − R_decayed) × 0.5

    This models the observation that studying a nearly-forgotten topic
    provides a bigger boost than re-studying a well-remembered one.
    """
    r_decayed = compute_retention(elapsed_days, adaptive_stability, floor=floor)
    gap = 1.0 - r_decayed
    quality = max(0.0, min(1.0, event_quality))
    boost = quality * gap * 0.5
    r_new = min(r_decayed + boost, 1.0)
    return round(max(r_new, floor), 4)


def compute_optimal_revision_time(
    adaptive_stability: float,
    target_retention: float = DEFAULT_REVISION_THRESHOLD,
) -> float:
    """
    When should the learner next revise to stay above target retention?

    From R(t) = e^(−t/S) = target:
        t = −S × ln(target)
    """
    if target_retention <= 0 or target_retention >= 1.0:
        return 0.0
    return round(max(adaptive_stability * (-math.log(target_retention)), 0.0), 4)
