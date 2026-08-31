"""
app/api/analytics.py
─────────────────────
REST endpoints for retention analytics.

Endpoint summary:
  GET  /v1/analytics/{user_id}/summary              — retention summary (global or scoped)
  GET  /v1/analytics/{user_id}/weak-topics           — weak topic detection
  GET  /v1/analytics/{user_id}/heatmap               — retention heatmap
  GET  /v1/analytics/{user_id}/distribution          — retention score distribution
  GET  /v1/analytics/{user_id}/report                — full analytics report
  GET  /v1/analytics/{user_id}/advanced              — advanced analytics report

Advanced analytics tracks:
  • retention evolution   — forgetting curve projection + decay velocity
  • stability changes     — stability band distribution + stagnation detection
  • reinforcement         — revision effectiveness + diminishing return detection
  • forgetting trends     — risk classification + difficulty↔decay correlation
  • scheduling efficiency — timing quality + gap analysis + health score

All retention values are computed at query time using the adaptive forgetting
engine (R = e^(-t/S_adaptive)). The analytics engine only aggregates and
analyses — it never estimates retention itself.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.analytics import (
    AdvancedAnalyticsReportResponse,
    AnalyticsReportResponse,
    DistributionResponse,
    HeatmapResponse,
    RetentionSummaryResponse,
    WeakTopicResponse,
)
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics Engine"])


@router.get(
    "/{user_id}/summary",
    response_model=RetentionSummaryResponse,
    summary="Retention summary for a user",
)
def retention_summary(
    user_id: uuid.UUID,
    subject_id: uuid.UUID | None = Query(None, description="Filter by subject"),
    module_id: uuid.UUID | None = Query(None, description="Filter by module"),
    chapter_id: uuid.UUID | None = Query(None, description="Filter by chapter"),
    db: Session = Depends(get_db),
):
    """
    Get aggregated retention summary for a learner.

    Returns:
    - **mean_retention** — importance-weighted average across topics
    - **zone** — health zone (mastered/strong/moderate/weak/critical)
    - **zone_distribution** — count of topics in each zone
    - **weak_count** / **critical_count** — topics below threshold

    Optionally scope by subject, module, or chapter.
    """
    return analytics_service.get_retention_summary(
        db, user_id,
        subject_id=subject_id,
        module_id=module_id,
        chapter_id=chapter_id,
    )


@router.get(
    "/{user_id}/weak-topics",
    response_model=list[WeakTopicResponse],
    summary="Detect weak topics",
)
def weak_topics(
    user_id: uuid.UUID,
    subject_id: uuid.UUID | None = Query(None, description="Filter by subject"),
    weak_threshold: float = Query(0.50, ge=0.0, le=1.0, description="Retention threshold"),
    limit: int | None = Query(None, ge=1, le=100, description="Max topics to return"),
    db: Session = Depends(get_db),
):
    """
    Detect topics where the learner's retention is below threshold.

    Returns a list sorted by retention ascending (worst first), with:
    - **severity** — mild / moderate / severe / critical
    - **reason** — human-readable explanation of why the topic is weak
    - **hierarchy context** — chapter, module, subject names
    """
    return analytics_service.get_weak_topics(
        db, user_id,
        subject_id=subject_id,
        weak_threshold=weak_threshold,
        limit=limit,
    )


@router.get(
    "/{user_id}/heatmap",
    response_model=HeatmapResponse,
    summary="Retention heatmap",
)
def retention_heatmap(
    user_id: uuid.UUID,
    subject_id: uuid.UUID | None = Query(None, description="Filter by subject"),
    group_by: str = Query("chapter", description="Group by: chapter or module"),
    db: Session = Depends(get_db),
):
    """
    Generate a retention heatmap for visualization.

    Each **row** is a hierarchy group (chapter or module).
    Each **cell** is a topic with retention score, zone, and urgency.

    Rows are sorted worst-first for immediate visual scanning.
    """
    return analytics_service.get_heatmap(
        db, user_id,
        subject_id=subject_id,
        group_by=group_by,
    )


@router.get(
    "/{user_id}/distribution",
    response_model=DistributionResponse,
    summary="Retention score distribution",
)
def retention_distribution(
    user_id: uuid.UUID,
    subject_id: uuid.UUID | None = Query(None, description="Filter by subject"),
    db: Session = Depends(get_db),
):
    """
    Get a histogram of the learner's retention scores across all topics.

    Returns fixed-width buckets from 0.0 to 1.0 with count, percentage,
    and zone classification per bucket. Ready for bar chart rendering.
    """
    return analytics_service.get_distribution(
        db, user_id,
        subject_id=subject_id,
    )


@router.get(
    "/{user_id}/report",
    response_model=AnalyticsReportResponse,
    summary="Full analytics report",
)
def full_report(
    user_id: uuid.UUID,
    subject_id: uuid.UUID | None = Query(None, description="Filter by subject"),
    db: Session = Depends(get_db),
):
    """
    Generate a comprehensive analytics report containing:

    - **Hierarchical retention summaries** — subject, module, chapter, global
    - **Weak topic detection** — flagged topics with severity and reasons
    - **Weak topic clusters** — grouped by chapter with recommendations
    - **Retention heatmap** — visualization-ready grid
    - **Retention distribution** — histogram with zone classification

    All retention values are computed at query time using the adaptive
    forgetting curve R = e^(-t/S_adaptive).
    """
    return analytics_service.get_full_report(
        db, user_id,
        subject_id=subject_id,
    )


@router.get(
    "/{user_id}/advanced",
    response_model=AdvancedAnalyticsReportResponse,
    summary="Advanced analytics report",
)
def advanced_report(
    user_id: uuid.UUID,
    subject_id: uuid.UUID | None = Query(None, description="Filter by subject"),
    db: Session = Depends(get_db),
):
    """
    Generate an advanced analytics report tracking:

    - **Retention evolution** — forgetting curve projection, decay velocity,
      half-life, time-to-weak for each topic
    - **Stability changes** — stability band distribution (fragile → robust),
      stagnation detection, stability-per-revision efficiency
    - **Reinforcement effectiveness** — revision impact grading,
      diminishing returns detection, composite reinforcement score
    - **Forgetting trends** — risk classification (safe → urgent),
      difficulty↔decay correlation, fastest-decaying topics
    - **Scheduling efficiency** — gap ratio analysis, timing quality
      (premature/optimal/late/overdue), scheduling health score

    All retention values are computed at query time using the adaptive
    forgetting curve R = e^(-t/S_adaptive).
    """
    return analytics_service.get_advanced_report(
        db, user_id,
        subject_id=subject_id,
    )
