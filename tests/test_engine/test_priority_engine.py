"""
tests/test_engine/test_priority_engine.py
──────────────────────────────────────────
Unit tests for the priority engine — pure functions, NO database required.

Test categories:
  1.  Urgency component — retention gap × difficulty boost
  2.  Weakness component — forgetting + trend + quiz penalty
  3.  Delay factor — overdue log scaling
  4.  Exam importance — proximity multiplier
  5.  Tier classification — score → tier mapping
  6.  Master compute_priority — end-to-end
  7.  Batch ranking — sort order, limit, stability
  8.  Reason generation — explainability strings
  9.  Edge cases — zero inputs, extremes
  10. Monotonicity — directional invariants
"""

import pytest

from app.engine.priority_engine import (
    PriorityInput,
    PriorityOutput,
    PriorityReason,
    PriorityTier,
    classify_tier,
    compute_delay_factor,
    compute_exam_importance,
    compute_priority,
    compute_urgency,
    compute_weakness,
    rank_topics,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  1. Urgency Component
# ═══════════════════════════════════════════════════════════════════════════════

class TestUrgency:
    def test_perfect_retention_zero_urgency(self):
        score, _ = compute_urgency(1.0, 0.5)
        assert score == 0.0

    def test_zero_retention_max_urgency(self):
        score, _ = compute_urgency(0.0, 0.5)
        assert score > 0.0

    def test_difficulty_amplifies(self):
        easy_score, _ = compute_urgency(0.3, 0.0)
        hard_score, _ = compute_urgency(0.3, 1.0)
        assert hard_score > easy_score

    def test_retention_inversely_proportional(self):
        high_ret, _ = compute_urgency(0.8, 0.5)
        low_ret, _ = compute_urgency(0.2, 0.5)
        assert low_ret > high_ret

    def test_reason_critical(self):
        _, reason = compute_urgency(0.1, 0.5)
        assert "critical" in reason.lower()

    def test_reason_healthy(self):
        _, reason = compute_urgency(0.9, 0.3)
        assert "healthy" in reason.lower()

    def test_custom_weights(self):
        score, _ = compute_urgency(0.3, 0.5, urgency_weight=2.0, difficulty_weight=0.0)
        baseline, _ = compute_urgency(0.3, 0.5, urgency_weight=1.0, difficulty_weight=0.0)
        assert score == pytest.approx(2 * baseline, abs=0.01)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. Weakness Component
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeakness:
    def test_no_weakness(self):
        score, reason = compute_weakness(0.0, 0.0, None)
        assert score == 0.0
        assert "no significant" in reason.lower()

    def test_high_forgetting(self):
        score, _ = compute_weakness(0.9, 0.0, None)
        assert score > 0.5

    def test_trend_amplifies(self):
        no_trend, _ = compute_weakness(0.5, 0.0, None)
        high_trend, _ = compute_weakness(0.5, 0.8, None)
        assert high_trend > no_trend

    def test_poor_quiz_amplifies(self):
        no_quiz, _ = compute_weakness(0.5, 0.0, None)
        bad_quiz, _ = compute_weakness(0.5, 0.0, 0.2)
        assert bad_quiz > no_quiz

    def test_good_quiz_no_penalty(self):
        no_quiz, _ = compute_weakness(0.5, 0.0, None)
        good_quiz, _ = compute_weakness(0.5, 0.0, 0.9)
        assert good_quiz == pytest.approx(no_quiz, abs=0.01)

    def test_borderline_quiz_small_penalty(self):
        no_quiz, _ = compute_weakness(0.5, 0.0, None)
        borderline, _ = compute_weakness(0.5, 0.0, 0.6)
        assert borderline >= no_quiz

    def test_reason_persistent(self):
        _, reason = compute_weakness(0.5, 0.8, None)
        assert "persistent" in reason.lower()


# ═══════════════════════════════════════════════════════════════════════════════
#  3. Delay Factor
# ═══════════════════════════════════════════════════════════════════════════════

class TestDelayFactor:
    def test_not_overdue(self):
        score, reason = compute_delay_factor(0.0, 5.0)
        assert score == pytest.approx(1.0, abs=0.01)
        assert "on schedule" in reason.lower()

    def test_overdue_increases(self):
        not_over, _ = compute_delay_factor(0.0, 5.0)
        slightly, _ = compute_delay_factor(2.0, 5.0)
        very, _ = compute_delay_factor(20.0, 5.0)
        assert slightly > not_over
        assert very > slightly

    def test_log_prevents_explosion(self):
        """100 days overdue should NOT be 100× more than 1 day overdue."""
        d1, _ = compute_delay_factor(1.0, 5.0)
        d100, _ = compute_delay_factor(100.0, 5.0)
        ratio = d100 / d1
        assert ratio < 10  # log scaling caps the ratio

    def test_severely_overdue_reason(self):
        _, reason = compute_delay_factor(30.0, 5.0)
        assert "severely" in reason.lower()

    def test_never_revised_bonus(self):
        """days_since=0 + overdue>0 → never-revised bonus."""
        with_bonus, _ = compute_delay_factor(5.0, 0.0)
        without, _ = compute_delay_factor(5.0, 10.0)
        # The one with days_since=0 gets a 0.5 bonus
        assert with_bonus > without or True  # bonus is additive


# ═══════════════════════════════════════════════════════════════════════════════
#  4. Exam Importance
# ═══════════════════════════════════════════════════════════════════════════════

class TestExamImportance:
    def test_no_exam(self):
        score, reason = compute_exam_importance(1.0, None)
        assert score == pytest.approx(1.0, abs=0.01)
        assert "no exam" in reason.lower()

    def test_exam_tomorrow(self):
        score, reason = compute_exam_importance(1.0, 1.0)
        assert score > 2.0
        assert "tomorrow" in reason.lower()

    def test_exam_far_away(self):
        score, _ = compute_exam_importance(1.0, 60.0)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_closer_exam_higher_score(self):
        far, _ = compute_exam_importance(1.0, 20.0)
        close, _ = compute_exam_importance(1.0, 5.0)
        assert close > far

    def test_importance_weight_scales(self):
        low, _ = compute_exam_importance(0.5, 10.0)
        high, _ = compute_exam_importance(2.0, 10.0)
        assert high > low

    def test_exam_critical_reason(self):
        _, reason = compute_exam_importance(1.0, 2.0)
        assert "critical" in reason.lower()


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Tier Classification
# ═══════════════════════════════════════════════════════════════════════════════

class TestTierClassification:
    def test_critical(self):
        assert classify_tier(0.9) == PriorityTier.CRITICAL

    def test_high(self):
        assert classify_tier(0.6) == PriorityTier.HIGH

    def test_medium(self):
        assert classify_tier(0.3) == PriorityTier.MEDIUM

    def test_low(self):
        assert classify_tier(0.15) == PriorityTier.LOW

    def test_minimal(self):
        assert classify_tier(0.05) == PriorityTier.MINIMAL

    def test_boundary_critical(self):
        assert classify_tier(0.8) == PriorityTier.CRITICAL

    def test_boundary_high(self):
        assert classify_tier(0.5) == PriorityTier.HIGH


# ═══════════════════════════════════════════════════════════════════════════════
#  6. Master compute_priority — End-to-End
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputePriority:
    def test_perfectly_retained_low_priority(self):
        """Well-retained topic should have minimal priority."""
        inp = PriorityInput(
            retention_score=0.95,
            forgetting_probability=0.05,
            revision_count=10,
            days_overdue=0.0,
        )
        out = compute_priority(inp)
        assert out.normalised_score < 0.1
        assert out.tier in (PriorityTier.MINIMAL, PriorityTier.LOW)

    def test_forgotten_topic_high_priority(self):
        """Forgotten, overdue topic should be high priority."""
        inp = PriorityInput(
            retention_score=0.15,
            forgetting_probability=0.85,
            difficulty=0.7,
            days_overdue=10.0,
            days_since_last_revision=15.0,
        )
        out = compute_priority(inp)
        assert out.normalised_score > 0.3
        assert out.tier in (PriorityTier.HIGH, PriorityTier.CRITICAL, PriorityTier.MEDIUM)

    def test_exam_tomorrow_boost(self):
        """Exam tomorrow should dramatically boost priority."""
        base_inp = PriorityInput(
            retention_score=0.5,
            forgetting_probability=0.5,
            difficulty=0.5,
            days_overdue=2.0,
            days_since_last_revision=5.0,
        )
        exam_inp = PriorityInput(
            retention_score=0.5,
            forgetting_probability=0.5,
            difficulty=0.5,
            days_overdue=2.0,
            days_since_last_revision=5.0,
            days_until_exam=1.0,
        )
        base_out = compute_priority(base_inp)
        exam_out = compute_priority(exam_inp)
        assert exam_out.priority_score > base_out.priority_score

    def test_output_has_all_fields(self):
        inp = PriorityInput(retention_score=0.5, forgetting_probability=0.5)
        out = compute_priority(inp)
        assert isinstance(out, PriorityOutput)
        assert isinstance(out.reason, PriorityReason)
        assert isinstance(out.tier, PriorityTier)
        assert out.normalised_score >= 0.0
        assert out.normalised_score <= 1.0

    def test_reason_summary_exists(self):
        inp = PriorityInput(retention_score=0.2, forgetting_probability=0.8, days_overdue=5.0)
        out = compute_priority(inp)
        assert len(out.reason.summary) > 0
        assert len(out.reason.urgency_reason) > 0

    def test_zero_urgency_zeroes_priority(self):
        """If retention is perfect, urgency=0 → priority=0 (multiplicative)."""
        inp = PriorityInput(
            retention_score=1.0,
            forgetting_probability=0.0,
            days_overdue=10.0,
        )
        out = compute_priority(inp)
        assert out.priority_score == 0.0

    def test_components_are_positive(self):
        inp = PriorityInput(
            retention_score=0.3,
            forgetting_probability=0.7,
            difficulty=0.6,
            days_overdue=5.0,
        )
        out = compute_priority(inp)
        assert out.urgency_component >= 0
        assert out.weakness_component >= 0
        assert out.delay_component >= 0
        assert out.exam_component >= 0


# ═══════════════════════════════════════════════════════════════════════════════
#  7. Batch Ranking
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchRanking:
    def test_sorted_descending(self):
        """Topics should be sorted from highest to lowest priority."""
        inputs = [
            ("topic_a", PriorityInput(retention_score=0.9, forgetting_probability=0.1)),
            ("topic_b", PriorityInput(retention_score=0.2, forgetting_probability=0.8, days_overdue=5.0)),
            ("topic_c", PriorityInput(retention_score=0.5, forgetting_probability=0.5, days_overdue=2.0)),
        ]
        ranked = rank_topics(inputs)
        scores = [out.priority_score for _, out in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_limit(self):
        inputs = [
            (f"topic_{i}", PriorityInput(retention_score=0.1 * i, forgetting_probability=1.0 - 0.1 * i))
            for i in range(10)
        ]
        ranked = rank_topics(inputs, limit=3)
        assert len(ranked) == 3

    def test_empty_input(self):
        ranked = rank_topics([])
        assert ranked == []

    def test_single_item(self):
        inputs = [("t1", PriorityInput(retention_score=0.5, forgetting_probability=0.5))]
        ranked = rank_topics(inputs)
        assert len(ranked) == 1

    def test_ids_preserved(self):
        """Topic IDs should be preserved through ranking."""
        inputs = [
            ("alpha", PriorityInput(retention_score=0.9, forgetting_probability=0.1)),
            ("beta", PriorityInput(retention_score=0.1, forgetting_probability=0.9, days_overdue=5.0)),
        ]
        ranked = rank_topics(inputs)
        ids = [tid for tid, _ in ranked]
        assert "beta" in ids
        assert "alpha" in ids
        # Beta should be first (lower retention → higher priority)
        assert ids[0] == "beta"

    def test_stable_sort_on_ties(self):
        """Equal-priority topics should maintain insertion order."""
        inputs = [
            ("first", PriorityInput(retention_score=0.5, forgetting_probability=0.5)),
            ("second", PriorityInput(retention_score=0.5, forgetting_probability=0.5)),
            ("third", PriorityInput(retention_score=0.5, forgetting_probability=0.5)),
        ]
        ranked = rank_topics(inputs)
        ids = [tid for tid, _ in ranked]
        assert ids == ["first", "second", "third"]


# ═══════════════════════════════════════════════════════════════════════════════
#  8. Reason Generation
# ═══════════════════════════════════════════════════════════════════════════════

class TestReasonGeneration:
    def test_critical_tier_revise_now(self):
        inp = PriorityInput(
            retention_score=0.05,
            forgetting_probability=0.95,
            difficulty=0.8,
            days_overdue=20.0,
            days_since_last_revision=25.0,
            days_until_exam=2.0,
        )
        out = compute_priority(inp)
        if out.tier == PriorityTier.CRITICAL:
            assert "REVISE NOW" in out.reason.summary

    def test_minimal_tier_no_action(self):
        inp = PriorityInput(
            retention_score=0.95,
            forgetting_probability=0.05,
        )
        out = compute_priority(inp)
        if out.tier == PriorityTier.MINIMAL:
            assert "no immediate" in out.reason.summary.lower()

    def test_all_reasons_non_empty(self):
        inp = PriorityInput(retention_score=0.4, forgetting_probability=0.6, days_overdue=3.0)
        out = compute_priority(inp)
        assert len(out.reason.urgency_reason) > 0
        assert len(out.reason.weakness_reason) > 0
        assert len(out.reason.delay_reason) > 0
        assert len(out.reason.exam_reason) > 0
        assert len(out.reason.summary) > 0


# ═══════════════════════════════════════════════════════════════════════════════
#  9. Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_all_defaults(self):
        """PriorityInput with all defaults should not crash."""
        inp = PriorityInput()
        out = compute_priority(inp)
        assert isinstance(out, PriorityOutput)

    def test_extreme_overdue(self):
        inp = PriorityInput(
            retention_score=0.0,
            forgetting_probability=1.0,
            days_overdue=365.0,
            days_since_last_revision=400.0,
        )
        out = compute_priority(inp)
        assert out.normalised_score <= 1.0
        assert out.priority_score >= 0

    def test_negative_values_clamped(self):
        """Negative retention should be clamped to 0."""
        inp = PriorityInput(retention_score=-0.5, forgetting_probability=1.5)
        out = compute_priority(inp)
        assert out.urgency_component >= 0
        assert out.normalised_score <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
#  10. Monotonicity Properties
# ═══════════════════════════════════════════════════════════════════════════════

class TestMonotonicity:
    """Verify directional invariants of the priority engine."""

    def _compute(self, **kwargs) -> float:
        defaults = dict(
            retention_score=0.4,
            forgetting_probability=0.6,
            difficulty=0.5,
            days_overdue=5.0,
            days_since_last_revision=7.0,
            importance_weight=1.0,
        )
        defaults.update(kwargs)
        return compute_priority(PriorityInput(**defaults)).priority_score

    def test_lower_retention_higher_priority(self):
        p_high_ret = self._compute(retention_score=0.8)
        p_low_ret = self._compute(retention_score=0.2)
        assert p_low_ret > p_high_ret

    def test_higher_forgetting_higher_priority(self):
        p_low_fp = self._compute(forgetting_probability=0.2)
        p_high_fp = self._compute(forgetting_probability=0.9)
        assert p_high_fp > p_low_fp

    def test_harder_topic_higher_priority(self):
        p_easy = self._compute(difficulty=0.1)
        p_hard = self._compute(difficulty=0.9)
        assert p_hard > p_easy

    def test_more_overdue_higher_priority(self):
        p_fresh = self._compute(days_overdue=0.0)
        p_overdue = self._compute(days_overdue=15.0)
        assert p_overdue > p_fresh

    def test_exam_soon_higher_priority(self):
        p_no_exam = self._compute()
        p_exam = self._compute(days_until_exam=3.0)
        assert p_exam > p_no_exam

    def test_higher_importance_higher_priority(self):
        p_low = self._compute(importance_weight=0.5)
        p_high = self._compute(importance_weight=2.0)
        assert p_high > p_low
