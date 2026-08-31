"""
tests/test_api/test_api_schemas.py
──────────────────────────────────
Validates that API schemas correctly expose all retention evolution fields,
are backward-compatible with defaults, and enforce field constraints.

Pure unit tests — no DB, no HTTP required.
"""

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.memory import (
    MemoryStateInit,
    MemoryStateResponse,
    MemoryStateSummary,
    RetentionAggregate,
)
from app.schemas.retention import (
    RetentionBreakdown,
    RetentionPredictRequest,
    RetentionPredictResponse,
)
from app.schemas.priority import (
    PriorityBreakdown,
    PriorityRankRequest,
    PriorityRankResponse,
    PriorityReasonResponse,
)
from app.schemas.schedule import (
    ScheduleBreakdown,
    ScheduleGenerateRequest,
    ScheduleSingleRequest,
    ScheduleSingleResponse,
)
from app.schemas.recalibration import (
    RecalibrationEventRequest,
    RecalibrationResponse,
    StateChangeDetail,
    StateDeltaResponse,
)
from app.schemas.analytics import (
    AdvancedAnalyticsReportResponse,
    RetentionSummaryResponse,
)
from app.api.health import HealthResponse

_NOW = datetime.now(timezone.utc)
_UUID = uuid.uuid4()


# ═══════════════════════════════════════════════════════════════════════════════
#  1. MemoryStateResponse — Retention Evolution Fields
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryStateResponseFields:
    """MemoryStateResponse must expose all Phase 8.5 + retention evolution fields."""

    @pytest.fixture
    def full_response(self):
        return MemoryStateResponse(
            id=_UUID, user_id=_UUID, topic_id=_UUID,
            retention_score=0.7, stability_score=5.0, decay_rate=0.1,
            confidence_score=0.6, revision_strength=2.0, revision_count=3,
            forgetting_probability=0.3, urgency_score=0.5, updated_at=_NOW,
        )

    def test_phase85_fields_have_defaults(self, full_response):
        assert full_response.base_stability == 1.0
        assert full_response.revision_quality == 0.5
        assert full_response.difficulty_factor == 1.0
        assert full_response.performance_trend == 0.0

    def test_adaptive_stability_fields(self, full_response):
        assert full_response.adaptive_stability == 1.0
        assert full_response.stability_growth_rate == 0.0
        assert full_response.half_life_days == 0.0

    def test_decay_parameter_fields(self, full_response):
        assert full_response.effective_decay_rate == 0.1
        assert full_response.time_to_critical == 0.0
        assert full_response.days_until_target == 0.0

    def test_reinforcement_fields(self, full_response):
        assert full_response.quality_variance == 0.0
        assert full_response.effective_revision_count == 0
        assert full_response.revision_effectiveness_ratio == 0.0
        assert full_response.time_pattern_regularity == 0.5
        assert full_response.confidence_calibration_error == 0.0

    def test_retention_history_fields(self, full_response):
        assert full_response.peak_retention == 0.0
        assert full_response.retention_at_last_revision == 0.0
        assert full_response.total_forgetting_events == 0
        assert full_response.last_forgetting_event_at is None

    def test_explicit_retention_evolution_values(self):
        resp = MemoryStateResponse(
            id=_UUID, user_id=_UUID, topic_id=_UUID,
            retention_score=0.8, stability_score=10.0, decay_rate=0.05,
            confidence_score=0.9, revision_strength=3.0, revision_count=5,
            forgetting_probability=0.2, urgency_score=0.3, updated_at=_NOW,
            adaptive_stability=8.5,
            stability_growth_rate=0.12,
            half_life_days=6.0,
            effective_decay_rate=0.08,
            quality_variance=0.15,
            effective_revision_count=4,
            revision_effectiveness_ratio=0.8,
            peak_retention=0.95,
            total_forgetting_events=1,
        )
        assert resp.adaptive_stability == 8.5
        assert resp.stability_growth_rate == 0.12
        assert resp.effective_revision_count == 4
        assert resp.peak_retention == 0.95

    def test_from_attributes_mode(self):
        assert MemoryStateResponse.model_config["from_attributes"] is True

    def test_field_count_minimum(self):
        """MemoryStateResponse should have at least 33 fields (12 core + 4 Phase 8.5 + 15 evolution + timestamps)."""
        field_count = len(MemoryStateResponse.model_fields)
        assert field_count >= 33


