"""
app/engine/ml_augmentor.py
────────────────────────────
ML Augmentation Engine — PURE FUNCTIONS, NO DB, NO I/O.

Provides optional correction signals that AUGMENT the deterministic
adaptive stability estimation and personalise decay behaviour.

Architecture
════════════
  stability_engine → S_deterministic          (foundational, unchanged)
  ml_augmentor     → correction + modifier    (THIS MODULE — augmentation)
  adaptive_forgetting → S_augmented = S_det × (1 + α × correction)
                        R(t) = e^(−t / (S_augmented × decay_mod))

Design Invariant
════════════════
  When blend_weight = 0  OR  all inputs are neutral:
    correction → 0.0
    modifier   → 1.0
    → system behaves IDENTICALLY to pure deterministic engine

  ML NEVER replaces the deterministic engine.  It only tunes its output.

Correction Bounds
═════════════════
  stability_correction ∈ [−MAX_CORRECTION, +MAX_CORRECTION]   (default ±0.3)
  decay_modifier       ∈ [1−MAX_DECAY_RANGE, 1+MAX_DECAY_RANGE] (default 0.7–1.3)

Feature Engineering
═══════════════════
  The augmentor uses hand-crafted feature signals derived from the learner's
  accumulated state.  This is a lightweight heuristic model that can later
  be swapped for a trained model behind the same interface.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════════════════════
#  Default Parameters
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_MAX_STABILITY_CORRECTION: float = 0.3   # ±30% max
DEFAULT_MAX_DECAY_MODIFIER_RANGE: float = 0.3   # 0.7–1.3

# Component weights for stability correction
_W_CONSISTENCY: float = 0.40
_W_TRAJECTORY: float = 0.30
_W_CALIBRATION: float = 0.30

# Component weights for decay modifier
_W_REGULARITY: float = 0.15
_W_EFFECTIVENESS: float = 0.15


# ═══════════════════════════════════════════════════════════════════════════════
#  Data Transfer Objects
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class AugmentorInput:
    """
    Feature vector for ML augmentation.

    These features are derived from the learner's accumulated MemoryState
    by the service layer.  The augmentor engine never touches the DB.
    """

    # ── Revision consistency features ─────────────────────────────────────
    revision_count: int = 0
    avg_revision_quality: float = 0.5       # running mean of event quality
    quality_variance: float = 0.0           # variance in quality (0 = perfectly consistent)

    # ── Stability trajectory ──────────────────────────────────────────────
    stability_growth_rate: float = 0.0      # avg base_stability growth per event
    #   positive = stability is growing steadily
    #   zero     = stable
    #   negative = stability is shrinking despite events

    # ── Temporal regularity ───────────────────────────────────────────────
    time_pattern_regularity: float = 0.5    # 0 = chaotic intervals, 1 = perfectly regular
    #   Computed from the coefficient of variation of inter-revision gaps.

    # ── Performance calibration ───────────────────────────────────────────
    confidence_calibration_error: float = 0.0
    #   |confidence − actual_performance|  averaged over time
    #   0 = perfectly calibrated
    #   high = overconfident or underconfident

    # ── Revision effectiveness ────────────────────────────────────────────
    revision_effectiveness_ratio: float = 0.5
    #   fraction of revisions that actually improved retention
    #   1.0 = every revision was effective
    #   0.0 = revisions not helping

    # ── Topic properties ──────────────────────────────────────────────────
    difficulty: float = 0.5


@dataclass(frozen=True, slots=True)
class AugmentorOutput:
    """
    ML augmentation signals.

    These are passed into ForgettingInput for blending with the deterministic
    stability computation.
    """

    stability_correction: float     # ∈ [−max, +max], multiplicative adjustment
    decay_modifier: float           # ∈ [1−range, 1+range], decay rate scaling

    # Explainability — what drove the correction
    consistency_signal: float       # contribution from revision consistency
    trajectory_signal: float        # contribution from stability growth trajectory
    calibration_signal: float       # contribution from confidence calibration
    regularity_signal: float        # contribution from temporal regularity
    effectiveness_signal: float     # contribution from revision effectiveness

    explanation: str                # human-readable reasoning


# ═══════════════════════════════════════════════════════════════════════════════
#  Stability Correction — Feature-Engineered
# ═══════════════════════════════════════════════════════════════════════════════

def compute_stability_correction(
    inp: AugmentorInput,
    *,
    max_correction: float = DEFAULT_MAX_STABILITY_CORRECTION,
) -> tuple[float, float, float, float]:
    """
    Compute a stability correction factor from learner features.

    Positive correction → stability is likely underestimated
      (consistent, high-quality learner deserves more credit)
    Negative correction → stability is likely overestimated
      (erratic, declining learner needs more conservative estimates)

    Components:
      consistency_signal  = (1 − quality_variance) × avg_quality
        → High quality + low variance = learner is reliably strong

      trajectory_signal   = tanh(growth_rate × 2)
        → Normalises growth rate to (−1, +1) using tanh

      calibration_signal  = −confidence_calibration_error
        → Lower error = better signal; error is penalised

    Formula:
      raw = W_c × consistency + W_t × trajectory + W_l × calibration
      correction = clamp(raw − 0.5, −max, +max)
        (centred at 0.5 so neutral inputs → 0 correction)

    Returns: (correction, consistency_signal, trajectory_signal, calibration_signal)
    """
    # ── Consistency signal ────────────────────────────────────────────────
    # Low variance + high quality → strong positive signal
    variance = _clamp01(inp.quality_variance)
    quality = _clamp01(inp.avg_revision_quality)
    consistency = (1.0 - variance) * quality

    # ── Trajectory signal ─────────────────────────────────────────────────
    # Map growth rate to (−1, +1) via tanh, then normalise to (0, 1)
    trajectory = (math.tanh(inp.stability_growth_rate * 2.0) + 1.0) / 2.0

    # ── Calibration signal ────────────────────────────────────────────────
    # Low error → signal near 1.0; high error → signal near 0.0
    cal_error = _clamp01(abs(inp.confidence_calibration_error))
    calibration = 1.0 - cal_error

    # ── Combine ───────────────────────────────────────────────────────────
    raw = _W_CONSISTENCY * consistency + _W_TRAJECTORY * trajectory + _W_CALIBRATION * calibration
    # Centre at 0 so that neutral inputs (raw ≈ 0.5) → correction ≈ 0
    correction = _clamp(raw - 0.5, -max_correction, max_correction)

    return (
        round(correction, 4),
        round(consistency, 4),
        round(trajectory, 4),
        round(calibration, 4),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Decay Modifier — Personalised Decay Rate
# ═══════════════════════════════════════════════════════════════════════════════

def compute_decay_modifier(
    inp: AugmentorInput,
    *,
    max_range: float = DEFAULT_MAX_DECAY_MODIFIER_RANGE,
) -> tuple[float, float, float]:
    """
    Compute a personalised decay rate modifier.

    modifier < 1.0 → learner forgets SLOWER than average
      (regular study patterns, revisions are effective)
    modifier > 1.0 → learner forgets FASTER than average
      (irregular, revisions aren't sticking)

    Components:
      regularity_bonus     = W_r × time_pattern_regularity
        → Regular studiers decay slower

      effectiveness_bonus  = W_e × revision_effectiveness_ratio
        → Effective revisers decay slower

    Formula:
      modifier = clamp(1.0 − regularity_bonus − effectiveness_bonus, 1−max, 1+max)

    Returns: (modifier, regularity_signal, effectiveness_signal)
    """
    regularity = _clamp01(inp.time_pattern_regularity)
    effectiveness = _clamp01(inp.revision_effectiveness_ratio)

    reg_bonus = _W_REGULARITY * regularity
    eff_bonus = _W_EFFECTIVENESS * effectiveness

    # Subtract bonuses from 1.0 → lower modifier for good learners
    raw_mod = 1.0 - reg_bonus - eff_bonus
    modifier = _clamp(raw_mod, 1.0 - max_range, 1.0 + max_range)

    return (
        round(modifier, 4),
        round(regularity, 4),
        round(effectiveness, 4),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Master Function
# ═══════════════════════════════════════════════════════════════════════════════

def compute_augmentation(
    inp: AugmentorInput,
    *,
    max_correction: float = DEFAULT_MAX_STABILITY_CORRECTION,
    max_decay_range: float = DEFAULT_MAX_DECAY_MODIFIER_RANGE,
) -> AugmentorOutput:
    """
    Master ML augmentation computation.

    Produces both a stability correction and a decay modifier from the
    learner's accumulated behavioural features.

    Design guarantee: when all inputs are at their neutral defaults,
    correction ≈ 0.0 and modifier ≈ 1.0 (no augmentation effect).
    """
    correction, consistency, trajectory, calibration = compute_stability_correction(
        inp, max_correction=max_correction,
    )
    modifier, regularity, effectiveness = compute_decay_modifier(
        inp, max_range=max_decay_range,
    )

    # ── Explanation ───────────────────────────────────────────────────────
    parts = []
    if correction > 0.05:
        parts.append(f"stability boosted +{correction:.0%} (consistent, growing)")
    elif correction < -0.05:
        parts.append(f"stability reduced {correction:.0%} (erratic or declining)")
    else:
        parts.append("stability correction negligible")

    if modifier < 0.95:
        parts.append(f"decay slowed to {modifier:.0%} (regular, effective reviser)")
    elif modifier > 1.05:
        parts.append(f"decay increased to {modifier:.0%} (irregular, low effectiveness)")
    else:
        parts.append("decay modifier neutral")

    return AugmentorOutput(
        stability_correction=correction,
        decay_modifier=modifier,
        consistency_signal=consistency,
        trajectory_signal=trajectory,
        calibration_signal=calibration,
        regularity_signal=regularity,
        effectiveness_signal=effectiveness,
        explanation="; ".join(parts),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
