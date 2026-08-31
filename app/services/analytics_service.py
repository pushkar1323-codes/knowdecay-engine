"""
app/services/analytics_service.py
───────────────────────────────────
Orchestration layer between the API and the analytics engine.

Responsibilities:
  1. Load memory states + hierarchy metadata from DB
  2. Compute real-time retention via adaptive forgetting engine
  3. Build TopicSnapshot DTOs with pre-computed retention values
  4. Call the pure analytics engine (which never estimates retention itself)
  5. Return response schemas

Architecture:
  • Retention estimation → adaptive_forgetting.py (R = e^(-t/S_adaptive))
  • Analytics aggregation → analytics_engine.py (pure functions)
  • DB orchestration → THIS MODULE
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.engine.adaptive_forgetting import (
    ForgettingInput,
    compute_adaptive_forgetting,
)
from app.engine.analytics_engine import (
    AdvancedAnalyticsReport,
    AnalyticsReport,
    RetentionHistoryPoint,
    RetentionSummary,
    TopicSnapshot,
    TrendAnalysis,
    WeakTopic,
    aggregate_by_hierarchy,
    analyze_trend,
    compute_advanced_analytics,
    compute_analytics_report,
    compute_distribution,
    compute_retention_summary,
    detect_weak_topics,
    generate_heatmap,
)
from app.models.hierarchy import Chapter, Module, Subject, Topic
from app.models.memory_state import MemoryState
from app.schemas.analytics import (
    AdvancedAnalyticsReportResponse,
    AnalyticsReportResponse,
    DistributionBucketResponse,
    DistributionResponse,
    ForgettingTrendsResponse,
    HeatmapCellResponse,
    HeatmapResponse,
    HeatmapRowResponse,
    ProjectionPointResponse,
    ReinforcementEffectivenessResponse,
    RetentionEvolutionResponse,
    RetentionSummaryResponse,
    SchedulingEfficiencyResponse,
    StabilityProgressionResponse,
    TopicEvolutionResponse,
    TopicForgettingProfileResponse,
    TopicReinforcementResponse,
    TopicScheduleEfficiencyResponse,
    TopicStabilityResponse,
    TrendAnalysisResponse,
    TrendPointResponse,
    WeakTopicClusterResponse,
    WeakTopicResponse,
)
from app.utils.time_utils import utcnow
from app.services.ml_feature_builder import build_ml_features

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Snapshot Builder — Computes real-time retention via adaptive forgetting
# ═══════════════════════════════════════════════════════════════════════════════

def _build_snapshot(
    state: MemoryState,
    topic: Topic,
    chapter: Chapter | None,
    module: Module | None,
    subject: Subject | None,
    now: datetime,
) -> TopicSnapshot:
    """
    Build a TopicSnapshot with real-time retention from the adaptive
    forgetting engine.

    Retention estimation happens HERE in the service layer.
    The analytics engine only receives pre-computed values.
    """
    # Elapsed days since last revision
    if state.last_revision_at is not None:
        elapsed = (now - state.last_revision_at).total_seconds() / 86400.0
    else:
        elapsed = 0.0

    # Compute real-time retention via adaptive forgetting curve
    base_stability = getattr(state, 'base_stability', None)
    if base_stability is not None and elapsed > 0:
        difficulty = topic.difficulty if topic else 0.5
        ml = build_ml_features(state, difficulty=difficulty)
        forg_out = compute_adaptive_forgetting(ForgettingInput(
            elapsed_days=elapsed,
            base_stability=base_stability,
            revision_count=state.revision_count,
            revision_quality=getattr(state, 'revision_quality', 0.5),
            quiz_score=0.0,
            confidence_score=state.confidence_score,
            performance_trend=getattr(state, 'performance_trend', 0.0),
            difficulty=difficulty,
            ml_stability_correction=ml.stability_correction,
            ml_decay_modifier=ml.decay_modifier,
            ml_blend_weight=ml.blend_weight,
        ))
        realtime_retention = forg_out.retention
        realtime_forgetting = forg_out.forgetting_probability
    else:
        # Fallback: use persisted values
        realtime_retention = state.retention_score
        realtime_forgetting = state.forgetting_probability

    return TopicSnapshot(
        topic_id=state.topic_id,
        topic_name=topic.name if topic else "",
        retention_score=realtime_retention,
        forgetting_probability=realtime_forgetting,
        stability_score=state.stability_score,
        base_stability=getattr(state, 'base_stability', 1.0),
        urgency_score=state.urgency_score,
        revision_count=state.revision_count,
        confidence_score=state.confidence_score,
        performance_trend=getattr(state, 'performance_trend', 0.0),
        difficulty=topic.difficulty if topic else 0.5,
        importance_weight=topic.importance_weight if topic else 1.0,
        chapter_id=chapter.id if chapter else None,
        chapter_name=chapter.name if chapter else "",
        module_id=module.id if module else None,
        module_name=module.name if module else "",
        subject_id=subject.id if subject else None,
        subject_name=subject.name if subject else "",
        days_since_last_revision=elapsed,
    )


def _load_snapshots(
    db: Session,
    user_id: uuid.UUID,
    *,
    subject_id: uuid.UUID | None = None,
    module_id: uuid.UUID | None = None,
    chapter_id: uuid.UUID | None = None,
) -> list[TopicSnapshot]:
    """
    Load all memory states for a user and build TopicSnapshots.

    Optionally filter by hierarchy level.
    """
    now = utcnow()

    # Build query with hierarchy joins
    stmt = (
        select(MemoryState)
        .join(Topic, MemoryState.topic_id == Topic.id)
        .join(Chapter, Topic.chapter_id == Chapter.id)
        .join(Module, Chapter.module_id == Module.id)
        .join(Subject, Module.subject_id == Subject.id)
        .where(MemoryState.user_id == user_id)
        .options(
            joinedload(MemoryState.topic)
            .joinedload(Topic.chapter)
            .joinedload(Chapter.module)
            .joinedload(Module.subject)
        )
    )

    # Apply hierarchy filters
    if subject_id is not None:
        stmt = stmt.where(Subject.id == subject_id)
    if module_id is not None:
        stmt = stmt.where(Module.id == module_id)
    if chapter_id is not None:
        stmt = stmt.where(Chapter.id == chapter_id)

    states = db.execute(stmt).scalars().unique().all()

    snapshots = []
    for state in states:
        topic = state.topic
        chapter = topic.chapter if topic else None
        module = chapter.module if chapter else None
        subject = module.subject if module else None
        snapshots.append(_build_snapshot(state, topic, chapter, module, subject, now))

    return snapshots


# ═══════════════════════════════════════════════════════════════════════════════
#  Response Converters
# ═══════════════════════════════════════════════════════════════════════════════

def _summary_to_response(s: RetentionSummary) -> RetentionSummaryResponse:
    return RetentionSummaryResponse(
        level=s.level,
        level_id=s.level_id,
        level_name=s.level_name,
        mean_retention=s.mean_retention,
        min_retention=s.min_retention,
        max_retention=s.max_retention,
        median_retention=s.median_retention,
        std_retention=s.std_retention,
        topic_count=s.topic_count,
        weak_count=s.weak_count,
        critical_count=s.critical_count,
        zone=s.zone.value,
        zone_distribution=s.zone_distribution,
        summary=s.summary,
    )


def _weak_to_response(w: WeakTopic) -> WeakTopicResponse:
    return WeakTopicResponse(
        topic_id=w.topic_id,
        topic_name=w.topic_name,
        retention_score=w.retention_score,
        forgetting_probability=w.forgetting_probability,
        urgency_score=w.urgency_score,
        difficulty=w.difficulty,
        revision_count=w.revision_count,
        performance_trend=w.performance_trend,
        days_since_last_revision=w.days_since_last_revision,
        severity=w.severity.value,
        reason=w.reason,
        chapter_name=w.chapter_name,
        module_name=w.module_name,
        subject_name=w.subject_name,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Public Service Functions
# ═══════════════════════════════════════════════════════════════════════════════

def get_retention_summary(
    db: Session,
    user_id: uuid.UUID,
    *,
    subject_id: uuid.UUID | None = None,
    module_id: uuid.UUID | None = None,
    chapter_id: uuid.UUID | None = None,
) -> RetentionSummaryResponse:
    """Get aggregated retention summary for a user, optionally scoped."""
    snapshots = _load_snapshots(
        db, user_id,
        subject_id=subject_id,
        module_id=module_id,
        chapter_id=chapter_id,
    )

    # Determine level
    if chapter_id:
        level, lid, lname = "chapter", chapter_id, ""
    elif module_id:
        level, lid, lname = "module", module_id, ""
    elif subject_id:
        level, lid, lname = "subject", subject_id, ""
    else:
        level, lid, lname = "global", None, "All Topics"

    summary = compute_retention_summary(
        snapshots, level=level, level_id=lid, level_name=lname,
    )
    return _summary_to_response(summary)


def get_weak_topics(
    db: Session,
    user_id: uuid.UUID,
    *,
    subject_id: uuid.UUID | None = None,
    weak_threshold: float = 0.50,
    limit: int | None = None,
) -> list[WeakTopicResponse]:
    """Detect and return weak topics for a user."""
    snapshots = _load_snapshots(db, user_id, subject_id=subject_id)
    weak = detect_weak_topics(snapshots, weak_threshold=weak_threshold)

    if limit is not None and limit > 0:
        weak = weak[:limit]

    return [_weak_to_response(w) for w in weak]


def get_heatmap(
    db: Session,
    user_id: uuid.UUID,
    *,
    subject_id: uuid.UUID | None = None,
    group_by: str = "chapter",
) -> HeatmapResponse:
    """Generate retention heatmap for a user."""
    snapshots = _load_snapshots(db, user_id, subject_id=subject_id)
    heatmap = generate_heatmap(snapshots, group_by=group_by)

    return HeatmapResponse(
        rows=[
            HeatmapRowResponse(
                group_id=row.group_id,
                group_name=row.group_name,
                cells=[
                    HeatmapCellResponse(
                        topic_id=c.topic_id,
                        topic_name=c.topic_name,
                        retention=c.retention,
                        zone=c.zone.value,
                        urgency=c.urgency,
                    )
                    for c in row.cells
                ],
                mean_retention=row.mean_retention,
            )
            for row in heatmap.rows
        ],
        group_level=heatmap.group_level,
        total_topics=heatmap.total_topics,
        global_mean=heatmap.global_mean,
    )


def get_distribution(
    db: Session,
    user_id: uuid.UUID,
    *,
    subject_id: uuid.UUID | None = None,
) -> DistributionResponse:
    """Get retention distribution histogram for a user."""
    snapshots = _load_snapshots(db, user_id, subject_id=subject_id)
    dist = compute_distribution(snapshots)

    return DistributionResponse(
        buckets=[
            DistributionBucketResponse(
                lower=b.lower, upper=b.upper,
                count=b.count, percentage=b.percentage,
                zone=b.zone.value,
            )
            for b in dist.buckets
        ],
        total_topics=dist.total_topics,
        mean=dist.mean,
        median=dist.median,
    )


def get_full_report(
    db: Session,
    user_id: uuid.UUID,
    *,
    subject_id: uuid.UUID | None = None,
) -> AnalyticsReportResponse:
    """
    Generate a complete analytics report for a user.

    All retention values are computed at query time using the adaptive
    forgetting engine (R = e^(-t/S_adaptive)).
    """
    snapshots = _load_snapshots(db, user_id, subject_id=subject_id)
    report = compute_analytics_report(snapshots)

    return AnalyticsReportResponse(
        user_id=user_id,
        subject_summaries=[_summary_to_response(s) for s in report.subject_summaries],
        module_summaries=[_summary_to_response(s) for s in report.module_summaries],
        chapter_summaries=[_summary_to_response(s) for s in report.chapter_summaries],
        global_summary=_summary_to_response(report.global_summary),
        weak_topics=[_weak_to_response(w) for w in report.weak_topics],
        weak_clusters=[
            WeakTopicClusterResponse(
                cluster_name=c.cluster_name,
                cluster_level=c.cluster_level,
                topics=[_weak_to_response(t) for t in c.topics],
                mean_retention=c.mean_retention,
                severity=c.severity.value,
                recommendation=c.recommendation,
            )
            for c in report.weak_clusters
        ],
        heatmap=HeatmapResponse(
            rows=[
                HeatmapRowResponse(
                    group_id=row.group_id,
                    group_name=row.group_name,
                    cells=[
                        HeatmapCellResponse(
                            topic_id=c.topic_id,
                            topic_name=c.topic_name,
                            retention=c.retention,
                            zone=c.zone.value,
                            urgency=c.urgency,
                        )
                        for c in row.cells
                    ],
                    mean_retention=row.mean_retention,
                )
                for row in report.heatmap.rows
            ],
            group_level=report.heatmap.group_level,
            total_topics=report.heatmap.total_topics,
            global_mean=report.heatmap.global_mean,
        ),
        distribution=DistributionResponse(
            buckets=[
                DistributionBucketResponse(
                    lower=b.lower, upper=b.upper,
                    count=b.count, percentage=b.percentage,
                    zone=b.zone.value,
                )
                for b in report.distribution.buckets
            ],
            total_topics=report.distribution.total_topics,
            mean=report.distribution.mean,
            median=report.distribution.median,
        ),
        total_topics=report.total_topics,
        total_weak=report.total_weak,
        total_critical=report.total_critical,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Advanced Analytics
# ═══════════════════════════════════════════════════════════════════════════════

def _evolution_to_response(e) -> TopicEvolutionResponse:
    return TopicEvolutionResponse(
        topic_id=e.topic_id, topic_name=e.topic_name,
        current_retention=e.current_retention,
        current_zone=e.current_zone.value,
        base_stability=e.base_stability,
        decay_velocity=e.decay_velocity,
        half_life_days=e.half_life_days,
        time_to_weak=e.time_to_weak,
        projection=[
            ProjectionPointResponse(
                days_from_now=p.days_from_now,
                projected_retention=p.projected_retention,
                zone=p.zone.value,
            ) for p in e.projection
        ],
        chapter_name=e.chapter_name,
        module_name=e.module_name,
    )


def _stability_to_response(ts) -> TopicStabilityResponse:
    return TopicStabilityResponse(
        topic_id=ts.topic_id, topic_name=ts.topic_name,
        base_stability=ts.base_stability,
        band=ts.band.value,
        revision_count=ts.revision_count,
        stability_per_revision=ts.stability_per_revision,
        is_stagnating=ts.is_stagnating,
        explanation=ts.explanation,
        chapter_name=ts.chapter_name,
    )


def _reinforcement_to_response(tr) -> TopicReinforcementResponse:
    return TopicReinforcementResponse(
        topic_id=tr.topic_id, topic_name=tr.topic_name,
        revision_count=tr.revision_count,
        retention_score=tr.retention_score,
        confidence_score=tr.confidence_score,
        performance_trend=tr.performance_trend,
        retention_per_revision=tr.retention_per_revision,
        reinforcement_score=tr.reinforcement_score,
        grade=tr.grade.value,
        is_diminishing=tr.is_diminishing,
        explanation=tr.explanation,
    )


def _forgetting_to_response(fp) -> TopicForgettingProfileResponse:
    return TopicForgettingProfileResponse(
        topic_id=fp.topic_id, topic_name=fp.topic_name,
        forgetting_probability=fp.forgetting_probability,
        decay_velocity=fp.decay_velocity,
        base_stability=fp.base_stability,
        difficulty=fp.difficulty,
        risk=fp.risk.value,
        days_until_forgotten=fp.days_until_forgotten,
        explanation=fp.explanation,
        chapter_name=fp.chapter_name,
        module_name=fp.module_name,
    )


def _sched_eff_to_response(se) -> TopicScheduleEfficiencyResponse:
    return TopicScheduleEfficiencyResponse(
        topic_id=se.topic_id, topic_name=se.topic_name,
        days_since_last_revision=se.days_since_last_revision,
        optimal_interval=se.optimal_interval,
        gap_ratio=se.gap_ratio,
        timing=se.timing.value,
        retention_at_revision_time=se.retention_at_revision_time,
        wasted_effort=se.wasted_effort,
        explanation=se.explanation,
    )


def get_advanced_report(
    db: Session,
    user_id: uuid.UUID,
    *,
    subject_id: uuid.UUID | None = None,
) -> AdvancedAnalyticsReportResponse:
    """
    Generate an advanced analytics report covering:
      - retention evolution (forgetting curve projection)
      - stability progression (stability band distribution)
      - reinforcement effectiveness (revision impact analysis)
      - forgetting trends (decay velocity, risk classification)
      - scheduling efficiency (timing quality, gap analysis)

    All retention values are computed at query time using the adaptive
    forgetting engine (R = e^(-t/S_adaptive)).
    """
    snapshots = _load_snapshots(db, user_id, subject_id=subject_id)
    report = compute_advanced_analytics(snapshots)

    re = report.retention_evolution
    sp = report.stability_progression
    rf = report.reinforcement_effectiveness
    ft = report.forgetting_trends
    se = report.scheduling_efficiency

    return AdvancedAnalyticsReportResponse(
        user_id=user_id,
        retention_evolution=RetentionEvolutionResponse(
            topic_evolutions=[_evolution_to_response(e) for e in re.topic_evolutions],
            fastest_decaying=[_evolution_to_response(e) for e in re.fastest_decaying],
            most_stable=[_evolution_to_response(e) for e in re.most_stable],
            avg_decay_velocity=re.avg_decay_velocity,
            avg_half_life=re.avg_half_life,
            topics_reaching_weak_in_7d=re.topics_reaching_weak_in_7d,
            explanation=re.explanation,
        ),
        stability_progression=StabilityProgressionResponse(
            topic_stabilities=[_stability_to_response(ts) for ts in sp.topic_stabilities],
            band_distribution=sp.band_distribution,
            mean_stability=sp.mean_stability,
            median_stability=sp.median_stability,
            stagnating_topics=[_stability_to_response(ts) for ts in sp.stagnating_topics],
            most_fragile=[_stability_to_response(ts) for ts in sp.most_fragile],
            most_robust=[_stability_to_response(ts) for ts in sp.most_robust],
            avg_stability_per_revision=sp.avg_stability_per_revision,
            explanation=sp.explanation,
        ),
        reinforcement_effectiveness=ReinforcementEffectivenessResponse(
            topic_reinforcements=[_reinforcement_to_response(tr) for tr in rf.topic_reinforcements],
            grade_distribution=rf.grade_distribution,
            mean_retention_per_revision=rf.mean_retention_per_revision,
            mean_reinforcement_score=rf.mean_reinforcement_score,
            diminishing_return_topics=[_reinforcement_to_response(tr) for tr in rf.diminishing_return_topics],
            most_effective=[_reinforcement_to_response(tr) for tr in rf.most_effective],
            least_effective=[_reinforcement_to_response(tr) for tr in rf.least_effective],
            total_revisions=rf.total_revisions,
            explanation=rf.explanation,
        ),
        forgetting_trends=ForgettingTrendsResponse(
            topic_profiles=[_forgetting_to_response(fp) for fp in ft.topic_profiles],
            risk_distribution=ft.risk_distribution,
            avg_forgetting_probability=ft.avg_forgetting_probability,
            avg_decay_velocity=ft.avg_decay_velocity,
            fastest_decaying=[_forgetting_to_response(fp) for fp in ft.fastest_decaying],
            difficulty_correlation=ft.difficulty_correlation,
            urgent_topics=[_forgetting_to_response(fp) for fp in ft.urgent_topics],
            explanation=ft.explanation,
        ),
        scheduling_efficiency=SchedulingEfficiencyResponse(
            topic_efficiencies=[_sched_eff_to_response(e) for e in se.topic_efficiencies],
            timing_distribution=se.timing_distribution,
            mean_gap_ratio=se.mean_gap_ratio,
            optimal_rate=se.optimal_rate,
            overdue_rate=se.overdue_rate,
            premature_rate=se.premature_rate,
            wasted_revision_count=se.wasted_revision_count,
            scheduling_health_score=se.scheduling_health_score,
            explanation=se.explanation,
        ),
        total_topics=report.total_topics,
    )