# ═══════════════════════════════════════════════════════════════════════════════
#  2. MemoryStateSummary — Retention Evolution Fields
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryStateSummaryFields:
    """MemoryStateSummary must expose all 15 retention evolution fields."""

    def test_all_evolution_fields_exist(self):
        fields = MemoryStateSummary.model_fields
        evolution_fields = [
            "adaptive_stability", "stability_growth_rate", "half_life_days",
            "effective_decay_rate", "time_to_critical", "days_until_target",
            "quality_variance", "effective_revision_count",
            "revision_effectiveness_ratio", "time_pattern_regularity",
            "confidence_calibration_error",
            "peak_retention", "retention_at_last_revision",
            "total_forgetting_events",
        ]
        for f in evolution_fields:
            assert f in fields, f"Missing field: {f}"

    def test_defaults_backward_compatible(self):
        summary = MemoryStateSummary(
            topic_id=_UUID,
            retention_score=0.5, stability_score=1.0,
            forgetting_probability=0.5, urgency_score=0.5,
            revision_count=0,
        )
        assert summary.adaptive_stability == 1.0
        assert summary.time_pattern_regularity == 0.5
        assert summary.total_forgetting_events == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  3. RecalibrationResponse — Extended Fields
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecalibrationResponseFields:
    """RecalibrationResponse must include all new_ retention evolution fields."""

    @pytest.fixture
    def minimal_delta(self):
        return StateDeltaResponse(
            retention_delta=0.1, stability_delta=0.5,
            decay_rate_new=0.08, confidence_delta=0.05,
            revision_strength_delta=0.3, revision_count_delta=1,
            forgetting_probability_new=0.2, urgency_delta=-0.1,
        )

    @pytest.fixture
    def minimal_response(self, minimal_delta):
        return RecalibrationResponse(
            user_id=_UUID, topic_id=_UUID, event_type="quiz_submitted",
            new_retention=0.8, new_stability=5.0, new_decay_rate=0.08,
            new_confidence=0.7, new_revision_strength=2.5, new_revision_count=3,
            new_forgetting_probability=0.2, new_urgency=0.4,
            delta=minimal_delta,
            changes=[], summary="Quiz processed",
        )

    def test_new_evolution_fields_have_defaults(self, minimal_response):
        assert minimal_response.new_adaptive_stability == 1.0
        assert minimal_response.new_stability_growth_rate == 0.0
        assert minimal_response.new_half_life_days == 0.0
        assert minimal_response.new_effective_decay_rate == 0.1
        assert minimal_response.new_quality_variance == 0.0
        assert minimal_response.new_effective_revision_count == 0
        assert minimal_response.new_revision_effectiveness_ratio == 0.0
        assert minimal_response.new_time_pattern_regularity == 0.5
        assert minimal_response.new_confidence_calibration_error == 0.0
        assert minimal_response.new_peak_retention == 0.0
        assert minimal_response.new_retention_at_last_revision == 0.0
        assert minimal_response.new_total_forgetting_events == 0

    def test_explicit_evolution_values(self, minimal_delta):
        resp = RecalibrationResponse(
            user_id=_UUID, topic_id=_UUID, event_type="revision_completed",
            new_retention=0.9, new_stability=8.0, new_decay_rate=0.05,
            new_confidence=0.85, new_revision_strength=3.0, new_revision_count=5,
            new_forgetting_probability=0.1, new_urgency=0.2,
            new_adaptive_stability=7.5,
            new_quality_variance=0.12,
            new_peak_retention=0.95,
            new_total_forgetting_events=2,
            delta=minimal_delta,
            changes=[], summary="Revision processed",
        )
        assert resp.new_adaptive_stability == 7.5
        assert resp.new_quality_variance == 0.12
        assert resp.new_peak_retention == 0.95
        assert resp.new_total_forgetting_events == 2

    def test_phase85_fields_in_response(self, minimal_response):
        assert minimal_response.new_base_stability == 1.0
        assert minimal_response.new_revision_quality == 0.5
        assert minimal_response.new_difficulty_factor == 1.0
        assert minimal_response.new_performance_trend == 0.0

    def test_field_count_minimum(self):
        """RecalibrationResponse should have 30+ fields."""
        assert len(RecalibrationResponse.model_fields) >= 30


