"""
simulation/analytics_reporter.py
─────────────────────────────────
Post-simulation analytics report generator.

Generates structured reports from simulation results for analysis
and validation of the retention intelligence engine.
"""

import json
from dataclasses import asdict
from pathlib import Path

from simulation.learner_profiles import Archetype
from simulation.timeline_simulator import LearnerResult
from simulation.validators import run_all_validations, ValidationResult


def compute_archetype_summary(results: list[LearnerResult]) -> dict:
    """
    Compute per-archetype aggregate metrics from simulation results.
    """
    summary = {}

    for archetype in Archetype:
        arch_results = [r for r in results if r.learner.archetype == archetype]
        if not arch_results:
            continue

        all_final_retention = []
        all_final_stability = []
        total_events = 0
        total_forgetting = 0

        for r in arch_results:
            total_events += r.total_events
            if not r.snapshots:
                continue
            last_day = max(s.day for s in r.snapshots)
            for s in r.snapshots:
                if s.day == last_day:
                    all_final_retention.append(s.retention_score)
                    all_final_stability.append(s.stability_score)
                    total_forgetting += s.total_forgetting_events

        n = len(all_final_retention) or 1
        summary[archetype.value] = {
            "learner_count": len(arch_results),
            "mean_final_retention": round(sum(all_final_retention) / n, 4),
            "min_final_retention": round(min(all_final_retention, default=0.0), 4),
            "max_final_retention": round(max(all_final_retention, default=0.0), 4),
            "mean_final_stability": round(sum(all_final_stability) / n, 4),
            "total_events": total_events,
            "total_forgetting_events": total_forgetting,
        }

    return summary


def compute_retention_evolution(results: list[LearnerResult]) -> dict:
    """
    Compute daily mean retention per archetype for evolution curves.
    Returns {archetype: [{day, mean_retention}, ...]}.
    """
    evolution = {}

    for archetype in Archetype:
        arch_results = [r for r in results if r.learner.archetype == archetype]
        if not arch_results:
            continue

        # Collect all snapshots grouped by day
        day_retentions: dict[int, list[float]] = {}
        for r in arch_results:
            for s in r.snapshots:
                day_retentions.setdefault(s.day, []).append(s.retention_score)

        curve = []
        for day in sorted(day_retentions):
            vals = day_retentions[day]
            curve.append({
                "day": day,
                "mean_retention": round(sum(vals) / len(vals), 4),
                "topic_count": len(vals),
            })

        evolution[archetype.value] = curve

    return evolution


def compute_scheduling_efficiency(results: list[LearnerResult]) -> dict:
    """
    Analyse scheduling efficiency across the simulation.
    """
    total_short_intervals = 0  # < 0.5 days
    total_long_intervals = 0   # > 30 days
    total_optimal = 0          # 0.5–30 days
    total = 0

    for r in results:
        if not r.snapshots:
            continue
        last_day = max(s.day for s in r.snapshots)
        for s in r.snapshots:
            if s.day == last_day:
                total += 1
                if s.next_revision_days < 0.5:
                    total_short_intervals += 1
                elif s.next_revision_days > 30.0:
                    total_long_intervals += 1
                else:
                    total_optimal += 1

    return {
        "total_topics_evaluated": total,
        "short_intervals": total_short_intervals,
        "optimal_intervals": total_optimal,
        "long_intervals": total_long_intervals,
        "optimal_rate": round(total_optimal / max(total, 1), 4),
    }


def generate_report(
    results: list[LearnerResult],
    total_days: int,
    seed: int,
) -> dict:
    """
    Generate a complete simulation report.
    """
    validations = run_all_validations(results)

    report = {
        "simulation_config": {
            "total_learners": len(results),
            "total_days": total_days,
            "seed": seed,
            "topics_per_learner": len(results[0].learner.topics) if results else 0,
        },
        "archetype_summary": compute_archetype_summary(results),
        "retention_evolution": compute_retention_evolution(results),
        "scheduling_efficiency": compute_scheduling_efficiency(results),
        "engine_invariants": [
            {"name": v.name, "passed": v.passed, "detail": v.detail}
            for v in validations
        ],
        "invariants_passed": sum(1 for v in validations if v.passed),
        "invariants_total": len(validations),
        "all_invariants_pass": all(v.passed for v in validations),
    }

    return report


def save_report(report: dict, output_dir: str = "simulation/output") -> str:
    """Save report as JSON. Returns the file path."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    filepath = path / "simulation_report.json"
    with open(filepath, "w") as f:
        json.dump(report, f, indent=2, default=str)
    return str(filepath)


def print_summary(report: dict) -> None:
    """Print a human-readable summary to stdout."""
    cfg = report["simulation_config"]
    print(f"\n{'=' * 60}")
    print(f"  KnowDecay Engine — Simulation Report")
    print(f"{'=' * 60}")
    print(f"  Learners: {cfg['total_learners']}  |  Topics: {cfg['topics_per_learner']}  |  Days: {cfg['total_days']}  |  Seed: {cfg['seed']}")
    print()

    # Archetype summary
    print(f"  {'Archetype':<15} {'Mean R':>8} {'Min R':>8} {'Max R':>8} {'Events':>8} {'Forget':>8}")
    print(f"  {'-'*15} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    for name, data in report["archetype_summary"].items():
        print(
            f"  {name:<15} "
            f"{data['mean_final_retention']:>8.3f} "
            f"{data['min_final_retention']:>8.3f} "
            f"{data['max_final_retention']:>8.3f} "
            f"{data['total_events']:>8} "
            f"{data['total_forgetting_events']:>8}"
        )
    print()

    # Scheduling
    sched = report["scheduling_efficiency"]
    print(f"  Scheduling: {sched['optimal_rate']:.0%} optimal  |  "
          f"{sched['short_intervals']} short  |  {sched['long_intervals']} long")
    print()

    # Invariants
    passed = report["invariants_passed"]
    total = report["invariants_total"]
    status = "ALL PASS" if report["all_invariants_pass"] else "FAILURES"
    print(f"  Engine Invariants: {passed}/{total} {status}")
    for inv in report["engine_invariants"]:
        icon = "[PASS]" if inv["passed"] else "[FAIL]"
        print(f"    {icon} {inv['name']}: {inv['detail']}")

    print(f"\n{'=' * 60}")
