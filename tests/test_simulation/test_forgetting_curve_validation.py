"""
tests/test_simulation/test_forgetting_curve_validation.py
──────────────────────────────────────────────────────────
Forgetting curve validation at discrete time checkpoints.

Validates the core Ebbinghaus forgetting curve:

    R(t) = e^(−t / S_adaptive)

at specific time points (0, 1, 3, 7, 15, 30, 60, 90 days) using both
the adaptive forgetting engine and the recalibration engine.

Test categories:
  1. Exponential accuracy — R matches math.exp(−t/S) within tolerance
  2. Monotonic decay     — R decreases over time for fixed S
  3. Stability ordering  — higher S → slower decay
  4. Floor / ceiling     — 0.05 ≤ R ≤ 1.0
  5. Recalibration path  — study event → verify decay over time
  6. Archetype curves    — 5 Phase 11 archetypes produce valid curves

All tests are pure — no DB, no HTTP, no I/O.
"""

import math
import random

import pytest

from app.engine.adaptive_forgetting import (
    ForgettingInput,
    ForgettingOutput,
    compute_adaptive_forgetting,
    compute_retention,
)
from app.engine.recalibration_engine import (
    CurrentState,
    EventData,
    EventType,
    RecalibrationOutput,
    recalibrate,
    apply_delta,
)
from simulation.learner_profiles import (
    Archetype,
    ARCHETYPE_CONFIGS,
    generate_learners,
    generate_topics,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════════════

TIME_POINTS: list[float] = [0, 1, 3, 7, 15, 30, 60, 90]
STABILITY_VALUES: list[float] = [1.0, 3.0, 7.0, 14.0, 30.0]
RETENTION_FLOOR: float = 0.05
RETENTION_CEILING: float = 1.0
ABS_TOL: float = 1e-4   # tolerance for exponential match
SEED: int = 42

PHASE_11_ARCHETYPES: list[Archetype] = [
    Archetype.BEGINNER,
    Archetype.AVERAGE,
    Archetype.ADVANCED,
    Archetype.INCONSISTENT,
    Archetype.HIGH_FREQUENCY,
]


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _expected_retention(t: float, s: float) -> float:
    """Ground-truth retention via the raw Ebbinghaus formula."""
    if t <= 0:
        return 1.0
    return max(math.exp(-t / s), RETENTION_FLOOR)


def _forgetting_output_at(
    elapsed_days: float,
    base_stability: float,
    *,
    revision_count: int = 0,
    quiz_score: float = 0.0,
    difficulty: float = 0.5,
) -> ForgettingOutput:
    """Convenience wrapper for compute_adaptive_forgetting."""
    inp = ForgettingInput(
        elapsed_days=elapsed_days,
        base_stability=base_stability,
        revision_count=revision_count,
        quiz_score=quiz_score,
        difficulty=difficulty,
    )
    return compute_adaptive_forgetting(inp, floor=RETENTION_FLOOR)


# ═══════════════════════════════════════════════════════════════════════════════
#  1. Exponential Accuracy — R matches e^(−t/S) at every time point
# ═══════════════════════════════════════════════════════════════════════════════

class TestExponentialAccuracy:
    """Verify the engine reproduces the raw exponential at each checkpoint."""

    @pytest.mark.parametrize("stability", STABILITY_VALUES)
    def test_retention_at_time_zero(self, stability: float):
        """t=0 → R = 1.0 regardless of stability."""
        out = _forgetting_output_at(0.0, stability)
        assert out.retention == pytest.approx(1.0, abs=ABS_TOL)

    @pytest.mark.parametrize("stability", STABILITY_VALUES)
    @pytest.mark.parametrize("t", [1, 3, 7, 15, 30, 60, 90])
    def test_retention_matches_exponential(self, stability: float, t: float):
        """
        R(t) from the engine must match e^(−t/S_adaptive) within tolerance.

        We compare against the engine's own adaptive_stability (which may
        differ from base_stability due to default learner parameters) to
        ensure the formula is correctly applied.
        """
        out = _forgetting_output_at(t, stability)
        s_eff = out.adaptive_stability  # effective S used in computation
        expected = _expected_retention(t, s_eff)
        assert out.retention == pytest.approx(expected, abs=ABS_TOL), (
            f"S_eff={s_eff:.4f}, t={t}, expected={expected:.6f}, got={out.retention}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  2. Monotonic Decay — R decreases over time for fixed stability
# ═══════════════════════════════════════════════════════════════════════════════

class TestMonotonicDecay:
    """R(t₁) ≥ R(t₂) whenever t₁ < t₂, for each stability value."""

    @pytest.mark.parametrize("stability", STABILITY_VALUES)
    def test_retention_monotonically_decreases(self, stability: float):
        """Walk through all time points and assert strict non-increase."""
        retentions = [
            _forgetting_output_at(t, stability).retention
            for t in TIME_POINTS
        ]
        for i in range(len(retentions) - 1):
            assert retentions[i] >= retentions[i + 1], (
                f"S={stability}, t={TIME_POINTS[i]}→{TIME_POINTS[i+1]}: "
                f"R={retentions[i]:.6f} < R={retentions[i+1]:.6f}"
            )

    def test_decay_is_strict_for_nonzero_time(self):
        """From t=0 onward, R should strictly decrease (not just ≥)."""
        stability = 7.0
        r0 = _forgetting_output_at(0.0, stability).retention
        r1 = _forgetting_output_at(1.0, stability).retention
        assert r0 > r1, "Retention must strictly decrease from t=0 to t=1"


# ═══════════════════════════════════════════════════════════════════════════════
#  3. Stability Ordering — higher S → slower decay
# ═══════════════════════════════════════════════════════════════════════════════

class TestStabilityOrdering:
    """Higher adaptive stability must produce higher retention at every t > 0."""

    @pytest.mark.parametrize("t", [1, 3, 7, 15, 30, 60, 90])
    def test_higher_stability_higher_retention(self, t: float):
        """
        For each pair of adjacent stability values S_low < S_high,
        R(t, S_high) > R(t, S_low).

        We use compute_retention directly with explicit S to isolate the
        comparison from the stability engine's transformations.
        """
        for i in range(len(STABILITY_VALUES) - 1):
            s_low = STABILITY_VALUES[i]
            s_high = STABILITY_VALUES[i + 1]
            r_low = compute_retention(t, s_low, floor=RETENTION_FLOOR)
            r_high = compute_retention(t, s_high, floor=RETENTION_FLOOR)
            assert r_high >= r_low, (
                f"t={t}, S={s_low}→{s_high}: R_high={r_high:.6f} < R_low={r_low:.6f}"
            )

    def test_double_stability_halves_decay_rate(self):
        """
        At t = S₁, R ≈ 1/e. At t = S₁ with S₂ = 2·S₁, R should be
        substantially higher because the time ratio is halved.
        """
        s1 = 7.0
        s2 = 14.0
        t = s1  # one time-constant for s1
        r1 = compute_retention(t, s1, floor=RETENTION_FLOOR)
        r2 = compute_retention(t, s2, floor=RETENTION_FLOOR)
        # r1 ≈ 1/e ≈ 0.368, r2 ≈ e^(-0.5) ≈ 0.607
        assert r2 > r1
        assert r1 == pytest.approx(1.0 / math.e, abs=0.01)
        assert r2 == pytest.approx(math.exp(-0.5), abs=0.01)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. Floor / Ceiling Bounds
# ═══════════════════════════════════════════════════════════════════════════════

class TestRetentionBounds:
    """R is always in [floor, 1.0]."""

    @pytest.mark.parametrize("stability", STABILITY_VALUES)
    @pytest.mark.parametrize("t", TIME_POINTS)
    def test_retention_within_bounds(self, stability: float, t: float):
        """Every (S, t) combination must respect the floor and ceiling."""
        out = _forgetting_output_at(t, stability)
        assert out.retention >= RETENTION_FLOOR - ABS_TOL, (
            f"Below floor: S={stability}, t={t}, R={out.retention}"
        )
        assert out.retention <= RETENTION_CEILING + ABS_TOL, (
            f"Above ceiling: S={stability}, t={t}, R={out.retention}"
        )

    def test_extreme_elapsed_time_hits_floor(self):
        """After thousands of days with low stability, retention sits at floor."""
        out = _forgetting_output_at(10000.0, 1.0)
        assert out.retention == pytest.approx(RETENTION_FLOOR, abs=ABS_TOL)

    def test_zero_elapsed_time_hits_ceiling(self):
        """t=0 → R = 1.0 exactly."""
        out = _forgetting_output_at(0.0, 1.0)
        assert out.retention == RETENTION_CEILING

    def test_forgetting_probability_complement(self):
        """forgetting_probability = 1 − R(t), always."""
        for t in TIME_POINTS:
            out = _forgetting_output_at(t, 7.0)
            expected_fp = round(1.0 - out.retention, 4)
            assert out.forgetting_probability == pytest.approx(expected_fp, abs=ABS_TOL)


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Recalibration Path — study event then decay verification
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecalibrationDecay:
    """
    Process a STUDY_SESSION event through recalibrate(), then verify
    that the adaptive forgetting curve decays correctly from the new state.
    """

    def test_study_event_then_decay_over_time(self):
        """
        After a study session:
          1. recalibrate produces a valid new state
          2. Using the new adaptive_stability, the forgetting curve
             decays monotonically and stays within bounds
        """
        # Initial state: fresh learner
        state = CurrentState(
            retention_score=0.5,
            stability_score=3.0,
            base_stability=3.0,
            adaptive_stability=3.0,
            revision_count=1,
            revision_quality=0.6,
            confidence_score=0.5,
            decay_rate=0.1,
        )
        event = EventData(
            event_type=EventType.STUDY_SESSION,
            study_duration_minutes=30.0,
            elapsed_days=1.0,
            difficulty=0.5,
        )

        result = recalibrate(state, event)

        # The recalibration should produce valid outputs
        assert result.new_retention >= RETENTION_FLOOR
        assert result.new_retention <= RETENTION_CEILING
        assert result.new_adaptive_stability > 0

        # Now verify the forgetting curve from the new state
        s_eff = result.new_adaptive_stability
        prev_r = RETENTION_CEILING
        for t in TIME_POINTS:
            r = compute_retention(t, s_eff, floor=RETENTION_FLOOR)
            assert r >= RETENTION_FLOOR
            assert r <= RETENTION_CEILING
            assert r <= prev_r, (
                f"Non-monotonic decay at t={t}: R={r:.6f} > prev={prev_r:.6f}"
            )
            prev_r = r

    def test_quiz_event_improves_stability(self):
        """
        A good quiz should increase adaptive_stability, producing a
        flatter (slower) decay curve compared to the pre-quiz state.
        """
        state = CurrentState(
            retention_score=0.4,
            stability_score=2.0,
            base_stability=2.0,
            adaptive_stability=2.0,
            revision_count=2,
            revision_quality=0.5,
            confidence_score=0.5,
            decay_rate=0.15,
        )
        event = EventData(
            event_type=EventType.QUIZ_SUBMITTED,
            quiz_score=0.9,
            quiz_confidence=0.8,
            elapsed_days=2.0,
            difficulty=0.5,
        )

        result = recalibrate(state, event)

        # Good quiz → stability should grow
        assert result.new_adaptive_stability >= state.adaptive_stability, (
            "Good quiz must not decrease adaptive stability"
        )

        # Verify the new curve is flatter: at t=7, new_R > old_R
        old_r7 = compute_retention(7.0, state.adaptive_stability, floor=RETENTION_FLOOR)
        new_r7 = compute_retention(7.0, result.new_adaptive_stability, floor=RETENTION_FLOOR)
        assert new_r7 >= old_r7, (
            f"Post-quiz curve should be flatter: old_R7={old_r7:.4f}, new_R7={new_r7:.4f}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  6. Multi-Stability Sweep
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultiStabilitySweep:
    """
    Sweep across all 5 stability values and validate the complete
    curve at every time checkpoint.
    """

    @pytest.mark.parametrize("stability", STABILITY_VALUES)
    def test_full_curve_accuracy(self, stability: float):
        """
        For a given base_stability (with default learner params), collect
        the entire curve and verify each point against ground truth.
        """
        for t in TIME_POINTS:
            out = _forgetting_output_at(t, stability)
            s_eff = out.adaptive_stability
            expected = _expected_retention(t, s_eff)
            assert out.retention == pytest.approx(expected, abs=ABS_TOL), (
                f"S_base={stability}, S_eff={s_eff:.4f}, t={t}: "
                f"expected={expected:.6f}, got={out.retention}"
            )

    def test_half_life_consistency(self):
        """
        Half-life = S × ln(2). Verify the reported half_life_days matches.
        """
        for stability in STABILITY_VALUES:
            out = _forgetting_output_at(1.0, stability)
            s_eff = out.adaptive_stability
            expected_hl = round(s_eff * math.log(2), 4)
            assert out.half_life_days == pytest.approx(expected_hl, abs=0.01), (
                f"S_base={stability}, S_eff={s_eff:.4f}: "
                f"expected HL={expected_hl:.4f}, got={out.half_life_days}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
#  7. Phase 11 Archetype Forgetting Curves
# ═══════════════════════════════════════════════════════════════════════════════

class TestArchetypeForgettingCurves:
    """
    For each Phase 11 archetype, generate a learner profile, derive
    representative inputs, and validate the forgetting curve.
    """

    @pytest.fixture(scope="class")
    def archetype_learners(self):
        """Generate one learner per Phase 11 archetype."""
        rng = random.Random(SEED)
        learners = {}
        for arch in PHASE_11_ARCHETYPES:
            config = ARCHETYPE_CONFIGS[arch]
            # Deterministic mid-range quiz score for this archetype
            score_lo, score_hi = config["quiz_score_range"]
            mid_score = (score_lo + score_hi) / 2.0
            learners[arch] = {
                "quiz_score": mid_score,
                "difficulty": 0.5,
                "revision_count": 3,
                "base_stability": 5.0,  # uniform starting point
            }
        return learners

    @pytest.mark.parametrize("archetype", PHASE_11_ARCHETYPES)
    def test_archetype_curve_monotonic(self, archetype, archetype_learners):
        """Each archetype's forgetting curve must decrease monotonically."""
        params = archetype_learners[archetype]
        prev_r = RETENTION_CEILING
        for t in TIME_POINTS:
            out = _forgetting_output_at(
                t,
                params["base_stability"],
                revision_count=params["revision_count"],
                quiz_score=params["quiz_score"],
                difficulty=params["difficulty"],
            )
            assert out.retention <= prev_r + ABS_TOL, (
                f"{archetype.value}: non-monotonic at t={t}"
            )
            prev_r = out.retention

    @pytest.mark.parametrize("archetype", PHASE_11_ARCHETYPES)
    def test_archetype_curve_within_bounds(self, archetype, archetype_learners):
        """Every point on an archetype's curve must respect floor/ceiling."""
        params = archetype_learners[archetype]
        for t in TIME_POINTS:
            out = _forgetting_output_at(
                t,
                params["base_stability"],
                revision_count=params["revision_count"],
                quiz_score=params["quiz_score"],
                difficulty=params["difficulty"],
            )
            assert out.retention >= RETENTION_FLOOR - ABS_TOL
            assert out.retention <= RETENTION_CEILING + ABS_TOL

    def test_advanced_decays_slower_than_beginner(self, archetype_learners):
        """
        Advanced learners have higher quiz scores → higher S_adaptive
        → flatter decay curve. At t=30, Advanced should retain more.
        """
        adv = archetype_learners[Archetype.ADVANCED]
        beg = archetype_learners[Archetype.BEGINNER]

        out_adv = _forgetting_output_at(
            30.0, adv["base_stability"],
            revision_count=adv["revision_count"],
            quiz_score=adv["quiz_score"],
            difficulty=adv["difficulty"],
        )
        out_beg = _forgetting_output_at(
            30.0, beg["base_stability"],
            revision_count=beg["revision_count"],
            quiz_score=beg["quiz_score"],
            difficulty=beg["difficulty"],
        )
        assert out_adv.retention >= out_beg.retention, (
            f"Advanced R30={out_adv.retention:.4f} < "
            f"Beginner R30={out_beg.retention:.4f}"
        )

    def test_advanced_has_higher_stability(self, archetype_learners):
        """Advanced archetype should produce higher adaptive_stability."""
        adv = archetype_learners[Archetype.ADVANCED]
        beg = archetype_learners[Archetype.BEGINNER]

        out_adv = _forgetting_output_at(
            1.0, adv["base_stability"],
            revision_count=adv["revision_count"],
            quiz_score=adv["quiz_score"],
            difficulty=adv["difficulty"],
        )
        out_beg = _forgetting_output_at(
            1.0, beg["base_stability"],
            revision_count=beg["revision_count"],
            quiz_score=beg["quiz_score"],
            difficulty=beg["difficulty"],
        )
        assert out_adv.adaptive_stability >= out_beg.adaptive_stability, (
            f"Advanced S_eff={out_adv.adaptive_stability:.4f} < "
            f"Beginner S_eff={out_beg.adaptive_stability:.4f}"
        )

    @pytest.mark.parametrize("archetype", PHASE_11_ARCHETYPES)
    def test_archetype_curve_matches_exponential(self, archetype, archetype_learners):
        """Each archetype's curve must match the exponential formula exactly."""
        params = archetype_learners[archetype]
        for t in TIME_POINTS:
            out = _forgetting_output_at(
                t,
                params["base_stability"],
                revision_count=params["revision_count"],
                quiz_score=params["quiz_score"],
                difficulty=params["difficulty"],
            )
            s_eff = out.adaptive_stability
            expected = _expected_retention(t, s_eff)
            assert out.retention == pytest.approx(expected, abs=ABS_TOL), (
                f"{archetype.value}: t={t}, S_eff={s_eff:.4f}, "
                f"expected={expected:.6f}, got={out.retention}"
            )
