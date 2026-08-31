"""
tests/test_engine/test_stability_engine.py
─────────────────────────────────────────────
Unit tests for the Adaptive Memory Stability Engine.

Categories:
  1. Reinforcement factor — diminishing returns, quality weighting
  2. Quiz performance factor — score + trend effects
  3. Confidence factor — range and linearity
  4. Difficulty penalty — superlinear penalty
  5. Master computation — S_adaptive formula end-to-end
  6. Stability evolution — base growth after events
  7. Stability degradation — inactivity loss
  8. Edge cases — zero state, extreme values
  9. Monotonicity — directional invariants
"""

import pytest

from app.engine.stability_engine import (
    StabilityInput,
    StabilityOutput,
    StabilityEvolution,
    compute_reinforcement_factor,
    compute_quiz_performance_factor,
    compute_confidence_factor,
    compute_difficulty_penalty,
    compute_adaptive_stability,
    evolve_stability,
    degrade_stability,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  1. Reinforcement Factor
# ═══════════════════════════════════════════════════════════════════════════════

class TestReinforcementFactor:
    def test_zero_revisions_returns_one(self):
        assert compute_reinforcement_factor(0, 0.5) == 1.0

    def test_more_revisions_increases(self):
        f1 = compute_reinforcement_factor(1, 0.5)
        f5 = compute_reinforcement_factor(5, 0.5)
        assert f5 > f1 > 1.0

    def test_diminishing_returns(self):
        """Marginal reinforcement gain decreases with more revisions."""
        # Compare marginal increase from adding 1 more revision at count=2 vs count=20
        f2 = compute_reinforcement_factor(2, 0.5)
        f3 = compute_reinforcement_factor(3, 0.5)
        f20 = compute_reinforcement_factor(20, 0.5)
        f21 = compute_reinforcement_factor(21, 0.5)
        marginal_early = f3 - f2
        marginal_late = f21 - f20
        assert marginal_early > marginal_late

    def test_higher_quality_higher_factor(self):
        low = compute_reinforcement_factor(5, 0.1)
        high = compute_reinforcement_factor(5, 0.9)
        assert high > low

    def test_quality_still_contributes_when_low(self):
        """Even quality=0 gives half-weight reinforcement."""
        f = compute_reinforcement_factor(5, 0.0)
        assert f > 1.0  # still contributes

    def test_negative_revisions_treated_as_zero(self):
        assert compute_reinforcement_factor(-1, 0.5) == 1.0


# ═══════════════════════════════════════════════════════════════════════════════
#  2. Quiz Performance Factor
# ═══════════════════════════════════════════════════════════════════════════════

class TestQuizPerformanceFactor:
    def test_perfect_score(self):
        f = compute_quiz_performance_factor(1.0)
        assert f == pytest.approx(1.0, abs=0.01)

    def test_zero_score(self):
        f = compute_quiz_performance_factor(0.0)
        assert f == pytest.approx(0.5, abs=0.01)

    def test_positive_trend_boosts(self):
        no_trend = compute_quiz_performance_factor(0.5, 0.0)
        pos_trend = compute_quiz_performance_factor(0.5, 1.0)
        assert pos_trend > no_trend

    def test_negative_trend_lowers(self):
        no_trend = compute_quiz_performance_factor(0.5, 0.0)
        neg_trend = compute_quiz_performance_factor(0.5, -1.0)
        assert neg_trend < no_trend

    def test_range_clamped(self):
        lowest = compute_quiz_performance_factor(0.0, -1.0)
        highest = compute_quiz_performance_factor(1.0, 1.0)
        assert 0.4 <= lowest <= 1.1
        assert 0.4 <= highest <= 1.1


# ═══════════════════════════════════════════════════════════════════════════════
#  3. Confidence Factor
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfidenceFactor:
    def test_zero_confidence(self):
        assert compute_confidence_factor(0.0) == 0.7

    def test_full_confidence(self):
        assert compute_confidence_factor(1.0) == 1.0

    def test_mid_confidence(self):
        assert compute_confidence_factor(0.5) == pytest.approx(0.85, abs=0.01)

    def test_linearity(self):
        f1 = compute_confidence_factor(0.25)
        f2 = compute_confidence_factor(0.5)
        f3 = compute_confidence_factor(0.75)
        # Linear: equal spacing
        assert (f2 - f1) == pytest.approx(f3 - f2, abs=0.001)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. Difficulty Penalty
# ═══════════════════════════════════════════════════════════════════════════════

class TestDifficultyPenalty:
    def test_zero_difficulty_no_penalty(self):
        assert compute_difficulty_penalty(0.0) == 0.0

    def test_max_difficulty(self):
        p = compute_difficulty_penalty(1.0)
        assert p == pytest.approx(0.3, abs=0.01)

    def test_superlinear(self):
        """Mid-difficulty penalty should be less than half of max penalty."""
        mid = compute_difficulty_penalty(0.5)
        full = compute_difficulty_penalty(1.0)
        assert mid < full * 0.5

    def test_harder_more_penalty(self):
        easy = compute_difficulty_penalty(0.2)
        hard = compute_difficulty_penalty(0.8)
        assert hard > easy


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Master Stability Computation
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdaptiveStability:
    def test_default_input(self):
        inp = StabilityInput()
        out = compute_adaptive_stability(inp)
        assert isinstance(out, StabilityOutput)
        assert out.adaptive_stability >= 0.1

    def test_output_has_all_components(self):
        inp = StabilityInput()
        out = compute_adaptive_stability(inp)
        assert out.reinforcement_factor >= 1.0
        assert 0.4 <= out.quiz_performance_factor <= 1.1
        assert 0.7 <= out.confidence_factor <= 1.0
        assert out.difficulty_penalty >= 0.0

    def test_high_base_high_stability(self):
        low = compute_adaptive_stability(StabilityInput(base_stability=1.0))
        high = compute_adaptive_stability(StabilityInput(base_stability=10.0))
        assert high.adaptive_stability > low.adaptive_stability

    def test_more_revisions_higher_stability(self):
        few = compute_adaptive_stability(StabilityInput(revision_count=1))
        many = compute_adaptive_stability(StabilityInput(revision_count=20))
        assert many.adaptive_stability > few.adaptive_stability

    def test_hard_topic_lower_stability(self):
        easy = compute_adaptive_stability(StabilityInput(difficulty=0.1))
        hard = compute_adaptive_stability(StabilityInput(difficulty=0.9))
        assert easy.adaptive_stability > hard.adaptive_stability

    def test_high_confidence_higher_stability(self):
        low = compute_adaptive_stability(StabilityInput(confidence_score=0.1))
        high = compute_adaptive_stability(StabilityInput(confidence_score=0.9))
        assert high.adaptive_stability > low.adaptive_stability

    def test_clamped_minimum(self):
        inp = StabilityInput(base_stability=0.01, difficulty=1.0)
        out = compute_adaptive_stability(inp)
        assert out.adaptive_stability >= 0.1

    def test_clamped_maximum(self):
        inp = StabilityInput(base_stability=1000.0, revision_count=100)
        out = compute_adaptive_stability(inp)
        assert out.adaptive_stability <= 365.0


# ═══════════════════════════════════════════════════════════════════════════════
#  6. Stability Evolution
# ═══════════════════════════════════════════════════════════════════════════════

class TestStabilityEvolution:
    def test_basic_growth(self):
        evo = evolve_stability(
            current_base=1.0, event_quality=0.8,
            revision_count=0, current_quality_avg=0.5,
            current_trend=0.0,
        )
        assert isinstance(evo, StabilityEvolution)
        assert evo.new_base_stability > 1.0

    def test_higher_quality_more_growth(self):
        evo_low = evolve_stability(1.0, 0.2, 0, 0.5, 0.0)
        evo_high = evolve_stability(1.0, 0.9, 0, 0.5, 0.0)
        assert evo_high.growth_applied > evo_low.growth_applied

    def test_growth_diminishes_with_revisions(self):
        evo_early = evolve_stability(1.0, 0.8, 0, 0.5, 0.0)
        evo_late = evolve_stability(1.0, 0.8, 50, 0.5, 0.0)
        assert evo_early.growth_applied > evo_late.growth_applied

    def test_quality_average_updates(self):
        evo = evolve_stability(1.0, 0.9, 5, 0.5, 0.0)
        # New quality should be pulled toward 0.9
        assert evo.new_revision_quality > 0.5

    def test_trend_shifts_toward_quality(self):
        evo = evolve_stability(1.0, 0.9, 0, 0.5, -0.5)
        # High quality should shift trend upward
        assert evo.new_performance_trend > -0.5

    def test_zero_quality_no_growth(self):
        evo = evolve_stability(1.0, 0.0, 0, 0.5, 0.0)
        assert evo.new_base_stability == 1.0  # no growth from quality=0

    def test_growth_capped(self):
        evo = evolve_stability(1.0, 1.0, 0, 0.5, 0.0)
        assert evo.growth_applied <= 0.5  # max_growth default


# ═══════════════════════════════════════════════════════════════════════════════
#  7. Stability Degradation
# ═══════════════════════════════════════════════════════════════════════════════

class TestStabilityDegradation:
    def test_within_grace_no_change(self):
        result = degrade_stability(5.0, 5.0)
        assert result == 5.0

    def test_past_grace_degrades(self):
        result = degrade_stability(5.0, 20.0)
        assert result < 5.0

    def test_longer_inactivity_more_degradation(self):
        short = degrade_stability(5.0, 10.0)
        long = degrade_stability(5.0, 30.0)
        assert long < short

    def test_never_below_minimum(self):
        result = degrade_stability(5.0, 365.0)
        assert result >= 0.5

    def test_exact_onset_no_change(self):
        result = degrade_stability(5.0, 7.0)
        assert result == 5.0


# ═══════════════════════════════════════════════════════════════════════════════
#  8. Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_all_defaults(self):
        inp = StabilityInput()
        out = compute_adaptive_stability(inp)
        assert out.adaptive_stability > 0

    def test_all_zeros(self):
        inp = StabilityInput(
            base_stability=0.0, revision_count=0, revision_quality=0.0,
            quiz_score=0.0, confidence_score=0.0, performance_trend=-1.0,
            difficulty=1.0,
        )
        out = compute_adaptive_stability(inp)
        assert out.adaptive_stability >= 0.1  # minimum bound

    def test_all_maxed(self):
        inp = StabilityInput(
            base_stability=100.0, revision_count=100, revision_quality=1.0,
            quiz_score=1.0, confidence_score=1.0, performance_trend=1.0,
            difficulty=0.0,
        )
        out = compute_adaptive_stability(inp)
        assert out.adaptive_stability <= 365.0  # maximum bound


# ═══════════════════════════════════════════════════════════════════════════════
#  9. Monotonicity
# ═══════════════════════════════════════════════════════════════════════════════

class TestMonotonicity:
    def test_more_base_more_stability(self):
        s1 = compute_adaptive_stability(StabilityInput(base_stability=1.0))
        s10 = compute_adaptive_stability(StabilityInput(base_stability=10.0))
        assert s10.adaptive_stability > s1.adaptive_stability

    def test_more_revisions_more_stability(self):
        r0 = compute_adaptive_stability(StabilityInput(revision_count=0))
        r20 = compute_adaptive_stability(StabilityInput(revision_count=20))
        assert r20.adaptive_stability > r0.adaptive_stability

    def test_better_quiz_more_stability(self):
        low = compute_adaptive_stability(StabilityInput(quiz_score=0.1))
        high = compute_adaptive_stability(StabilityInput(quiz_score=0.9))
        assert high.adaptive_stability > low.adaptive_stability

    def test_more_confidence_more_stability(self):
        low = compute_adaptive_stability(StabilityInput(confidence_score=0.1))
        high = compute_adaptive_stability(StabilityInput(confidence_score=0.9))
        assert high.adaptive_stability > low.adaptive_stability

    def test_harder_less_stability(self):
        easy = compute_adaptive_stability(StabilityInput(difficulty=0.1))
        hard = compute_adaptive_stability(StabilityInput(difficulty=0.9))
        assert easy.adaptive_stability > hard.adaptive_stability

    def test_evolution_always_positive_for_positive_quality(self):
        for q in [0.1, 0.3, 0.5, 0.7, 1.0]:
            evo = evolve_stability(1.0, q, 5, 0.5, 0.0)
            assert evo.new_base_stability >= 1.0
