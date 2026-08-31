"""
tests/test_engine/test_advanced_analytics.py
─────────────────────────────────────────────
Unit tests for advanced analytics (sections 7–11):
  7.  Retention Evolution
  8.  Stability Progression
  9.  Reinforcement Effectiveness
  10. Forgetting Trends
  11. Scheduling Efficiency
  12. Advanced Analytics Report (master)

All functions are pure — no DB, no mocking required.
"""

import math

import pytest

from app.engine.analytics_engine import (
    # DTOs
    TopicSnapshot,
    # Enums
    ForgettingRisk,
    ReinforcementGrade,
    RetentionZone,
    StabilityBand,
    TimingQuality,
    # Functions
    compute_advanced_analytics,
    compute_forgetting_trends,
    compute_reinforcement_effectiveness,
    compute_retention_evolution,
    compute_scheduling_efficiency,
    compute_stability_progression,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

def _snap(
    topic_id="t1", topic_name="Topic 1",
    retention_score=0.8, forgetting_probability=0.2,
    stability_score=10.0, base_stability=10.0,
    urgency_score=0.0, revision_count=3,
    confidence_score=0.7, performance_trend=0.1,
    difficulty=0.5, importance_weight=1.0,
    days_since_last_revision=2.0,
    chapter_id="ch1", chapter_name="Chapter 1",
    module_id="m1", module_name="Module 1",
    subject_id="s1", subject_name="Subject 1",
):
    return TopicSnapshot(
        topic_id=topic_id, topic_name=topic_name,
        retention_score=retention_score,
        forgetting_probability=forgetting_probability,
        stability_score=stability_score,
        base_stability=base_stability,
        urgency_score=urgency_score,
        revision_count=revision_count,
        confidence_score=confidence_score,
        performance_trend=performance_trend,
        difficulty=difficulty,
        importance_weight=importance_weight,
        days_since_last_revision=days_since_last_revision,
        chapter_id=chapter_id, chapter_name=chapter_name,
        module_id=module_id, module_name=module_name,
        subject_id=subject_id, subject_name=subject_name,
    )


@pytest.fixture
def diverse_snapshots():
    """A mix of well-retained, moderate, and poorly-retained topics."""
    return [
        _snap("t1", "Well Retained", retention_score=0.95, base_stability=30.0,
              revision_count=10, confidence_score=0.9, performance_trend=0.3,
              days_since_last_revision=1.0, difficulty=0.2),
        _snap("t2", "Moderate", retention_score=0.60, base_stability=8.0,
              revision_count=5, confidence_score=0.5, performance_trend=0.0,
              days_since_last_revision=4.0, difficulty=0.5),
        _snap("t3", "Weak", retention_score=0.30, base_stability=3.0,
              revision_count=2, confidence_score=0.3, performance_trend=-0.2,
              days_since_last_revision=5.0, difficulty=0.8),
        _snap("t4", "Critical", retention_score=0.10, base_stability=1.0,
              revision_count=8, confidence_score=0.2, performance_trend=-0.5,
              days_since_last_revision=7.0, difficulty=0.9,
              forgetting_probability=0.9),
        _snap("t5", "Just Revised", retention_score=0.99, base_stability=15.0,
              revision_count=6, confidence_score=0.8, performance_trend=0.2,
              days_since_last_revision=0.1, difficulty=0.3),
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  7. Retention Evolution Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestRetentionEvolution:

    def test_empty_snapshots(self):
        result = compute_retention_evolution([])
        assert result.topic_evolutions == []
        assert result.avg_decay_velocity == 0.0
        assert result.avg_half_life == 0.0

    def test_single_topic_has_projection(self):
        s = _snap(base_stability=10.0, days_since_last_revision=2.0)
        result = compute_retention_evolution([s])
        assert len(result.topic_evolutions) == 1
        evo = result.topic_evolutions[0]
        assert evo.topic_id == "t1"
        assert len(evo.projection) == 5  # 1, 3, 7, 14, 30 days
        assert evo.projection[0].days_from_now == 1.0

    def test_projection_is_monotonically_decreasing(self):
        s = _snap(base_stability=10.0, days_since_last_revision=1.0)
        result = compute_retention_evolution([s])
        proj = result.topic_evolutions[0].projection
        for i in range(1, len(proj)):
            assert proj[i].projected_retention <= proj[i - 1].projected_retention

    def test_decay_velocity_is_negative(self):
        s = _snap(base_stability=10.0, days_since_last_revision=2.0)
        result = compute_retention_evolution([s])
        assert result.topic_evolutions[0].decay_velocity < 0

    def test_higher_stability_slower_decay(self):
        slow = _snap("slow", base_stability=50.0, days_since_last_revision=1.0)
        fast = _snap("fast", base_stability=2.0, days_since_last_revision=1.0)
        result = compute_retention_evolution([slow, fast])
        by_id = {e.topic_id: e for e in result.topic_evolutions}
        # Slower decay → less negative velocity
        assert by_id["slow"].decay_velocity > by_id["fast"].decay_velocity

    def test_fastest_decaying_sorted(self, diverse_snapshots):
        result = compute_retention_evolution(diverse_snapshots)
        velocities = [e.decay_velocity for e in result.fastest_decaying]
        # Should be sorted most-negative first
        assert velocities == sorted(velocities)

    def test_half_life_positive(self):
        s = _snap(base_stability=10.0, days_since_last_revision=0.5)
        result = compute_retention_evolution([s])
        assert result.topic_evolutions[0].half_life_days > 0

    def test_topics_reaching_weak_count(self):
        # Very low stability → will reach weak threshold quickly
        fragile = _snap("fragile", base_stability=1.0, days_since_last_revision=0.1)
        # Very high stability → won't reach weak in 7 days
        robust = _snap("robust", base_stability=100.0, days_since_last_revision=0.1)
        result = compute_retention_evolution([fragile, robust])
        # fragile should reach weak in 7d, robust shouldn't
        assert result.topics_reaching_weak_in_7d >= 1

    def test_explanation_contains_topic_count(self, diverse_snapshots):
        result = compute_retention_evolution(diverse_snapshots)
        assert "5 topics" in result.explanation


# ═══════════════════════════════════════════════════════════════════════════════
#  8. Stability Progression Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestStabilityProgression:

    def test_empty_snapshots(self):
        result = compute_stability_progression([])
        assert result.topic_stabilities == []
        assert result.mean_stability == 0.0

    def test_band_classification_fragile(self):
        s = _snap(base_stability=1.0)
        result = compute_stability_progression([s])
        assert result.topic_stabilities[0].band == StabilityBand.FRAGILE

    def test_band_classification_developing(self):
        s = _snap(base_stability=4.0)
        result = compute_stability_progression([s])
        assert result.topic_stabilities[0].band == StabilityBand.DEVELOPING

    def test_band_classification_moderate(self):
        s = _snap(base_stability=10.0)
        result = compute_stability_progression([s])
        assert result.topic_stabilities[0].band == StabilityBand.MODERATE

    def test_band_classification_strong(self):
        s = _snap(base_stability=30.0)
        result = compute_stability_progression([s])
        assert result.topic_stabilities[0].band == StabilityBand.STRONG

    def test_band_classification_robust(self):
        s = _snap(base_stability=90.0)
        result = compute_stability_progression([s])
        assert result.topic_stabilities[0].band == StabilityBand.ROBUST

    def test_stagnation_detection(self):
        # Many revisions but low stability → stagnating
        s = _snap(base_stability=2.0, revision_count=10)
        result = compute_stability_progression([s])
        assert result.topic_stabilities[0].is_stagnating is True
        assert len(result.stagnating_topics) == 1

    def test_not_stagnating_with_few_revisions(self):
        s = _snap(base_stability=2.0, revision_count=2)
        result = compute_stability_progression([s])
        assert result.topic_stabilities[0].is_stagnating is False

    def test_stability_per_revision(self):
        s = _snap(base_stability=15.0, revision_count=5)
        result = compute_stability_progression([s])
        assert result.topic_stabilities[0].stability_per_revision == 3.0

    def test_band_distribution(self, diverse_snapshots):
        result = compute_stability_progression(diverse_snapshots)
        total = sum(result.band_distribution.values())
        assert total == 5

    def test_most_fragile_sorted(self, diverse_snapshots):
        result = compute_stability_progression(diverse_snapshots)
        stabs = [t.base_stability for t in result.most_fragile]
        assert stabs == sorted(stabs)

    def test_mean_and_median(self):
        snaps = [_snap("a", base_stability=2.0), _snap("b", base_stability=10.0)]
        result = compute_stability_progression(snaps)
        assert result.mean_stability == 6.0
        assert result.median_stability == 6.0


# ═══════════════════════════════════════════════════════════════════════════════
#  9. Reinforcement Effectiveness Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestReinforcementEffectiveness:

    def test_empty_snapshots(self):
        result = compute_reinforcement_effectiveness([])
        assert result.topic_reinforcements == []
        assert result.total_revisions == 0

    def test_high_retention_high_grade(self):
        s = _snap(retention_score=0.95, confidence_score=0.9,
                  revision_count=2, performance_trend=0.5)
        result = compute_reinforcement_effectiveness([s])
        grade = result.topic_reinforcements[0].grade
        assert grade in (ReinforcementGrade.EXCELLENT, ReinforcementGrade.GOOD)

    def test_low_retention_low_grade(self):
        s = _snap(retention_score=0.10, confidence_score=0.1,
                  revision_count=1, performance_trend=-0.5)
        result = compute_reinforcement_effectiveness([s])
        grade = result.topic_reinforcements[0].grade
        assert grade in (ReinforcementGrade.POOR, ReinforcementGrade.INEFFECTIVE)

    def test_diminishing_returns_detection(self):
        # Many revisions but still low retention
        s = _snap(retention_score=0.25, revision_count=10)
        result = compute_reinforcement_effectiveness([s])
        assert result.topic_reinforcements[0].is_diminishing is True
        assert len(result.diminishing_return_topics) == 1

    def test_not_diminishing_with_good_retention(self):
        s = _snap(retention_score=0.80, revision_count=10)
        result = compute_reinforcement_effectiveness([s])
        assert result.topic_reinforcements[0].is_diminishing is False

    def test_retention_per_revision(self):
        s = _snap(retention_score=0.80, revision_count=4)
        result = compute_reinforcement_effectiveness([s])
        assert result.topic_reinforcements[0].retention_per_revision == 0.2

    def test_grade_distribution_sums(self, diverse_snapshots):
        result = compute_reinforcement_effectiveness(diverse_snapshots)
        total = sum(result.grade_distribution.values())
        assert total == 5

    def test_most_effective_sorted_descending(self, diverse_snapshots):
        result = compute_reinforcement_effectiveness(diverse_snapshots)
        scores = [t.reinforcement_score for t in result.most_effective]
        assert scores == sorted(scores, reverse=True)

    def test_total_revisions_summed(self, diverse_snapshots):
        result = compute_reinforcement_effectiveness(diverse_snapshots)
        expected = sum(s.revision_count for s in diverse_snapshots)
        assert result.total_revisions == expected

    def test_reinforcement_score_bounded(self):
        s = _snap(retention_score=0.5, confidence_score=0.5,
                  revision_count=3, performance_trend=0.0)
        result = compute_reinforcement_effectiveness([s])
        score = result.topic_reinforcements[0].reinforcement_score
        assert 0.0 <= score <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
#  10. Forgetting Trends Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestForgettingTrends:

    def test_empty_snapshots(self):
        result = compute_forgetting_trends([])
        assert result.topic_profiles == []
        assert result.avg_forgetting_probability == 0.0

    def test_safe_risk_for_high_stability(self):
        s = _snap(base_stability=100.0, days_since_last_revision=1.0,
                  forgetting_probability=0.01)
        result = compute_forgetting_trends([s])
        assert result.topic_profiles[0].risk == ForgettingRisk.SAFE

    def test_urgent_risk_for_near_forgotten(self):
        # Very low stability, long elapsed → nearly forgotten
        s = _snap(base_stability=0.5, days_since_last_revision=5.0,
                  forgetting_probability=0.95)
        result = compute_forgetting_trends([s])
        assert result.topic_profiles[0].risk == ForgettingRisk.URGENT

    def test_at_risk_detection(self):
        s = _snap(base_stability=2.0, days_since_last_revision=1.5,
                  forgetting_probability=0.75)
        result = compute_forgetting_trends([s])
        risk = result.topic_profiles[0].risk
        assert risk in (ForgettingRisk.AT_RISK, ForgettingRisk.URGENT)

    def test_fastest_decaying_contains_low_stability(self, diverse_snapshots):
        result = compute_forgetting_trends(diverse_snapshots)
        # The topic with base_stability=1.0 should be among fastest decaying
        fastest_ids = [p.topic_id for p in result.fastest_decaying]
        assert "t4" in fastest_ids  # base_stability=1.0

    def test_risk_distribution_sums(self, diverse_snapshots):
        result = compute_forgetting_trends(diverse_snapshots)
        total = sum(result.risk_distribution.values())
        assert total == 5

    def test_difficulty_correlation_bounded(self, diverse_snapshots):
        result = compute_forgetting_trends(diverse_snapshots)
        assert -1.0 <= result.difficulty_correlation <= 1.0

    def test_decay_velocity_all_negative(self, diverse_snapshots):
        result = compute_forgetting_trends(diverse_snapshots)
        for p in result.topic_profiles:
            assert p.decay_velocity < 0

    def test_days_until_forgotten_positive(self):
        s = _snap(base_stability=10.0, days_since_last_revision=0.5)
        result = compute_forgetting_trends([s])
        assert result.topic_profiles[0].days_until_forgotten > 0

    def test_urgent_topics_list(self):
        urgent = _snap("u1", base_stability=0.3, days_since_last_revision=3.0,
                       forgetting_probability=0.99)
        safe = _snap("s1", base_stability=100.0, days_since_last_revision=0.1,
                     forgetting_probability=0.01)
        result = compute_forgetting_trends([urgent, safe])
        urgent_ids = [p.topic_id for p in result.urgent_topics]
        assert "u1" in urgent_ids
        assert "s1" not in urgent_ids


# ═══════════════════════════════════════════════════════════════════════════════
#  11. Scheduling Efficiency Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchedulingEfficiency:

    def test_empty_snapshots(self):
        result = compute_scheduling_efficiency([])
        assert result.topic_efficiencies == []
        assert result.scheduling_health_score == 0.0

    def test_optimal_timing(self):
        # base_stability=10, target R=0.7 → optimal ≈ -10*ln(0.7) ≈ 3.57 days
        # elapsed=3.5 → gap_ratio ≈ 0.98 → OPTIMAL
        s = _snap(base_stability=10.0, days_since_last_revision=3.5,
                  retention_score=0.70)
        result = compute_scheduling_efficiency([s])
        assert result.topic_efficiencies[0].timing == TimingQuality.OPTIMAL

    def test_premature_timing(self):
        # optimal ≈ 3.57 days, elapsed=0.5 → gap_ratio ≈ 0.14 → PREMATURE
        s = _snap(base_stability=10.0, days_since_last_revision=0.5,
                  retention_score=0.95)
        result = compute_scheduling_efficiency([s])
        assert result.topic_efficiencies[0].timing == TimingQuality.PREMATURE

    def test_overdue_timing(self):
        # optimal ≈ 3.57 days, elapsed=15 → gap_ratio ≈ 4.2 → OVERDUE
        s = _snap(base_stability=10.0, days_since_last_revision=15.0,
                  retention_score=0.20)
        result = compute_scheduling_efficiency([s])
        assert result.topic_efficiencies[0].timing == TimingQuality.OVERDUE

    def test_late_timing(self):
        # optimal ≈ 3.57 days, elapsed=5.5 → gap_ratio ≈ 1.54 → LATE
        s = _snap(base_stability=10.0, days_since_last_revision=5.5,
                  retention_score=0.55)
        result = compute_scheduling_efficiency([s])
        assert result.topic_efficiencies[0].timing == TimingQuality.LATE

    def test_wasted_effort_detection(self):
        # Revised very early AND retention was still very high
        s = _snap(base_stability=10.0, days_since_last_revision=0.3,
                  retention_score=0.97)
        result = compute_scheduling_efficiency([s])
        assert result.topic_efficiencies[0].wasted_effort is True
        assert result.wasted_revision_count == 1

    def test_not_wasted_when_retention_low(self):
        s = _snap(base_stability=10.0, days_since_last_revision=0.3,
                  retention_score=0.50)
        result = compute_scheduling_efficiency([s])
        assert result.topic_efficiencies[0].wasted_effort is False

    def test_gap_ratio_calculation(self):
        s = _snap(base_stability=10.0, days_since_last_revision=7.0)
        result = compute_scheduling_efficiency([s])
        eff = result.topic_efficiencies[0]
        expected_opt = round(-10.0 * math.log(0.70), 4)
        expected_ratio = round(7.0 / expected_opt, 4)
        assert abs(eff.gap_ratio - expected_ratio) < 0.01

    def test_timing_distribution_sums(self, diverse_snapshots):
        result = compute_scheduling_efficiency(diverse_snapshots)
        total = sum(result.timing_distribution.values())
        assert total == 5

    def test_health_score_bounded(self, diverse_snapshots):
        result = compute_scheduling_efficiency(diverse_snapshots)
        assert 0.0 <= result.scheduling_health_score <= 1.0

    def test_zero_elapsed_not_division_error(self):
        s = _snap(base_stability=10.0, days_since_last_revision=0.0)
        result = compute_scheduling_efficiency([s])
        assert result.topic_efficiencies[0].gap_ratio == 0.0

    def test_optimal_rate_calculation(self):
        # 2 optimal, 1 overdue
        snaps = [
            _snap("a", base_stability=10.0, days_since_last_revision=3.5, retention_score=0.70),
            _snap("b", base_stability=10.0, days_since_last_revision=3.0, retention_score=0.75),
            _snap("c", base_stability=10.0, days_since_last_revision=20.0, retention_score=0.15),
        ]
        result = compute_scheduling_efficiency(snaps)
        assert result.optimal_rate > 0.5
        assert result.overdue_rate > 0.0


# ═══════════════════════════════════════════════════════════════════════════════
#  12. Advanced Analytics Report Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdvancedAnalyticsReport:

    def test_empty_snapshots(self):
        result = compute_advanced_analytics([])
        assert result.total_topics == 0
        assert result.retention_evolution.topic_evolutions == []
        assert result.stability_progression.topic_stabilities == []
        assert result.reinforcement_effectiveness.topic_reinforcements == []
        assert result.forgetting_trends.topic_profiles == []
        assert result.scheduling_efficiency.topic_efficiencies == []

    def test_all_sections_populated(self, diverse_snapshots):
        result = compute_advanced_analytics(diverse_snapshots)
        assert result.total_topics == 5
        assert len(result.retention_evolution.topic_evolutions) == 5
        assert len(result.stability_progression.topic_stabilities) == 5
        assert len(result.reinforcement_effectiveness.topic_reinforcements) == 5
        assert len(result.forgetting_trends.topic_profiles) == 5
        assert len(result.scheduling_efficiency.topic_efficiencies) == 5

    def test_report_has_explanations(self, diverse_snapshots):
        result = compute_advanced_analytics(diverse_snapshots)
        assert result.retention_evolution.explanation
        assert result.stability_progression.explanation
        assert result.reinforcement_effectiveness.explanation
        assert result.forgetting_trends.explanation
        assert result.scheduling_efficiency.explanation

    def test_report_consistency(self, diverse_snapshots):
        """All sections should agree on topic count."""
        result = compute_advanced_analytics(diverse_snapshots)
        assert result.total_topics == len(result.retention_evolution.topic_evolutions)
        assert result.total_topics == len(result.stability_progression.topic_stabilities)
        assert result.total_topics == len(result.reinforcement_effectiveness.topic_reinforcements)
        assert result.total_topics == len(result.forgetting_trends.topic_profiles)
        assert result.total_topics == len(result.scheduling_efficiency.topic_efficiencies)


# ═══════════════════════════════════════════════════════════════════════════════
#  Cross-Capability Invariant Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrossCapabilityInvariants:

    def test_decay_velocity_consistent_across_evolution_and_forgetting(self):
        """Retention evolution and forgetting trends should compute
        the same decay velocity for the same topic."""
        s = _snap(base_stability=10.0, days_since_last_revision=3.0)
        evo = compute_retention_evolution([s])
        forg = compute_forgetting_trends([s])
        assert evo.topic_evolutions[0].decay_velocity == forg.topic_profiles[0].decay_velocity

    def test_low_stability_triggers_both_fragile_and_risk(self):
        """Very low stability should appear as fragile in stability
        analysis AND at-risk/urgent in forgetting trends."""
        s = _snap(base_stability=0.5, days_since_last_revision=3.0,
                  forgetting_probability=0.95)
        stab = compute_stability_progression([s])
        forg = compute_forgetting_trends([s])
        assert stab.topic_stabilities[0].band == StabilityBand.FRAGILE
        assert forg.topic_profiles[0].risk in (ForgettingRisk.AT_RISK, ForgettingRisk.URGENT)

    def test_high_revision_low_retention_triggers_both_stagnation_and_diminishing(self):
        """Many revisions + low retention should be flagged as both
        stagnating (stability) and diminishing returns (reinforcement)."""
        s = _snap(base_stability=2.0, revision_count=10, retention_score=0.20)
        stab = compute_stability_progression([s])
        reinf = compute_reinforcement_effectiveness([s])
        assert stab.topic_stabilities[0].is_stagnating is True
        assert reinf.topic_reinforcements[0].is_diminishing is True

    def test_premature_timing_aligns_with_wasted_when_retention_high(self):
        """If scheduling says premature AND retention is 95%, it should
        also flag wasted effort."""
        s = _snap(base_stability=20.0, days_since_last_revision=0.5,
                  retention_score=0.95)
        sched = compute_scheduling_efficiency([s])
        assert sched.topic_efficiencies[0].timing == TimingQuality.PREMATURE
        assert sched.topic_efficiencies[0].wasted_effort is True
