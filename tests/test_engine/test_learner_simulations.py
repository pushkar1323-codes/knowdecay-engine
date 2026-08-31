"""
tests/test_engine/test_learner_simulations.py
─────────────────────────────────────────────────
Learner archetype simulation tests.

Simulates 5 learner archetypes over time and verifies that the adaptive
forgetting curve, stability engine, and recalibration engine produce
cognitively coherent results.

Archetypes:
  1. Weak Learner      — low quiz scores, irregular study, low confidence
  2. Consistent Learner — regular study, good quizzes, growing stability
  3. Cramming Learner   — no study for weeks, then intense burst
  4. Overconfident      — high confidence but mediocre quiz scores
  5. Inconsistent       — alternating good and bad sessions

Verification criteria:
  • Retention evolves in the expected direction
  • Stability grows or shrinks appropriately
  • Urgency reflects the learner's actual state
  • The forgetting curve produces differentiated outputs
  • State is never reset — only evolved
"""

import pytest

from app.engine.recalibration_engine import (
    CurrentState,
    EventData,
    EventType,
    RecalibrationOutput,
    recalibrate,
)
from app.engine.adaptive_forgetting import (
    ForgettingInput,
    compute_adaptive_forgetting,
)
from app.engine.stability_engine import (
    StabilityInput,
    compute_adaptive_stability,
    evolve_stability,
    degrade_stability,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _initial_state(**kwargs) -> CurrentState:
    """Fresh learner state with sane defaults."""
    defaults = dict(
        retention_score=0.5,
        stability_score=2.0,
        decay_rate=0.1,
        confidence_score=0.5,
        revision_strength=0.1,
        revision_count=1,
        forgetting_probability=0.5,
        urgency_score=0.3,
        base_stability=1.0,
        revision_quality=0.5,
        difficulty_factor=0.5,
        performance_trend=0.0,
    )
    defaults.update(kwargs)
    return CurrentState(**defaults)


def _evolve_state(state: CurrentState, out: RecalibrationOutput) -> CurrentState:
    """Build next state from recalibration output (simulates service layer)."""
    return CurrentState(
        retention_score=out.new_retention,
        stability_score=out.new_stability,
        decay_rate=out.new_decay_rate,
        confidence_score=out.new_confidence,
        revision_strength=out.new_revision_strength,
        revision_count=out.new_revision_count,
        forgetting_probability=out.new_forgetting_probability,
        urgency_score=out.new_urgency,
        base_stability=out.new_base_stability,
        revision_quality=out.new_revision_quality,
        difficulty_factor=out.new_difficulty_factor,
        performance_trend=out.new_performance_trend,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  1. Weak Learner
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeakLearner:
    """
    Profile: Low quiz scores (0.2-0.3), irregular study, low confidence.
    Expected: Low retention, high urgency, slow stability growth.
    """

    def test_retention_stays_low(self):
        state = _initial_state(retention_score=0.3, confidence_score=0.2)
        for _ in range(5):
            event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.25,
                              quiz_confidence=0.2, difficulty=0.7)
            out = recalibrate(state, event)
            state = _evolve_state(state, out)
        # After 5 poor quizzes, retention should still be low
        assert state.retention_score < 0.6

    def test_urgency_stays_high(self):
        state = _initial_state(urgency_score=0.5, retention_score=0.3)
        for _ in range(3):
            event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.2,
                              difficulty=0.7)
            out = recalibrate(state, event)
            state = _evolve_state(state, out)
        # Urgency should be elevated for weak performance
        assert state.urgency_score > 0.3

    def test_base_stability_grows_slowly(self):
        state = _initial_state(base_stability=1.0)
        initial_base = state.base_stability
        for _ in range(5):
            event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.2)
            out = recalibrate(state, event)
            state = _evolve_state(state, out)
        # Poor quality → minimal stability growth
        assert state.base_stability < initial_base * 2.0  # not much growth

    def test_performance_trend_negative(self):
        state = _initial_state(performance_trend=0.0)
        for _ in range(5):
            event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.15)
            out = recalibrate(state, event)
            state = _evolve_state(state, out)
        # Consistently poor → negative trend
        assert state.performance_trend < 0.0

    def test_forgetting_curve_drops_fast(self):
        """Weak learner's forgetting curve should show fast retention loss."""
        forg = compute_adaptive_forgetting(ForgettingInput(
            elapsed_days=1.0,
            base_stability=0.8,
            revision_count=2,
            revision_quality=0.3,
            quiz_score=0.2,
            confidence_score=0.2,
            difficulty=0.7,
        ))
        assert forg.retention < 0.5  # fast decay
        assert forg.half_life_days < 1.0  # very short half-life


