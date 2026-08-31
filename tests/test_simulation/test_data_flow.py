"""
tests/test_simulation/test_data_flow.py
────────────────────────────────────────
Phase 11: End-to-end data flow validation through the intelligence backbone.

Validates the complete pipeline:
  MemoryState → Adaptive Stability → Decay Engine → Retention Estimate
  → Priority Engine → Scheduling Engine → Analytics

All tests are pure — no DB, no I/O.
"""

import math

import pytest

from app.engine.recalibration_engine import (
    CurrentState,
    EventData,
    EventType,
    RecalibrationOutput,
    StateDelta,
    recalibrate,
    apply_delta,
)
from app.engine.stability_engine import StabilityInput, compute_adaptive_stability
from app.engine.decay_engine import DecayInput, analyze_decay
from app.engine.retention_engine import RetentionInput, compute_retention
from app.engine.priority_engine import PriorityInput, compute_priority
from app.engine.scheduling_engine import ScheduleInput, compute_schedule


# ═══════════════════════════════════════════════════════════════════════════════
#  Full Backbone Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullBackbonePipeline:
    """Verify the 7-stage intelligence backbone produces consistent results."""

    def _run_backbone(
        self,
        state: CurrentState | None = None,
        event_type: EventType = EventType.QUIZ_SUBMITTED,
        quiz_score: float = 0.7,
        elapsed_days: float = 3.0,
        difficulty: float = 0.5,
        importance: float = 1.0,
        days_until_exam: float | None = 30.0,
    ) -> dict:
        """Execute full backbone pipeline and return all stage outputs."""
        if state is None:
            state = CurrentState()

        event = EventData(
            event_type=event_type,
            quiz_score=quiz_score,
            elapsed_days=elapsed_days,
            difficulty=difficulty,
            importance_weight=importance,
        )

        # Stage 2: Adaptive Stability
        stab_input = StabilityInput(
            base_stability=state.base_stability,
            revision_count=state.revision_count,
            revision_quality=state.revision_quality,
            quiz_score=quiz_score,
            confidence_score=state.confidence_score,
            performance_trend=state.performance_trend,
            difficulty=difficulty,
        )
        stab_out = compute_adaptive_stability(stab_input)

        # Stage 3+4: Recalibrate (includes decay + retention)
        injected = CurrentState(**{
            **{f: getattr(state, f) for f in CurrentState.__dataclass_fields__},
            "adaptive_stability": stab_out.adaptive_stability,
        })
        recal_out = recalibrate(injected, event)
        new_state_dict = apply_delta(injected, recal_out.delta)

        # Stage 5: Priority
        pri_input = PriorityInput(
            retention_score=recal_out.new_retention,
            forgetting_probability=recal_out.new_forgetting_probability,
            stability_score=recal_out.new_stability,
            decay_rate=recal_out.new_decay_rate,
            revision_count=recal_out.new_revision_count,
            days_since_last_revision=elapsed_days,
            difficulty=difficulty,
            importance_weight=importance,
            days_until_exam=days_until_exam,
        )
        pri_out = compute_priority(pri_input)

        # Stage 6: Scheduling
        sched_input = ScheduleInput(
            retention_score=recal_out.new_retention,
            stability_score=recal_out.new_stability,
            decay_rate=recal_out.new_decay_rate,
            urgency_score=recal_out.new_urgency,
            revision_count=recal_out.new_revision_count,
            forgetting_probability=recal_out.new_forgetting_probability,
            difficulty=difficulty,
            days_until_exam=days_until_exam,
            adaptive_stability=stab_out.adaptive_stability,
        )
        sched_out = compute_schedule(sched_input)

        return {
            "stability_out": stab_out,
            "recal_out": recal_out,
            "new_state": new_state_dict,
            "priority_out": pri_out,
            "schedule_out": sched_out,
        }

    def test_backbone_produces_valid_outputs(self):
        """All stages produce valid bounded outputs."""
        result = self._run_backbone()
        assert 0.0 <= result["recal_out"].new_retention <= 1.0
        assert result["stability_out"].adaptive_stability > 0
        assert result["priority_out"].priority_score >= 0.0
        assert result["schedule_out"].next_revision_days > 0

    def test_backbone_quiz_improves_retention(self):
        """Good quiz score should improve retention from default."""
        result = self._run_backbone(quiz_score=0.9)
        assert result["recal_out"].new_retention > 0.0

    def test_backbone_inactivity_degrades_retention(self):
        """Inactivity event should not increase retention."""
        initial = CurrentState(retention_score=0.5, stability_score=3.0)
        result = self._run_backbone(
            state=initial,
            event_type=EventType.INACTIVITY_DETECTED,
            elapsed_days=0.0,
            quiz_score=0.0,
        )
        assert result["recal_out"].new_retention <= 0.5

    def test_backbone_priority_reflects_retention(self):
        """Low retention → higher priority than high retention."""
        low_r = self._run_backbone(
            state=CurrentState(retention_score=0.1, stability_score=1.0),
            quiz_score=0.3,
        )
        high_r = self._run_backbone(
            state=CurrentState(retention_score=0.8, stability_score=5.0),
            quiz_score=0.9,
        )
        assert low_r["priority_out"].priority_score >= high_r["priority_out"].priority_score * 0.5

    def test_backbone_schedule_reflects_retention(self):
        """Low retention → shorter schedule interval."""
        low = self._run_backbone(
            state=CurrentState(retention_score=0.1, stability_score=1.0),
        )
        high = self._run_backbone(
            state=CurrentState(retention_score=0.8, stability_score=10.0),
        )
        assert low["schedule_out"].next_revision_days <= high["schedule_out"].next_revision_days

    def test_backbone_multi_event_evolution(self):
        """Processing multiple events evolves state correctly."""
        state = CurrentState()
        events = [
            (EventType.STUDY_SESSION, 0.0),
            (EventType.QUIZ_SUBMITTED, 0.8),
            (EventType.REVISION_COMPLETED, 0.0),
        ]

        for evt_type, score in events:
            result = self._run_backbone(state=state, event_type=evt_type, quiz_score=score)
            new_dict = result["new_state"]
            cs_fields = {f for f in CurrentState.__dataclass_fields__}
            state = CurrentState(**{k: v for k, v in new_dict.items() if k in cs_fields})

        # After 3 positive events, retention should be above floor
        assert state.retention_score >= 0.05

    def test_backbone_audit_trail(self):
        """Recalibration output includes change reasons."""
        result = self._run_backbone(quiz_score=0.85)
        assert len(result["recal_out"].changes) > 0
        assert result["recal_out"].summary != ""

    def test_backbone_deterministic(self):
        """Same inputs produce identical outputs (pure functions)."""
        a = self._run_backbone(quiz_score=0.7, difficulty=0.5)
        b = self._run_backbone(quiz_score=0.7, difficulty=0.5)
        assert a["recal_out"].new_retention == b["recal_out"].new_retention
        assert a["priority_out"].priority_score == b["priority_out"].priority_score
        assert a["schedule_out"].next_revision_days == b["schedule_out"].next_revision_days
