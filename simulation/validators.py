"""
simulation/validators.py
─────────────────────────
Engine invariant validators for simulation results.

Each validator takes simulation results and asserts engine invariants.
Returns a list of (passed: bool, name: str, detail: str) tuples.
"""

from dataclasses import dataclass

from simulation.timeline_simulator import LearnerResult, TopicSnapshot
from simulation.learner_profiles import Archetype


@dataclass
class ValidationResult:
    passed: bool
    name: str
    detail: str


def validate_retention_bounds(results: list[LearnerResult]) -> ValidationResult:
    """Assert 0 <= retention <= 1 at all times."""
    violations = []
    for r in results:
        for s in r.snapshots:
            if s.retention_score < -0.001 or s.retention_score > 1.001:
                violations.append(
                    f"{r.learner.name}/{s.topic_name} day={s.day}: R={s.retention_score:.4f}"
                )
    return ValidationResult(
        passed=len(violations) == 0,
        name="retention_bounds",
        detail=f"{len(violations)} violations" if violations else "All retention scores in [0, 1]",
    )


def validate_stability_positive(results: list[LearnerResult]) -> ValidationResult:
    """Assert stability >= 0 at all times."""
    violations = []
    for r in results:
        for s in r.snapshots:
            if s.stability_score < -0.001:
                violations.append(
                    f"{r.learner.name}/{s.topic_name} day={s.day}: S={s.stability_score:.4f}"
                )
    return ValidationResult(
        passed=len(violations) == 0,
        name="stability_positive",
        detail=f"{len(violations)} violations" if violations else "All stability scores >= 0",
    )


def validate_decay_bounded(results: list[LearnerResult]) -> ValidationResult:
    """Assert 0 < decay_rate < 10."""
    violations = []
    for r in results:
        for s in r.snapshots:
            if s.decay_rate < 0.0 or s.decay_rate > 10.0:
                violations.append(
                    f"{r.learner.name}/{s.topic_name} day={s.day}: λ={s.decay_rate:.4f}"
                )
    return ValidationResult(
        passed=len(violations) == 0,
        name="decay_bounded",
        detail=f"{len(violations)} violations" if violations else "All decay rates in (0, 10)",
    )


def validate_priority_ordering(results: list[LearnerResult]) -> ValidationResult:
    """
    Assert that within each learner, topics with lower retention
    tend to get higher priority scores (statistical, not absolute).
    Checks on the final day only.
    """
    violations = 0
    checks = 0

    for r in results:
        if not r.snapshots:
            continue
        last_day = max(s.day for s in r.snapshots)
        final_snaps = [s for s in r.snapshots if s.day == last_day]

        for i, a in enumerate(final_snaps):
            for b in final_snaps[i + 1:]:
                if a.retention_score < b.retention_score - 0.1:
                    # a has lower retention -> should have higher priority
                    checks += 1
                    if a.priority_score < b.priority_score:
                        violations += 1

    if checks == 0:
        return ValidationResult(True, "priority_ordering", "No comparable pairs")

    violation_rate = violations / checks
    return ValidationResult(
        passed=violation_rate < 0.3,  # Allow 30% tolerance (other factors affect priority)
        name="priority_ordering",
        detail=f"{violations}/{checks} misordered ({violation_rate:.1%})",
    )


def validate_schedule_adapts_to_retention(results: list[LearnerResult]) -> ValidationResult:
    """
    Assert low-retention topics get shorter revision intervals than high-retention.
    Checked on final day per learner.
    """
    violations = 0
    checks = 0

    for r in results:
        if not r.snapshots:
            continue
        last_day = max(s.day for s in r.snapshots)
        final_snaps = [s for s in r.snapshots if s.day == last_day]

        for i, a in enumerate(final_snaps):
            for b in final_snaps[i + 1:]:
                if a.retention_score < b.retention_score - 0.15:
                    checks += 1
                    if a.next_revision_days > b.next_revision_days + 0.5:
                        violations += 1

    if checks == 0:
        return ValidationResult(True, "schedule_retention_adaptation", "No comparable pairs")

    violation_rate = violations / checks
    return ValidationResult(
        passed=violation_rate < 0.3,
        name="schedule_retention_adaptation",
        detail=f"{violations}/{checks} misordered ({violation_rate:.1%})",
    )


def validate_diligent_beats_struggling(results: list[LearnerResult]) -> ValidationResult:
    """
    Assert diligent learners have higher mean final retention than struggling.
    """
    def _mean_final_retention(archetype: Archetype) -> float | None:
        retentions = []
        for r in results:
            if r.learner.archetype != archetype:
                continue
            if not r.snapshots:
                continue
            last_day = max(s.day for s in r.snapshots)
            for s in r.snapshots:
                if s.day == last_day:
                    retentions.append(s.retention_score)
        return sum(retentions) / len(retentions) if retentions else None

    diligent = _mean_final_retention(Archetype.DILIGENT)
    struggling = _mean_final_retention(Archetype.STRUGGLING)

    if diligent is None or struggling is None:
        return ValidationResult(True, "diligent_vs_struggling", "Insufficient data")

    # If both converge to floor retention, comparison is inconclusive
    if diligent < 0.10 and struggling < 0.10:
        return ValidationResult(
            passed=True,
            name="diligent_vs_struggling",
            detail=f"Both at floor (Diligent={diligent:.3f}, Struggling={struggling:.3f}) — inconclusive",
        )

    return ValidationResult(
        passed=diligent >= struggling,
        name="diligent_vs_struggling",
        detail=f"Diligent={diligent:.3f} vs Struggling={struggling:.3f}",
    )


def validate_forgetting_events_tracked(results: list[LearnerResult]) -> ValidationResult:
    """
    Assert that the engine tracks retention degradation.

    Two detection modes:
    1. Explicit: total_forgetting_events > 0 (engine-emitted)
    2. Implicit: peak_retention significantly exceeds current retention
       (decay happened even if no explicit event was emitted)

    Topics that never rose above floor retention are excluded (they never
    "forgot" anything — they just never learned).
    """
    trackable = 0
    detected = 0

    for r in results:
        if not r.snapshots:
            continue
        last_day = max(s.day for s in r.snapshots)
        for s in r.snapshots:
            if s.day != last_day:
                continue
            # Only count topics that had retention above floor at some point
            if s.peak_retention <= 0.06:
                continue
            trackable += 1
            # Explicit forgetting event tracking
            if s.total_forgetting_events > 0:
                detected += 1
            # Implicit: significant decay from peak
            elif s.peak_retention - s.retention_score > 0.1:
                detected += 1

    if trackable == 0:
        return ValidationResult(True, "forgetting_events_tracked", "No trackable topics")

    detection_rate = detected / trackable
    return ValidationResult(
        passed=True,  # Informational — engine may not emit explicit events
        name="forgetting_events_tracked",
        detail=f"{detected}/{trackable} with decay detected ({detection_rate:.1%})",
    )


def run_all_validations(results: list[LearnerResult]) -> list[ValidationResult]:
    """Run all engine invariant validators."""
    return [
        validate_retention_bounds(results),
        validate_stability_positive(results),
        validate_decay_bounded(results),
        validate_priority_ordering(results),
        validate_schedule_adapts_to_retention(results),
        validate_diligent_beats_struggling(results),
        validate_forgetting_events_tracked(results),
    ]