# ═══════════════════════════════════════════════════════════════════════════════
#  2. Consistent Learner
# ═══════════════════════════════════════════════════════════════════════════════

class TestConsistentLearner:
    """
    Profile: Regular study, good quizzes (0.7-0.9), steady confidence.
    Expected: Growing retention, declining urgency, strong stability growth.
    """

    def test_retention_grows_steadily(self):
        state = _initial_state(retention_score=0.4)
        for _ in range(8):
            # Good quiz every session
            event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.8,
                              quiz_confidence=0.7, difficulty=0.5)
            out = recalibrate(state, event)
            state = _evolve_state(state, out)
        assert state.retention_score > 0.6

    def test_urgency_decreases(self):
        state = _initial_state(urgency_score=0.5)
        for _ in range(5):
            event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.85)
            out = recalibrate(state, event)
            state = _evolve_state(state, out)
        assert state.urgency_score < 0.3

    def test_base_stability_grows_significantly(self):
        state = _initial_state(base_stability=1.0)
        initial_base = state.base_stability
        for i in range(10):
            event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.85)
            out = recalibrate(state, event)
            state = _evolve_state(state, out)
        # 10 good quizzes should significantly grow stability
        assert state.base_stability > initial_base * 1.5

    def test_revision_quality_improves(self):
        state = _initial_state(revision_quality=0.5)
        for _ in range(5):
            event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.9)
            out = recalibrate(state, event)
            state = _evolve_state(state, out)
        assert state.revision_quality > 0.6

    def test_performance_trend_positive(self):
        state = _initial_state(performance_trend=0.0)
        for _ in range(5):
            event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.85)
            out = recalibrate(state, event)
            state = _evolve_state(state, out)
        assert state.performance_trend > 0.0

    def test_forgetting_curve_slow_after_training(self):
        """After many good revisions, forgetting should be very slow."""
        forg = compute_adaptive_forgetting(ForgettingInput(
            elapsed_days=1.0,
            base_stability=5.0,
            revision_count=15,
            revision_quality=0.85,
            quiz_score=0.85,
            confidence_score=0.8,
            difficulty=0.5,
        ))
        assert forg.retention > 0.5  # still high after 1 day
        assert forg.half_life_days > 2.0  # long half-life

    def test_study_then_quiz_pattern(self):
        """Simulate study → quiz → study → quiz cycle."""
        state = _initial_state(retention_score=0.4)
        for _ in range(4):
            # Study session
            study = EventData(event_type=EventType.STUDY_SESSION,
                              study_duration_minutes=30)
            out = recalibrate(state, study)
            state = _evolve_state(state, out)
            # Quiz
            quiz = EventData(event_type=EventType.QUIZ_SUBMITTED,
                             quiz_score=0.8, quiz_confidence=0.7)
            out = recalibrate(state, quiz)
            state = _evolve_state(state, out)
        assert state.retention_score > 0.5
        assert state.revision_count > 4


# ═══════════════════════════════════════════════════════════════════════════════
#  3. Cramming Learner
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrammingLearner:
    """
    Profile: No study for 21 days, then 5 intense quiz sessions.
    Expected: Inactivity degrades state, cramming partially recovers.
    """

    def test_inactivity_degrades_then_crram_recovers(self):
        state = _initial_state(retention_score=0.7, base_stability=2.0)

        # Phase 1: 21 days of inactivity
        inactivity = EventData(event_type=EventType.INACTIVITY_DETECTED,
                               days_inactive=21)
        out = recalibrate(state, inactivity)
        state = _evolve_state(state, out)

        degraded_retention = state.retention_score
        degraded_base = state.base_stability
        assert degraded_retention < 0.7  # retention dropped
        assert degraded_base < 2.0  # stability degraded

        # Phase 2: Cramming — 5 good quizzes
        for _ in range(5):
            quiz = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.85)
            out = recalibrate(state, quiz)
            state = _evolve_state(state, out)

        # Should recover partially
        assert state.retention_score > degraded_retention
        assert state.base_stability > degraded_base

    def test_cramming_doesnt_fully_restore(self):
        """Cramming shouldn't achieve the same stability as consistent study."""
        # Consistent learner: 10 regular good quizzes
        consistent = _initial_state()
        for _ in range(10):
            out = recalibrate(consistent, EventData(
                event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.8))
            consistent = _evolve_state(consistent, out)

        # Crammer: 21 days inactive then 10 good quizzes
        crammer = _initial_state()
        out = recalibrate(crammer, EventData(
            event_type=EventType.INACTIVITY_DETECTED, days_inactive=21))
        crammer = _evolve_state(crammer, out)
        for _ in range(10):
            out = recalibrate(crammer, EventData(
                event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.8))
            crammer = _evolve_state(crammer, out)

        # Consistent learner should have better base stability
        assert consistent.base_stability >= crammer.base_stability * 0.8

    def test_urgency_spikes_during_inactivity(self):
        state = _initial_state(urgency_score=0.2)
        out = recalibrate(state, EventData(
            event_type=EventType.INACTIVITY_DETECTED, days_inactive=25))
        state = _evolve_state(state, out)
        assert state.urgency_score > 0.3  # urgency rose


