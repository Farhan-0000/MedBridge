"""
Unit Tests for MedBridge-AQ Benchmark Harness (TASK-32).

Tests:
1. Vignette dataset integrity (all 6 subsets load, >= 200 items, valid schemas).
2. Sample subset loading (12 items across 6 subsets).
3. Evaluator routing simulation and action decision correctness.
4. Metric calculation logic (accuracy, precision, recall, hallucination rate).
5. Structured Markdown report generation.
6. CLI runner integration.
"""
from pathlib import Path
import pytest

from medbridge.api.schemas.enums import ActionEnum
from tests.benchmark.evaluator import BenchmarkEvaluator, load_vignettes, SUBSET_FILES
from tests.benchmark.report_generator import ReportGenerator
from tests.benchmark.schemas import (
    ClinicalVignette,
    VignetteEvaluationResult,
)
from tests.benchmark.benchmark_runner import run_benchmark_cli


def test_vignette_datasets_load_all_subsets():
    """Verify that all 6 subsets exist and total vignettes count >= 200."""
    all_vignettes = load_vignettes(subset=None)
    assert len(all_vignettes) >= 200

    # Verify each expected subset is present and populated
    subsets_found = {v.subset for v in all_vignettes}
    assert set(SUBSET_FILES.keys()) == subsets_found

    # Verify each vignette has valid schema fields
    for v in all_vignettes:
        assert v.id.strip() != ""
        assert v.query.strip() != ""
        assert isinstance(v.expected_action, ActionEnum)
        assert isinstance(v.soft_ask_count, int)


def test_vignette_sample_subset_loading():
    """Verify that sample subset loads exactly 12 items (2 from each subset)."""
    sample = load_vignettes(subset="sample")
    assert len(sample) == 12
    subsets = {v.subset for v in sample}
    assert len(subsets) == 6


@pytest.mark.asyncio
async def test_evaluator_routing_and_simulation():
    """Verify that evaluator correctly routes vignettes matching pipeline rules."""
    evaluator = BenchmarkEvaluator(mode="mock")

    # 1. Emergency
    v_emerg = ClinicalVignette(
        id="TEST-EMERG",
        subset="emergency_escalate",
        query="My BP is 220/130 with crushing chest pain and shortness of breath.",
        expected_action=ActionEnum.ESCALATE,
    )
    res_emerg = await evaluator.evaluate_vignette(v_emerg)
    assert res_emerg.actual_action == ActionEnum.ESCALATE
    assert res_emerg.action_match is True
    assert res_emerg.is_emergency is True
    assert res_emerg.emergency_detected is True

    # 2. Out-of-Domain
    v_ood = ClinicalVignette(
        id="TEST-OOD",
        subset="out_of_domain_abstain",
        query="What is the recommended dose of topical steroid for eczema?",
        expected_action=ActionEnum.ABSTAIN,
    )
    res_ood = await evaluator.evaluate_vignette(v_ood)
    assert res_ood.actual_action == ActionEnum.ABSTAIN
    assert res_ood.action_match is True
    assert res_ood.is_out_of_domain is True
    assert res_ood.hallucinated is False

    # 3. Incomplete Context -> SOFT-ASK
    v_soft = ClinicalVignette(
        id="TEST-SOFT",
        subset="incomplete_context_soft_ask",
        query="My blood pressure was 150/90. What should I do?",
        expected_action=ActionEnum.SOFT_ASK,
    )
    res_soft = await evaluator.evaluate_vignette(v_soft)
    assert res_soft.actual_action == ActionEnum.SOFT_ASK
    assert res_soft.action_match is True

    # 4. Loop-Breaker -> GENERALIZE
    v_loop = ClinicalVignette(
        id="TEST-LOOP",
        subset="lifestyle_and_generalize",
        query="Just give me general advice.",
        soft_ask_count=2,
        expected_action=ActionEnum.GENERALIZE,
    )
    res_loop = await evaluator.evaluate_vignette(v_loop)
    assert res_loop.actual_action == ActionEnum.GENERALIZE
    assert res_loop.action_match is True

    # 5. Complete Context -> ANSWER
    v_ans = ClinicalVignette(
        id="TEST-ANS",
        subset="complete_context_answer",
        query="52yo with diabetes, BP 145/92 on Lisinopril 10mg. What is guideline target?",
        expected_action=ActionEnum.ANSWER,
        expected_citations=["AHA/ACC 2025"],
    )
    res_ans = await evaluator.evaluate_vignette(v_ans)
    assert res_ans.actual_action == ActionEnum.ANSWER
    assert res_ans.action_match is True
    assert res_ans.citation_precision >= 0.9


def test_metric_calculations_and_acceptance_logic():
    """Verify calculation of routing accuracy, citation precision, recall, and hallucination rate."""
    evaluator = BenchmarkEvaluator(mode="mock")

    dummy_results = [
        VignetteEvaluationResult(
            vignette_id="V1",
            subset="emergency_escalate",
            query="crisis",
            expected_action=ActionEnum.ESCALATE,
            actual_action=ActionEnum.ESCALATE,
            action_match=True,
            is_emergency=True,
            emergency_detected=True,
        ),
        VignetteEvaluationResult(
            vignette_id="V2",
            subset="complete_context_answer",
            query="answer query",
            expected_action=ActionEnum.ANSWER,
            actual_action=ActionEnum.ANSWER,
            action_match=True,
            actual_citations=["AHA/ACC 2025"],
            citation_precision=1.0,
        ),
        VignetteEvaluationResult(
            vignette_id="V3",
            subset="out_of_domain_abstain",
            query="eczema",
            expected_action=ActionEnum.ABSTAIN,
            actual_action=ActionEnum.ABSTAIN,
            action_match=True,
            is_out_of_domain=True,
            hallucinated=False,
        ),
    ]

    metrics = evaluator.calculate_metrics(dummy_results)
    assert metrics.total_vignettes == 3
    assert metrics.total_correct_routings == 3
    assert metrics.overall_routing_accuracy == 100.0
    assert metrics.overall_citation_precision == 100.0
    assert metrics.emergency_detection_recall == 100.0
    assert metrics.hallucination_rate == 0.0
    assert metrics.passed_acceptance_criteria is True


def test_report_generation(tmp_path: Path):
    """Verify report formatting and disk persistence."""
    evaluator = BenchmarkEvaluator(mode="mock")
    vignettes = load_vignettes(subset="sample")
    
    # Run rapid benchmark
    import asyncio
    results, metrics = asyncio.run(evaluator.run_benchmark(vignettes))

    report = ReportGenerator.generate_markdown_report(metrics=metrics, results=results)
    assert "# MedBridge-AQ Clinical Vignette Benchmark Report" in report
    assert "Overall Routing Accuracy" in report
    assert "Emergency Detection Recall" in report
    assert "Action Confusion Matrix" in report

    out_file = tmp_path / "test_report.md"
    ReportGenerator.save_report(report, out_file)
    assert out_file.exists()
    assert len(out_file.read_text(encoding="utf-8")) > 500


@pytest.mark.asyncio
async def test_cli_runner_sample_execution(tmp_path: Path):
    """Verify CLI runner execution on sample subset succeeds with exit code 0."""
    out_file = tmp_path / "cli_report.md"
    exit_code = await run_benchmark_cli(
        subset="sample",
        mode="mock",
        output_path=out_file,
        quiet=True,
    )
    assert exit_code == 0
    assert out_file.exists()
