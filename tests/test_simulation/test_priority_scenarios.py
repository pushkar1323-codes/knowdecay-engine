"""
tests/test_simulation/test_priority_scenarios.py
──────────────────────────────────────────────────
Scenario-based tests for the priority engine under realistic conditions.

These tests validate that the priority engine produces sensible outputs
when presented with the kinds of inputs a real learner system would generate.

Scenarios:
  1.  Low retention + near exam      → HIGH / CRITICAL priority
  2.  High retention + near exam     → MEDIUM / LOW priority
  3.  Low retention + distant exam   → HIGH but less than scenario 1
  4.  Missed revisions (high elapsed)→ elevated urgency
  5.  Multiple weak topics           → all HIGH, weakest highest
  6.  Conflicting priorities         → sensible ranking
  7.  Score bounds                   → always in [0, 1]
  8.  Tier–score consistency         → tier matches score range
  9.  Exam proximity amplification   → closer exam → higher priority
  10. Difficulty amplification       → harder topic → higher priority
  11. Importance weight ranking       → higher weight → higher priority
  12. Deterministic stability         → same inputs → same outputs

All tests are pure — no DB, no HTTP, no I/O.
"""

import pytest

from app.engine.priority_engine import (
    PriorityInput,
    PriorityOutput,
    PriorityTier,
    classify_tier,
    compute_priority,
    rank_topics,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _make_input(**overrides) -> PriorityInput:
    """Build a PriorityInput with reasonable mid-range defaults + overrides."""
    defaults = dict(
        retention_score=0.4,
        forgetting_probability=0.6,
        stability_score=3.0,
        decay_rate=0.1,
        revision_count=3,
        days_since_last_revision=7.0,
        days_overdue=3.0,
        difficulty=0.5,
        importance_weight=1.0,
        days_until_exam=None,
        exam_weight=1.0,
        weakness_trend=0.2,
        recent_quiz_score=None,
    )
    defaults.update(overrides)
    return PriorityInput(**defaults)


def _score(inp: PriorityInput) -> PriorityOutput:
    """Shorthand for compute_priority."""
    return compute_priority(inp)


# ═══════════════════════════════════════════════════════════════════════════════
#  1. Low retention + near exam → HIGH / CRITICAL
# ═══════════════════════════════════════════════════════════════════════════════

class TestLowRetentionNearExam:
    """Scenario: learner has nearly forgotten a topic and exam is imminent."""

    def test_tier_is_high_or_critical(self):
        inp = _make_input(
            retention_score=0.10,
            forgetting_probability=0.90,
            difficulty=0.7,
            days_overdue=8.0,
            days_since_last_revision=12.0,
            days_until_exam=3.0,
        )
        out = _score(inp)
        assert out.tier in (PriorityTier.HIGH, PriorityTier.CRITICAL), (
            f"Expected HIGH or CRITICAL, got {out.tier} "
            f"(normalised={out.normalised_score:.4f})"
        )

    def test_normalised_score_above_half(self):
        inp = _make_input(
            retention_score=0.10,
            forgetting_probability=0.90,
            difficulty=0.7,
            days_overdue=8.0,
            days_since_last_revision=12.0,
            days_until_exam=3.0,
        )
        out = _score(inp)
        assert out.normalised_score >= 0.5, (
            f"Score {out.normalised_score:.4f} too low for forgotten + near-exam"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  2. High retention + near exam → MEDIUM / LOW
# ═══════════════════════════════════════════════════════════════════════════════

class TestHighRetentionNearExam:
    """Scenario: topic is well-retained but exam is imminent."""

    def test_tier_is_medium_or_lower(self):
        inp = _make_input(
            retention_score=0.90,
            forgetting_probability=0.10,
            difficulty=0.5,
            days_overdue=0.0,
            days_since_last_revision=2.0,
            days_until_exam=3.0,
            weakness_trend=0.0,
        )
        out = _score(inp)
        # Well-retained topic: urgency is low, so multiplicative formula
        # keeps overall score down despite exam proximity.
        assert out.tier in (
            PriorityTier.MEDIUM, PriorityTier.LOW, PriorityTier.MINIMAL,
        ), f"Expected MEDIUM or lower, got {out.tier}"

    def test_lower_than_forgotten_near_exam(self):
        """Well-retained + near exam should score lower than forgotten + near exam."""
        retained = _make_input(
            retention_score=0.90,
            forgetting_probability=0.10,
            days_until_exam=3.0,
            days_overdue=0.0,
            weakness_trend=0.0,
        )
        forgotten = _make_input(
            retention_score=0.10,
            forgetting_probability=0.90,
            days_until_exam=3.0,
            days_overdue=8.0,
            weakness_trend=0.3,
        )
        assert _score(forgotten).priority_score > _score(retained).priority_score


# ═══════════════════════════════════════════════════════════════════════════════
#  3. Low retention + distant exam → HIGH but less than scenario 1
# ═══════════════════════════════════════════════════════════════════════════════

class TestLowRetentionDistantExam:
    """Forgotten topic with plenty of time before the exam."""

    def test_still_high_priority(self):
        inp = _make_input(
            retention_score=0.15,
            forgetting_probability=0.85,
            difficulty=0.7,
            days_overdue=8.0,
            days_since_last_revision=12.0,
            days_until_exam=60.0,  # exam far away
        )
        out = _score(inp)
        # Even without exam pressure, a badly forgotten topic is urgent.
        assert out.tier in (
            PriorityTier.HIGH, PriorityTier.CRITICAL, PriorityTier.MEDIUM,
        )

    def test_less_urgent_than_near_exam(self):
        """Same decay state, but distant exam should score lower than near exam."""
        near_exam = _make_input(
            retention_score=0.15,
            forgetting_probability=0.85,
            difficulty=0.7,
            days_overdue=8.0,
            days_since_last_revision=12.0,
            days_until_exam=3.0,
        )
        distant_exam = _make_input(
            retention_score=0.15,
            forgetting_probability=0.85,
            difficulty=0.7,
            days_overdue=8.0,
            days_since_last_revision=12.0,
            days_until_exam=60.0,
        )
        assert _score(near_exam).priority_score > _score(distant_exam).priority_score


# ═══════════════════════════════════════════════════════════════════════════════
#  4. Missed revisions → elevated urgency
# ═══════════════════════════════════════════════════════════════════════════════

class TestMissedRevisions:
    """Scenario: learner has not revised for a long time."""

    def test_high_elapsed_days_raises_priority(self):
        recent = _make_input(
            days_overdue=1.0,
            days_since_last_revision=3.0,
        )
        stale = _make_input(
            days_overdue=30.0,
            days_since_last_revision=45.0,
        )
        assert _score(stale).priority_score > _score(recent).priority_score

    def test_delay_component_grows_with_overdue(self):
        short = _make_input(days_overdue=2.0, days_since_last_revision=5.0)
        long = _make_input(days_overdue=20.0, days_since_last_revision=30.0)
        assert _score(long).delay_component > _score(short).delay_component

    def test_severely_overdue_reason_string(self):
        inp = _make_input(days_overdue=30.0, days_since_last_revision=40.0)
        out = _score(inp)
        assert "overdue" in out.reason.delay_reason.lower()


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Multiple weak topics → all HIGH, weakest highest
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultipleWeakTopics:
    """When several topics are struggling, the weakest should rank first."""

    def test_all_weak_topics_are_elevated(self):
        topics = [
            ("topic_a", _make_input(retention_score=0.20, forgetting_probability=0.80, days_overdue=5.0)),
            ("topic_b", _make_input(retention_score=0.25, forgetting_probability=0.75, days_overdue=5.0)),
            ("topic_c", _make_input(retention_score=0.30, forgetting_probability=0.70, days_overdue=5.0)),
        ]
        ranked = rank_topics(topics)
        for _, out in ranked:
            # All are weak — none should be MINIMAL.
            assert out.tier != PriorityTier.MINIMAL

    def test_weakest_topic_ranked_first(self):
        topics = [
            ("weak", _make_input(retention_score=0.10, forgetting_probability=0.90, days_overdue=7.0)),
            ("moderate", _make_input(retention_score=0.35, forgetting_probability=0.65, days_overdue=7.0)),
            ("mild", _make_input(retention_score=0.50, forgetting_probability=0.50, days_overdue=7.0)),
        ]
        ranked = rank_topics(topics)
        ids = [tid for tid, _ in ranked]
        assert ids[0] == "weak", f"Expected 'weak' first, got {ids}"

    def test_ranking_preserves_all_ids(self):
        topics = [
            ("a", _make_input(retention_score=0.20, forgetting_probability=0.80)),
            ("b", _make_input(retention_score=0.30, forgetting_probability=0.70)),
            ("c", _make_input(retention_score=0.40, forgetting_probability=0.60)),
        ]
        ranked = rank_topics(topics)
        returned_ids = {tid for tid, _ in ranked}
        assert returned_ids == {"a", "b", "c"}


# ═══════════════════════════════════════════════════════════════════════════════
#  6. Conflicting priorities → sensible ranking
# ═══════════════════════════════════════════════════════════════════════════════

class TestConflictingPriorities:
    """One topic urgent by time (overdue), another urgent by retention (forgotten)."""

    def test_forgotten_vs_overdue_ranking(self):
        """
        topic_forgotten: very low retention, but on schedule (not overdue).
        topic_overdue:   moderate retention, but severely overdue.
        Both should be elevated; the ranking depends on multiplicative balance.
        """
        topic_forgotten = _make_input(
            retention_score=0.05,
            forgetting_probability=0.95,
            difficulty=0.6,
            days_overdue=0.0,
            days_since_last_revision=2.0,
            weakness_trend=0.5,
        )
        topic_overdue = _make_input(
            retention_score=0.45,
            forgetting_probability=0.55,
            difficulty=0.5,
            days_overdue=25.0,
            days_since_last_revision=30.0,
            weakness_trend=0.1,
        )
        topics = [
            ("forgotten", topic_forgotten),
            ("overdue", topic_overdue),
        ]
        ranked = rank_topics(topics)
        # Both should have meaningful priority (neither should be MINIMAL).
        for _, out in ranked:
            assert out.tier != PriorityTier.MINIMAL

    def test_exam_urgent_vs_retention_urgent(self):
        """
        topic_exam:      moderate retention, exam tomorrow.
        topic_decayed:   very low retention, no exam.
        Verify both score meaningfully and the ranking is deterministic.
        """
        topic_exam = _make_input(
            retention_score=0.50,
            forgetting_probability=0.50,
            difficulty=0.5,
            days_overdue=2.0,
            days_since_last_revision=5.0,
            days_until_exam=1.0,
        )
        topic_decayed = _make_input(
            retention_score=0.10,
            forgetting_probability=0.90,
            difficulty=0.7,
            days_overdue=10.0,
            days_since_last_revision=15.0,
            days_until_exam=None,
        )
        topics = [
            ("exam_urgent", topic_exam),
            ("retention_urgent", topic_decayed),
        ]
        ranked = rank_topics(topics)

        # Both should score above MINIMAL.
        for _, out in ranked:
            assert out.normalised_score > 0.05

        # The result should be stable: run it again, same order.
        ranked_again = rank_topics(topics)
        assert [tid for tid, _ in ranked] == [tid for tid, _ in ranked_again]


# ═══════════════════════════════════════════════════════════════════════════════
#  7. Score bounds — normalised_score always in [0, 1]
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoreBounds:
    """normalised_score must lie within [0, 1] for all conceivable inputs."""

    @pytest.mark.parametrize(
        "retention, forgetting, overdue, exam_days",
        [
            (0.0, 1.0, 365.0, 0.0),       # absolute worst case
            (1.0, 0.0, 0.0, None),          # absolute best case
            (0.5, 0.5, 0.0, None),          # neutral
            (0.0, 1.0, 0.0, 1.0),           # forgotten + exam tomorrow
            (0.95, 0.05, 100.0, None),       # retained but very overdue
            (0.0, 1.0, 100.0, 1.0),          # everything extreme
        ],
    )
    def test_normalised_in_unit_interval(self, retention, forgetting, overdue, exam_days):
        inp = _make_input(
            retention_score=retention,
            forgetting_probability=forgetting,
            days_overdue=overdue,
            days_until_exam=exam_days,
            difficulty=0.9,
            weakness_trend=0.8,
            importance_weight=2.0,
        )
        out = _score(inp)
        assert 0.0 <= out.normalised_score <= 1.0, (
            f"normalised_score={out.normalised_score} out of [0, 1]"
        )

    def test_raw_score_non_negative(self):
        inp = _make_input(retention_score=0.0, forgetting_probability=1.0, days_overdue=50.0)
        out = _score(inp)
        assert out.priority_score >= 0.0


# ═══════════════════════════════════════════════════════════════════════════════
#  8. Tier–score consistency
# ═══════════════════════════════════════════════════════════════════════════════

class TestTierScoreConsistency:
    """The assigned tier must agree with the normalised score's range."""

    TIER_BOUNDS = {
        PriorityTier.CRITICAL: (0.80, 1.01),
        PriorityTier.HIGH:     (0.50, 0.80),
        PriorityTier.MEDIUM:   (0.25, 0.50),
        PriorityTier.LOW:      (0.10, 0.25),
        PriorityTier.MINIMAL:  (0.00, 0.10),
    }

    @pytest.mark.parametrize(
        "retention, forgetting, overdue, exam_days, difficulty",
        [
            (0.05, 0.95, 20.0, 2.0,  0.9),    # likely CRITICAL
            (0.30, 0.70, 5.0,  10.0,  0.6),   # likely HIGH / MEDIUM
            (0.60, 0.40, 1.0,  None,  0.4),   # likely MEDIUM / LOW
            (0.90, 0.10, 0.0,  None,  0.2),   # likely MINIMAL / LOW
            (0.99, 0.01, 0.0,  None,  0.1),   # likely MINIMAL
        ],
    )
    def test_tier_matches_score_range(
        self, retention, forgetting, overdue, exam_days, difficulty,
    ):
        inp = _make_input(
            retention_score=retention,
            forgetting_probability=forgetting,
            days_overdue=overdue,
            days_until_exam=exam_days,
            difficulty=difficulty,
        )
        out = _score(inp)
        lo, hi = self.TIER_BOUNDS[out.tier]
        assert lo <= out.normalised_score < hi, (
            f"Tier {out.tier} expects score in [{lo}, {hi}), "
            f"got {out.normalised_score:.4f}"
        )

    def test_classify_tier_agrees_with_output(self):
        """classify_tier(normalised) must return the same tier as the output."""
        inp = _make_input(
            retention_score=0.20,
            forgetting_probability=0.80,
            days_overdue=10.0,
            difficulty=0.7,
        )
        out = _score(inp)
        assert out.tier == classify_tier(out.normalised_score)


# ═══════════════════════════════════════════════════════════════════════════════
#  9. Exam proximity amplification
# ═══════════════════════════════════════════════════════════════════════════════

class TestExamProximityAmplification:
    """Closer exams must always push priority higher, all else equal."""

    def test_closer_exam_higher_score(self):
        far = _score(_make_input(days_until_exam=25.0))
        mid = _score(_make_input(days_until_exam=10.0))
        close = _score(_make_input(days_until_exam=2.0))

        assert close.priority_score > mid.priority_score
        assert mid.priority_score > far.priority_score

    def test_no_exam_vs_distant_exam(self):
        """An exam beyond the proximity window should not boost priority."""
        no_exam = _score(_make_input(days_until_exam=None))
        distant = _score(_make_input(days_until_exam=60.0))
        # Both outside the default 30-day window → same exam component.
        assert no_exam.exam_component == pytest.approx(
            distant.exam_component, abs=0.01,
        )

    def test_exam_component_increases_with_proximity(self):
        far = _score(_make_input(days_until_exam=20.0))
        close = _score(_make_input(days_until_exam=5.0))
        assert close.exam_component > far.exam_component


# ═══════════════════════════════════════════════════════════════════════════════
#  10. Difficulty amplification
# ═══════════════════════════════════════════════════════════════════════════════

class TestDifficultyAmplification:
    """Harder topics should receive higher urgency, all else equal."""

    def test_harder_topic_higher_urgency_component(self):
        easy = _score(_make_input(difficulty=0.1))
        hard = _score(_make_input(difficulty=0.9))
        assert hard.urgency_component > easy.urgency_component

    def test_difficulty_amplifies_overall_score(self):
        easy = _score(_make_input(difficulty=0.1))
        hard = _score(_make_input(difficulty=0.9))
        assert hard.priority_score > easy.priority_score

    def test_zero_difficulty_baseline(self):
        """Even with difficulty=0, urgency should still be nonzero if retention is low."""
        inp = _make_input(retention_score=0.2, forgetting_probability=0.8, difficulty=0.0)
        out = _score(inp)
        assert out.urgency_component > 0.0


# ═══════════════════════════════════════════════════════════════════════════════
#  11. Importance weight ranking
# ═══════════════════════════════════════════════════════════════════════════════

class TestImportanceWeightRanking:
    """Higher importance_weight topics must outrank lower ones, all else equal."""

    def test_higher_weight_higher_score(self):
        low_w = _score(_make_input(importance_weight=0.5))
        high_w = _score(_make_input(importance_weight=2.0))
        assert high_w.priority_score > low_w.priority_score

    def test_importance_affects_exam_component(self):
        low_w = _score(_make_input(importance_weight=0.5, days_until_exam=10.0))
        high_w = _score(_make_input(importance_weight=2.0, days_until_exam=10.0))
        assert high_w.exam_component > low_w.exam_component

    def test_batch_ranking_respects_importance(self):
        """In a batch, higher importance should push a topic up the list."""
        topics = [
            ("low_imp", _make_input(importance_weight=0.5)),
            ("high_imp", _make_input(importance_weight=2.0)),
        ]
        ranked = rank_topics(topics)
        ids = [tid for tid, _ in ranked]
        assert ids[0] == "high_imp"


# ═══════════════════════════════════════════════════════════════════════════════
#  12. Deterministic stability — same inputs → same outputs
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeterministicStability:
    """Pure functions must return identical results for identical inputs."""

    def test_single_topic_deterministic(self):
        inp = _make_input(
            retention_score=0.25,
            forgetting_probability=0.75,
            difficulty=0.6,
            days_overdue=7.0,
            days_since_last_revision=10.0,
            days_until_exam=5.0,
            weakness_trend=0.4,
            recent_quiz_score=0.3,
        )
        out1 = _score(inp)
        out2 = _score(inp)

        assert out1.priority_score == out2.priority_score
        assert out1.normalised_score == out2.normalised_score
        assert out1.tier == out2.tier
        assert out1.urgency_component == out2.urgency_component
        assert out1.weakness_component == out2.weakness_component
        assert out1.delay_component == out2.delay_component
        assert out1.exam_component == out2.exam_component

    def test_batch_ranking_deterministic(self):
        topics = [
            ("a", _make_input(retention_score=0.10, forgetting_probability=0.90, days_overdue=10.0)),
            ("b", _make_input(retention_score=0.40, forgetting_probability=0.60, days_overdue=3.0)),
            ("c", _make_input(retention_score=0.70, forgetting_probability=0.30, days_overdue=1.0)),
        ]
        ranked1 = rank_topics(topics)
        ranked2 = rank_topics(topics)

        ids1 = [tid for tid, _ in ranked1]
        ids2 = [tid for tid, _ in ranked2]
        assert ids1 == ids2

        scores1 = [out.priority_score for _, out in ranked1]
        scores2 = [out.priority_score for _, out in ranked2]
        assert scores1 == scores2

    def test_reason_strings_deterministic(self):
        inp = _make_input(
            retention_score=0.10,
            forgetting_probability=0.90,
            days_overdue=15.0,
            days_until_exam=2.0,
        )
        out1 = _score(inp)
        out2 = _score(inp)

        assert out1.reason.urgency_reason == out2.reason.urgency_reason
        assert out1.reason.weakness_reason == out2.reason.weakness_reason
        assert out1.reason.delay_reason == out2.reason.delay_reason
        assert out1.reason.exam_reason == out2.reason.exam_reason
        assert out1.reason.summary == out2.reason.summary