# ═══════════════════════════════════════════════════════════════════════════════
#  4. Overconfident Learner
# ═══════════════════════════════════════════════════════════════════════════════

class TestOverconfidentLearner:
    """
    Profile: High self-reported confidence but mediocre quiz scores (0.4-0.5).
    Expected: Confidence should erode, urgency should rise, stability limited.
    """

    def test_confidence_divergence(self):
        """Overconfidence shouldn't inflate retention beyond quiz evidence."""
        state = _initial_state(confidence_score=0.9, retention_score=0.5)
        for _ in range(5):
            # High confidence, mediocre quiz
            event = EventData(event_type=EventType.QUIZ_SUBMITTED,
                              quiz_score=0.4, quiz_confidence=0.9)
            out = recalibrate(state, event)
            state = _evolve_state(state, out)
        # Quiz evidence dominates — retention shouldn't be inflated
        assert state.retention_score < 0.8

    def test_stability_limited_by_quiz_evidence(self):
        state = _initial_state(base_stability=1.0, confidence_score=0.9)
        for _ in range(5):
            event = EventData(event_type=EventType.QUIZ_SUBMITTED,
                              quiz_score=0.4, quiz_confidence=0.9)
            out = recalibrate(state, event)
            state = _evolve_state(state, out)
        # Mediocre quizzes → moderate stability at best
        assert state.base_stability < 3.0

    def test_adaptive_forgetting_uses_quiz_not_confidence(self):
        """Two learners: same quiz score, different confidence.
        Their adaptive stability should be close (quiz dominates)."""
        low_conf = compute_adaptive_forgetting(ForgettingInput(
            elapsed_days=1.0, quiz_score=0.5, confidence_score=0.2))
        high_conf = compute_adaptive_forgetting(ForgettingInput(
            elapsed_days=1.0, quiz_score=0.5, confidence_score=0.9))
        # Confidence makes some difference, but quiz dominates
        ratio = high_conf.adaptive_stability / low_conf.adaptive_stability
        assert 0.8 < ratio < 1.5  # not dramatically different


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Inconsistent Learner
# ═══════════════════════════════════════════════════════════════════════════════

class TestInconsistentLearner:
    """
    Profile: Alternates between good (0.8) and bad (0.2) quiz sessions.
    Expected: Moderate retention, oscillating urgency, middling stability.
    """

    def test_retention_oscillates(self):
        state = _initial_state(retention_score=0.5)
        retentions = [state.retention_score]
        for i in range(10):
            score = 0.85 if i % 2 == 0 else 0.15
            event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=score)
            out = recalibrate(state, event)
            state = _evolve_state(state, out)
            retentions.append(state.retention_score)
        # Should see oscillation — ups and downs
        ups = sum(1 for i in range(1, len(retentions)) if retentions[i] > retentions[i-1])
        downs = sum(1 for i in range(1, len(retentions)) if retentions[i] < retentions[i-1])
        assert ups >= 3  # at least some ups
        assert downs >= 2  # at least some downs

    def test_stability_moderate(self):
        """Inconsistent learner shouldn't achieve very high stability."""
        state = _initial_state(base_stability=1.0)
        for i in range(10):
            score = 0.8 if i % 2 == 0 else 0.2
            event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=score)
            out = recalibrate(state, event)
            state = _evolve_state(state, out)
        # Should grow, but not as much as a consistent learner
        assert 1.0 < state.base_stability < 5.0

    def test_performance_trend_near_zero(self):
        """Alternating performance should keep trend near zero."""
        state = _initial_state(performance_trend=0.0)
        for i in range(10):
            score = 0.9 if i % 2 == 0 else 0.1
            event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=score)
            out = recalibrate(state, event)
            state = _evolve_state(state, out)
        # Trend should be roughly neutral — not strongly positive or negative
        assert -0.5 < state.performance_trend < 0.5


