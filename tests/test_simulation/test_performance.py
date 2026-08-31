"""
tests/test_simulation/test_performance.py
──────────────────────────────────────────
Phase 11: Performance validation for KnowDecay engine operations.

Validates that core engine computations complete within acceptable time:
  • Retention computation
  • Decay computation
  • Priority scoring
  • Schedule generation
  • Recalibration
  • Full backbone pipeline
  • Batch operations (1000 topics)

Uses wall-clock timing with generous thresholds. These tests verify
the engine is not catastrophically slow — not micro-benchmarks.

All tests are pure — no DB, no I/O.
"""

import time
import math

import pytest

from app.engine.recalibration_engine import (
    CurrentState,
    EventData,
    EventType,
    recalibrate,
    apply_delta,
)
from app.engine.retention_engine import RetentionInput, compute_retention
from app.engine.decay_engine import DecayInput, analyze_decay
from app.engine.stability_engine import StabilityInput, compute_adaptive_stability
from app.engine.priority_engine import PriorityInput, compute_priority
from app.engine.scheduling_engine import ScheduleInput, compute_schedule
from app.engine.adaptive_forgetting import ForgettingInput, compute_adaptive_forgetting
from simulation.learner_profiles import generate_learners
from simulation.timeline_simulator import run_simulation


# ═══════════════════════════════════════════════════════════════════════════════
#  Timing Helper
# ═══════════════════════════════════════════════════════════════════════════════

def _time_fn(fn, *args, iterations: int = 100, **kwargs) -> float:
    """Run fn iterations times and return total elapsed seconds."""
    start = time.perf_counter()
    for _ in range(iterations):
        fn(*args, **kwargs)
    return time.perf_counter() - start


# ═══════════════════════════════════════════════════════════════════════════════
#  Individual Engine Performance
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnginePerformance:
    """Verify individual engine operations complete quickly."""

    def test_retention_computation_fast(self):
        """100 retention computations complete under 1 second."""
        ri = RetentionInput(
            quiz_score=0.7,
            quiz_confidence=0.6,
            has_quiz=True,
            revision_count=3,
            revision_strength=0.3,
            elapsed_days=7.0,
            decay_rate=0.1,
            difficulty=0.5,
            importance_weight=1.0,
        )
        elapsed = _time_fn(compute_retention, ri)
        assert elapsed < 1.0, f"100 retention calls took {elapsed:.3f}s"

    def test_decay_computation_fast(self):
        """100 decay computations complete under 1 second."""
        di = DecayInput(
            current_retention=0.5,
            current_decay_rate=0.1,
            difficulty=0.5,
            revision_count=3,
            days_since_last_revision=7.0,
        )
        elapsed = _time_fn(analyze_decay, di)
        assert elapsed < 1.0, f"100 decay calls took {elapsed:.3f}s"

    def test_stability_computation_fast(self):
        """100 stability computations complete under 1 second."""
        si = StabilityInput(
            base_stability=3.0,
            revision_count=5,
            revision_quality=0.7,
            quiz_score=0.8,
            confidence_score=0.6,
            performance_trend=0.1,
            difficulty=0.5,
        )
        elapsed = _time_fn(compute_adaptive_stability, si)
        assert elapsed < 1.0, f"100 stability calls took {elapsed:.3f}s"

    def test_priority_computation_fast(self):
        """100 priority computations complete under 1 second."""
        pi = PriorityInput(
            retention_score=0.4,
            forgetting_probability=0.6,
            stability_score=3.0,
            decay_rate=0.1,
            revision_count=2,
            days_since_last_revision=7.0,
            difficulty=0.5,
            importance_weight=1.0,
            days_until_exam=30.0,
        )
        elapsed = _time_fn(compute_priority, pi)
        assert elapsed < 1.0, f"100 priority calls took {elapsed:.3f}s"

    def test_schedule_computation_fast(self):
        """100 schedule computations complete under 1 second."""
        si = ScheduleInput(
            retention_score=0.5,
            stability_score=3.0,
            decay_rate=0.1,
            urgency_score=0.4,
            revision_count=3,
            forgetting_probability=0.5,
            difficulty=0.5,
            days_until_exam=30.0,
        )
        elapsed = _time_fn(compute_schedule, si)
        assert elapsed < 1.0, f"100 schedule calls took {elapsed:.3f}s"

    def test_recalibration_fast(self):
        """100 recalibrations complete under 2 seconds."""
        state = CurrentState(retention_score=0.5, stability_score=3.0)
        event = EventData(
            event_type=EventType.QUIZ_SUBMITTED,
            quiz_score=0.7,
            elapsed_days=3.0,
            difficulty=0.5,
        )
        elapsed = _time_fn(recalibrate, state, event)
        assert elapsed < 2.0, f"100 recalibrations took {elapsed:.3f}s"


# ═══════════════════════════════════════════════════════════════════════════════
#  Batch / Scale Performance
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchPerformance:
    """Verify engine handles realistic batch sizes."""

    def test_1000_priority_rankings(self):
        """Ranking 1000 topics completes under 5 seconds."""
        topics = []
        for i in range(1000):
            topics.append(PriorityInput(
                retention_score=0.05 + (i / 1000) * 0.9,
                forgetting_probability=0.95 - (i / 1000) * 0.9,
                stability_score=1.0 + i * 0.01,
                decay_rate=0.05 + (i / 1000) * 0.2,
                revision_count=i % 20,
                days_since_last_revision=float(i % 30 + 1),
                difficulty=0.1 + (i / 1000) * 0.8,
                importance_weight=0.5 + (i / 1000),
                days_until_exam=30.0,
            ))

        start = time.perf_counter()
        results = [compute_priority(t) for t in topics]
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"1000 priority rankings took {elapsed:.3f}s"
        assert len(results) == 1000

    def test_simulation_10_learners_30_days(self):
        """Full simulation (10 learners × 8 topics × 30 days) under 10 seconds."""
        learners = generate_learners(10, 8, days_until_exam=30.0, seed=456)
        start = time.perf_counter()
        results = run_simulation(learners, total_days=30, base_seed=456)
        elapsed = time.perf_counter() - start

        assert elapsed < 10.0, f"10-learner simulation took {elapsed:.3f}s"
        assert len(results) == 10
        for r in results:
            assert r.total_events >= 0