# ═══════════════════════════════════════════════════════════════════════════════
#  4. StateDeltaResponse — Extended Fields
# ═══════════════════════════════════════════════════════════════════════════════

class TestStateDeltaResponseFields:
    """StateDeltaResponse must include all new delta fields."""

    def test_evolution_delta_fields_exist(self):
        fields = StateDeltaResponse.model_fields
        expected = [
            "adaptive_stability_new", "stability_growth_rate_new",
            "half_life_days_new", "effective_decay_rate_new",
            "time_to_critical_new", "days_until_target_new",
            "quality_variance_new", "effective_revision_count_delta",
            "revision_effectiveness_ratio_new", "time_pattern_regularity_new",
            "confidence_calibration_error_new",
            "peak_retention_new", "retention_at_last_revision_new",
            "total_forgetting_events_delta",
        ]
        for f in expected:
            assert f in fields, f"Missing delta field: {f}"

    def test_phase85_delta_fields_exist(self):
        fields = StateDeltaResponse.model_fields
        for f in ["base_stability_new", "revision_quality_new",
                   "difficulty_factor_new", "performance_trend_new"]:
            assert f in fields, f"Missing Phase 8.5 delta: {f}"

    def test_defaults_are_none_or_zero(self):
        delta = StateDeltaResponse(
            retention_delta=0.0, stability_delta=0.0,
            decay_rate_new=None, confidence_delta=0.0,
            revision_strength_delta=0.0, revision_count_delta=0,
            forgetting_probability_new=None, urgency_delta=0.0,
        )
        assert delta.adaptive_stability_new is None
        assert delta.quality_variance_new is None
        assert delta.effective_revision_count_delta == 0
        assert delta.total_forgetting_events_delta == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Request Schema Validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestRequestValidation:
    """Request schemas should enforce field constraints."""

    def test_retention_request_valid(self):
        req = RetentionPredictRequest(user_id=_UUID, topic_id=_UUID)
        assert req.user_id == _UUID

    def test_retention_request_quiz_score_bounds(self):
        with pytest.raises(ValidationError):
            RetentionPredictRequest(
                user_id=_UUID, topic_id=_UUID, quiz_score=1.5
            )

    def test_priority_request_valid(self):
        req = PriorityRankRequest(user_id=_UUID, topic_id=_UUID)
        assert req.user_id == _UUID

    def test_schedule_max_per_day_bounds(self):
        with pytest.raises(ValidationError):
            ScheduleGenerateRequest(
                user_id=_UUID, topic_ids=[_UUID], max_per_day=100
            )

    def test_recalibration_event_types(self):
        req = RecalibrationEventRequest(
            user_id=_UUID, topic_id=_UUID,
            event_type="quiz_submitted", quiz_score=0.8,
        )
        assert req.event_type == "quiz_submitted"

    def test_memory_init_defaults(self):
        init = MemoryStateInit(user_id=_UUID, topic_id=_UUID)
        assert init.retention_score == 0.0
        assert init.stability_score == 1.0
        assert init.decay_rate == 0.1
        assert init.confidence_score == 0.5


# ═══════════════════════════════════════════════════════════════════════════════
#  6. Response Schema Instantiation
# ═══════════════════════════════════════════════════════════════════════════════

