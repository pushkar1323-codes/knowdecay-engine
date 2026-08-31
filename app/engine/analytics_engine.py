"""
app/engine/analytics_engine.py
────────────────────────────────
Analytics intelligence engine — PURE FUNCTIONS, NO DB, NO I/O.

Answers the question: "How is the learner's knowledge distributed and evolving?"

This module receives pre-computed retention data (from the adaptive forgetting
engine via the service layer) and produces aggregated analytics, weak-topic
detection, retention heatmaps, and trend analysis.

Architecture
════════════
  Retention estimation  → adaptive_forgetting.py  (R = e^(-t/S_adaptive))
  Analytics aggregation → analytics_engine.py     (THIS MODULE)
  DB orchestration      → analytics_service.py    (service layer)

The analytics engine CONSUMES retention values — it never estimates retention.

Hierarchy
═════════
  Subject → Module → Chapter → Topic (leaf)
  Aggregation flows upward: Topic retention → Chapter avg → Module avg → Subject avg

Analytics Categories
════════════════════
  1. Retention Summary    — aggregated retention at any hierarchy level
  2. Weak Topic Detection — topics below threshold, clustered by severity
  3. Retention Heatmap    — 2D grid of topics × time bands with retention values
  4. Trend Analysis       — retention trajectory over time windows
  5. Distribution         — histogram of retention scores across topics

Design principles:
  • Every function is PURE — no DB, no I/O
  • All thresholds are configurable via keyword params
  • All outputs are visualization-ready (pre-formatted for charts/tables)
  • Explanations are always generated — no opaque numbers
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
#  Enums
# ═══════════════════════════════════════════════════════════════════════════════

class RetentionZone(str, Enum):
    """Retention health zone — maps retention score to a named band."""

    MASTERED = "mastered"        # ≥ 0.85
    STRONG = "strong"            # ≥ 0.70
    MODERATE = "moderate"        # ≥ 0.50
    WEAK = "weak"                # ≥ 0.30
    CRITICAL = "critical"        # < 0.30


class TrendDirection(str, Enum):
    """Retention trajectory over a time window."""

    IMPROVING = "improving"       # positive slope
    STABLE = "stable"             # near-zero slope
    DECLINING = "declining"       # negative slope


class WeaknessSeverity(str, Enum):
    """How severely a topic is underperforming."""

    MILD = "mild"               # slightly below threshold
    MODERATE = "moderate"       # significantly below threshold
    SEVERE = "severe"           # critically low retention
    CRITICAL = "critical"       # near-zero retention with high urgency


# ═══════════════════════════════════════════════════════════════════════════════
#  Data Transfer Objects — Input
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class TopicSnapshot:
    """
    A single topic's current state — pre-computed by the service layer.

    retention_score and forgetting_probability MUST come from the adaptive
    forgetting engine (R = e^(-t/S_adaptive)), NOT from stale persisted values.
    """

    topic_id: object                        # hashable identifier
    topic_name: str = ""

    # Pre-computed retention from adaptive forgetting engine
    retention_score: float = 0.0            # R(t) at query time
    forgetting_probability: float = 1.0     # 1 - R(t)

    # From memory state
    stability_score: float = 1.0            # S_adaptive
    base_stability: float = 1.0
    urgency_score: float = 0.0
    revision_count: int = 0
    confidence_score: float = 0.5
    performance_trend: float = 0.0

    # Topic metadata
    difficulty: float = 0.5
    importance_weight: float = 1.0

    # Hierarchy placement
    chapter_id: object = None
    chapter_name: str = ""
    module_id: object = None
    module_name: str = ""
    subject_id: object = None
    subject_name: str = ""

    # Time context
    days_since_last_revision: float = 0.0


@dataclass(frozen=True, slots=True)
class RetentionHistoryPoint:
    """A single data point in a topic's retention history timeline."""

    timestamp_days_ago: float               # 0 = now, positive = past
    retention_score: float                  # R at that time


# ═══════════════════════════════════════════════════════════════════════════════
#  Data Transfer Objects — Output
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class RetentionSummary:
    """Aggregated retention at a hierarchy level (chapter/module/subject)."""

    level: str                              # "chapter" | "module" | "subject" | "global"
    level_id: object                        # ID of the hierarchy entity
    level_name: str

    # Aggregated metrics
    mean_retention: float                   # weighted mean of topic retentions
    min_retention: float                    # worst topic
    max_retention: float                    # best topic
    median_retention: float
    std_retention: float                    # standard deviation (spread indicator)

    # Counts
    topic_count: int
    weak_count: int                         # topics below weak threshold
    critical_count: int                     # topics below critical threshold

    # Zone distribution
    zone: RetentionZone                     # zone based on mean retention
    zone_distribution: dict[str, int]       # count per zone

    # Explanation
    summary: str                            # human-readable summary


@dataclass(frozen=True, slots=True)
class WeakTopic:
    """A topic flagged as weak or underperforming."""

    topic_id: object
    topic_name: str
    retention_score: float
    forgetting_probability: float
    urgency_score: float
    difficulty: float
    revision_count: int
    performance_trend: float
    days_since_last_revision: float
    severity: WeaknessSeverity
    reason: str                             # human-readable explanation

    # Hierarchy context
    chapter_name: str = ""
    module_name: str = ""
    subject_name: str = ""


@dataclass(frozen=True, slots=True)
class WeakTopicCluster:
    """Group of weak topics within a single hierarchy unit."""

    cluster_id: object                      # chapter/module ID
    cluster_name: str
    cluster_level: str                      # "chapter" | "module"
    topics: list[WeakTopic]
    mean_retention: float
    severity: WeaknessSeverity              # worst severity in cluster
    recommendation: str


@dataclass(frozen=True, slots=True)
class HeatmapCell:
    """A single cell in the retention heatmap."""

    topic_id: object
    topic_name: str
    retention: float
    zone: RetentionZone
    urgency: float


@dataclass(frozen=True, slots=True)
class HeatmapRow:
    """A row in the heatmap (one hierarchy group)."""

    group_id: object
    group_name: str
    cells: list[HeatmapCell]
    mean_retention: float


@dataclass(frozen=True, slots=True)
class RetentionHeatmap:
    """Complete retention heatmap — visualization-ready."""

    rows: list[HeatmapRow]
    group_level: str                        # "chapter" | "module"
    total_topics: int
    global_mean: float


@dataclass(frozen=True, slots=True)
class TrendPoint:
    """A single point in a trend timeline."""

    window_label: str                       # "last_24h", "last_7d", etc.
    mean_retention: float
    topic_count: int


@dataclass(frozen=True, slots=True)
class TrendAnalysis:
    """Retention trend over time windows."""

    direction: TrendDirection
    slope: float                            # retention change per day
    current_mean: float
    trend_points: list[TrendPoint]
    explanation: str


@dataclass(frozen=True, slots=True)
class DistributionBucket:
    """One bucket in a retention histogram."""

    lower: float                            # inclusive
    upper: float                            # exclusive (except last bucket)
    count: int
    percentage: float
    zone: RetentionZone


