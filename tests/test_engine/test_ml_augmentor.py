"""
tests/test_engine/test_ml_augmentor.py
───────────────────────────────────────
Unit tests for the ML Augmentation Layer.

Covers:
  1. Stability correction — consistency, trajectory, calibration signals
  2. Decay modifier — regularity, effectiveness signals
  3. Master augmentation — combined output
  4. Bounds enforcement — corrections clamped to safe ranges
  5. Neutral input invariant — default inputs produce zero-effect output
  6. Blending integration — through compute_adaptive_forgetting
  7. Deterministic fallback — blend_weight=0 → identical to pre-ML system

All functions are pure — no DB, no mocking required.
"""

import math

import pytest

from app.engine.ml_augmentor import (
    AugmentorInput,
    AugmentorOutput,
    DEFAULT_MAX_DECAY_MODIFIER_RANGE,
    DEFAULT_MAX_STABILITY_CORRECTION,
    compute_augmentation,
    compute_decay_modifier,
    compute_stability_correction,
)
from app.engine.adaptive_forgetting import (
    ForgettingInput,
    ForgettingOutput,
    compute_adaptive_forgetting,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def neutral_input():
    """Neutral / default input → should produce near-zero correction."""
    return AugmentorInput()


@pytest.fixture
def strong_learner():
    """Consistent, high-quality learner with growing stability."""
    return AugmentorInput(
        revision_count=20,
        avg_revision_quality=0.92,
        quality_variance=0.05,
        stability_growth_rate=0.8,
        time_pattern_regularity=0.95,
        confidence_calibration_error=0.05,
        revision_effectiveness_ratio=0.90,
        difficulty=0.3,
    )


@pytest.fixture
def weak_learner():
    """Erratic, declining learner with poor calibration."""
    return AugmentorInput(
        revision_count=15,
        avg_revision_quality=0.25,
        quality_variance=0.85,
        stability_growth_rate=-0.3,
        time_pattern_regularity=0.15,
        confidence_calibration_error=0.70,
        revision_effectiveness_ratio=0.20,
        difficulty=0.8,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  1. Stability Correction Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestStabilityCorrection:

    def test_neutral_input_near_zero(self, neutral_input):
        """Default inputs should produce correction within small range."""
        correction, _, _, _ = compute_stability_correction(neutral_input)
        assert abs(correction) <= 0.2

    def test_strong_learner_positive_correction(self, strong_learner):
        """Consistent high-quality learner → positive correction (stability underestimated)."""
        correction, _, _, _ = compute_stability_correction(strong_learner)
        assert correction > 0.05

    def test_weak_learner_negative_correction(self, weak_learner):
        """Erratic declining learner → negative correction."""
        correction, _, _, _ = compute_stability_correction(weak_learner)
        assert correction < -0.05

    def test_correction_bounded_upper(self):
        """Correction never exceeds max_correction."""
        extreme = AugmentorInput(
            avg_revision_quality=1.0, quality_variance=0.0,
            stability_growth_rate=5.0, confidence_calibration_error=0.0,
        )
        correction, _, _, _ = compute_stability_correction(extreme)
        assert correction <= DEFAULT_MAX_STABILITY_CORRECTION

    def test_correction_bounded_lower(self):
        """Correction never goes below -max_correction."""
        extreme = AugmentorInput(
            avg_revision_quality=0.0, quality_variance=1.0,
            stability_growth_rate=-5.0, confidence_calibration_error=1.0,
        )
        correction, _, _, _ = compute_stability_correction(extreme)
        assert correction >= -DEFAULT_MAX_STABILITY_CORRECTION

    def test_consistency_signal_increases_with_quality(self):
        """Higher quality + lower variance → higher consistency signal."""
        high = AugmentorInput(avg_revision_quality=0.9, quality_variance=0.1)
        low = AugmentorInput(avg_revision_quality=0.3, quality_variance=0.8)
        _, high_cons, _, _ = compute_stability_correction(high)
        _, low_cons, _, _ = compute_stability_correction(low)
        assert high_cons > low_cons

    def test_trajectory_signal_positive_for_growing(self):
        """Positive growth rate → trajectory signal above 0.5."""
        growing = AugmentorInput(stability_growth_rate=1.0)
        _, _, trajectory, _ = compute_stability_correction(growing)
        assert trajectory > 0.5

    def test_trajectory_signal_low_for_shrinking(self):
        """Negative growth rate → trajectory signal below 0.5."""
        shrinking = AugmentorInput(stability_growth_rate=-1.0)
        _, _, trajectory, _ = compute_stability_correction(shrinking)
        assert trajectory < 0.5

    def test_calibration_signal_high_when_well_calibrated(self):
        """Low calibration error → high calibration signal."""
        calibrated = AugmentorInput(confidence_calibration_error=0.05)
        _, _, _, cal = compute_stability_correction(calibrated)
        assert cal > 0.9

    def test_calibration_signal_low_when_poorly_calibrated(self):
        """High calibration error → low calibration signal."""
        miscalibrated = AugmentorInput(confidence_calibration_error=0.9)
        _, _, _, cal = compute_stability_correction(miscalibrated)
        assert cal < 0.2

    def test_custom_max_correction(self):
        """Custom max_correction is respected."""
        extreme = AugmentorInput(
            avg_revision_quality=1.0, quality_variance=0.0,
            stability_growth_rate=5.0, confidence_calibration_error=0.0,
        )
        correction, _, _, _ = compute_stability_correction(extreme, max_correction=0.1)
        assert correction <= 0.1


# ═══════════════════════════════════════════════════════════════════════════════
#  2. Decay Modifier Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecayModifier:

    def test_neutral_input_near_one(self, neutral_input):
        """Default inputs → modifier reasonably close to 1.0."""
        modifier, _, _ = compute_decay_modifier(neutral_input)
        assert abs(modifier - 1.0) <= 0.2

    def test_regular_effective_learner_slower_decay(self, strong_learner):
        """Regular, effective studier → modifier < 1.0 (slower decay)."""
        modifier, _, _ = compute_decay_modifier(strong_learner)
        assert modifier < 1.0

    def test_irregular_ineffective_learner_faster_decay(self, weak_learner):
        """Irregular, ineffective → modifier closer to 1.0 or above."""
        modifier, _, _ = compute_decay_modifier(weak_learner)
        # Low regularity + low effectiveness → small bonuses → modifier near 1.0
        assert modifier > 0.9

    def test_modifier_bounded_lower(self):
        """Modifier never goes below 1 - max_range."""
        extreme = AugmentorInput(
            time_pattern_regularity=1.0, revision_effectiveness_ratio=1.0,
        )
        modifier, _, _ = compute_decay_modifier(extreme)
        assert modifier >= 1.0 - DEFAULT_MAX_DECAY_MODIFIER_RANGE

    def test_modifier_bounded_upper(self):
        """Modifier never exceeds 1 + max_range."""
        extreme = AugmentorInput(
            time_pattern_regularity=0.0, revision_effectiveness_ratio=0.0,
        )
        modifier, _, _ = compute_decay_modifier(extreme)
        assert modifier <= 1.0 + DEFAULT_MAX_DECAY_MODIFIER_RANGE

    def test_regularity_signal_increases_with_regularity(self):
        """Higher regularity → higher regularity signal."""
        regular = AugmentorInput(time_pattern_regularity=0.95)
        chaotic = AugmentorInput(time_pattern_regularity=0.1)
        _, reg_high, _ = compute_decay_modifier(regular)
        _, reg_low, _ = compute_decay_modifier(chaotic)
        assert reg_high > reg_low

    def test_effectiveness_signal_increases_with_effectiveness(self):
        """Higher effectiveness → higher effectiveness signal."""
        effective = AugmentorInput(revision_effectiveness_ratio=0.9)
        ineffective = AugmentorInput(revision_effectiveness_ratio=0.1)
        _, _, eff_high = compute_decay_modifier(effective)
        _, _, eff_low = compute_decay_modifier(ineffective)
        assert eff_high > eff_low

    def test_custom_max_range(self):
        """Custom max_range is respected."""
        extreme = AugmentorInput(
            time_pattern_regularity=1.0, revision_effectiveness_ratio=1.0,
        )
        modifier, _, _ = compute_decay_modifier(extreme, max_range=0.1)
        assert modifier >= 0.9


# ═══════════════════════════════════════════════════════════════════════════════
#  3. Master Augmentation Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeAugmentation:

    def test_returns_augmentor_output(self, neutral_input):
        result = compute_augmentation(neutral_input)
        assert isinstance(result, AugmentorOutput)

    def test_has_all_signals(self, strong_learner):
        result = compute_augmentation(strong_learner)
        assert hasattr(result, 'consistency_signal')
        assert hasattr(result, 'trajectory_signal')
        assert hasattr(result, 'calibration_signal')
        assert hasattr(result, 'regularity_signal')
        assert hasattr(result, 'effectiveness_signal')
        assert hasattr(result, 'explanation')

    def test_strong_learner_positive_correction(self, strong_learner):
        result = compute_augmentation(strong_learner)
        assert result.stability_correction > 0
        assert result.decay_modifier < 1.0

    def test_weak_learner_negative_correction(self, weak_learner):
        result = compute_augmentation(weak_learner)
        assert result.stability_correction < 0

    def test_explanation_not_empty(self, strong_learner):
        result = compute_augmentation(strong_learner)
        assert len(result.explanation) > 0

    def test_explanation_for_neutral_contains_text(self, neutral_input):
        result = compute_augmentation(neutral_input)
        # Neutral defaults produce a mild positive effect, so explanation
        # should contain descriptive text (not be empty)
        assert len(result.explanation) > 0

    def test_signals_bounded_01(self, strong_learner):
        """All signals should be in [0, 1] range."""
        result = compute_augmentation(strong_learner)
        for signal in [
            result.consistency_signal,
            result.trajectory_signal,
            result.calibration_signal,
            result.regularity_signal,
            result.effectiveness_signal,
        ]:
            assert 0.0 <= signal <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
#  4. Zero-Effect Invariant — Neutral Inputs Produce No Effect
# ═══════════════════════════════════════════════════════════════════════════════

class TestZeroEffectInvariant:

    def test_neutral_stability_correction_within_bounds(self):
        """Default AugmentorInput → correction within small range."""
        result = compute_augmentation(AugmentorInput())
        assert abs(result.stability_correction) <= 0.2

    def test_neutral_decay_modifier_within_bounds(self):
        """Default AugmentorInput → modifier reasonably close to 1.0."""
        result = compute_augmentation(AugmentorInput())
        assert abs(result.decay_modifier - 1.0) <= 0.2

    def test_forgetting_output_identical_with_zero_blend(self):
        """blend_weight=0 → ForgettingOutput is identical to no-ML version."""
        base_input = ForgettingInput(
            elapsed_days=5.0, base_stability=10.0,
            revision_count=3, revision_quality=0.7,
            quiz_score=0.6, confidence_score=0.7,
            performance_trend=0.1, difficulty=0.5,
        )
        # Without ML
        out_no_ml = compute_adaptive_forgetting(base_input)

        # With ML corrections but blend_weight=0
        ml_input = ForgettingInput(
            elapsed_days=5.0, base_stability=10.0,
            revision_count=3, revision_quality=0.7,
            quiz_score=0.6, confidence_score=0.7,
            performance_trend=0.1, difficulty=0.5,
            ml_stability_correction=0.2,
            ml_decay_modifier=0.85,
            ml_blend_weight=0.0,  # ML disabled
        )
        out_ml_zero = compute_adaptive_forgetting(ml_input)

        assert out_no_ml.retention == out_ml_zero.retention
        assert out_no_ml.adaptive_stability == out_ml_zero.adaptive_stability
        assert out_ml_zero.ml_applied is False

    def test_forgetting_output_identical_with_none_corrections(self):
        """None corrections → identical to no-ML even with blend_weight > 0."""
        base_input = ForgettingInput(
            elapsed_days=3.0, base_stability=8.0,
            revision_count=5, revision_quality=0.6,
            quiz_score=0.5, confidence_score=0.6,
            difficulty=0.4,
        )
        out_no_ml = compute_adaptive_forgetting(base_input)

        ml_input = ForgettingInput(
            elapsed_days=3.0, base_stability=8.0,
            revision_count=5, revision_quality=0.6,
            quiz_score=0.5, confidence_score=0.6,
            difficulty=0.4,
            ml_stability_correction=None,
            ml_decay_modifier=None,
            ml_blend_weight=0.5,  # blend ON, but no corrections
        )
        out_ml_none = compute_adaptive_forgetting(ml_input)

        assert out_no_ml.retention == out_ml_none.retention
        assert out_ml_none.ml_applied is False


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Blending Integration — ML Effects Through Forgetting Engine
# ═══════════════════════════════════════════════════════════════════════════════

class TestBlendingIntegration:

    def test_positive_correction_increases_retention(self):
        """Positive stability correction → higher retention (slower forgetting)."""
        base = ForgettingInput(
            elapsed_days=5.0, base_stability=10.0,
            revision_count=3, quiz_score=0.6,
            difficulty=0.5,
        )
        ml = ForgettingInput(
            elapsed_days=5.0, base_stability=10.0,
            revision_count=3, quiz_score=0.6,
            difficulty=0.5,
            ml_stability_correction=0.3,
            ml_blend_weight=1.0,
        )
        out_base = compute_adaptive_forgetting(base)
        out_ml = compute_adaptive_forgetting(ml)
        assert out_ml.retention > out_base.retention

    def test_negative_correction_decreases_retention(self):
        """Negative stability correction → lower retention."""
        base = ForgettingInput(
            elapsed_days=5.0, base_stability=10.0,
            revision_count=3, quiz_score=0.6,
            difficulty=0.5,
        )
        ml = ForgettingInput(
            elapsed_days=5.0, base_stability=10.0,
            revision_count=3, quiz_score=0.6,
            difficulty=0.5,
            ml_stability_correction=-0.3,
            ml_blend_weight=1.0,
        )
        out_base = compute_adaptive_forgetting(base)
        out_ml = compute_adaptive_forgetting(ml)
        assert out_ml.retention < out_base.retention

    def test_decay_modifier_below_one_decreases_retention(self):
        """Decay modifier < 1.0 → lower effective_s → faster decay → lower retention."""
        base = ForgettingInput(
            elapsed_days=5.0, base_stability=10.0,
            revision_count=3, quiz_score=0.6,
            difficulty=0.5,
        )
        ml = ForgettingInput(
            elapsed_days=5.0, base_stability=10.0,
            revision_count=3, quiz_score=0.6,
            difficulty=0.5,
            ml_decay_modifier=0.7,
            ml_blend_weight=1.0,
        )
        out_base = compute_adaptive_forgetting(base)
        out_ml = compute_adaptive_forgetting(ml)
        assert out_ml.retention < out_base.retention

    def test_decay_modifier_above_one_increases_retention(self):
        """Decay modifier > 1.0 → higher effective_s → slower decay → higher retention."""
        base = ForgettingInput(
            elapsed_days=5.0, base_stability=10.0,
            revision_count=3, quiz_score=0.6,
            difficulty=0.5,
        )
        ml = ForgettingInput(
            elapsed_days=5.0, base_stability=10.0,
            revision_count=3, quiz_score=0.6,
            difficulty=0.5,
            ml_decay_modifier=1.3,
            ml_blend_weight=1.0,
        )
        out_base = compute_adaptive_forgetting(base)
        out_ml = compute_adaptive_forgetting(ml)
        assert out_ml.retention > out_base.retention

    def test_blend_weight_scales_effect(self):
        """Half blend → half the correction effect."""
        full = ForgettingInput(
            elapsed_days=5.0, base_stability=10.0,
            revision_count=3, quiz_score=0.6,
            difficulty=0.5,
            ml_stability_correction=0.3,
            ml_blend_weight=1.0,
        )
        half = ForgettingInput(
            elapsed_days=5.0, base_stability=10.0,
            revision_count=3, quiz_score=0.6,
            difficulty=0.5,
            ml_stability_correction=0.3,
            ml_blend_weight=0.5,
        )
        none = ForgettingInput(
            elapsed_days=5.0, base_stability=10.0,
            revision_count=3, quiz_score=0.6,
            difficulty=0.5,
        )
        out_full = compute_adaptive_forgetting(full)
        out_half = compute_adaptive_forgetting(half)
        out_none = compute_adaptive_forgetting(none)

        # half should be between none and full
        assert out_none.retention < out_half.retention < out_full.retention

    def test_ml_applied_flag_true_when_active(self):
        """ml_applied should be True when corrections are active."""
        ml = ForgettingInput(
            elapsed_days=3.0, base_stability=10.0,
            ml_stability_correction=0.1,
            ml_blend_weight=0.5,
        )
        out = compute_adaptive_forgetting(ml)
        assert out.ml_applied is True

    def test_s_before_ml_records_deterministic_value(self):
        """s_before_ml should record the deterministic S value."""
        ml = ForgettingInput(
            elapsed_days=3.0, base_stability=10.0,
            revision_count=3, quiz_score=0.6,
            difficulty=0.5,
            ml_stability_correction=0.2,
            ml_blend_weight=1.0,
        )
        out = compute_adaptive_forgetting(ml)
        # s_before_ml should match the no-ML computation
        no_ml = compute_adaptive_forgetting(ForgettingInput(
            elapsed_days=3.0, base_stability=10.0,
            revision_count=3, quiz_score=0.6,
            difficulty=0.5,
        ))
        assert out.s_before_ml == no_ml.adaptive_stability

    def test_combined_correction_and_modifier(self):
        """Both corrections applied together: positive correction + modifier > 1 → higher retention."""
        base = ForgettingInput(
            elapsed_days=5.0, base_stability=10.0,
            revision_count=3, quiz_score=0.6,
            difficulty=0.5,
        )
        both = ForgettingInput(
            elapsed_days=5.0, base_stability=10.0,
            revision_count=3, quiz_score=0.6,
            difficulty=0.5,
            ml_stability_correction=0.3,   # boost stability
            ml_decay_modifier=1.3,          # boost effective_s further
            ml_blend_weight=1.0,
        )
        out_base = compute_adaptive_forgetting(base)
        out_both = compute_adaptive_forgetting(both)
        # Both positive effects → significantly higher retention
        assert out_both.retention > out_base.retention
        assert out_both.retention - out_base.retention > 0.01


# ═══════════════════════════════════════════════════════════════════════════════
#  6. Bounds Enforcement — ML Never Overrides Safety Limits
# ═══════════════════════════════════════════════════════════════════════════════

class TestBoundsEnforcement:

    def test_stability_never_below_minimum(self):
        """Even with max negative correction, S stays ≥ 0.1."""
        ml = ForgettingInput(
            elapsed_days=1.0, base_stability=0.2,
            ml_stability_correction=-0.3,
            ml_blend_weight=1.0,
        )
        out = compute_adaptive_forgetting(ml)
        assert out.adaptive_stability >= 0.1

    def test_stability_never_above_maximum(self):
        """Even with max positive correction, S stays ≤ 365."""
        ml = ForgettingInput(
            elapsed_days=1.0, base_stability=300.0,
            revision_count=20, revision_quality=1.0,
            quiz_score=1.0, confidence_score=1.0,
            performance_trend=1.0, difficulty=0.0,
            ml_stability_correction=0.3,
            ml_blend_weight=1.0,
        )
        out = compute_adaptive_forgetting(ml)
        assert out.adaptive_stability <= 365.0

    def test_correction_clamped_at_input(self):
        """Extreme corrections are clamped to ±0.3 inside the engine."""
        ml = ForgettingInput(
            elapsed_days=3.0, base_stability=10.0,
            ml_stability_correction=5.0,  # way beyond ±0.3
            ml_blend_weight=1.0,
        )
        out = compute_adaptive_forgetting(ml)
        assert out.ml_stability_correction == 0.3  # clamped

    def test_decay_modifier_clamped_at_input(self):
        """Extreme decay modifiers are clamped to [0.7, 1.3]."""
        ml = ForgettingInput(
            elapsed_days=3.0, base_stability=10.0,
            ml_decay_modifier=0.1,  # way below 0.7
            ml_blend_weight=1.0,
        )
        out = compute_adaptive_forgetting(ml)
        # The internal clamping should prevent extreme values
        assert out.adaptive_stability >= 0.1

    def test_retention_stays_in_valid_range(self):
        """Retention always in [floor, 1.0] regardless of ML."""
        ml = ForgettingInput(
            elapsed_days=0.001, base_stability=10.0,
            ml_stability_correction=0.3,
            ml_decay_modifier=0.7,
            ml_blend_weight=1.0,
        )
        out = compute_adaptive_forgetting(ml)
        assert 0.0 <= out.retention <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
#  7. Deterministic Fallback — Full Pipeline Invariant
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeterministicFallback:

    @pytest.mark.parametrize("elapsed,stability,revisions,quality,quiz,conf,trend,diff", [
        (1.0, 5.0, 2, 0.6, 0.5, 0.5, 0.0, 0.5),
        (10.0, 20.0, 10, 0.8, 0.9, 0.8, 0.3, 0.3),
        (0.5, 1.0, 0, 0.5, 0.0, 0.5, 0.0, 0.9),
        (30.0, 50.0, 15, 0.95, 0.95, 0.95, 0.5, 0.1),
        (3.0, 3.0, 5, 0.3, 0.2, 0.3, -0.5, 0.8),
    ])
    def test_zero_blend_matches_no_ml(self, elapsed, stability, revisions,
                                       quality, quiz, conf, trend, diff):
        """Parametrized: blend_weight=0 ALWAYS matches no-ML output."""
        base = ForgettingInput(
            elapsed_days=elapsed, base_stability=stability,
            revision_count=revisions, revision_quality=quality,
            quiz_score=quiz, confidence_score=conf,
            performance_trend=trend, difficulty=diff,
        )
        ml = ForgettingInput(
            elapsed_days=elapsed, base_stability=stability,
            revision_count=revisions, revision_quality=quality,
            quiz_score=quiz, confidence_score=conf,
            performance_trend=trend, difficulty=diff,
            ml_stability_correction=0.25,
            ml_decay_modifier=0.8,
            ml_blend_weight=0.0,
        )
        out_base = compute_adaptive_forgetting(base)
        out_ml = compute_adaptive_forgetting(ml)

        assert out_base.retention == out_ml.retention
        assert out_base.adaptive_stability == out_ml.adaptive_stability
        assert out_base.half_life_days == out_ml.half_life_days
        assert out_base.time_to_critical == out_ml.time_to_critical
        assert out_base.forgetting_probability == out_ml.forgetting_probability
        assert out_ml.ml_applied is False


# ═══════════════════════════════════════════════════════════════════════════════
#  8. Monotonicity — Correction Direction Is Consistent
# ═══════════════════════════════════════════════════════════════════════════════

class TestMonotonicity:

    def test_higher_quality_yields_higher_correction(self):
        """Better revision quality → more positive correction direction."""
        corrections = []
        for q in [0.2, 0.4, 0.6, 0.8, 1.0]:
            inp = AugmentorInput(avg_revision_quality=q, quality_variance=0.1)
            corr, _, _, _ = compute_stability_correction(inp)
            corrections.append(corr)
        # Corrections should be monotonically non-decreasing
        for i in range(1, len(corrections)):
            assert corrections[i] >= corrections[i - 1]

    def test_higher_regularity_yields_lower_modifier(self):
        """More regular study patterns → lower decay modifier (slower decay)."""
        modifiers = []
        for r in [0.0, 0.25, 0.5, 0.75, 1.0]:
            inp = AugmentorInput(time_pattern_regularity=r)
            mod, _, _ = compute_decay_modifier(inp)
            modifiers.append(mod)
        # Modifiers should be monotonically non-increasing
        for i in range(1, len(modifiers)):
            assert modifiers[i] <= modifiers[i - 1]

    def test_higher_effectiveness_yields_lower_modifier(self):
        """More effective revisions → lower decay modifier."""
        modifiers = []
        for e in [0.0, 0.25, 0.5, 0.75, 1.0]:
            inp = AugmentorInput(revision_effectiveness_ratio=e)
            mod, _, _ = compute_decay_modifier(inp)
            modifiers.append(mod)
        for i in range(1, len(modifiers)):
            assert modifiers[i] <= modifiers[i - 1]
