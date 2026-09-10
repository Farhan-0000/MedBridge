"""
Pydantic Schemas for MedBridge-AQ Clinical Vignette Benchmark (TASK-32).

Defines data contracts for:
- Clinical vignettes and evaluation subsets
- Per-vignette evaluation outcomes
- Aggregate benchmark metrics, safety recalls, and confusion matrices
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from medbridge.api.schemas.enums import ActionEnum


class ClinicalVignette(BaseModel):
    """Represents a single clinical vignette in the MedBridge-AQ dataset."""

    id: str = Field(description="Unique vignette identifier (e.g., 'EMERG-001')")
    subset: str = Field(description="Subset category (e.g., 'emergency_escalate')")
    query: str = Field(description="Patient conversational query")
    patient_snapshot: Dict[str, Any] = Field(
        default_factory=dict,
        description="Prior clinical context snapshot (demographics, meds, readings)",
    )
    soft_ask_count: int = Field(
        default=0,
        description="Current conversational SOFT-ASK counter",
    )
    expected_action: ActionEnum = Field(
        description="Target clinical routing action (ANSWER, SOFT-ASK, GENERALIZE, ABSTAIN, ESCALATE)",
    )
    expected_citations: List[str] = Field(
        default_factory=list,
        description="Expected guideline citation sources (e.g. ['AHA/ACC', 'ESC/ESH'])",
    )
    clinical_rationale: str = Field(
        default="",
        description="Expert clinical justification for the expected action",
    )
    contraindications: List[str] = Field(
        default_factory=list,
        description="Clinical contraindications or high-risk considerations",
    )


class VignetteEvaluationResult(BaseModel):
    """Result of running a single vignette through the evaluation harness."""

    vignette_id: str
    subset: str
    query: str
    expected_action: ActionEnum
    actual_action: ActionEnum
    action_match: bool
    actual_citations: List[str] = Field(default_factory=list)
    citation_precision: float = 1.0
    is_emergency: bool = False
    emergency_detected: bool = False
    is_out_of_domain: bool = False
    hallucinated: bool = False
    response_text: str = ""
    latency_ms: float = 0.0
    notes: Optional[str] = None


class SubsetMetrics(BaseModel):
    """Aggregated performance metrics for a specific vignette subset."""

    subset_name: str
    total_vignettes: int
    correct_routings: int
    routing_accuracy: float
    avg_citation_precision: float
    avg_latency_ms: float


class BenchmarkMetrics(BaseModel):
    """System-wide evaluation metrics computed across all subsets."""

    total_vignettes: int
    total_correct_routings: int
    overall_routing_accuracy: float
    overall_citation_precision: float
    emergency_count: int
    emergency_detected_count: int
    emergency_detection_recall: float
    out_of_domain_count: int
    out_of_domain_abstain_count: int
    hallucination_rate: float
    subsets: Dict[str, SubsetMetrics] = Field(default_factory=dict)
    confusion_matrix: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    mean_latency_ms: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    passed_acceptance_criteria: bool = False
