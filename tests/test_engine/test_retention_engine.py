"""
tests/test_engine/test_retention_engine.py
───────────────────────────────────────────
Unit tests for the retention engine — pure functions, NO database required.

Test categories:
  1. Component functions — each formula independently
  2. Edge cases — zero inputs, boundary values, extremes
  3. Master compute_retention — end-to-end with known inputs
  4. Monotonicity — verify directional properties
     (more study → higher retention, more time → lower retention, etc.)
"""

import math

import pytest

from app.engine.retention_engine import (
    RetentionInput,
    RetentionOutput,
    compute_base_strength,
    compute_confidence,
    compute_difficulty_penalty,
    compute_quiz_boost,
    compute_retention,
    compute_revision_reinforcement,
    compute_stability,
    compute_time_decay,
    compute_updated_decay_rate,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  1. Component Functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestBaseStrength:
    def test_zero_study(self):
        assert compute_base_strength(0.0) == 0.0

    def test_negative_study(self):
        assert compute_base_strength(-10.0) == 0.0

    def test_positive_study(self):
        result = compute_base_strength(30.0)
        assert 0.0 < result < 0.20  # can't exceed weight

    def test_saturation_curve(self):
        """More study → higher base, but diminishing returns."""
        s10 = compute_base_strength(10.0)
        s30 = compute_base_strength(30.0)
        s120 = compute_base_strength(120.0)
        assert s10 < s30 < s120
        # 120 min should be close to the weight cap (0.20)
        assert s120 < 0.20

    def test_custom_weight(self):
        result = compute_base_strength(60.0, weight=0.5)
        assert result == pytest.approx(0.25, abs=0.01)


class TestRevisionReinforcement:
    def test_zero_revisions(self):
        assert compute_revision_reinforcement(0) == 0.0

    def test_negative_revisions(self):
        assert compute_revision_reinforcement(-1) == 0.0

    def test_single_revision(self):
        result = compute_revision_reinforcement(1)
        expected = 0.15 * math.log(2)
        assert result == pytest.approx(expected, abs=0.001)

    def test_diminishing_returns(self):
        """Each subsequent revision contributes less."""
        r1 = compute_revision_reinforcement(1)
        r2 = compute_revision_reinforcement(2)
        r10 = compute_revision_reinforcement(10)
        gain_1_to_2 = r2 - r1
        gain_2_to_10 = r10 - r2
        # 8 revisions (2→10) should give less per-revision gain than 1→2
        assert gain_2_to_10 / 8 < gain_1_to_2


class TestQuizBoost:
    def test_no_quiz(self):
        assert compute_quiz_boost(0.9, has_quiz=False) == 0.0

    def test_perfect_score(self):
        result = compute_quiz_boost(1.0, has_quiz=True)
        assert result == pytest.approx(0.30, abs=0.001)

    def test_half_score(self):
        result = compute_quiz_boost(0.5, has_quiz=True)
        assert result == pytest.approx(0.15, abs=0.001)

    def test_zero_score(self):
        assert compute_quiz_boost(0.0, has_quiz=True) == 0.0

    def test_score_clamped(self):
        """Scores above 1.0 are clamped."""
        result = compute_quiz_boost(1.5, has_quiz=True)
        assert result == pytest.approx(0.30, abs=0.001)


class TestTimeDecay:
    def test_zero_elapsed(self):
        assert compute_time_decay(0.0, 0.1) == 0.0

    def test_negative_elapsed(self):
        assert compute_time_decay(-5.0, 0.1) == 0.0

    def test_zero_decay_rate(self):
        assert compute_time_decay(10.0, 0.0) == 0.0

    def test_short_time(self):
        """After 1 day with λ=0.1, decay should be small."""
        result = compute_time_decay(1.0, 0.1)
        expected = 1.0 - math.exp(-0.1)
        assert result == pytest.approx(expected, abs=0.001)
        assert result < 0.15

    def test_long_time(self):
        """After 30 days with λ=0.1, decay should be significant."""
        result = compute_time_decay(30.0, 0.1)
        assert result > 0.9

    def test_very_long_approaches_one(self):
        result = compute_time_decay(1000.0, 0.1)
        assert result == pytest.approx(1.0, abs=0.001)

    def test_monotonic_increase(self):
        d1 = compute_time_decay(1.0, 0.1)
        d5 = compute_time_decay(5.0, 0.1)
        d30 = compute_time_decay(30.0, 0.1)
        assert d1 < d5 < d30


class TestDifficultyPenalty:
    def test_zero_difficulty(self):
        assert compute_difficulty_penalty(0.0) == 0.0

    def test_max_difficulty(self):
        result = compute_difficulty_penalty(1.0)
        assert result == pytest.approx(0.15, abs=0.001)

    def test_medium_difficulty(self):
        result = compute_difficulty_penalty(0.5)
        assert result == pytest.approx(0.075, abs=0.001)

    def test_clamped(self):
        """Difficulty above 1.0 is clamped."""
        result = compute_difficulty_penalty(2.0)
        assert result == pytest.approx(0.15, abs=0.001)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. Stability
# ═══════════════════════════════════════════════════════════════════════════════

class TestStability:
    def test_first_revision_easy_topic(self):
        result = compute_stability(0, 0.0, 0.0)
        # base_interval × 1^0.5 × 1.0 / 1.0 = 1.0
        assert result == pytest.approx(1.0, abs=0.01)

    def test_more_revisions_increases_stability(self):
        s0 = compute_stability(0, 0.5, 0.5)
        s3 = compute_stability(3, 0.5, 0.5)
        s10 = compute_stability(10, 0.5, 0.5)
        assert s0 < s3 < s10

    def test_higher_difficulty_decreases_stability(self):
        s_easy = compute_stability(3, 0.8, 0.0)
        s_hard = compute_stability(3, 0.8, 1.0)
        assert s_hard < s_easy

    def test_higher_quiz_score_increases_stability(self):
        s_low = compute_stability(3, 0.2, 0.5)
        s_high = compute_stability(3, 0.9, 0.5)
        assert s_low < s_high

    def test_never_negative(self):
        result = compute_stability(0, 0.0, 1.0)
        assert result >= 0.1


# ═══════════════════════════════════════════════════════════════════════════════
#  3. Confidence
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfidence:
    def test_no_quiz_discounted(self):
        """Without quiz data, self-report is discounted to 60%."""
        result = compute_confidence(0.0, 0.8, has_quiz=False)
        assert result == pytest.approx(0.48, abs=0.01)

    def test_perfect_match_high_confidence(self):
        """Score=0.9, self-reported=0.9 → consistency=1.0 → high confidence."""
        result = compute_confidence(0.9, 0.9, has_quiz=True)
        assert result > 0.8

    def test_overconfident_penalised(self):
        """Score=0.3, self-reported=0.9 → large mismatch → lower confidence."""
        result = compute_confidence(0.3, 0.9, has_quiz=True)
        overconfident = result
        matched = compute_confidence(0.3, 0.3, has_quiz=True)
        # Overconfident case should not be higher than matched case's blended
        assert overconfident <= matched + 0.1  # allowing small tolerance

    def test_range_0_to_1(self):
        for score in [0.0, 0.3, 0.5, 0.7, 1.0]:
            for conf in [0.0, 0.3, 0.5, 0.7, 1.0]:
                result = compute_confidence(score, conf, has_quiz=True)
                assert 0.0 <= result <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
#  4. Decay Rate Update
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecayRateUpdate:
    def test_high_score_lowers_rate(self):
        high = compute_updated_decay_rate(0.1, 0.9, 0.5, 3)
        low = compute_updated_decay_rate(0.1, 0.2, 0.5, 3)
        assert high < low

    def test_high_difficulty_raises_rate(self):
        easy = compute_updated_decay_rate(0.1, 0.5, 0.0, 3)
        hard = compute_updated_decay_rate(0.1, 0.5, 1.0, 3)
        assert easy < hard

    def test_more_revisions_lower_rate(self):
        few = compute_updated_decay_rate(0.1, 0.5, 0.5, 0)
        many = compute_updated_decay_rate(0.1, 0.5, 0.5, 20)
        assert many < few

    def test_bounded(self):
        result = compute_updated_decay_rate(0.1, 0.0, 1.0, 0)
        assert 0.01 <= result <= 0.5


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Master compute_retention — End-to-End
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeRetention:
    def test_fresh_topic_no_data(self):
        """Brand new topic with no study, no quiz, no revisions."""
        inp = RetentionInput()
        out = compute_retention(inp)
        # Should hit the floor (0.05) since all components are 0 except penalty
        assert out.retention_score == pytest.approx(0.05, abs=0.01)
        assert out.forgetting_probability == pytest.approx(0.95, abs=0.01)

    def test_well_studied_topic(self):
        """Good study, multiple revisions, decent quiz, recent."""
        inp = RetentionInput(
            study_duration_minutes=45.0,
            quiz_score=0.85,
            quiz_confidence=0.8,
            has_quiz=True,
            revision_count=5,
            elapsed_days=1.0,
            decay_rate=0.05,
            difficulty=0.3,
        )
        out = compute_retention(inp)
        assert out.retention_score > 0.4
        assert out.stability_score > 2.0
        assert out.confidence_score > 0.6

    def test_forgotten_topic(self):
        """Long elapsed time, no recent revision."""
        inp = RetentionInput(
            study_duration_minutes=10.0,
            revision_count=1,
            elapsed_days=60.0,
            decay_rate=0.1,
            difficulty=0.7,
        )
        out = compute_retention(inp)
        assert out.retention_score < 0.2
        assert out.forgetting_probability > 0.8

    def test_output_types(self):
        inp = RetentionInput(
            study_duration_minutes=30.0,
            quiz_score=0.7,
            has_quiz=True,
            revision_count=3,
            elapsed_days=2.0,
        )
        out = compute_retention(inp)
        assert isinstance(out, RetentionOutput)
        assert isinstance(out.retention_score, float)
        assert isinstance(out.stability_score, float)
        assert isinstance(out.confidence_score, float)
        assert isinstance(out.base_strength, float)
        assert isinstance(out.time_decay, float)

    def test_retention_clamped_to_floor(self):
        """Even with maximum penalties, retention shouldn't go below floor."""
        inp = RetentionInput(
            elapsed_days=1000.0,
            decay_rate=0.5,
            difficulty=1.0,
        )
        out = compute_retention(inp)
        assert out.retention_score >= 0.05

    def test_retention_clamped_to_one(self):
        """Even with maximum bonuses, retention can't exceed 1.0."""
        inp = RetentionInput(
            study_duration_minutes=1000.0,
            quiz_score=1.0,
            has_quiz=True,
            revision_count=100,
            elapsed_days=0.0,
            difficulty=0.0,
        )
        out = compute_retention(inp)
        assert out.retention_score <= 1.0

    def test_explainability_components_sum(self):
        """Verify that components reconstruct the raw score."""
        inp = RetentionInput(
            study_duration_minutes=30.0,
            quiz_score=0.7,
            has_quiz=True,
            revision_count=3,
            elapsed_days=5.0,
            decay_rate=0.08,
            difficulty=0.4,
        )
        out = compute_retention(inp)
        raw = (
            out.base_strength
            + out.revision_reinforcement
            + out.quiz_boost
            - out.time_decay
            - out.difficulty_penalty
        )
        # Retention should be the clamped version of raw
        expected = max(0.05, min(1.0, raw))
        assert out.retention_score == pytest.approx(expected, abs=0.001)


# ═══════════════════════════════════════════════════════════════════════════════
#  6. Monotonicity Properties
# ═══════════════════════════════════════════════════════════════════════════════

class TestMonotonicity:
    """Verify directional properties: more X → higher/lower Y."""

    def _compute(self, **kwargs) -> float:
        defaults = dict(
            study_duration_minutes=30.0,
            quiz_score=0.6,
            has_quiz=True,
            revision_count=3,
            elapsed_days=3.0,
            decay_rate=0.08,
            difficulty=0.5,
        )
        defaults.update(kwargs)
        return compute_retention(RetentionInput(**defaults)).retention_score

    def test_more_study_higher_retention(self):
        r1 = self._compute(study_duration_minutes=10.0)
        r2 = self._compute(study_duration_minutes=60.0)
        assert r2 > r1

    def test_more_revisions_higher_retention(self):
        r1 = self._compute(revision_count=1)
        r2 = self._compute(revision_count=10)
        assert r2 > r1

    def test_higher_quiz_score_higher_retention(self):
        r1 = self._compute(quiz_score=0.2)
        r2 = self._compute(quiz_score=0.9)
        assert r2 > r1

    def test_more_time_lower_retention(self):
        r1 = self._compute(elapsed_days=1.0)
        r2 = self._compute(elapsed_days=30.0)
        assert r2 < r1

    def test_higher_difficulty_lower_retention(self):
        r1 = self._compute(difficulty=0.1)
        r2 = self._compute(difficulty=0.9)
        assert r2 < r1

    def test_higher_decay_rate_lower_retention(self):
        r1 = self._compute(decay_rate=0.02)
        r2 = self._compute(decay_rate=0.3)
        assert r2 < r1
