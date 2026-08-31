"""
tests/test_engine/test_decay_engine.py
────────────────────────────────────────
Unit tests for the decay engine — pure functions, NO database required.

Test categories:
  1. Effective decay rate  — difficulty, reinforcement, inactivity effects
  2. Retention projection  — Ebbinghaus curve R(t) = R₀ × e^(−λt)
  3. Forgetting probability — soft sigmoid transition
  4. Half-life and time-to-threshold — analytic solutions
  5. Inactivity penalty — onset, super-linear growth
  6. Predicted retention drop — ΔR over time windows
  7. Forgetting curve projection — sampled points
  8. Master analyze_decay — end-to-end integration
  9. Monotonicity properties — directional invariants
"""

import math

import pytest

from app.engine.decay_engine import (
    CurvePoint,
    DecayInput,
    DecayOutput,
    analyze_decay,
    compute_effective_decay_rate,
    compute_forgetting_probability,
    compute_half_life,
    compute_inactivity_penalty,
    compute_predicted_retention_drop,
    compute_retention_at_time,
    compute_time_to_threshold,
    project_forgetting_curve,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  1. Effective Decay Rate
# ═══════════════════════════════════════════════════════════════════════════════

class TestEffectiveDecayRate:
    def test_baseline_no_modifiers(self):
        """Base rate with 0 difficulty, 0 revisions, 0 inactivity."""
        rate = compute_effective_decay_rate(0.1, 0.0, 0, 0.0)
        # difficulty_factor=1.0, reinforcement_factor=1.0, inactivity=0
        assert rate == pytest.approx(0.1, abs=0.01)

    def test_difficulty_increases_rate(self):
        easy = compute_effective_decay_rate(0.1, 0.0, 0, 0.0)
        hard = compute_effective_decay_rate(0.1, 1.0, 0, 0.0)
        assert hard > easy

    def test_revisions_decrease_rate(self):
        few = compute_effective_decay_rate(0.1, 0.5, 0, 0.0)
        many = compute_effective_decay_rate(0.1, 0.5, 10, 0.0)
        assert many < few

    def test_inactivity_increases_rate(self):
        recent = compute_effective_decay_rate(0.1, 0.5, 3, 1.0)
        inactive = compute_effective_decay_rate(0.1, 0.5, 3, 30.0)
        assert inactive > recent

    def test_bounded_min(self):
        rate = compute_effective_decay_rate(0.001, 0.0, 100, 0.0)
        assert rate >= 0.005

    def test_bounded_max(self):
        rate = compute_effective_decay_rate(0.5, 1.0, 0, 100.0)
        assert rate <= 1.0

    def test_max_difficulty_factor(self):
        """Difficulty=1.0 should give factor of 1.5."""
        rate = compute_effective_decay_rate(0.1, 1.0, 0, 0.0)
        expected = 0.1 * 1.5  # 1 + 0.5 * 1.0
        assert rate == pytest.approx(expected, abs=0.01)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. Retention Projection
# ═══════════════════════════════════════════════════════════════════════════════

class TestRetentionAtTime:
    def test_zero_elapsed(self):
        assert compute_retention_at_time(0.8, 0.1, 0.0) == pytest.approx(0.8, abs=0.001)

    def test_negative_elapsed(self):
        assert compute_retention_at_time(0.8, 0.1, -5.0) == pytest.approx(0.8, abs=0.001)

    def test_zero_decay_rate(self):
        assert compute_retention_at_time(0.8, 0.0, 10.0) == pytest.approx(0.8, abs=0.001)

    def test_exponential_decay(self):
        """R(t) = 0.8 × e^(−0.1 × 5) ≈ 0.485"""
        result = compute_retention_at_time(0.8, 0.1, 5.0)
        expected = 0.8 * math.exp(-0.5)
        assert result == pytest.approx(expected, abs=0.001)

    def test_never_below_floor(self):
        result = compute_retention_at_time(0.8, 0.5, 1000.0)
        assert result >= 0.02  # default floor

    def test_custom_floor(self):
        result = compute_retention_at_time(0.8, 0.5, 1000.0, floor=0.1)
        assert result >= 0.1

    def test_monotonic_decrease(self):
        r1 = compute_retention_at_time(0.9, 0.1, 1.0)
        r5 = compute_retention_at_time(0.9, 0.1, 5.0)
        r30 = compute_retention_at_time(0.9, 0.1, 30.0)
        assert r1 > r5 > r30


# ═══════════════════════════════════════════════════════════════════════════════
#  3. Forgetting Probability
# ═══════════════════════════════════════════════════════════════════════════════

class TestForgettingProbability:
    def test_just_learned(self):
        """Zero elapsed → high retention → low forgetting probability."""
        prob = compute_forgetting_probability(0.9, 0.1, 0.0)
        assert prob < 0.1

    def test_long_elapsed(self):
        """Long elapsed → low retention → high forgetting probability."""
        prob = compute_forgetting_probability(0.9, 0.1, 60.0)
        assert prob > 0.8

    def test_at_threshold(self):
        """When retention ≈ threshold, probability should be ≈ 0.5."""
        # Find the time when R(t) = threshold (0.4)
        # 0.4 = 0.8 × e^(−0.1t) → t = −ln(0.5)/0.1 ≈ 6.93
        t = -math.log(0.5) / 0.1
        prob = compute_forgetting_probability(0.8, 0.1, t, threshold=0.4)
        assert 0.3 < prob < 0.7  # should be near 0.5

    def test_range_always_valid(self):
        for t in [0, 1, 5, 10, 50, 100]:
            prob = compute_forgetting_probability(0.8, 0.1, float(t))
            assert 0.0 <= prob <= 1.0

    def test_zero_threshold(self):
        prob = compute_forgetting_probability(0.8, 0.1, 5.0, threshold=0.0)
        assert prob == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
#  4. Half-Life
# ═══════════════════════════════════════════════════════════════════════════════

class TestHalfLife:
    def test_known_rate(self):
        """λ=0.1 → t_half = ln(2)/0.1 ≈ 6.93 days."""
        hl = compute_half_life(0.1)
        assert hl == pytest.approx(math.log(2) / 0.1, abs=0.01)

    def test_high_rate_short_halflife(self):
        hl = compute_half_life(0.5)
        assert hl < 2.0

    def test_low_rate_long_halflife(self):
        hl = compute_half_life(0.01)
        assert hl > 60.0

    def test_zero_rate_infinite(self):
        hl = compute_half_life(0.0)
        assert hl == float("inf")

    def test_negative_rate_infinite(self):
        hl = compute_half_life(-0.1)
        assert hl == float("inf")


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Time to Threshold
# ═══════════════════════════════════════════════════════════════════════════════

class TestTimeToThreshold:
    def test_above_threshold(self):
        """R₀=0.9, threshold=0.4 → positive time."""
        t = compute_time_to_threshold(0.9, 0.1, threshold=0.4)
        assert t > 0

    def test_already_below(self):
        """R₀=0.3 < threshold=0.4 → time = 0."""
        t = compute_time_to_threshold(0.3, 0.1, threshold=0.4)
        assert t == 0.0

    def test_zero_decay_infinite(self):
        t = compute_time_to_threshold(0.9, 0.0, threshold=0.4)
        assert t == float("inf")

    def test_analytic_check(self):
        """t = −ln(0.4/0.8) / 0.1 = −ln(0.5)/0.1 ≈ 6.93."""
        t = compute_time_to_threshold(0.8, 0.1, threshold=0.4)
        expected = -math.log(0.5) / 0.1
        assert t == pytest.approx(expected, abs=0.01)

    def test_higher_rate_shorter_time(self):
        t_slow = compute_time_to_threshold(0.9, 0.05, threshold=0.4)
        t_fast = compute_time_to_threshold(0.9, 0.2, threshold=0.4)
        assert t_fast < t_slow


# ═══════════════════════════════════════════════════════════════════════════════
#  6. Inactivity Penalty
# ═══════════════════════════════════════════════════════════════════════════════

class TestInactivityPenalty:
    def test_within_onset_no_penalty(self):
        pen = compute_inactivity_penalty(5.0, onset=7.0)
        assert pen == 0.0

    def test_at_onset_no_penalty(self):
        pen = compute_inactivity_penalty(7.0, onset=7.0)
        assert pen == 0.0

    def test_just_past_onset(self):
        pen = compute_inactivity_penalty(8.0, onset=7.0)
        assert pen > 0.0

    def test_super_linear_growth(self):
        """Penalty at 20 excess days should be more than 2× penalty at 10 excess days."""
        p10 = compute_inactivity_penalty(17.0, onset=7.0)   # 10 excess days
        p20 = compute_inactivity_penalty(27.0, onset=7.0)   # 20 excess days
        assert p20 > 2 * p10  # super-linear (exponent 1.3)

    def test_zero_days(self):
        pen = compute_inactivity_penalty(0.0)
        assert pen == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
#  7. Predicted Retention Drop
# ═══════════════════════════════════════════════════════════════════════════════

class TestPredictedRetentionDrop:
    def test_zero_projection(self):
        drop = compute_predicted_retention_drop(0.8, 0.1, 0.0)
        assert drop == 0.0

    def test_positive_drop(self):
        drop = compute_predicted_retention_drop(0.8, 0.1, 10.0)
        assert drop > 0.0

    def test_drop_bounded_by_initial(self):
        drop = compute_predicted_retention_drop(0.8, 0.1, 1000.0)
        assert drop <= 0.8

    def test_higher_rate_bigger_drop(self):
        d_slow = compute_predicted_retention_drop(0.8, 0.05, 7.0)
        d_fast = compute_predicted_retention_drop(0.8, 0.3, 7.0)
        assert d_fast > d_slow


# ═══════════════════════════════════════════════════════════════════════════════
#  8. Forgetting Curve Projection
# ═══════════════════════════════════════════════════════════════════════════════

class TestForgettingCurve:
    def test_returns_correct_count(self):
        curve = project_forgetting_curve(0.9, 0.1, 7.0, num_points=5)
        assert len(curve) == 5

    def test_first_point_is_initial(self):
        curve = project_forgetting_curve(0.9, 0.1, 7.0, num_points=5)
        assert curve[0].day == 0.0
        assert curve[0].retention == pytest.approx(0.9, abs=0.001)

    def test_last_point_is_end(self):
        curve = project_forgetting_curve(0.9, 0.1, 7.0, num_points=5)
        assert curve[-1].day == pytest.approx(7.0, abs=0.01)

    def test_retention_decreases(self):
        curve = project_forgetting_curve(0.9, 0.1, 7.0, num_points=5)
        for i in range(1, len(curve)):
            assert curve[i].retention <= curve[i - 1].retention

    def test_forgetting_prob_increases(self):
        curve = project_forgetting_curve(0.9, 0.1, 30.0, num_points=10)
        for i in range(1, len(curve)):
            assert curve[i].forgetting_probability >= curve[i - 1].forgetting_probability

    def test_all_points_are_curve_point(self):
        curve = project_forgetting_curve(0.9, 0.1, 7.0)
        for point in curve:
            assert isinstance(point, CurvePoint)

    def test_min_two_points(self):
        curve = project_forgetting_curve(0.9, 0.1, 7.0, num_points=1)
        assert len(curve) >= 2  # forced minimum

    def test_zero_projection(self):
        curve = project_forgetting_curve(0.9, 0.1, 0.0)
        assert len(curve) == 1
        assert curve[0].day == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
#  9. Master analyze_decay — End-to-End
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalyzeDecay:
    def test_fresh_topic(self):
        """Just learned, high retention, no decay yet."""
        inp = DecayInput(
            current_retention=0.9,
            current_decay_rate=0.1,
            difficulty=0.3,
            revision_count=1,
            days_since_last_revision=0.0,
            projection_days=7.0,
        )
        out = analyze_decay(inp)
        assert isinstance(out, DecayOutput)
        assert out.predicted_retention < 0.9   # will decay
        assert out.predicted_retention_drop > 0
        assert out.half_life_days > 0
        assert out.inactivity_penalty == 0.0
        assert out.is_critically_decayed is False
        assert len(out.curve) == 10  # default

    def test_long_inactive_topic(self):
        """Topic abandoned for 60 days — should show critical decay."""
        inp = DecayInput(
            current_retention=0.6,
            current_decay_rate=0.1,
            difficulty=0.7,
            revision_count=2,
            days_since_last_revision=60.0,
            projection_days=7.0,
        )
        out = analyze_decay(inp)
        assert out.inactivity_penalty > 0.0
        assert out.effective_decay_rate > 0.1  # boosted by inactivity
        assert out.forgetting_probability > 0.5

    def test_well_reinforced_topic(self):
        """Many revisions, easy topic — slow decay."""
        inp = DecayInput(
            current_retention=0.85,
            current_decay_rate=0.08,
            difficulty=0.2,
            revision_count=15,
            days_since_last_revision=3.0,
            projection_days=14.0,
        )
        out = analyze_decay(inp)
        assert out.effective_decay_rate < 0.08  # reinforcement lowers rate
        assert out.half_life_days > 10
        assert out.predicted_retention > 0.4

    def test_output_types(self):
        inp = DecayInput(current_retention=0.7, projection_days=5.0)
        out = analyze_decay(inp)
        assert isinstance(out.effective_decay_rate, float)
        assert isinstance(out.forgetting_probability, float)
        assert isinstance(out.predicted_retention, float)
        assert isinstance(out.predicted_retention_drop, float)
        assert isinstance(out.half_life_days, float)
        assert isinstance(out.time_to_threshold_days, float)
        assert isinstance(out.inactivity_penalty, float)
        assert isinstance(out.is_critically_decayed, bool)
        assert isinstance(out.curve, list)

    def test_curve_included_in_output(self):
        inp = DecayInput(current_retention=0.8, projection_days=7.0)
        out = analyze_decay(inp, curve_points=5)
        assert len(out.curve) == 5

    def test_drop_equals_initial_minus_predicted(self):
        inp = DecayInput(current_retention=0.85, current_decay_rate=0.1, projection_days=10.0)
        out = analyze_decay(inp)
        expected_drop = inp.current_retention - out.predicted_retention
        assert out.predicted_retention_drop == pytest.approx(expected_drop, abs=0.001)


# ═══════════════════════════════════════════════════════════════════════════════
#  10. Monotonicity Properties
# ═══════════════════════════════════════════════════════════════════════════════

class TestMonotonicity:
    """Verify directional invariants of the decay engine."""

    def _analyze(self, **kwargs) -> DecayOutput:
        defaults = dict(
            current_retention=0.8,
            current_decay_rate=0.1,
            difficulty=0.5,
            revision_count=3,
            days_since_last_revision=5.0,
            projection_days=7.0,
        )
        defaults.update(kwargs)
        return analyze_decay(DecayInput(**defaults))

    def test_higher_difficulty_faster_decay(self):
        out_easy = self._analyze(difficulty=0.1)
        out_hard = self._analyze(difficulty=0.9)
        assert out_hard.effective_decay_rate > out_easy.effective_decay_rate

    def test_more_revisions_slower_decay(self):
        out_few = self._analyze(revision_count=1)
        out_many = self._analyze(revision_count=20)
        assert out_many.effective_decay_rate < out_few.effective_decay_rate

    def test_longer_inactivity_faster_decay(self):
        out_recent = self._analyze(days_since_last_revision=1.0)
        out_stale = self._analyze(days_since_last_revision=30.0)
        assert out_stale.effective_decay_rate > out_recent.effective_decay_rate

    def test_higher_initial_retention_bigger_drop(self):
        out_low = self._analyze(current_retention=0.3)
        out_high = self._analyze(current_retention=0.9)
        assert out_high.predicted_retention_drop > out_low.predicted_retention_drop

    def test_longer_projection_bigger_drop(self):
        out_short = self._analyze(projection_days=3.0)
        out_long = self._analyze(projection_days=30.0)
        assert out_long.predicted_retention_drop > out_short.predicted_retention_drop

    def test_higher_decay_rate_shorter_halflife(self):
        out_slow = self._analyze(current_decay_rate=0.05)
        out_fast = self._analyze(current_decay_rate=0.3)
        assert out_fast.half_life_days < out_slow.half_life_days
