"""
simulation/run_simulation.py
─────────────────────────────
CLI entry point for running KnowDecay Engine simulations.

Usage:
    python -m simulation.run_simulation --learners 5 --topics 10 --days 30 --seed 42

All computation is pure — no DB, no HTTP, no I/O except final report output.
"""

import argparse
import sys
import time

from simulation.learner_profiles import generate_learners
from simulation.timeline_simulator import run_simulation
from simulation.analytics_reporter import generate_report, save_report, print_summary


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="knowdecay-simulation",
        description="KnowDecay Engine — Retention Simulation System",
    )
    parser.add_argument(
        "--learners", type=int, default=5,
        help="Number of synthetic learners to generate (default: 5)",
    )
    parser.add_argument(
        "--topics", type=int, default=10,
        help="Number of topics per learner (default: 10)",
    )
    parser.add_argument(
        "--days", type=int, default=30,
        help="Simulation timeline in days (default: 30)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--exam-days", type=float, default=30.0,
        help="Days until exam for all learners (default: 30.0)",
    )
    parser.add_argument(
        "--output-dir", type=str, default="simulation/output",
        help="Output directory for the report JSON (default: simulation/output)",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress summary output",
    )
    args = parser.parse_args()

    # ── Generate Learners ─────────────────────────────────────────────────
    print(f"Generating {args.learners} learners × {args.topics} topics...")
    learners = generate_learners(
        n_learners=args.learners,
        n_topics=args.topics,
        days_until_exam=args.exam_days,
        seed=args.seed,
    )

    # ── Run Simulation ────────────────────────────────────────────────────
    print(f"Running {args.days}-day simulation (seed={args.seed})...")
    t0 = time.perf_counter()
    results = run_simulation(learners, total_days=args.days, base_seed=args.seed)
    elapsed = time.perf_counter() - t0
    print(f"Simulation complete in {elapsed:.2f}s")

    # ── Generate Report ───────────────────────────────────────────────────
    report = generate_report(results, total_days=args.days, seed=args.seed)

    # ── Output ────────────────────────────────────────────────────────────
    filepath = save_report(report, output_dir=args.output_dir)
    print(f"Report saved: {filepath}")

    if not args.quiet:
        print_summary(report)

    # Exit code: 0 if all invariants pass, 1 otherwise
    return 0 if report["all_invariants_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
