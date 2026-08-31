"""
app/schemas/analytics.py
─────────────────────────
Pydantic schemas for analytics API responses.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
#  Retention Summary
# ═══════════════════════════════════════════════════════════════════════════════

class RetentionSummaryResponse(BaseModel):
    level: str
    level_id: uuid.UUID | str | None = None
    level_name: str
    mean_retention: float
    min_retention: float
    max_retention: float
    median_retention: float
    std_retention: float
    topic_count: int
    weak_count: int
    critical_count: int
    zone: str
    zone_distribution: dict[str, int]
    summary: str


# ═══════════════════════════════════════════════════════════════════════════════
#  Weak Topics
# ═══════════════════════════════════════════════════════════════════════════════

class WeakTopicResponse(BaseModel):
    topic_id: uuid.UUID | str
    topic_name: str
    retention_score: float
    forgetting_probability: float
    urgency_score: float
    difficulty: float
    revision_count: int
    performance_trend: float
    days_since_last_revision: float
    severity: str
    reason: str
    chapter_name: str = ""
    module_name: str = ""
    subject_name: str = ""


class WeakTopicClusterResponse(BaseModel):
    cluster_name: str
    cluster_level: str
    topics: list[WeakTopicResponse]
    mean_retention: float
    severity: str
    recommendation: str


# ═══════════════════════════════════════════════════════════════════════════════
#  Heatmap
# ═══════════════════════════════════════════════════════════════════════════════

class HeatmapCellResponse(BaseModel):
    topic_id: uuid.UUID | str
    topic_name: str
    retention: float
    zone: str
    urgency: float


class HeatmapRowResponse(BaseModel):
    group_id: uuid.UUID | str | None = None
    group_name: str
    cells: list[HeatmapCellResponse]
    mean_retention: float


class HeatmapResponse(BaseModel):
    rows: list[HeatmapRowResponse]
    group_level: str
    total_topics: int
    global_mean: float


# ═══════════════════════════════════════════════════════════════════════════════
#  Trend Analysis
# ═══════════════════════════════════════════════════════════════════════════════

class TrendPointResponse(BaseModel):
    window_label: str
    mean_retention: float
    topic_count: int


class TrendAnalysisResponse(BaseModel):
    direction: str
    slope: float
    current_mean: float
    trend_points: list[TrendPointResponse]
    explanation: str


# ═══════════════════════════════════════════════════════════════════════════════
#  Distribution
# ═══════════════════════════════════════════════════════════════════════════════

class DistributionBucketResponse(BaseModel):
    lower: float
    upper: float
    count: int
    percentage: float
    zone: str


class DistributionResponse(BaseModel):
    buckets: list[DistributionBucketResponse]
    total_topics: int
    mean: float
    median: float


# ═══════════════════════════════════════════════════════════════════════════════
#  Full Analytics Report
# ═══════════════════════════════════════════════════════════════════════════════

class AnalyticsReportResponse(BaseModel):
    user_id: uuid.UUID
    subject_summaries: list[RetentionSummaryResponse]
    module_summaries: list[RetentionSummaryResponse]
    chapter_summaries: list[RetentionSummaryResponse]
    global_summary: RetentionSummaryResponse
    weak_topics: list[WeakTopicResponse]
    weak_clusters: list[WeakTopicClusterResponse]
    heatmap: HeatmapResponse
    distribution: DistributionResponse
    total_topics: int
    total_weak: int
    total_critical: int


# ═══════════════════════════════════════════════════════════════════════════════
#  Retention Evolution
# ═══════════════════════════════════════════════════════════════════════════════

class ProjectionPointResponse(BaseModel):
    days_from_now: float
    projected_retention: float
    zone: str


class TopicEvolutionResponse(BaseModel):
    topic_id: uuid.UUID | str
    topic_name: str
    current_retention: float
    current_zone: str
    base_stability: float
    decay_velocity: float
    half_life_days: float
    time_to_weak: float
    projection: list[ProjectionPointResponse]
    chapter_name: str = ""
    module_name: str = ""


class RetentionEvolutionResponse(BaseModel):
    topic_evolutions: list[TopicEvolutionResponse]
    fastest_decaying: list[TopicEvolutionResponse]
    most_stable: list[TopicEvolutionResponse]
    avg_decay_velocity: float
    avg_half_life: float
    topics_reaching_weak_in_7d: int
    explanation: str


# ═══════════════════════════════════════════════════════════════════════════════
#  Stability Progression
# ═══════════════════════════════════════════════════════════════════════════════

class TopicStabilityResponse(BaseModel):
    topic_id: uuid.UUID | str
    topic_name: str
    base_stability: float
    band: str
    revision_count: int
    stability_per_revision: float
    is_stagnating: bool
    explanation: str
    chapter_name: str = ""


class StabilityProgressionResponse(BaseModel):
    topic_stabilities: list[TopicStabilityResponse]
    band_distribution: dict[str, int]
    mean_stability: float
    median_stability: float
    stagnating_topics: list[TopicStabilityResponse]
    most_fragile: list[TopicStabilityResponse]
    most_robust: list[TopicStabilityResponse]
    avg_stability_per_revision: float
    explanation: str


# ═══════════════════════════════════════════════════════════════════════════════
#  Reinforcement Effectiveness
# ═══════════════════════════════════════════════════════════════════════════════

class TopicReinforcementResponse(BaseModel):
    topic_id: uuid.UUID | str
    topic_name: str
    revision_count: int
    retention_score: float
    confidence_score: float
    performance_trend: float
    retention_per_revision: float
    reinforcement_score: float
    grade: str
    is_diminishing: bool
    explanation: str


class ReinforcementEffectivenessResponse(BaseModel):
    topic_reinforcements: list[TopicReinforcementResponse]
    grade_distribution: dict[str, int]
    mean_retention_per_revision: float
    mean_reinforcement_score: float
    diminishing_return_topics: list[TopicReinforcementResponse]
    most_effective: list[TopicReinforcementResponse]
    least_effective: list[TopicReinforcementResponse]
    total_revisions: int
    explanation: str


# ═══════════════════════════════════════════════════════════════════════════════
#  Forgetting Trends
# ═══════════════════════════════════════════════════════════════════════════════

class TopicForgettingProfileResponse(BaseModel):
    topic_id: uuid.UUID | str
    topic_name: str
    forgetting_probability: float
    decay_velocity: float
    base_stability: float
    difficulty: float
    risk: str
    days_until_forgotten: float
    explanation: str
    chapter_name: str = ""
    module_name: str = ""


class ForgettingTrendsResponse(BaseModel):
    topic_profiles: list[TopicForgettingProfileResponse]
    risk_distribution: dict[str, int]
    avg_forgetting_probability: float
    avg_decay_velocity: float
    fastest_decaying: list[TopicForgettingProfileResponse]
    difficulty_correlation: float
    urgent_topics: list[TopicForgettingProfileResponse]
    explanation: str


# ═══════════════════════════════════════════════════════════════════════════════
#  Scheduling Efficiency
# ═══════════════════════════════════════════════════════════════════════════════

class TopicScheduleEfficiencyResponse(BaseModel):
    topic_id: uuid.UUID | str
    topic_name: str
    days_since_last_revision: float
    optimal_interval: float
    gap_ratio: float
    timing: str
    retention_at_revision_time: float
    wasted_effort: bool
    explanation: str


class SchedulingEfficiencyResponse(BaseModel):
    topic_efficiencies: list[TopicScheduleEfficiencyResponse]
    timing_distribution: dict[str, int]
    mean_gap_ratio: float
    optimal_rate: float
    overdue_rate: float
    premature_rate: float
    wasted_revision_count: int
    scheduling_health_score: float
    explanation: str


# ═══════════════════════════════════════════════════════════════════════════════
#  Advanced Analytics Report
# ═══════════════════════════════════════════════════════════════════════════════

class AdvancedAnalyticsReportResponse(BaseModel):
    user_id: uuid.UUID
    retention_evolution: RetentionEvolutionResponse
    stability_progression: StabilityProgressionResponse
    reinforcement_effectiveness: ReinforcementEffectivenessResponse
    forgetting_trends: ForgettingTrendsResponse
    scheduling_efficiency: SchedulingEfficiencyResponse
    total_topics: int