@dataclass(frozen=True, slots=True)
class RetentionDistribution:
    """Histogram of retention scores across all topics."""

    buckets: list[DistributionBucket]
    total_topics: int
    mean: float
    median: float


@dataclass(frozen=True, slots=True)
class AnalyticsReport:
    """Complete analytics report — combines all analytics outputs."""

    # Hierarchy summaries
    subject_summaries: list[RetentionSummary]
    module_summaries: list[RetentionSummary]
    chapter_summaries: list[RetentionSummary]
    global_summary: RetentionSummary

    # Weak topics
    weak_topics: list[WeakTopic]
    weak_clusters: list[WeakTopicCluster]

    # Heatmap
    heatmap: RetentionHeatmap

    # Distribution
    distribution: RetentionDistribution

    # Totals
    total_topics: int
    total_weak: int
    total_critical: int


# ═══════════════════════════════════════════════════════════════════════════════
#  Default Configuration
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_WEAK_THRESHOLD: float = 0.50
DEFAULT_CRITICAL_THRESHOLD: float = 0.30
DEFAULT_MASTERED_THRESHOLD: float = 0.85
DEFAULT_STRONG_THRESHOLD: float = 0.70
DEFAULT_TREND_STABLE_BAND: float = 0.02    # slope within ±0.02/day = stable
DEFAULT_HISTOGRAM_BINS: int = 10


# ═══════════════════════════════════════════════════════════════════════════════
#  Zone Classification
# ═══════════════════════════════════════════════════════════════════════════════

def classify_zone(
    retention: float,
    *,
    mastered: float = DEFAULT_MASTERED_THRESHOLD,
    strong: float = DEFAULT_STRONG_THRESHOLD,
    weak: float = DEFAULT_WEAK_THRESHOLD,
    critical: float = DEFAULT_CRITICAL_THRESHOLD,
) -> RetentionZone:
    """Map a retention score to a named health zone."""
    r = _clamp01(retention)
    if r >= mastered:
        return RetentionZone.MASTERED
    elif r >= strong:
        return RetentionZone.STRONG
    elif r >= weak:
        return RetentionZone.MODERATE
    elif r >= critical:
        return RetentionZone.WEAK
    else:
        return RetentionZone.CRITICAL


def _zone_distribution(retentions: list[float]) -> dict[str, int]:
    """Count how many retention scores fall into each zone."""
    dist = {z.value: 0 for z in RetentionZone}
    for r in retentions:
        dist[classify_zone(r).value] += 1
    return dist


