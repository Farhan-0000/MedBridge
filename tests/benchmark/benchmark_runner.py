"""
CLI Runner for MedBridge-AQ Clinical Vignette Benchmark (TASK-32).

Executes the benchmark evaluation harness across 200+ clinical hypertension vignettes,
computes clinical routing accuracy, citation precision, emergency recall, and
hallucination rates, and generates a structured Markdown report.

Usage:
    # Run rapid 12-item sample subset:
    python -m tests.benchmark.benchmark_runner --subset sample

    # Run full 225-item benchmark suite:
    python -m tests.benchmark.benchmark_runner --all

    # Run specific subset:
    python -m tests.benchmark.benchmark_runner --subset emergency_escalate

    # Custom report output:
    python -m tests.benchmark.benchmark_runner --all --output reports/my_report.md
"""
import argparse
import asyncio
from pathlib import Path
import sys

from tests.benchmark.evaluator import BenchmarkEvaluator, load_vignettes
from tests.benchmark.report_generator import ReportGenerator


DEFAULT_REPORT_PATH = Path("reports") / "medbridge_aq_benchmark_report.md"


async def run_benchmark_cli(
    subset: str = "sample",
    mode: str = "mock",
    output_path: Path = DEFAULT_REPORT_PATH,
    quiet: bool = False,
) -> int:
    """Execute benchmark run and return exit code (0 = passed, 1 = failed)."""
    if not quiet:
        print("\n" + "=" * 75)
        print("MedBridge-AQ Clinical Vignette Benchmark Runner (TASK-32)")
        print("=" * 75)
        print(f"• Evaluation Mode:  {mode}")
        print(f"• Target Subset:    {subset}")
        print(f"• Report Path:      {output_path}\n")

    vignettes = load_vignettes(subset=subset if subset != "all" else None)
    if not vignettes:
        print(f"[ERROR] No vignettes found for subset '{subset}'", file=sys.stderr)
        return 1

    if not quiet:
        print(f"Loaded {len(vignettes)} clinical vignettes. Starting evaluation...")

    evaluator = BenchmarkEvaluator(mode=mode)
    results, metrics = await evaluator.run_benchmark(vignettes)

    # Generate and save report
    report_md = ReportGenerator.generate_markdown_report(
        metrics=metrics,
        results=results,
        eval_mode=f"{mode}_mode",
    )
    saved_path = ReportGenerator.save_report(report_md, output_path)

    if not quiet:
        print("\n" + "=" * 75)
        print("Benchmark Results Summary")
        print("=" * 75)
        print(f"Total Evaluated:              {metrics.total_vignettes}")
        print(f"Overall Routing Accuracy:     {metrics.overall_routing_accuracy}% (Target: >=90%)")
        print(f"Citation Precision:           {metrics.overall_citation_precision}% (Target: >=90%)")
        print(f"Emergency Detection Recall:   {metrics.emergency_detection_recall}% (Target: 100%)")
        print(f"Out-of-Domain Hallucination:  {metrics.hallucination_rate}% (Target: 0%)")
        print(f"Mean Latency:                 {metrics.mean_latency_ms} ms (P95: {metrics.latency_p95_ms} ms)")
        print("-" * 75)

        if metrics.passed_acceptance_criteria:
            print(">> ALL ACCEPTANCE CRITERIA PASSED [OK]")
        else:
            print(">> ACCEPTANCE CRITERIA FAILED [FAIL]")

        print(f">> Full Markdown Report written to: {saved_path}")
        print("=" * 75 + "\n")

    return 0 if metrics.passed_acceptance_criteria else 1


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="MedBridge-AQ Clinical Vignette Benchmark Runner (TASK-32)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all 225 clinical vignettes across all 6 subsets",
    )
    parser.add_argument(
        "--subset",
        type=str,
        default="sample",
        help="Target subset (sample, emergency_escalate, complete_context_answer, "
             "incomplete_context_soft_ask, lifestyle_and_generalize, "
             "out_of_domain_abstain, complex_comorbid_contraindications)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="mock",
        choices=["mock", "live"],
        help="Execution mode: 'mock' (fast deterministic simulator) or 'live' (invokes orchestrator)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Output path for the Markdown evaluation summary report",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console progress banners",
    )

    args = parser.parse_args()
    target_subset = "all" if args.all else args.subset

    exit_code = asyncio.run(
        run_benchmark_cli(
            subset=target_subset,
            mode=args.mode,
            output_path=args.output,
            quiet=args.quiet,
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