class TestResponseInstantiation:
    """All response schemas should instantiate with minimal required fields."""

    def test_retention_predict_response(self):
        resp = RetentionPredictResponse(
            user_id=_UUID, topic_id=_UUID,
            retention_score=0.8, stability_score=5.0,
            confidence_score=0.7, forgetting_probability=0.2,
            decay_rate=0.1, revision_count=3,
            breakdown=RetentionBreakdown(
                base_strength=0.5, revision_reinforcement=0.2,
                quiz_boost=0.1, time_decay=-0.05, difficulty_penalty=-0.02
            ),
        )
        assert resp.retention_score == 0.8

    def test_priority_rank_response(self):
        resp = PriorityRankResponse(
            user_id=_UUID, topic_id=_UUID,
            priority_score=3.5, normalised_score=0.7, tier="high",
            retention_score=0.4, forgetting_probability=0.6,
            revision_count=2,
            breakdown=PriorityBreakdown(
                urgency_component=1.5, weakness_component=1.0,
                delay_component=0.8, exam_component=0.2,
            ),
            reason=PriorityReasonResponse(
                urgency_reason="Low retention",
                weakness_reason="Declining trend",
                delay_reason="3 days since revision",
                exam_reason="No exam pressure",
                summary="Needs revision",
            ),
        )
        assert resp.tier == "high"

    def test_schedule_single_response(self):
        resp = ScheduleSingleResponse(
            user_id=_UUID, topic_id=_UUID,
            next_revision_days=2.5, mode="long_term",
            schedule_priority=0.7,
            retention_score=0.6, revision_count=4,
            breakdown=ScheduleBreakdown(
                base_interval=3.0, adjusted_interval=2.5,
                retention_factor=0.8, difficulty_modifier=1.1,
                exam_compression=1.0,
            ),
            recommendation="Revise in 2–3 days.",
        )
        assert resp.next_revision_days == 2.5


# ═══════════════════════════════════════════════════════════════════════════════
#  7. Health Response
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthResponse:
    """Health response schema validation."""

    def test_health_response_fields(self):
        resp = HealthResponse(
            status="ok", engine="KnowDecay Engine",
            version="0.1.0", environment="test",
            timestamp="2026-01-01T00:00:00Z",
            uptime_seconds=123.45, database="connected",
            capabilities=["retention_prediction"],
        )
        assert resp.status == "ok"
        assert resp.database == "connected"
        assert len(resp.capabilities) == 1

    def test_degraded_status(self):
        resp = HealthResponse(
            status="degraded", engine="KnowDecay Engine",
            version="0.1.0", environment="test",
            timestamp="2026-01-01T00:00:00Z",
            uptime_seconds=0.5, database="unavailable",
            capabilities=[],
        )
        assert resp.status == "degraded"
        assert resp.database == "unavailable"


# ═══════════════════════════════════════════════════════════════════════════════
#  8. OpenAPI Tag Coverage
# ═══════════════════════════════════════════════════════════════════════════════

class TestOpenAPISupport:
    """FastAPI app should expose all routers with correct tags."""

    def test_app_imports_and_routes_registered(self):
        from app.main import app
        openapi_paths = app.openapi()["paths"]

        # Verify all 6 required capabilities are covered
        assert "/health" in openapi_paths
        assert "/v1/retention/predict" in openapi_paths
        assert "/v1/priority/rank/batch" in openapi_paths
        assert "/v1/recalibrate" in openapi_paths
        assert "/v1/schedule/generate" in openapi_paths
        assert "/v1/analytics/{user_id}/summary" in openapi_paths

    def test_openapi_schema_generates(self):
        from app.main import app
        schema = app.openapi()
        assert "paths" in schema
        assert len(schema["paths"]) >= 15  # We have 20+ endpoints

    def test_openapi_info_block(self):
        from app.main import app
        schema = app.openapi()
        assert schema["info"]["title"] == "KnowDecay Engine"
        assert "version" in schema["info"]
        assert "Retention Intelligence" in schema["info"]["description"]
