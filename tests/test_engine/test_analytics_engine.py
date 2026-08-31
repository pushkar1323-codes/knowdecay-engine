"""
tests/test_engine/test_analytics_engine.py
───────────────────────────────────────────
Unit tests for the analytics engine — pure functions, NO database required.

Test categories:
  1.  Zone classification — retention → zone mapping
  2.  Retention summary — aggregation metrics
  3.  Hierarchical aggregation — chapter/module/subject summaries
  4.  Weak topic detection — threshold + severity + sorting
  5.  Weak topic clustering — grouping by hierarchy level
  6.  Retention heatmap — grid generation
  7.  Trend analysis — direction, slope, time windows
  8.  Retention distribution — histogram buckets
  9.  Master report — end-to-end analytics
  10. Edge cases — empty inputs, single topics, extremes
  11. Monotonicity — directional invariants
"""

import pytest
import uuid

from app.engine.analytics_engine import (
    AnalyticsReport,
    DistributionBucket,
    HeatmapCell,
    HeatmapRow,
    RetentionDistribution,
    RetentionHeatmap,
    RetentionHistoryPoint,
    RetentionSummary,
    RetentionZone,
    TopicSnapshot,
    TrendAnalysis,
    TrendDirection,
    TrendPoint,
    WeakTopic,
    WeakTopicCluster,
    WeaknessSeverity,
    aggregate_by_hierarchy,
    analyze_trend,
    classify_zone,
    cluster_weak_topics,
    compute_analytics_report,
    compute_distribution,
    compute_retention_summary,
    detect_weak_topics,
    generate_heatmap,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Test Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

def _snap(
    retention: float = 0.5,
    topic_id: object = None,
    topic_name: str = "Topic",
    difficulty: float = 0.5,
    urgency: float = 0.0,
    revision_count: int = 1,
    chapter_id: object = None,
    chapter_name: str = "Ch1",
    module_id: object = None,
    module_name: str = "Mod1",
    subject_id: object = None,
    subject_name: str = "Sub1",
    importance_weight: float = 1.0,
    days_since_last_revision: float = 1.0,
    performance_trend: float = 0.0,
) -> TopicSnapshot:
    """Create a TopicSnapshot for testing."""
    return TopicSnapshot(
        topic_id=topic_id or uuid.uuid4(),
        topic_name=topic_name,
        retention_score=retention,
        forgetting_probability=1.0 - retention,
        urgency_score=urgency,
        revision_count=revision_count,
        difficulty=difficulty,
        importance_weight=importance_weight,
        chapter_id=chapter_id or uuid.uuid4(),
        chapter_name=chapter_name,
        module_id=module_id or uuid.uuid4(),
        module_name=module_name,
        subject_id=subject_id or uuid.uuid4(),
        subject_name=subject_name,
        days_since_last_revision=days_since_last_revision,
        performance_trend=performance_trend,
    )


def _hierarchy_snapshots():
    """Create a set of snapshots spanning a realistic hierarchy."""
    ch1 = uuid.uuid4()
    ch2 = uuid.uuid4()
    mod1 = uuid.uuid4()
    mod2 = uuid.uuid4()
    sub1 = uuid.uuid4()

    return [
        # Chapter 1 (Module 1, Subject 1): mixed retention
        _snap(retention=0.90, chapter_id=ch1, chapter_name="Kinematics",
              module_id=mod1, module_name="Mechanics",
              subject_id=sub1, subject_name="Physics", topic_name="Velocity"),
        _snap(retention=0.45, chapter_id=ch1, chapter_name="Kinematics",
              module_id=mod1, module_name="Mechanics",
              subject_id=sub1, subject_name="Physics", topic_name="Acceleration"),
        _snap(retention=0.20, chapter_id=ch1, chapter_name="Kinematics",
              module_id=mod1, module_name="Mechanics",
              subject_id=sub1, subject_name="Physics", topic_name="Free Fall",
              urgency=0.8),

        # Chapter 2 (Module 2, Subject 1): mostly strong
        _snap(retention=0.85, chapter_id=ch2, chapter_name="Thermodynamics",
              module_id=mod2, module_name="Heat",
              subject_id=sub1, subject_name="Physics", topic_name="First Law"),
        _snap(retention=0.75, chapter_id=ch2, chapter_name="Thermodynamics",
              module_id=mod2, module_name="Heat",
              subject_id=sub1, subject_name="Physics", topic_name="Entropy"),
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  1. Zone Classification
# ═══════════════════════════════════════════════════════════════════════════════

class TestZoneClassification:
    def test_mastered(self):
        assert classify_zone(0.90) == RetentionZone.MASTERED

    def test_strong(self):
        assert classify_zone(0.75) == RetentionZone.STRONG

    def test_moderate(self):
        assert classify_zone(0.55) == RetentionZone.MODERATE

    def test_weak(self):
        assert classify_zone(0.35) == RetentionZone.WEAK

    def test_critical(self):
        assert classify_zone(0.10) == RetentionZone.CRITICAL

    def test_boundary_mastered(self):
        assert classify_zone(0.85) == RetentionZone.MASTERED

    def test_boundary_strong(self):
        assert classify_zone(0.70) == RetentionZone.STRONG

    def test_boundary_moderate(self):
        assert classify_zone(0.50) == RetentionZone.MODERATE

    def test_boundary_weak(self):
        assert classify_zone(0.30) == RetentionZone.WEAK

    def test_zero(self):
        assert classify_zone(0.0) == RetentionZone.CRITICAL

    def test_one(self):
        assert classify_zone(1.0) == RetentionZone.MASTERED

    def test_clamping_above_one(self):
        assert classify_zone(1.5) == RetentionZone.MASTERED

    def test_clamping_below_zero(self):
        assert classify_zone(-0.5) == RetentionZone.CRITICAL


# ═══════════════════════════════════════════════════════════════════════════════
#  2. Retention Summary
# ═══════════════════════════════════════════════════════════════════════════════

class TestRetentionSummary:
    def test_basic_aggregation(self):
        snaps = [_snap(retention=0.8), _snap(retention=0.4), _snap(retention=0.6)]
        s = compute_retention_summary(snaps)
        assert s.topic_count == 3
        assert s.min_retention == 0.4
        assert s.max_retention == 0.8
        assert 0.5 <= s.mean_retention <= 0.7

    def test_empty_snapshots(self):
        s = compute_retention_summary([])
        assert s.topic_count == 0
        assert s.mean_retention == 0.0
        assert s.zone == RetentionZone.CRITICAL
        assert "No topics" in s.summary

    def test_single_topic(self):
        s = compute_retention_summary([_snap(retention=0.75)])
        assert s.topic_count == 1
        assert s.mean_retention == 0.75
        assert s.median_retention == 0.75
        assert s.std_retention == 0.0

    def test_weak_count(self):
        snaps = [_snap(retention=0.2), _snap(retention=0.3), _snap(retention=0.8)]
        s = compute_retention_summary(snaps, weak_threshold=0.5)
        assert s.weak_count == 2

    def test_critical_count(self):
        snaps = [_snap(retention=0.1), _snap(retention=0.2), _snap(retention=0.8)]
        s = compute_retention_summary(snaps, critical_threshold=0.3)
        assert s.critical_count == 2

    def test_zone_distribution(self):
        snaps = [_snap(retention=0.9), _snap(retention=0.5), _snap(retention=0.1)]
        s = compute_retention_summary(snaps)
        assert s.zone_distribution["mastered"] == 1
        assert s.zone_distribution["moderate"] == 1
        assert s.zone_distribution["critical"] == 1

    def test_importance_weighted_mean(self):
        """Higher importance topics should pull the mean toward them."""
        snaps = [
            _snap(retention=0.9, importance_weight=10.0),
            _snap(retention=0.1, importance_weight=1.0),
        ]
        s = compute_retention_summary(snaps)
        # Weighted mean should be much closer to 0.9 than 0.5
        assert s.mean_retention > 0.7

    def test_summary_string_contains_count(self):
        snaps = [_snap(retention=0.5)] * 5
        s = compute_retention_summary(snaps)
        assert "5 topics" in s.summary


# ═══════════════════════════════════════════════════════════════════════════════
#  3. Hierarchical Aggregation
# ═══════════════════════════════════════════════════════════════════════════════

class TestHierarchicalAggregation:
    def test_chapter_grouping(self):
        snaps = _hierarchy_snapshots()
        ch_sum, mod_sum, sub_sum = aggregate_by_hierarchy(snaps)
        assert len(ch_sum) == 2   # Two chapters
        assert len(mod_sum) == 2  # Two modules
        assert len(sub_sum) == 1  # One subject

    def test_chapter_topic_counts(self):
        snaps = _hierarchy_snapshots()
        ch_sum, _, _ = aggregate_by_hierarchy(snaps)
        counts = sorted([s.topic_count for s in ch_sum])
        assert counts == [2, 3]

    def test_subject_aggregates_all(self):
        snaps = _hierarchy_snapshots()
        _, _, sub_sum = aggregate_by_hierarchy(snaps)
        assert sub_sum[0].topic_count == 5

    def test_module_names_preserved(self):
        snaps = _hierarchy_snapshots()
        _, mod_sum, _ = aggregate_by_hierarchy(snaps)
        names = {s.level_name for s in mod_sum}
        assert "Mechanics" in names
        assert "Heat" in names


# ═══════════════════════════════════════════════════════════════════════════════
#  4. Weak Topic Detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeakTopicDetection:
    def test_detects_below_threshold(self):
        snaps = [_snap(retention=0.2), _snap(retention=0.8)]
        weak = detect_weak_topics(snaps, weak_threshold=0.5)
        assert len(weak) == 1
        assert weak[0].retention_score == 0.2

    def test_no_weak_topics(self):
        snaps = [_snap(retention=0.8), _snap(retention=0.9)]
        weak = detect_weak_topics(snaps, weak_threshold=0.5)
        assert len(weak) == 0

    def test_sorted_worst_first(self):
        snaps = [_snap(retention=0.4), _snap(retention=0.1), _snap(retention=0.3)]
        weak = detect_weak_topics(snaps, weak_threshold=0.5)
        assert weak[0].retention_score == 0.1
        assert weak[1].retention_score == 0.3
        assert weak[2].retention_score == 0.4

    def test_severity_critical(self):
        snaps = [_snap(retention=0.05, urgency=0.8)]
        weak = detect_weak_topics(snaps)
        assert weak[0].severity == WeaknessSeverity.CRITICAL

    def test_severity_severe(self):
        snaps = [_snap(retention=0.15)]
        weak = detect_weak_topics(snaps)
        assert weak[0].severity == WeaknessSeverity.SEVERE

    def test_severity_moderate(self):
        snaps = [_snap(retention=0.32)]
        weak = detect_weak_topics(snaps)
        assert weak[0].severity == WeaknessSeverity.MODERATE

    def test_severity_mild(self):
        snaps = [_snap(retention=0.45)]
        weak = detect_weak_topics(snaps)
        assert weak[0].severity == WeaknessSeverity.MILD

    def test_reason_contains_retention(self):
        snaps = [_snap(retention=0.1)]
        weak = detect_weak_topics(snaps)
        assert "10%" in weak[0].reason or "0%" in weak[0].reason

    def test_reason_mentions_high_difficulty(self):
        snaps = [_snap(retention=0.2, difficulty=0.9)]
        weak = detect_weak_topics(snaps)
        assert "difficulty" in weak[0].reason.lower()

    def test_reason_mentions_never_revised(self):
        snaps = [_snap(retention=0.2, revision_count=0)]
        weak = detect_weak_topics(snaps)
        assert "never revised" in weak[0].reason.lower()


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Weak Topic Clustering
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeakTopicClustering:
    def test_clusters_by_chapter(self):
        snaps = [
            _snap(retention=0.2, chapter_name="Ch1"),
            _snap(retention=0.3, chapter_name="Ch1"),
            _snap(retention=0.1, chapter_name="Ch2"),
        ]
        weak = detect_weak_topics(snaps)
        clusters = cluster_weak_topics(weak, cluster_by="chapter")
        assert len(clusters) == 2

    def test_cluster_sorted_worst_first(self):
        snaps = [
            _snap(retention=0.4, chapter_name="Ch1"),
            _snap(retention=0.1, chapter_name="Ch2"),
        ]
        weak = detect_weak_topics(snaps)
        clusters = cluster_weak_topics(weak)
        assert clusters[0].mean_retention < clusters[1].mean_retention

    def test_cluster_severity_is_worst(self):
        snaps = [
            _snap(retention=0.05, urgency=0.8, chapter_name="Ch1"),
            _snap(retention=0.4, chapter_name="Ch1"),
        ]
        weak = detect_weak_topics(snaps)
        clusters = cluster_weak_topics(weak)
        assert clusters[0].severity == WeaknessSeverity.CRITICAL

    def test_cluster_recommendation_urgent(self):
        snaps = [_snap(retention=0.05, urgency=0.8, chapter_name="Ch1")]
        weak = detect_weak_topics(snaps)
        clusters = cluster_weak_topics(weak)
        assert "URGENT" in clusters[0].recommendation

    def test_empty_weak_list(self):
        clusters = cluster_weak_topics([])
        assert len(clusters) == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  6. Retention Heatmap
# ═══════════════════════════════════════════════════════════════════════════════

class TestRetentionHeatmap:
    def test_groups_by_chapter(self):
        snaps = _hierarchy_snapshots()
        heatmap = generate_heatmap(snaps, group_by="chapter")
        assert len(heatmap.rows) == 2
        assert heatmap.total_topics == 5

    def test_groups_by_module(self):
        snaps = _hierarchy_snapshots()
        heatmap = generate_heatmap(snaps, group_by="module")
        assert len(heatmap.rows) == 2

    def test_cells_have_zones(self):
        snaps = _hierarchy_snapshots()
        heatmap = generate_heatmap(snaps)
        for row in heatmap.rows:
            for cell in row.cells:
                assert isinstance(cell.zone, RetentionZone)

    def test_cells_sorted_by_retention(self):
        snaps = _hierarchy_snapshots()
        heatmap = generate_heatmap(snaps)
        for row in heatmap.rows:
            retentions = [c.retention for c in row.cells]
            assert retentions == sorted(retentions)

    def test_rows_sorted_worst_first(self):
        snaps = _hierarchy_snapshots()
        heatmap = generate_heatmap(snaps)
        means = [r.mean_retention for r in heatmap.rows]
        assert means == sorted(means)

    def test_global_mean(self):
        snaps = [_snap(retention=0.5), _snap(retention=0.7)]
        heatmap = generate_heatmap(snaps)
        assert 0.55 <= heatmap.global_mean <= 0.65

    def test_empty_snapshots(self):
        heatmap = generate_heatmap([])
        assert heatmap.total_topics == 0
        assert len(heatmap.rows) == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  7. Trend Analysis
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrendAnalysis:
    def test_improving_trend(self):
        history = [
            RetentionHistoryPoint(timestamp_days_ago=7.0, retention_score=0.3),
            RetentionHistoryPoint(timestamp_days_ago=3.0, retention_score=0.5),
            RetentionHistoryPoint(timestamp_days_ago=0.0, retention_score=0.8),
        ]
        trend = analyze_trend(history)
        assert trend.direction == TrendDirection.IMPROVING
        assert trend.slope > 0

    def test_declining_trend(self):
        history = [
            RetentionHistoryPoint(timestamp_days_ago=7.0, retention_score=0.9),
            RetentionHistoryPoint(timestamp_days_ago=3.0, retention_score=0.6),
            RetentionHistoryPoint(timestamp_days_ago=0.0, retention_score=0.3),
        ]
        trend = analyze_trend(history)
        assert trend.direction == TrendDirection.DECLINING
        assert trend.slope < 0

    def test_stable_trend(self):
        history = [
            RetentionHistoryPoint(timestamp_days_ago=7.0, retention_score=0.70),
            RetentionHistoryPoint(timestamp_days_ago=3.0, retention_score=0.71),
            RetentionHistoryPoint(timestamp_days_ago=0.0, retention_score=0.70),
        ]
        trend = analyze_trend(history)
        assert trend.direction == TrendDirection.STABLE

    def test_empty_history(self):
        trend = analyze_trend([])
        assert trend.direction == TrendDirection.STABLE
        assert trend.slope == 0.0
        assert "No history" in trend.explanation

    def test_single_point(self):
        history = [RetentionHistoryPoint(timestamp_days_ago=0.0, retention_score=0.6)]
        trend = analyze_trend(history)
        assert trend.direction == TrendDirection.STABLE
        assert trend.current_mean == 0.6

    def test_trend_points_generated(self):
        history = [
            RetentionHistoryPoint(timestamp_days_ago=0.0, retention_score=0.8),
            RetentionHistoryPoint(timestamp_days_ago=2.0, retention_score=0.6),
            RetentionHistoryPoint(timestamp_days_ago=5.0, retention_score=0.4),
        ]
        trend = analyze_trend(history)
        assert len(trend.trend_points) > 0

    def test_explanation_contains_direction(self):
        history = [
            RetentionHistoryPoint(timestamp_days_ago=7.0, retention_score=0.3),
            RetentionHistoryPoint(timestamp_days_ago=0.0, retention_score=0.8),
        ]
        trend = analyze_trend(history)
        assert "improving" in trend.explanation.lower() or trend.slope > 0


# ═══════════════════════════════════════════════════════════════════════════════
#  8. Retention Distribution
# ═══════════════════════════════════════════════════════════════════════════════

class TestRetentionDistribution:
    def test_basic_distribution(self):
        snaps = [_snap(retention=r / 10.0) for r in range(11)]  # 0.0 to 1.0
        dist = compute_distribution(snaps)
        assert dist.total_topics == 11
        assert len(dist.buckets) == 10

    def test_total_count_matches(self):
        snaps = [_snap(retention=0.5)] * 20
        dist = compute_distribution(snaps)
        total = sum(b.count for b in dist.buckets)
        assert total == 20

    def test_percentages_sum_to_100(self):
        snaps = [_snap(retention=r / 10.0) for r in range(10)]
        dist = compute_distribution(snaps)
        total_pct = sum(b.percentage for b in dist.buckets)
        assert abs(total_pct - 100.0) < 0.1

    def test_empty_distribution(self):
        dist = compute_distribution([])
        assert dist.total_topics == 0
        assert len(dist.buckets) == 0

    def test_mean_and_median(self):
        snaps = [_snap(retention=0.2), _snap(retention=0.4), _snap(retention=0.6)]
        dist = compute_distribution(snaps)
        assert 0.35 <= dist.mean <= 0.45
        assert dist.median == 0.4

    def test_buckets_have_zones(self):
        snaps = [_snap(retention=0.5)]
        dist = compute_distribution(snaps)
        for b in dist.buckets:
            assert isinstance(b.zone, RetentionZone)


# ═══════════════════════════════════════════════════════════════════════════════
#  9. Master Report
# ═══════════════════════════════════════════════════════════════════════════════

class TestMasterReport:
    def test_report_structure(self):
        snaps = _hierarchy_snapshots()
        report = compute_analytics_report(snaps)
        assert isinstance(report, AnalyticsReport)
        assert report.total_topics == 5

    def test_report_has_all_summaries(self):
        snaps = _hierarchy_snapshots()
        report = compute_analytics_report(snaps)
        assert len(report.chapter_summaries) == 2
        assert len(report.module_summaries) == 2
        assert len(report.subject_summaries) == 1
        assert report.global_summary.topic_count == 5

    def test_report_weak_detection(self):
        snaps = _hierarchy_snapshots()  # has topics at 0.20 and 0.45
        report = compute_analytics_report(snaps)
        assert report.total_weak >= 2

    def test_report_heatmap_present(self):
        snaps = _hierarchy_snapshots()
        report = compute_analytics_report(snaps)
        assert report.heatmap.total_topics == 5
        assert len(report.heatmap.rows) > 0

    def test_report_distribution_present(self):
        snaps = _hierarchy_snapshots()
        report = compute_analytics_report(snaps)
        assert report.distribution.total_topics == 5
        assert len(report.distribution.buckets) > 0

    def test_empty_report(self):
        report = compute_analytics_report([])
        assert report.total_topics == 0
        assert report.total_weak == 0
        assert report.global_summary.topic_count == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  10. Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_all_zero_retention(self):
        snaps = [_snap(retention=0.0) for _ in range(5)]
        s = compute_retention_summary(snaps)
        assert s.mean_retention == 0.0
        assert s.zone == RetentionZone.CRITICAL
        assert s.weak_count == 5

    def test_all_perfect_retention(self):
        snaps = [_snap(retention=1.0) for _ in range(5)]
        s = compute_retention_summary(snaps)
        assert s.mean_retention == 1.0
        assert s.zone == RetentionZone.MASTERED
        assert s.weak_count == 0

    def test_single_topic_full_report(self):
        snaps = [_snap(retention=0.6)]
        report = compute_analytics_report(snaps)
        assert report.total_topics == 1
        assert report.global_summary.topic_count == 1

    def test_identical_retentions(self):
        snaps = [_snap(retention=0.5) for _ in range(10)]
        s = compute_retention_summary(snaps)
        assert s.std_retention == 0.0
        assert s.mean_retention == 0.5

    def test_extreme_importance_weight(self):
        snaps = [
            _snap(retention=0.1, importance_weight=100.0),
            _snap(retention=0.9, importance_weight=0.01),
        ]
        s = compute_retention_summary(snaps)
        # Should be very close to 0.1 due to weight
        assert s.mean_retention < 0.2


# ═══════════════════════════════════════════════════════════════════════════════
#  11. Monotonicity Invariants
# ═══════════════════════════════════════════════════════════════════════════════

class TestMonotonicity:
    def test_more_weak_topics_lower_threshold(self):
        snaps = [_snap(retention=r / 10.0) for r in range(10)]
        weak_50 = detect_weak_topics(snaps, weak_threshold=0.50)
        weak_70 = detect_weak_topics(snaps, weak_threshold=0.70)
        assert len(weak_70) >= len(weak_50)

    def test_lower_retention_higher_weakness_severity(self):
        snaps_low = [_snap(retention=0.05, urgency=0.8)]
        snaps_med = [_snap(retention=0.40)]
        weak_low = detect_weak_topics(snaps_low)
        weak_med = detect_weak_topics(snaps_med)
        severity_order = [WeaknessSeverity.MILD, WeaknessSeverity.MODERATE,
                          WeaknessSeverity.SEVERE, WeaknessSeverity.CRITICAL]
        assert severity_order.index(weak_low[0].severity) >= severity_order.index(weak_med[0].severity)

    def test_adding_weak_topic_increases_weak_count(self):
        snaps_base = [_snap(retention=0.8)]
        snaps_with_weak = [_snap(retention=0.8), _snap(retention=0.1)]
        s1 = compute_retention_summary(snaps_base)
        s2 = compute_retention_summary(snaps_with_weak)
        assert s2.weak_count >= s1.weak_count

    def test_improving_all_retentions_improves_mean(self):
        snaps_low = [_snap(retention=0.3), _snap(retention=0.4)]
        snaps_high = [_snap(retention=0.7), _snap(retention=0.8)]
        s1 = compute_retention_summary(snaps_low)
        s2 = compute_retention_summary(snaps_high)
        assert s2.mean_retention > s1.mean_retention
