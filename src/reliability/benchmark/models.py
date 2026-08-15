"""
Benchmark data models for C0/C1/A1 capability comparison.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence


class GroundTruthLabel(BaseModel):
    """
    Ground truth label for a benchmark case.
    Defines what the correct classification and cause keywords should be.
    Used ONLY for offline evaluation — never passed to investigators.
    """
    correct_classification: str = Field(
        description="Expected cause classification: DATA, OPERATIONAL, MIXED, or UNKNOWN"
    )
    correct_claim_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords that should appear in the correct claim (for partial match scoring)"
    )
    is_false_positive: bool = Field(
        default=False,
        description="Whether this incident is a known false positive in ground truth"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional notes about the ground truth rationale"
    )

    @field_validator('correct_classification', mode='before')
    @classmethod
    def validate_classification(cls, v):
        valid = {"DATA", "OPERATIONAL", "MIXED", "UNKNOWN"}
        if isinstance(v, str) and v in valid:
            return v
        raise ValueError(f"Invalid classification: {v}")


class BenchmarkCase(BaseModel):
    """
    Single benchmark case containing incident, evidence, and ground truth.
    Each case tests a specific investigator capability (L1 rule matching,
    contextual drift detection, mixed evidence, abstention, etc.).
    """
    case_id: str = Field(description="Unique benchmark case identifier")
    case_name: str = Field(description="Human-readable test case name")
    description: str = Field(description="What capability this case tests")

    incident: Incident = Field(description="Incident to investigate")
    evidence: List[Evidence] = Field(
        default_factory=list,
        description="Evidence available to investigators"
    )
    ground_truth: Optional[GroundTruthLabel] = Field(
        default=None,
        description="Ground truth label (for evaluation only, NOT passed to investigators)"
    )

    category: Literal[
        "L1_RULE", "L2_CONTEXTUAL", "L3_RELATIONAL", "L4_CHANGEPOINT",
        "ABSTENTION", "MIXED_EVIDENCE", "FALSE_POSITIVE", "EDGE_CASE"
    ] = Field(
        description="Benchmark category / detector layer this case targets"
    )
    difficulty: Literal["EASY", "MEDIUM", "HARD"] = Field(
        default="MEDIUM",
        description="Expected difficulty for this case"
    )
    expected_investigator: Literal["C0", "C1", "A1"] = Field(
        default="A1",
        description="Which investigator should handle this best"
    )


class InvestigatorResult(BaseModel):
    """
    Result from a single investigator run on a benchmark case.
    Contains both the output and metadata for metric computation.
    """
    case_id: str
    investigator_id: Literal["C0", "C1", "A1"]

    # Output
    hypothesis_claim: Optional[str] = None
    hypothesis_classification: Optional[str] = None
    hypothesis_confidence: Optional[float] = None
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    status: Literal["RESOLVED", "ABSTAINED", "NONE"] = "NONE"

    # Metadata
    wall_clock_ms: float = 0.0
    tokens_used: int = 0
    tool_calls_made: int = 0
    stop_reason: Optional[str] = None

    # Evaluation (computed after comparison with ground truth)
    classification_correct: Optional[bool] = None
    keyword_match_score: Optional[float] = None  # 0.0 - 1.0
    false_positive_detected: Optional[bool] = None


class BenchmarkResults(BaseModel):
    """
    Aggregated results for all investigators across all benchmark cases.
    Contains per-investigator metrics and per-case breakdowns.
    """
    benchmark_version: str = Field(
        default="v1.0",
        description="Benchmark harness version for reproducibility"
    )
    total_cases: int = 0
    categories_covered: List[str] = Field(default_factory=list)

    # Per-investigator aggregated metrics
    investigator_metrics: dict[str, "InvestigatorMetrics"] = Field(
        default_factory=dict
    )

    # Per-case results
    case_results: List["BenchmarkCaseResult"] = Field(default_factory=list)


class InvestigatorMetrics(BaseModel):
    """
    Aggregated metrics for a single investigator across all benchmark cases.
    """
    investigator_id: Literal["C0", "C1", "A1"]

    # Classification metrics
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0

    # Keyword match
    avg_keyword_match_score: float = 0.0

    # Performance
    avg_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    avg_tokens_used: float = 0.0
    avg_tool_calls: float = 0.0

    # Behavior
    abstention_rate: float = 0.0
    false_positive_rate: float = 0.0

    # Per-category breakdown
    metrics_by_category: dict[str, "CategoryMetrics"] = Field(default_factory=dict)

    # Counts
    total_cases: int = 0
    cases_resolved: int = 0


class CategoryMetrics(BaseModel):
    """
    Metrics broken down by benchmark category.
    """
    category: str
    case_count: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    avg_latency_ms: float = 0.0
    abstention_count: int = 0


class BenchmarkCaseResult(BaseModel):
    """
    Per-case result with all investigator outputs and evaluation.
    """
    case_id: str
    case_name: str
    category: str
    difficulty: str

    ground_truth: Optional[GroundTruthLabel] = None

    c0_result: Optional[InvestigatorResult] = None
    c1_result: Optional[InvestigatorResult] = None
    a1_result: Optional[InvestigatorResult] = None

    winner: Literal["C0", "C1", "A1", "TIE", None] = None
    winner_reason: Optional[str] = None
