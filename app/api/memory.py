"""
app/api/memory.py
──────────────────
REST endpoints for memory state management.

These endpoints expose the memory state service to external consumers.
Engine modules call the service layer directly — they do NOT go through HTTP.

Endpoint summary:
  GET  /v1/memory/{user_id}/{topic_id}     — single state lookup
  POST /v1/memory/init                      — explicit state initialisation
  GET  /v1/memory/{user_id}                 — list all states (paginated)
  GET  /v1/memory/{user_id}/overdue         — overdue items
  GET  /v1/memory/{user_id}/at-risk         — low-retention topics
  POST /v1/memory/batch                     — batch lookup by topic_ids
  GET  /v1/memory/{user_id}/overview        — full hierarchical overview
  GET  /v1/memory/{user_id}/aggregate/chapter/{id}  — chapter aggregate
  GET  /v1/memory/{user_id}/aggregate/module/{id}   — module aggregate
  GET  /v1/memory/{user_id}/aggregate/subject/{id}  — subject aggregate
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.deps import get_db
from app.schemas.memory import (
    BatchMemoryStateRequest,
    BatchMemoryStateResponse,
    MemoryStateInit,
    MemoryStateResponse,
    MemoryStateSummary,
    RetentionAggregate,
    UserRetentionOverview,
)
from app.services import memory_service

router = APIRouter(prefix="/memory", tags=["Memory States"])


# ── Single state ──────────────────────────────────────────────────────────────

@router.get(
    "/{user_id}/{topic_id}",
    response_model=MemoryStateResponse,
    summary="Get memory state for a user × topic pair",
)
def get_state(
    user_id: uuid.UUID,
    topic_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    state = memory_service.get_memory_state(db, user_id, topic_id)
    if state is None:
        raise NotFoundError("MemoryState", f"user={user_id} topic={topic_id}")
    return state


@router.post(
    "/init",
    response_model=MemoryStateResponse,
    status_code=201,
    summary="Initialise memory state with explicit values",
)
def init_state(
    payload: MemoryStateInit,
    db: Session = Depends(get_db),
):
    """
    Create or return existing memory state for a user × topic pair.
    If the state already exists, the existing values are preserved.
    """
    state = memory_service.init_memory_state(db, payload)
    return state


# ── List / Filter ─────────────────────────────────────────────────────────────

@router.get(
    "/{user_id}",
    response_model=list[MemoryStateSummary],
    summary="List all memory states for a user (by urgency)",
)
def list_states(
    user_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    states = memory_service.list_memory_states(db, user_id, limit, offset)
    return [MemoryStateSummary.model_validate(s) for s in states]


@router.get(
    "/{user_id}/overdue",
    response_model=list[MemoryStateSummary],
    summary="List overdue memory states",
)
def list_overdue(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Topics where next_revision_at is in the past or NULL (never scheduled)."""
    states = memory_service.list_overdue(db, user_id)
    return [MemoryStateSummary.model_validate(s) for s in states]


@router.get(
    "/{user_id}/at-risk",
    response_model=list[MemoryStateSummary],
    summary="List topics at forgetting risk",
)
def list_at_risk(
    user_id: uuid.UUID,
    threshold: float = Query(default=0.4, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    """Topics where retention_score is below the given threshold."""
    states = memory_service.list_at_risk(db, user_id, threshold)
    return [MemoryStateSummary.model_validate(s) for s in states]


# ── Batch ─────────────────────────────────────────────────────────────────────

@router.post(
    "/batch",
    response_model=BatchMemoryStateResponse,
    summary="Batch-fetch memory states for multiple topics",
)
def batch_get(
    payload: BatchMemoryStateRequest,
    db: Session = Depends(get_db),
):
    states = memory_service.batch_get(db, payload.user_id, payload.topic_ids)
    summaries = [MemoryStateSummary.model_validate(s) for s in states]
    return BatchMemoryStateResponse(
        user_id=payload.user_id,
        states=summaries,
        total=len(summaries),
    )


# ── Aggregation ───────────────────────────────────────────────────────────────

@router.get(
    "/{user_id}/overview",
    response_model=UserRetentionOverview,
    summary="Full retention overview across all subjects",
)
def user_overview(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    return memory_service.get_user_overview(db, user_id)


@router.get(
    "/{user_id}/aggregate/chapter/{chapter_id}",
    response_model=RetentionAggregate,
    summary="Retention aggregate for a chapter",
)
def chapter_aggregate(
    user_id: uuid.UUID,
    chapter_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    return memory_service.aggregate_for_chapter(db, user_id, chapter_id)


@router.get(
    "/{user_id}/aggregate/module/{module_id}",
    response_model=RetentionAggregate,
    summary="Retention aggregate for a module",
)
def module_aggregate(
    user_id: uuid.UUID,
    module_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    return memory_service.aggregate_for_module(db, user_id, module_id)


@router.get(
    "/{user_id}/aggregate/subject/{subject_id}",
    response_model=RetentionAggregate,
    summary="Retention aggregate for a subject",
)
def subject_aggregate(
    user_id: uuid.UUID,
    subject_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    return memory_service.aggregate_for_subject(db, user_id, subject_id)