# ═══════════════════════════════════════════════════════════════════════════════
#  Statistical Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _weighted_mean(values: list[float], weights: list[float]) -> float:
    """Importance-weighted mean retention."""
    total_w = sum(weights)
    if total_w <= 0 or not values:
        return _mean(values)
    return sum(v * w for v, w in zip(values, weights)) / total_w


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2.0
    return s[mid]


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    variance = sum((v - m) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


# ═══════════════════════════════════════════════════════════════════════════════
#  1. Retention Summary — Hierarchical Aggregation
# ═══════════════════════════════════════════════════════════════════════════════

def compute_retention_summary(
    snapshots: list[TopicSnapshot],
    *,
    level: str = "global",
    level_id: object = None,
    level_name: str = "All Topics",
    weak_threshold: float = DEFAULT_WEAK_THRESHOLD,
    critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
) -> RetentionSummary:
    """
    Compute aggregated retention metrics for a group of topics.

    Uses importance_weight for weighted mean — more important topics
    contribute more to the aggregate score.
    """
    if not snapshots:
        return RetentionSummary(
            level=level, level_id=level_id, level_name=level_name,
            mean_retention=0.0, min_retention=0.0, max_retention=0.0,
            median_retention=0.0, std_retention=0.0,
            topic_count=0, weak_count=0, critical_count=0,
            zone=RetentionZone.CRITICAL,
            zone_distribution=_zone_distribution([]),
            summary="No topics available for analysis.",
        )

    retentions = [s.retention_score for s in snapshots]
    weights = [s.importance_weight for s in snapshots]

    mean_r = round(_weighted_mean(retentions, weights), 4)
    min_r = round(min(retentions), 4)
    max_r = round(max(retentions), 4)
    med_r = round(_median(retentions), 4)
    std_r = round(_std(retentions), 4)
    weak_count = sum(1 for r in retentions if r < weak_threshold)
    crit_count = sum(1 for r in retentions if r < critical_threshold)
    zone = classify_zone(mean_r)
    dist = _zone_distribution(retentions)

    # Generate summary
    n = len(snapshots)
    summary_parts = [f"{n} topics, mean retention {mean_r:.0%}"]
    if crit_count > 0:
        summary_parts.append(f"{crit_count} critical")
    if weak_count > 0:
        summary_parts.append(f"{weak_count} weak")
    if std_r > 0.2:
        summary_parts.append("high variance — uneven mastery")

    return RetentionSummary(
        level=level, level_id=level_id, level_name=level_name,
        mean_retention=mean_r, min_retention=min_r, max_retention=max_r,
        median_retention=med_r, std_retention=std_r,
        topic_count=n, weak_count=weak_count, critical_count=crit_count,
        zone=zone, zone_distribution=dist,
        summary="; ".join(summary_parts),
    )


def aggregate_by_hierarchy(
    snapshots: list[TopicSnapshot],
    *,
    weak_threshold: float = DEFAULT_WEAK_THRESHOLD,
    critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
) -> tuple[list[RetentionSummary], list[RetentionSummary], list[RetentionSummary]]:
    """
    Aggregate retention at all hierarchy levels: chapter → module → subject.

    Returns: (chapter_summaries, module_summaries, subject_summaries)
    """
    # Group by chapter
    chapters: dict[object, list[TopicSnapshot]] = {}
    chapter_names: dict[object, str] = {}
    for s in snapshots:
        key = s.chapter_id
        chapters.setdefault(key, []).append(s)
        if s.chapter_name:
            chapter_names[key] = s.chapter_name

    chapter_summaries = [
        compute_retention_summary(
            topics, level="chapter", level_id=cid,
            level_name=chapter_names.get(cid, ""),
            weak_threshold=weak_threshold,
            critical_threshold=critical_threshold,
        )
        for cid, topics in chapters.items()
    ]

    # Group by module
    modules: dict[object, list[TopicSnapshot]] = {}
    module_names: dict[object, str] = {}
    for s in snapshots:
        key = s.module_id
        modules.setdefault(key, []).append(s)
        if s.module_name:
            module_names[key] = s.module_name

    module_summaries = [
        compute_retention_summary(
            topics, level="module", level_id=mid,
            level_name=module_names.get(mid, ""),
            weak_threshold=weak_threshold,
            critical_threshold=critical_threshold,
        )
        for mid, topics in modules.items()
    ]

    # Group by subject
    subjects: dict[object, list[TopicSnapshot]] = {}
    subject_names: dict[object, str] = {}
    for s in snapshots:
        key = s.subject_id
        subjects.setdefault(key, []).append(s)
        if s.subject_name:
            subject_names[key] = s.subject_name

    subject_summaries = [
        compute_retention_summary(
            topics, level="subject", level_id=sid,
            level_name=subject_names.get(sid, ""),
            weak_threshold=weak_threshold,
            critical_threshold=critical_threshold,
        )
        for sid, topics in subjects.items()
    ]

    return chapter_summaries, module_summaries, subject_summaries


# ═══════════════════════════════════════════════════════════════════════════════
#  2. Weak Topic Detection
# ═══════════════════════════════════════════════════════════════════════════════

def _classify_weakness(
    retention: float,
    urgency: float,
    *,
    weak_threshold: float = DEFAULT_WEAK_THRESHOLD,
    critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
) -> WeaknessSeverity:
    """Classify how severely a topic is underperforming."""
    if retention < 0.10 and urgency > 0.5:
        return WeaknessSeverity.CRITICAL
    if retention < critical_threshold:
        return WeaknessSeverity.SEVERE
    if retention < weak_threshold * 0.7:
        return WeaknessSeverity.MODERATE
    return WeaknessSeverity.MILD


def _weak_reason(snap: TopicSnapshot, severity: WeaknessSeverity) -> str:
    """Generate human-readable explanation for weakness."""
    parts = []
    if severity == WeaknessSeverity.CRITICAL:
        parts.append(f"Retention critically low ({snap.retention_score:.0%})")
    elif severity == WeaknessSeverity.SEVERE:
        parts.append(f"Retention severely degraded ({snap.retention_score:.0%})")
    else:
        parts.append(f"Retention below threshold ({snap.retention_score:.0%})")

    if snap.days_since_last_revision > 14:
        parts.append(f"not revised in {snap.days_since_last_revision:.0f} days")
    if snap.difficulty > 0.7:
        parts.append(f"high difficulty ({snap.difficulty:.0%})")
    if snap.performance_trend < -0.3:
        parts.append("declining trend")
    if snap.revision_count == 0:
        parts.append("never revised")

    return "; ".join(parts)


def detect_weak_topics(
    snapshots: list[TopicSnapshot],
    *,
    weak_threshold: float = DEFAULT_WEAK_THRESHOLD,
    critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
) -> list[WeakTopic]:
    """
    Identify topics below the weak retention threshold.

    Returns a list sorted by retention ascending (worst first).
    """
    weak = []
    for s in snapshots:
        if s.retention_score < weak_threshold:
            severity = _classify_weakness(
                s.retention_score, s.urgency_score,
                weak_threshold=weak_threshold,
                critical_threshold=critical_threshold,
            )
            weak.append(WeakTopic(
                topic_id=s.topic_id,
                topic_name=s.topic_name,
                retention_score=s.retention_score,
                forgetting_probability=s.forgetting_probability,
                urgency_score=s.urgency_score,
                difficulty=s.difficulty,
                revision_count=s.revision_count,
                performance_trend=s.performance_trend,
                days_since_last_revision=s.days_since_last_revision,
                severity=severity,
                reason=_weak_reason(s, severity),
                chapter_name=s.chapter_name,
                module_name=s.module_name,
                subject_name=s.subject_name,
            ))

    # Sort: worst retention first
    weak.sort(key=lambda w: w.retention_score)
    return weak


def cluster_weak_topics(
    weak_topics: list[WeakTopic],
    *,
    cluster_by: str = "chapter",
) -> list[WeakTopicCluster]:
    """
    Group weak topics into clusters by hierarchy level.

    Each cluster gets a severity (worst topic in cluster) and recommendation.
    """
    groups: dict[tuple[object, str], list[WeakTopic]] = {}
    for w in weak_topics:
        if cluster_by == "module":
            key = (w.module_name, w.module_name)
        else:
            key = (w.chapter_name, w.chapter_name)
        groups.setdefault(key, []).append(w)

    clusters = []
    for (gid, gname), topics in groups.items():
        retentions = [t.retention_score for t in topics]
        mean_r = _mean(retentions)

        # Worst severity in cluster
        severity_order = [WeaknessSeverity.CRITICAL, WeaknessSeverity.SEVERE,
                          WeaknessSeverity.MODERATE, WeaknessSeverity.MILD]
        worst = WeaknessSeverity.MILD
        for sev in severity_order:
            if any(t.severity == sev for t in topics):
                worst = sev
                break

        # Recommendation
        if worst == WeaknessSeverity.CRITICAL:
            rec = f"URGENT: {len(topics)} topics in '{gname}' need immediate revision"
        elif worst == WeaknessSeverity.SEVERE:
            rec = f"HIGH PRIORITY: {len(topics)} topics in '{gname}' are severely weak"
        elif worst == WeaknessSeverity.MODERATE:
            rec = f"Schedule revision for {len(topics)} topics in '{gname}'"
        else:
            rec = f"Monitor {len(topics)} topics in '{gname}'"

        clusters.append(WeakTopicCluster(
            cluster_id=gid,
            cluster_name=gname,
            cluster_level=cluster_by,
            topics=topics,
            mean_retention=round(mean_r, 4),
            severity=worst,
            recommendation=rec,
        ))

    # Sort: worst cluster first
    clusters.sort(key=lambda c: c.mean_retention)
    return clusters


# ═══════════════════════════════════════════════════════════════════════════════
#  3. Retention Heatmap
# ═══════════════════════════════════════════════════════════════════════════════

def generate_heatmap(
    snapshots: list[TopicSnapshot],
    *,
    group_by: str = "chapter",
) -> RetentionHeatmap:
    """
    Generate a retention heatmap grouped by hierarchy level.

    Each row = one hierarchy group (chapter/module).
    Each cell = one topic with retention score, zone, and urgency.

    Output is visualization-ready for front-end rendering.
    """
    # Group snapshots
    groups: dict[tuple[object, str], list[TopicSnapshot]] = {}
    for s in snapshots:
        if group_by == "module":
            key = (s.module_id, s.module_name)
        else:
            key = (s.chapter_id, s.chapter_name)
        groups.setdefault(key, []).append(s)

    rows = []
    for (gid, gname), topics in groups.items():
        cells = [
            HeatmapCell(
                topic_id=s.topic_id,
                topic_name=s.topic_name,
                retention=round(s.retention_score, 4),
                zone=classify_zone(s.retention_score),
                urgency=round(s.urgency_score, 4),
            )
            for s in sorted(topics, key=lambda t: t.retention_score)
        ]
        mean_r = _mean([s.retention_score for s in topics])
        rows.append(HeatmapRow(
            group_id=gid,
            group_name=gname,
            cells=cells,
            mean_retention=round(mean_r, 4),
        ))

    # Sort rows: worst mean retention first
    rows.sort(key=lambda r: r.mean_retention)

    all_retentions = [s.retention_score for s in snapshots]
    return RetentionHeatmap(
        rows=rows,
        group_level=group_by,
        total_topics=len(snapshots),
        global_mean=round(_mean(all_retentions), 4),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  4. Trend Analysis
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_trend(
    history: list[RetentionHistoryPoint],
    *,
    stable_band: float = DEFAULT_TREND_STABLE_BAND,
) -> TrendAnalysis:
    """
    Analyze the retention trend from a time-series of retention data points.

    Uses linear regression to estimate slope (retention change per day).
    Points are ordered by timestamp_days_ago (0 = now, larger = older).

    The service layer is responsible for building the history from DB records.
    """
    if not history:
        return TrendAnalysis(
            direction=TrendDirection.STABLE,
            slope=0.0,
            current_mean=0.0,
            trend_points=[],
            explanation="No history available for trend analysis.",
        )

    if len(history) == 1:
        r = history[0].retention_score
        return TrendAnalysis(
            direction=TrendDirection.STABLE,
            slope=0.0,
            current_mean=round(r, 4),
            trend_points=[TrendPoint(
                window_label="current",
                mean_retention=round(r, 4),
                topic_count=1,
            )],
            explanation=f"Single data point at {r:.0%} — insufficient history for trend.",
        )

    # Linear regression: y = retention, x = days_ago (inverted so older = negative)
    xs = [-pt.timestamp_days_ago for pt in history]  # older → more negative
    ys = [pt.retention_score for pt in history]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    # Slope via least squares
    numer = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denom = sum((x - mean_x) ** 2 for x in xs)
    slope = (numer / denom) if denom > 0 else 0.0

    # Direction
    if slope > stable_band:
        direction = TrendDirection.IMPROVING
    elif slope < -stable_band:
        direction = TrendDirection.DECLINING
    else:
        direction = TrendDirection.STABLE

    # Build trend points from windows
    windows = [
        ("current", 0.0, 1.0),
        ("last_3d", 0.0, 3.0),
        ("last_7d", 0.0, 7.0),
        ("last_14d", 0.0, 14.0),
        ("last_30d", 0.0, 30.0),
    ]
    trend_points = []
    for label, lo, hi in windows:
        pts_in_window = [p for p in history if lo <= p.timestamp_days_ago <= hi]
        if pts_in_window:
            mean_r = _mean([p.retention_score for p in pts_in_window])
            trend_points.append(TrendPoint(
                window_label=label,
                mean_retention=round(mean_r, 4),
                topic_count=len(pts_in_window),
            ))

    current_mean = round(mean_y, 4)

    # Explanation
    if direction == TrendDirection.IMPROVING:
        exp = f"Retention improving at {slope:.4f}/day — consistent study is working"
    elif direction == TrendDirection.DECLINING:
        exp = f"Retention declining at {slope:.4f}/day — increased revision recommended"
    else:
        exp = f"Retention stable around {current_mean:.0%}"

    return TrendAnalysis(
        direction=direction,
        slope=round(slope, 6),
        current_mean=current_mean,
        trend_points=trend_points,
        explanation=exp,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Retention Distribution
# ═══════════════════════════════════════════════════════════════════════════════

def compute_distribution(
    snapshots: list[TopicSnapshot],
    *,
    num_bins: int = DEFAULT_HISTOGRAM_BINS,
) -> RetentionDistribution:
    """
    Compute a histogram of retention scores across all topics.

    Output is visualization-ready for bar chart / histogram rendering.
    """
    if not snapshots:
        return RetentionDistribution(
            buckets=[], total_topics=0, mean=0.0, median=0.0,
        )

    retentions = [s.retention_score for s in snapshots]
    n = len(retentions)
    bin_width = 1.0 / num_bins

    buckets = []
    for i in range(num_bins):
        lower = round(i * bin_width, 4)
        upper = round((i + 1) * bin_width, 4)
        # Last bucket is inclusive on upper
        if i == num_bins - 1:
            count = sum(1 for r in retentions if lower <= r <= upper)
        else:
            count = sum(1 for r in retentions if lower <= r < upper)
        pct = round(count / n * 100, 2) if n > 0 else 0.0
        zone = classify_zone((lower + upper) / 2)
        buckets.append(DistributionBucket(
            lower=lower, upper=upper, count=count,
            percentage=pct, zone=zone,
        ))

    return RetentionDistribution(
        buckets=buckets,
        total_topics=n,
        mean=round(_mean(retentions), 4),
        median=round(_median(retentions), 4),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  6. Master Analytics Report
# ═══════════════════════════════════════════════════════════════════════════════

def compute_analytics_report(
    snapshots: list[TopicSnapshot],
    *,
    weak_threshold: float = DEFAULT_WEAK_THRESHOLD,
    critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
    heatmap_group_by: str = "chapter",
) -> AnalyticsReport:
    """
    Master analytics computation — produces a complete report.

    All retention values in snapshots MUST be pre-computed by the service
    layer using the adaptive forgetting engine. This engine only aggregates
    and analyzes — it never estimates retention.

    Returns a full report with:
      • Hierarchical summaries (subject/module/chapter)
      • Weak topic detection and clustering
      • Retention heatmap
      • Distribution histogram
    """
    # 1. Hierarchy summaries
    ch_sum, mod_sum, sub_sum = aggregate_by_hierarchy(
        snapshots,
        weak_threshold=weak_threshold,
        critical_threshold=critical_threshold,
    )

    # 2. Global summary
    global_sum = compute_retention_summary(
        snapshots, level="global", level_name="All Topics",
        weak_threshold=weak_threshold,
        critical_threshold=critical_threshold,
    )

    # 3. Weak topic detection
    weak = detect_weak_topics(
        snapshots,
        weak_threshold=weak_threshold,
        critical_threshold=critical_threshold,
    )
    clusters = cluster_weak_topics(weak)

    # 4. Heatmap
    heatmap = generate_heatmap(snapshots, group_by=heatmap_group_by)

    # 5. Distribution
    dist = compute_distribution(snapshots)

    return AnalyticsReport(
        subject_summaries=sub_sum,
        module_summaries=mod_sum,
        chapter_summaries=ch_sum,
        global_summary=global_sum,
        weak_topics=weak,
        weak_clusters=clusters,
        heatmap=heatmap,
        distribution=dist,
        total_topics=len(snapshots),
        total_weak=len(weak),
        total_critical=sum(1 for w in weak if w.severity == WeaknessSeverity.CRITICAL),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  7. Retention Evolution — Forgetting Curve Projection
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class RetentionProjectionPoint:
    """A single point on the projected forgetting curve."""

    days_from_now: float
    projected_retention: float
    zone: RetentionZone


@dataclass(frozen=True, slots=True)
class TopicEvolution:
    """Retention evolution profile for a single topic."""

    topic_id: object
    topic_name: str
    current_retention: float
    current_zone: RetentionZone
    base_stability: float
    decay_velocity: float               # dR/dt at current time (negative)
    half_life_days: float               # days until R drops to 50%
    time_to_weak: float                 # days until R drops below weak threshold
    projection: list[RetentionProjectionPoint]
    chapter_name: str = ""
    module_name: str = ""


@dataclass(frozen=True, slots=True)
class RetentionEvolution:
    """Retention evolution analysis across all topics."""

    topic_evolutions: list[TopicEvolution]
    fastest_decaying: list[TopicEvolution]   # top topics losing retention fastest
    most_stable: list[TopicEvolution]        # top topics with slowest decay
    avg_decay_velocity: float
    avg_half_life: float
    topics_reaching_weak_in_7d: int          # count reaching weak threshold within a week
    explanation: str


def _project_retention(
    stability: float,
    current_elapsed: float,
    *,
    projection_days: tuple[float, ...] = (1, 3, 7, 14, 30),
    floor: float = 0.02,
) -> list[RetentionProjectionPoint]:
    """Project retention at future time points using R = e^(-t/S)."""
    s = max(stability, 0.1)
    points = []
    for d in projection_days:
        total_t = current_elapsed + d
        r = max(math.exp(-total_t / s), floor)
        points.append(RetentionProjectionPoint(
            days_from_now=d,
            projected_retention=round(r, 4),
            zone=classify_zone(r),
        ))
    return points


def _decay_velocity(stability: float, elapsed: float) -> float:
    """
    Compute instantaneous decay velocity dR/dt at current elapsed time.

    dR/dt = -1/S × e^(-t/S)  (always negative — retention is always falling)
    """
    s = max(stability, 0.1)
    return round(-math.exp(-elapsed / s) / s, 6)


def _time_to_threshold(stability: float, elapsed: float, threshold: float) -> float:
    """Days from NOW until retention drops below threshold.

    R(t_total) = e^(-t_total/S) = threshold
    t_total = -S × ln(threshold)
    remaining = t_total - elapsed
    """
    s = max(stability, 0.1)
    if threshold <= 0 or threshold >= 1:
        return 999.0
    t_total = -s * math.log(threshold)
    remaining = t_total - elapsed
    return round(max(remaining, 0.0), 4)


def compute_retention_evolution(
    snapshots: list[TopicSnapshot],
    *,
    weak_threshold: float = DEFAULT_WEAK_THRESHOLD,
    top_n: int = 5,
) -> RetentionEvolution:
    """
    Analyze how retention is evolving for each topic.

    For every topic, projects the forgetting curve forward and computes:
    - decay velocity (how fast retention is falling RIGHT NOW)
    - half-life (days until R = 50%)
    - time until weak threshold is crossed
    - future retention at 1/3/7/14/30 day projections

    All computed from the adaptive forgetting curve R = e^(-t/S_adaptive).
    """
    if not snapshots:
        return RetentionEvolution(
            topic_evolutions=[], fastest_decaying=[], most_stable=[],
            avg_decay_velocity=0.0, avg_half_life=0.0,
            topics_reaching_weak_in_7d=0,
            explanation="No topics available for evolution analysis.",
        )

    evolutions = []
    for s in snapshots:
        stability = s.base_stability
        elapsed = s.days_since_last_revision

        vel = _decay_velocity(stability, elapsed)
        hl = _time_to_threshold(stability, elapsed, 0.5)
        ttw = _time_to_threshold(stability, elapsed, weak_threshold)
        proj = _project_retention(stability, elapsed)

        evolutions.append(TopicEvolution(
            topic_id=s.topic_id,
            topic_name=s.topic_name,
            current_retention=s.retention_score,
            current_zone=classify_zone(s.retention_score),
            base_stability=stability,
            decay_velocity=vel,
            half_life_days=hl,
            time_to_weak=ttw,
            projection=proj,
            chapter_name=s.chapter_name,
            module_name=s.module_name,
        ))

    # Sort by decay velocity (most negative = fastest decay)
    by_decay = sorted(evolutions, key=lambda e: e.decay_velocity)
    fastest = by_decay[:top_n]
    most_stable = by_decay[-top_n:][::-1]

    velocities = [e.decay_velocity for e in evolutions]
    half_lives = [e.half_life_days for e in evolutions if e.half_life_days < 999]
    weak_7d = sum(1 for e in evolutions if e.time_to_weak <= 7.0)

    avg_vel = round(_mean(velocities), 6) if velocities else 0.0
    avg_hl = round(_mean(half_lives), 2) if half_lives else 0.0

    explanation_parts = [f"{len(evolutions)} topics analyzed"]
    if weak_7d > 0:
        explanation_parts.append(f"{weak_7d} will reach weak threshold within 7 days")
    if avg_hl > 0:
        explanation_parts.append(f"average half-life {avg_hl:.1f} days")

    return RetentionEvolution(
        topic_evolutions=evolutions,
        fastest_decaying=fastest,
        most_stable=most_stable,
        avg_decay_velocity=avg_vel,
        avg_half_life=avg_hl,
        topics_reaching_weak_in_7d=weak_7d,
        explanation="; ".join(explanation_parts),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  8. Stability Progression
# ═══════════════════════════════════════════════════════════════════════════════

class StabilityBand(str, Enum):
    """Stability health classification."""

    FRAGILE = "fragile"            # < 2 days
    DEVELOPING = "developing"      # 2–7 days
    MODERATE = "moderate"          # 7–21 days
    STRONG = "strong"              # 21–60 days
    ROBUST = "robust"              # > 60 days


@dataclass(frozen=True, slots=True)
class TopicStability:
    """Stability analysis for a single topic."""

    topic_id: object
    topic_name: str
    base_stability: float
    band: StabilityBand
    revision_count: int
    stability_per_revision: float       # base_stability / max(revision_count, 1)
    is_stagnating: bool                 # high revisions but low stability
    explanation: str
    chapter_name: str = ""


@dataclass(frozen=True, slots=True)
class StabilityProgression:
    """Stability progression analysis across all topics."""

    topic_stabilities: list[TopicStability]
    band_distribution: dict[str, int]
    mean_stability: float
    median_stability: float
    stagnating_topics: list[TopicStability]
    most_fragile: list[TopicStability]
    most_robust: list[TopicStability]
    avg_stability_per_revision: float
    explanation: str


def _classify_stability_band(stability: float) -> StabilityBand:
    if stability >= 60:
        return StabilityBand.ROBUST
    if stability >= 21:
        return StabilityBand.STRONG
    if stability >= 7:
        return StabilityBand.MODERATE
    if stability >= 2:
        return StabilityBand.DEVELOPING
    return StabilityBand.FRAGILE


def compute_stability_progression(
    snapshots: list[TopicSnapshot],
    *,
    stagnation_threshold_revisions: int = 5,
    stagnation_threshold_stability: float = 3.0,
    top_n: int = 5,
) -> StabilityProgression:
    """
    Analyze how memory stability has evolved across topics.

    Tracks:
    - stability band distribution (fragile → robust)
    - stability efficiency (stability gained per revision)
    - stagnation detection (many revisions but stability isn't growing)
    - most fragile and most robust topics
    """
    if not snapshots:
        return StabilityProgression(
            topic_stabilities=[], band_distribution={b.value: 0 for b in StabilityBand},
            mean_stability=0.0, median_stability=0.0,
            stagnating_topics=[], most_fragile=[], most_robust=[],
            avg_stability_per_revision=0.0,
            explanation="No topics available for stability analysis.",
        )

    stabilities = []
    stagnating = []

    for s in snapshots:
        stab = s.base_stability
        band = _classify_stability_band(stab)
        rev = max(s.revision_count, 1)
        spr = round(stab / rev, 4)

        is_stag = (s.revision_count >= stagnation_threshold_revisions
                   and stab < stagnation_threshold_stability)

        parts = [f"stability {stab:.1f}d ({band.value})"]
        if is_stag:
            parts.append(f"STAGNATING: {s.revision_count} revisions but only {stab:.1f}d stability")
        elif spr > 3:
            parts.append(f"efficient: {spr:.1f}d stability per revision")

        ts = TopicStability(
            topic_id=s.topic_id, topic_name=s.topic_name,
            base_stability=stab, band=band,
            revision_count=s.revision_count,
            stability_per_revision=spr,
            is_stagnating=is_stag,
            explanation="; ".join(parts),
            chapter_name=s.chapter_name,
        )
        stabilities.append(ts)
        if is_stag:
            stagnating.append(ts)

    # Band distribution
    dist = {b.value: 0 for b in StabilityBand}
    for ts in stabilities:
        dist[ts.band.value] += 1

    # Sort and slice
    by_stab = sorted(stabilities, key=lambda t: t.base_stability)
    most_fragile = by_stab[:top_n]
    most_robust = by_stab[-top_n:][::-1]

    stab_values = [t.base_stability for t in stabilities]
    spr_values = [t.stability_per_revision for t in stabilities]

    mean_s = round(_mean(stab_values), 2)
    med_s = round(_median(stab_values), 2)
    avg_spr = round(_mean(spr_values), 4)

    exp_parts = [f"{len(stabilities)} topics"]
    if stagnating:
        exp_parts.append(f"{len(stagnating)} stagnating")
    exp_parts.append(f"mean stability {mean_s:.1f}d")
    exp_parts.append(f"avg {avg_spr:.2f}d gained per revision")

    return StabilityProgression(
        topic_stabilities=stabilities,
        band_distribution=dist,
        mean_stability=mean_s,
        median_stability=med_s,
        stagnating_topics=stagnating,
        most_fragile=most_fragile,
        most_robust=most_robust,
        avg_stability_per_revision=avg_spr,
        explanation="; ".join(exp_parts),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  9. Reinforcement Effectiveness
# ═══════════════════════════════════════════════════════════════════════════════

class ReinforcementGrade(str, Enum):
    """How effectively revisions are building retention."""

    EXCELLENT = "excellent"        # high retention, good efficiency
    GOOD = "good"                  # solid retention per revision
    FAIR = "fair"                  # moderate efficiency
    POOR = "poor"                  # many revisions, low return
    INEFFECTIVE = "ineffective"    # revisions not helping


@dataclass(frozen=True, slots=True)
class TopicReinforcement:
    """Reinforcement analysis for a single topic."""

    topic_id: object
    topic_name: str
    revision_count: int
    retention_score: float
    confidence_score: float
    performance_trend: float
    retention_per_revision: float       # R / max(revision_count, 1)
    reinforcement_score: float          # composite efficiency metric
    grade: ReinforcementGrade
    is_diminishing: bool                # high revisions, low retention gain
    explanation: str


@dataclass(frozen=True, slots=True)
class ReinforcementEffectiveness:
    """Reinforcement analysis across all topics."""

    topic_reinforcements: list[TopicReinforcement]
    grade_distribution: dict[str, int]
    mean_retention_per_revision: float
    mean_reinforcement_score: float
    diminishing_return_topics: list[TopicReinforcement]
    most_effective: list[TopicReinforcement]
    least_effective: list[TopicReinforcement]
    total_revisions: int
    explanation: str


def _compute_reinforcement_score(
    retention: float,
    confidence: float,
    revision_count: int,
    performance_trend: float,
) -> float:
    """
    Composite reinforcement effectiveness score (0–1).

    Measures how effectively revisions are building durable retention.

    Formula:
        score = (0.4 × retention + 0.2 × confidence + 0.2 × efficiency + 0.2 × trend_bonus)

    Where efficiency = min(retention / max(revision_count, 1), 1.0)
          trend_bonus = (performance_trend + 1) / 2   (normalised to 0–1)
    """
    r = _clamp01(retention)
    c = _clamp01(confidence)
    eff = min(r / max(revision_count, 1), 1.0) if revision_count > 0 else r
    t_bonus = _clamp01((performance_trend + 1.0) / 2.0)
    return round(_clamp01(0.4 * r + 0.2 * c + 0.2 * eff + 0.2 * t_bonus), 4)


def _grade_reinforcement(score: float) -> ReinforcementGrade:
    if score >= 0.80:
        return ReinforcementGrade.EXCELLENT
    if score >= 0.60:
        return ReinforcementGrade.GOOD
    if score >= 0.40:
        return ReinforcementGrade.FAIR
    if score >= 0.20:
        return ReinforcementGrade.POOR
    return ReinforcementGrade.INEFFECTIVE


def compute_reinforcement_effectiveness(
    snapshots: list[TopicSnapshot],
    *,
    diminishing_threshold_revisions: int = 5,
    diminishing_threshold_retention: float = 0.40,
    top_n: int = 5,
) -> ReinforcementEffectiveness:
    """
    Analyze how effectively revisions are building retention.

    Tracks:
    - retention gained per revision
    - reinforcement quality score per topic
    - diminishing returns detection (many revisions, still low retention)
    - grade distribution across topics
    """
    if not snapshots:
        return ReinforcementEffectiveness(
            topic_reinforcements=[], grade_distribution={g.value: 0 for g in ReinforcementGrade},
            mean_retention_per_revision=0.0, mean_reinforcement_score=0.0,
            diminishing_return_topics=[], most_effective=[], least_effective=[],
            total_revisions=0,
            explanation="No topics available for reinforcement analysis.",
        )

    reinforcements = []
    diminishing = []

    for s in snapshots:
        rev = max(s.revision_count, 1)
        rpr = round(s.retention_score / rev, 4)
        rs = _compute_reinforcement_score(
            s.retention_score, s.confidence_score,
            s.revision_count, s.performance_trend,
        )
        grade = _grade_reinforcement(rs)
        is_dim = (s.revision_count >= diminishing_threshold_revisions
                  and s.retention_score < diminishing_threshold_retention)

        parts = [f"grade={grade.value}, {s.revision_count} revisions → R={s.retention_score:.0%}"]
        if is_dim:
            parts.append("DIMINISHING RETURNS: many revisions but retention remains low")
        if s.performance_trend < -0.3:
            parts.append("performance declining despite revisions")

        tr = TopicReinforcement(
            topic_id=s.topic_id, topic_name=s.topic_name,
            revision_count=s.revision_count,
            retention_score=s.retention_score,
            confidence_score=s.confidence_score,
            performance_trend=s.performance_trend,
            retention_per_revision=rpr,
            reinforcement_score=rs,
            grade=grade,
            is_diminishing=is_dim,
            explanation="; ".join(parts),
        )
        reinforcements.append(tr)
        if is_dim:
            diminishing.append(tr)

    # Grade distribution
    dist = {g.value: 0 for g in ReinforcementGrade}
    for tr in reinforcements:
        dist[tr.grade.value] += 1

    # Sort by reinforcement score
    by_score = sorted(reinforcements, key=lambda t: t.reinforcement_score, reverse=True)
    most_eff = by_score[:top_n]
    least_eff = by_score[-top_n:][::-1]

    rpr_values = [t.retention_per_revision for t in reinforcements]
    rs_values = [t.reinforcement_score for t in reinforcements]
    total_rev = sum(s.revision_count for s in snapshots)

    exp_parts = [f"{len(reinforcements)} topics, {total_rev} total revisions"]
    if diminishing:
        exp_parts.append(f"{len(diminishing)} showing diminishing returns")
    exp_parts.append(f"mean reinforcement score {_mean(rs_values):.2f}")

    return ReinforcementEffectiveness(
        topic_reinforcements=reinforcements,
        grade_distribution=dist,
        mean_retention_per_revision=round(_mean(rpr_values), 4),
        mean_reinforcement_score=round(_mean(rs_values), 4),
        diminishing_return_topics=diminishing,
        most_effective=most_eff,
        least_effective=least_eff,
        total_revisions=total_rev,
        explanation="; ".join(exp_parts),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  10. Forgetting Trends
# ═══════════════════════════════════════════════════════════════════════════════

class ForgettingRisk(str, Enum):
    """How urgently a topic's forgetting needs attention."""

    SAFE = "safe"                  # slow decay, well retained
    WATCH = "watch"                # moderate decay
    AT_RISK = "at_risk"            # fast decay, needs revision soon
    URGENT = "urgent"              # very fast decay, near-forgotten


@dataclass(frozen=True, slots=True)
class TopicForgettingProfile:
    """Forgetting analysis for a single topic."""

    topic_id: object
    topic_name: str
    forgetting_probability: float
    decay_velocity: float               # dR/dt — how fast it's decaying
    base_stability: float
    difficulty: float
    risk: ForgettingRisk
    days_until_forgotten: float         # days until R < 0.3
    explanation: str
    chapter_name: str = ""
    module_name: str = ""


@dataclass(frozen=True, slots=True)
class ForgettingTrends:
    """Forgetting trend analysis across all topics."""

    topic_profiles: list[TopicForgettingProfile]
    risk_distribution: dict[str, int]
    avg_forgetting_probability: float
    avg_decay_velocity: float
    fastest_decaying: list[TopicForgettingProfile]
    difficulty_correlation: float       # correlation between difficulty and decay rate
    urgent_topics: list[TopicForgettingProfile]
    explanation: str


def _classify_forgetting_risk(
    forgetting_prob: float,
    decay_velocity: float,
    days_until_forgotten: float,
) -> ForgettingRisk:
    if days_until_forgotten < 1:
        return ForgettingRisk.URGENT
    if days_until_forgotten < 3 or forgetting_prob > 0.7:
        return ForgettingRisk.AT_RISK
    if forgetting_prob > 0.4 or decay_velocity < -0.1:
        return ForgettingRisk.WATCH
    return ForgettingRisk.SAFE


def _pearson_correlation(xs: list[float], ys: list[float]) -> float:
    """Simple Pearson correlation coefficient."""
    n = len(xs)
    if n < 3:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    numer = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx * dy == 0:
        return 0.0
    return round(numer / (dx * dy), 4)


def compute_forgetting_trends(
    snapshots: list[TopicSnapshot],
    *,
    critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
    top_n: int = 5,
) -> ForgettingTrends:
    """
    Analyze forgetting patterns across topics.

    Tracks:
    - decay velocity per topic (how fast retention is falling)
    - risk classification (safe → urgent)
    - time until forgotten for each topic
    - correlation between difficulty and forgetting speed
    """
    if not snapshots:
        return ForgettingTrends(
            topic_profiles=[], risk_distribution={r.value: 0 for r in ForgettingRisk},
            avg_forgetting_probability=0.0, avg_decay_velocity=0.0,
            fastest_decaying=[], difficulty_correlation=0.0,
            urgent_topics=[],
            explanation="No topics available for forgetting analysis.",
        )

    profiles = []
    urgent = []

    for s in snapshots:
        vel = _decay_velocity(s.base_stability, s.days_since_last_revision)
        dtf = _time_to_threshold(s.base_stability, s.days_since_last_revision, critical_threshold)
        risk = _classify_forgetting_risk(s.forgetting_probability, vel, dtf)

        parts = [f"P(forgotten)={s.forgetting_probability:.0%}, risk={risk.value}"]
        if dtf < 3:
            parts.append(f"reaching critical in {dtf:.1f}d")
        if s.difficulty > 0.7:
            parts.append("high difficulty accelerates decay")

        tp = TopicForgettingProfile(
            topic_id=s.topic_id, topic_name=s.topic_name,
            forgetting_probability=s.forgetting_probability,
            decay_velocity=vel,
            base_stability=s.base_stability,
            difficulty=s.difficulty,
            risk=risk,
            days_until_forgotten=dtf,
            explanation="; ".join(parts),
            chapter_name=s.chapter_name,
            module_name=s.module_name,
        )
        profiles.append(tp)
        if risk == ForgettingRisk.URGENT:
            urgent.append(tp)

    # Risk distribution
    dist = {r.value: 0 for r in ForgettingRisk}
    for tp in profiles:
        dist[tp.risk.value] += 1

    # Fastest decaying (most negative velocity)
    by_vel = sorted(profiles, key=lambda p: p.decay_velocity)
    fastest = by_vel[:top_n]

    # Difficulty ↔ decay correlation
    difficulties = [s.difficulty for s in snapshots]
    # Use 1/stability as a proxy for "decay rate" (higher = faster decay)
    decay_rates = [1.0 / max(s.base_stability, 0.1) for s in snapshots]
    diff_corr = _pearson_correlation(difficulties, decay_rates)

    fp_values = [s.forgetting_probability for s in snapshots]
    vel_values = [p.decay_velocity for p in profiles]

    exp_parts = [f"{len(profiles)} topics"]
    if urgent:
        exp_parts.append(f"{len(urgent)} URGENT")
    exp_parts.append(f"difficulty↔decay correlation {diff_corr:+.2f}")

    return ForgettingTrends(
        topic_profiles=profiles,
        risk_distribution=dist,
        avg_forgetting_probability=round(_mean(fp_values), 4),
        avg_decay_velocity=round(_mean(vel_values), 6),
        fastest_decaying=fastest,
        difficulty_correlation=diff_corr,
        urgent_topics=urgent,
        explanation="; ".join(exp_parts),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  11. Scheduling Efficiency
# ═══════════════════════════════════════════════════════════════════════════════

class TimingQuality(str, Enum):
    """How well-timed a revision was relative to the optimal interval."""

    PREMATURE = "premature"        # revised too early (wasted effort)
    OPTIMAL = "optimal"            # revised near the ideal time
    LATE = "late"                  # revised after retention started dropping
    OVERDUE = "overdue"            # revised far too late, significant retention loss


@dataclass(frozen=True, slots=True)
class TopicScheduleEfficiency:
    """Scheduling efficiency for a single topic."""

    topic_id: object
    topic_name: str
    days_since_last_revision: float
    optimal_interval: float             # ideal days between revisions
    gap_ratio: float                    # actual / optimal (1.0 = perfect)
    timing: TimingQuality
    retention_at_revision_time: float   # what R was when they last revised
    wasted_effort: bool                 # revised when retention was still high
    explanation: str


@dataclass(frozen=True, slots=True)
class SchedulingEfficiency:
    """Scheduling efficiency analysis across all topics."""

    topic_efficiencies: list[TopicScheduleEfficiency]
    timing_distribution: dict[str, int]
    mean_gap_ratio: float
    optimal_rate: float                 # fraction of topics with optimal timing
    overdue_rate: float                 # fraction with overdue timing
    premature_rate: float               # fraction revised too early
    wasted_revision_count: int          # topics revised prematurely
    scheduling_health_score: float      # 0–1 composite score
    explanation: str


def _compute_optimal_interval(stability: float, target_retention: float = 0.70) -> float:
    """
    Optimal revision interval: when R drops to target retention threshold.

    t_optimal = -S × ln(target)
    """
    s = max(stability, 0.1)
    if target_retention <= 0 or target_retention >= 1:
        return s
    return round(-s * math.log(target_retention), 4)


def _classify_timing(gap_ratio: float) -> TimingQuality:
    if gap_ratio < 0.5:
        return TimingQuality.PREMATURE
    if gap_ratio <= 1.3:
        return TimingQuality.OPTIMAL
    if gap_ratio <= 2.0:
        return TimingQuality.LATE
    return TimingQuality.OVERDUE


def compute_scheduling_efficiency(
    snapshots: list[TopicSnapshot],
    *,
    target_retention: float = 0.70,
    high_retention_waste_threshold: float = 0.90,
) -> SchedulingEfficiency:
    """
    Analyze how well the scheduling system is timing revisions.

    Compares actual revision gaps against optimal intervals derived from
    the adaptive forgetting curve. Detects:
    - premature revisions (wasted effort — retention still high)
    - optimal timing (revised near the ideal point)
    - late/overdue revisions (retention dropped too low)

    Produces a composite scheduling health score.
    """
    if not snapshots:
        return SchedulingEfficiency(
            topic_efficiencies=[], timing_distribution={t.value: 0 for t in TimingQuality},
            mean_gap_ratio=0.0, optimal_rate=0.0, overdue_rate=0.0, premature_rate=0.0,
            wasted_revision_count=0, scheduling_health_score=0.0,
            explanation="No topics available for scheduling analysis.",
        )

    efficiencies = []
    wasted = 0

    for s in snapshots:
        opt = _compute_optimal_interval(s.base_stability, target_retention)
        elapsed = s.days_since_last_revision

        if opt > 0 and elapsed > 0:
            gap_r = round(elapsed / opt, 4)
        elif elapsed == 0:
            gap_r = 0.0  # just revised
        else:
            gap_r = 1.0

        timing = _classify_timing(gap_r)
        is_wasted = (s.retention_score >= high_retention_waste_threshold
                     and timing == TimingQuality.PREMATURE)
        if is_wasted:
            wasted += 1

        parts = [f"gap ratio {gap_r:.2f} ({timing.value})"]
        if timing == TimingQuality.OVERDUE:
            parts.append(f"overdue by {elapsed - opt:.1f}d, R dropped to {s.retention_score:.0%}")
        elif timing == TimingQuality.PREMATURE:
            parts.append(f"revised {opt - elapsed:.1f}d early")
            if is_wasted:
                parts.append("WASTED: retention was still high")

        efficiencies.append(TopicScheduleEfficiency(
            topic_id=s.topic_id, topic_name=s.topic_name,
            days_since_last_revision=elapsed,
            optimal_interval=opt,
            gap_ratio=gap_r,
            timing=timing,
            retention_at_revision_time=s.retention_score,
            wasted_effort=is_wasted,
            explanation="; ".join(parts),
        ))

    n = len(efficiencies)
    dist = {t.value: 0 for t in TimingQuality}
    for e in efficiencies:
        dist[e.timing.value] += 1

    gap_ratios = [e.gap_ratio for e in efficiencies if e.gap_ratio > 0]
    mean_gr = round(_mean(gap_ratios), 4) if gap_ratios else 0.0
    opt_rate = round(dist.get("optimal", 0) / n, 4) if n > 0 else 0.0
    overdue_r = round(dist.get("overdue", 0) / n, 4) if n > 0 else 0.0
    prem_r = round(dist.get("premature", 0) / n, 4) if n > 0 else 0.0

    # Health score: high optimal rate, low overdue rate, low waste
    health = round(_clamp01(opt_rate * 0.6 + (1.0 - overdue_r) * 0.3 + (1.0 - prem_r) * 0.1), 4)

    exp_parts = [f"{n} topics"]
    exp_parts.append(f"{dist.get('optimal', 0)} optimal, {dist.get('overdue', 0)} overdue, {dist.get('premature', 0)} premature")
    exp_parts.append(f"health score {health:.0%}")

    return SchedulingEfficiency(
        topic_efficiencies=efficiencies,
        timing_distribution=dist,
        mean_gap_ratio=mean_gr,
        optimal_rate=opt_rate,
        overdue_rate=overdue_r,
        premature_rate=prem_r,
        wasted_revision_count=wasted,
        scheduling_health_score=health,
        explanation="; ".join(exp_parts),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  12. Advanced Analytics Report — Combines Sections 7–11
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class AdvancedAnalyticsReport:
    """Extended analytics combining evolution, stability, reinforcement,
    forgetting, and scheduling intelligence."""

    retention_evolution: RetentionEvolution
    stability_progression: StabilityProgression
    reinforcement_effectiveness: ReinforcementEffectiveness
    forgetting_trends: ForgettingTrends
    scheduling_efficiency: SchedulingEfficiency
    total_topics: int


def compute_advanced_analytics(
    snapshots: list[TopicSnapshot],
) -> AdvancedAnalyticsReport:
    """
    Master computation for all advanced analytics (sections 7–11).

    All retention values in snapshots MUST be pre-computed by the service
    layer. This engine only aggregates and analyses.
    """
    return AdvancedAnalyticsReport(
        retention_evolution=compute_retention_evolution(snapshots),
        stability_progression=compute_stability_progression(snapshots),
        reinforcement_effectiveness=compute_reinforcement_effectiveness(snapshots),
        forgetting_trends=compute_forgetting_trends(snapshots),
        scheduling_efficiency=compute_scheduling_efficiency(snapshots),
        total_topics=len(snapshots),
    )
