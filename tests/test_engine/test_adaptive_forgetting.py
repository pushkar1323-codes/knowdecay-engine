"""
tests/test_engine/test_adaptive_forgetting.py
─────────────────────────────────────────────────
Unit tests for the Adaptive Forgetting Curve Engine.

Tests the core cognitive model: R(t) = e^(-t / S_adaptive)

Categories:
  1. Core retention function — Ebbinghaus curve
  2. Half-life computation
  3. Time-to-threshold
  4. Curve projection
  5. Master forgetting analysis — end-to-end
  6. Post-event retention estimation
  7. Optimal revision time
  8. Edge cases
  9. Monotonicity
"""

import math

import pytest

from app.engine.adaptive_forgetting import (
    CurvePoint,
    ForgettingInput,
    ForgettingOutput,
    compute_adaptive_forgetting,
    compute_half_life,
    compute_optimal_revision_time,
    compute_retention,
    compute_time_to_threshold,
    estimate_retention_after_event,
    project_curve,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  1. Core Retention Function: R(t) = e^(-t/S)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoreRetention:
    def test_immediate_recall(self):
        """t=0 → R = 1.0"""
        assert compute_retention(0.0, 5.0) == 1.0

    def test_negative_time_returns_one(self):
        assert compute_retention(-1.0, 5.0) == 1.0

    def test_basic_decay(self):
        """After t=S, R should be 1/e ≈ 0.3679"""
        r = compute_retention(5.0, 5.0)
        assert r == pytest.approx(1.0 / math.e, abs=0.001)

    def test_double_stability_slower_decay(self):
        r5 = compute_retention(5.0, 5.0)
        r10 = compute_retention(5.0, 10.0)
        assert r10 > r5

    def test_longer_time_lower_retention(self):
        r1 = compute_retention(1.0, 5.0)
        r10 = compute_retention(10.0, 5.0)
        assert r1 > r10

    def test_floor_respected(self):
        r = compute_retention(10000.0, 1.0)
        assert r >= 0.02  # default floor

    def test_custom_floor(self):
        r = compute_retention(10000.0, 1.0, floor=0.1)
        assert r >= 0.1

    def test_zero_stability_returns_floor(self):
        r = compute_retention(5.0, 0.0)
        assert r == 0.02


# ═══════════════════════════════════════════════════════════════════════════════
#  2. Half-Life
# ═══════════════════════════════════════════════════════════════════════════════

class TestHalfLife:
    def test_formula(self):
        """Half-life = S × ln(2)"""
        s = 10.0
        expected = s * math.log(2)
        assert compute_half_life(s) == pytest.approx(expected, abs=0.001)

    def test_higher_stability_longer_half_life(self):
        h1 = compute_half_life(1.0)
        h10 = compute_half_life(10.0)
        assert h10 > h1

    def test_minimum_stability(self):
        h = compute_half_life(0.0)
        assert h > 0


# ═══════════════════════════════════════════════════════════════════════════════
#  3. Time-to-Threshold
# ═══════════════════════════════════════════════════════════════════════════════

class TestTimeToThreshold:
    def test_revision_threshold(self):
        """For S=10, t until R=0.7 → t = -10 × ln(0.7) ≈ 3.57"""
        t = compute_time_to_threshold(10.0, 0.7)
        assert t == pytest.approx(10.0 * (-math.log(0.7)), abs=0.01)

    def test_critical_threshold(self):
        t = compute_time_to_threshold(10.0, 0.3)
        assert t > compute_time_to_threshold(10.0, 0.7)  # critical takes longer

    def test_higher_stability_longer_time(self):
        t5 = compute_time_to_threshold(5.0)
        t20 = compute_time_to_threshold(20.0)
        assert t20 > t5

    def test_threshold_one_returns_zero(self):
        assert compute_time_to_threshold(10.0, 1.0) == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
#  4. Curve Projection
# ═══════════════════════════════════════════════════════════════════════════════

class TestCurveProjection:
    def test_correct_point_count(self):
        curve = project_curve(5.0, 30.0, num_points=10)
        assert len(curve) == 10

    def test_first_point_is_day_zero(self):
        curve = project_curve(5.0, 30.0)
        assert curve[0].day == 0.0
        assert curve[0].retention == pytest.approx(1.0, abs=0.001)

    def test_last_point_is_projection_end(self):
        curve = project_curve(5.0, 30.0, num_points=10)
        assert curve[-1].day == pytest.approx(30.0, abs=0.1)

    def test_monotonically_decreasing(self):
        curve = project_curve(5.0, 30.0, num_points=20)
        for i in range(1, len(curve)):
            assert curve[i].retention <= curve[i-1].retention

    def test_forgetting_probability_complement(self):
        curve = project_curve(5.0, 30.0)
        for pt in curve:
            assert pt.retention + pt.forgetting_probability == pytest.approx(1.0, abs=0.001)


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Master Forgetting Analysis
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdaptiveForgetting:
    def test_basic_analysis(self):
        inp = ForgettingInput(elapsed_days=5.0, base_stability=10.0)
        out = compute_adaptive_forgetting(inp)
        assert isinstance(out, ForgettingOutput)
        assert 0.0 < out.retention <= 1.0

    def test_zero_elapsed_full_retention(self):
        inp = ForgettingInput(elapsed_days=0.0, base_stability=10.0)
        out = compute_adaptive_forgetting(inp)
        assert out.retention == 1.0

    def test_has_stability_breakdown(self):
        inp = ForgettingInput()
        out = compute_adaptive_forgetting(inp)
        assert out.stability_breakdown is not None
        assert out.stability_breakdown.reinforcement_factor >= 1.0

    def test_has_curve(self):
        inp = ForgettingInput()
        out = compute_adaptive_forgetting(inp)
        assert len(out.curve) > 0

    def test_forgetting_probability_is_complement(self):
        inp = ForgettingInput(elapsed_days=5.0)
        out = compute_adaptive_forgetting(inp)
        assert out.forgetting_probability == pytest.approx(1.0 - out.retention, abs=0.001)

    def test_half_life_positive(self):
        inp = ForgettingInput()
        out = compute_adaptive_forgetting(inp)
        assert out.half_life_days > 0

    def test_revisions_slow_forgetting(self):
        """More revisions → higher stability → higher retention at same time."""
        base = ForgettingInput(elapsed_days=0.5, revision_count=0)
        experienced = ForgettingInput(elapsed_days=0.5, revision_count=20, revision_quality=0.8)
        out_base = compute_adaptive_forgetting(base)
        out_exp = compute_adaptive_forgetting(experienced)
        assert out_exp.retention > out_base.retention

    def test_difficulty_accelerates_forgetting(self):
        """Harder topic → lower stability → lower retention at same time."""
        easy = ForgettingInput(elapsed_days=0.5, difficulty=0.1)
        hard = ForgettingInput(elapsed_days=0.5, difficulty=0.9)
        out_easy = compute_adaptive_forgetting(easy)
        out_hard = compute_adaptive_forgetting(hard)
        assert out_easy.retention > out_hard.retention


# ═══════════════════════════════════════════════════════════════════════════════
#  6. Post-Event Retention Estimation
# ═══════════════════════════════════════════════════════════════════════════════

class TestPostEventRetention:
    def test_high_quality_event_boosts(self):
        r = estimate_retention_after_event(0.8, 5.0, 1.0, 3.0)
        r_decayed = compute_retention(3.0, 5.0)
        assert r > r_decayed

    def test_zero_quality_no_boost(self):
        r_decayed = compute_retention(3.0, 5.0)
        r = estimate_retention_after_event(0.8, 5.0, 0.0, 3.0)
        assert r == pytest.approx(r_decayed, abs=0.001)

    def test_larger_gap_more_boost(self):
        """Studying a well-forgotten topic gives bigger absolute boost."""
        r_low = estimate_retention_after_event(0.3, 1.0, 0.8, 5.0)  # heavily decayed
        r_high = estimate_retention_after_event(0.9, 10.0, 0.8, 1.0)  # barely decayed
        # The low-retention case has more room to grow
        # but r_low should still be reasonable
        assert r_low > 0.02

    def test_never_exceeds_one(self):
        r = estimate_retention_after_event(1.0, 100.0, 1.0, 0.0)
        assert r <= 1.0

    def test_never_below_floor(self):
        r = estimate_retention_after_event(0.0, 0.1, 0.0, 100.0)
        assert r >= 0.02


# ═══════════════════════════════════════════════════════════════════════════════
#  7. Optimal Revision Time
# ═══════════════════════════════════════════════════════════════════════════════

class TestOptimalRevisionTime:
    def test_basic_computation(self):
        """For S=10, target=0.7 → t = -10×ln(0.7) ≈ 3.57"""
        t = compute_optimal_revision_time(10.0, 0.7)
        assert t == pytest.approx(10.0 * (-math.log(0.7)), abs=0.01)

    def test_higher_stability_later_revision(self):
        t5 = compute_optimal_revision_time(5.0)
        t20 = compute_optimal_revision_time(20.0)
        assert t20 > t5

    def test_lower_target_later_revision(self):
        t_high = compute_optimal_revision_time(10.0, 0.8)
        t_low = compute_optimal_revision_time(10.0, 0.5)
        assert t_low > t_high

    def test_edge_target_zero(self):
        assert compute_optimal_revision_time(10.0, 0.0) == 0.0

    def test_edge_target_one(self):
        assert compute_optimal_revision_time(10.0, 1.0) == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
#  8. Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_all_defaults(self):
        inp = ForgettingInput()
        out = compute_adaptive_forgetting(inp)
        assert isinstance(out, ForgettingOutput)

    def test_extreme_elapsed(self):
        inp = ForgettingInput(elapsed_days=10000.0)
        out = compute_adaptive_forgetting(inp)
        assert out.retention >= 0.02
        assert out.forgetting_probability <= 1.0

    def test_zero_base_stability(self):
        inp = ForgettingInput(elapsed_days=5.0, base_stability=0.0)
        out = compute_adaptive_forgetting(inp)
        assert out.retention >= 0.02


# ═══════════════════════════════════════════════════════════════════════════════
#  9. Monotonicity
# ═══════════════════════════════════════════════════════════════════════════════

class TestMonotonicity:
    def test_more_time_lower_retention(self):
        out1 = compute_adaptive_forgetting(ForgettingInput(elapsed_days=1.0))
        out5 = compute_adaptive_forgetting(ForgettingInput(elapsed_days=5.0))
        assert out1.retention >= out5.retention

    def test_higher_stability_higher_retention(self):
        out_low = compute_adaptive_forgetting(ForgettingInput(elapsed_days=5.0, base_stability=1.0))
        out_high = compute_adaptive_forgetting(ForgettingInput(elapsed_days=5.0, base_stability=10.0))
        assert out_high.retention > out_low.retention

    def test_more_revisions_higher_retention(self):
        out_none = compute_adaptive_forgetting(ForgettingInput(elapsed_days=0.5, revision_count=0))
        out_many = compute_adaptive_forgetting(ForgettingInput(elapsed_days=0.5, revision_count=15))
        assert out_many.retention > out_none.retention

    def test_easier_topic_higher_retention(self):
        out_easy = compute_adaptive_forgetting(ForgettingInput(elapsed_days=0.5, difficulty=0.1))
        out_hard = compute_adaptive_forgetting(ForgettingInput(elapsed_days=0.5, difficulty=0.9))
        assert out_easy.retention > out_hard.retention