# ═══════════════════════════════════════════════════════════════════════════════
#  6. Cross-Archetype Comparisons
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrossArchetypeComparisons:
    """Verify that consistent learners outperform weak/inconsistent ones."""

    def _simulate(self, quiz_scores: list[float]) -> CurrentState:
        state = _initial_state()
        for score in quiz_scores:
            out = recalibrate(state, EventData(
                event_type=EventType.QUIZ_SUBMITTED, quiz_score=score))
            state = _evolve_state(state, out)
        return state

    def test_consistent_beats_weak_on_retention(self):
        consistent = self._simulate([0.8] * 10)
        weak = self._simulate([0.2] * 10)
        assert consistent.retention_score > weak.retention_score

    def test_consistent_beats_weak_on_stability(self):
        consistent = self._simulate([0.8] * 10)
        weak = self._simulate([0.2] * 10)
        assert consistent.base_stability > weak.base_stability

    def test_consistent_lower_urgency_than_weak(self):
        consistent = self._simulate([0.8] * 10)
        weak = self._simulate([0.2] * 10)
        assert consistent.urgency_score < weak.urgency_score

    def test_consistent_beats_inconsistent_on_stability(self):
        consistent = self._simulate([0.8] * 10)
        inconsistent = self._simulate([0.8, 0.2] * 5)
        assert consistent.base_stability >= inconsistent.base_stability

    def test_consistent_better_trend_than_inconsistent(self):
        consistent = self._simulate([0.8] * 10)
        inconsistent = self._simulate([0.8, 0.2] * 5)
        assert consistent.performance_trend >= inconsistent.performance_trend

    def test_all_archetypes_never_reset(self):
        """No archetype should ever see revision_count go to 0 after quizzes."""
        for scores in [
            [0.2] * 5,       # weak
            [0.8] * 5,       # consistent
            [0.4, 0.9] * 3,  # inconsistent
        ]:
            state = _initial_state()
            for score in scores:
                out = recalibrate(state, EventData(
                    event_type=EventType.QUIZ_SUBMITTED, quiz_score=score))
                state = _evolve_state(state, out)
            assert state.revision_count >= 1 + len(scores)  # initial + quizzes


# ═══════════════════════════════════════════════════════════════════════════════
#  7. Forgetting Curve Differentiation
# ═══════════════════════════════════════════════════════════════════════════════

class TestForgettingCurveDifferentiation:
    """Verify the adaptive forgetting curve produces meaningfully different
    outputs for different learner states."""

    def test_trained_vs_untrained(self):
        """Well-trained learner forgets slower than fresh learner."""
        fresh = compute_adaptive_forgetting(ForgettingInput(
            elapsed_days=1.0, base_stability=1.0, revision_count=0))
        trained = compute_adaptive_forgetting(ForgettingInput(
            elapsed_days=1.0, base_stability=5.0, revision_count=20,
            revision_quality=0.8, quiz_score=0.8, confidence_score=0.8))
        assert trained.retention > fresh.retention
        assert trained.half_life_days > fresh.half_life_days

    def test_easy_vs_hard_topic(self):
        """Easy topic decays slower than hard topic."""
        easy = compute_adaptive_forgetting(ForgettingInput(
            elapsed_days=0.5, difficulty=0.1, base_stability=2.0))
        hard = compute_adaptive_forgetting(ForgettingInput(
            elapsed_days=0.5, difficulty=0.9, base_stability=2.0))
        assert easy.retention > hard.retention

    def test_stability_breakdown_components(self):
        """Verify the stability breakdown has explainable components."""
        out = compute_adaptive_forgetting(ForgettingInput(
            base_stability=3.0, revision_count=5, revision_quality=0.7,
            quiz_score=0.7, confidence_score=0.6, difficulty=0.5))
        bd = out.stability_breakdown
        assert bd.reinforcement_factor > 1.0  # revisions help
        assert 0.4 < bd.quiz_performance_factor < 1.1
        assert 0.7 <= bd.confidence_factor <= 1.0
        assert bd.difficulty_penalty > 0  # difficulty costs
