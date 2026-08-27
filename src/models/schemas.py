import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


# --- Legacy Chat & Basic API Schemas ---
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=80000, description="User message")
    session_id: str = Field(default="default", description="Chat session ID")
    dataset_key: Optional[str] = Field(default=None, description="Dataset context for this chat message")
    lang: Optional[str] = Field(default="vi", description="Language preference: 'vi' (Vietnamese) or 'en' (English)")
    use_llm: Optional[bool] = Field(default=None, description="Global LLM mode flag: True for LLM ON, False for LLM OFF")
    mode: Optional[str] = Field(default=None, description="Execution mode: 'llm' or 'deterministic'")
    active_day: Optional[int] = Field(default=None, description="Active Day Index selected from Time Bar")



class ChatResponse(BaseModel):
    response: str = Field(..., description="Agent response")
    analysis: str = Field(default="", description="Internal analysis")
    state: Optional[str] = Field(default=None, description="Workflow state")
    agent_execution: Optional[Dict[str, Any]] = Field(default=None, description="Agent execution details")


# --- Enums ---
class RunState(str, Enum):
    CREATED = "CREATED"
    PROFILING = "PROFILING"
    PROFILED = "PROFILED"
    PROPOSING = "PROPOSING"
    PROPOSED = "PROPOSED"
    VALIDATING = "VALIDATING"
    NEEDS_REPAIR = "NEEDS_REPAIR"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    ABSTAINED = "ABSTAINED"
    APPROVED = "APPROVED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuleSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    CRITICAL = "CRITICAL"


class RuleFamily(str, Enum):
    NULL = "null"
    DUPLICATE = "duplicate"
    INVALID_FORMAT = "invalid_format"
    OUTLIER_RANGE = "outlier_range"
    SCHEMA_DRIFT = "schema_drift"
    CROSS_FIELD = "cross_field"
    UNIQUE = "unique"
    NOT_NULL = "not_null"
    RANGE = "range"
    FORMAT = "format"
    CUSTOM = "custom"


class RuleAction(str, Enum):
    DROP_DUPLICATES = "drop_duplicates"
    FILL_NULL = "fill_null"
    QUARANTINE_RANGE = "quarantine_range"
    ALIGN_SCHEMA = "align_schema"
    QUARANTINE_CROSS_FIELD = "quarantine_cross_field"
    QUARANTINE = "quarantine"
    DROP = "drop"
    FLAG = "flag"


# --- Data Profiling & Quality Flags ---
class RawSnapshot(BaseModel):
    checksum_sha256: str
    row_count: int
    schema_info: List[Dict[str, Any]] = Field(default_factory=list)
    file_path: str = ""
    file_format: Optional[str] = None
    source_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QualityFlag(BaseModel):
    column: str
    flag_type: str
    message: str
    severity: Any = RuleSeverity.WARNING


class ColumnProfile(BaseModel):
    column_name: Optional[str] = None
    name: Optional[str] = None
    data_type: str = "VARCHAR"
    dtype: Optional[str] = None
    total_count: int = 0
    null_count: int = 0
    null_pct: float = 0.0
    null_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    distinct_count: int = 0
    unique_count: int = 0
    cardinality: float = 0.0
    min: Optional[Any] = None
    max: Optional[Any] = None
    min_val: Optional[Any] = None
    max_val: Optional[Any] = None
    mean: Optional[float] = None
    mean_val: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    top_values: List[Dict[str, Any]] = Field(default_factory=list)
    pattern_summary: Optional[str] = None
    anomaly_count: Optional[int] = 0
    anomaly_description: Optional[str] = None
    stats: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.column_name and self.name:
            self.column_name = self.name
        elif not self.name and self.column_name:
            self.name = self.column_name
        if not self.dtype and self.data_type:
            self.dtype = self.data_type
        elif not self.data_type and self.dtype:
            self.data_type = self.dtype
        if self.min_val is None and self.min is not None:
            self.min_val = self.min
        elif self.min is None and self.min_val is not None:
            self.min = self.min_val
        if self.max_val is None and self.max is not None:
            self.max_val = self.max
        elif self.max is None and self.max_val is not None:
            self.max = self.max_val
        if self.distinct_count == 0 and self.unique_count > 0:
            self.distinct_count = self.unique_count
        elif self.unique_count == 0 and self.distinct_count > 0:
            self.unique_count = self.distinct_count


class Profile(BaseModel):
    snapshot_id: str = "snap_001"
    source_type: str = "structured"
    file_format: str = "csv"
    checksum_sha256: str = ""
    file_path: str = ""
    columns: List[ColumnProfile] = Field(default_factory=list)
    row_count: int = 0
    column_count: int = 0
    duplicate_count: int = 0
    cross_field_correlations: Any = Field(default_factory=list)
    candidate_keys: List[str] = Field(default_factory=list)
    quality_flags: List[QualityFlag] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if self.column_count == 0 and self.columns:
            self.column_count = len(self.columns)


class ProfileResult(Profile):
    """
    ProfileResult wraps multi-format profiling metadata for structured and unstructured sources.
    """
    pass


class ProfileReport(BaseModel):
    snapshot_id: str = "snap_001"
    columns: List[ColumnProfile] = Field(default_factory=list)
    row_count: int = 0
    column_count: int = 0
    duplicate_count: int = 0
    candidate_keys: List[str] = Field(default_factory=list)
    cross_field_correlations: Any = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if self.column_count == 0 and self.columns:
            self.column_count = len(self.columns)


class DataProfile(BaseModel):
    table_name: str = "dataset"
    total_rows: int = 0
    columns: Any = Field(default_factory=dict)
    total_anomalies: Optional[int] = 0
    data_health_score: Optional[float] = 100.0
    schema_summary: str = Field(default="", description="Summary of table structure and constraints")


# --- Decision Object Schema ---
class DecisionObject(BaseModel):
    issue: str = Field(..., description="Description of the issue or rationale for next step")
    evidence_refs: List[str] = Field(default_factory=list, description="References to profile stats or rule outputs")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    risk: str = Field(default="low", description="Risk level (low, medium, high, critical)")
    next_action: str = Field(..., description="Name of whitelisted tool to invoke")
    action_input: Dict[str, Any] = Field(default_factory=dict, description="Arguments for next_action")


# --- Data Quality Rules & Compiler Schemas ---
class RuleSpec(BaseModel):
    rule_id: str = Field(default="rule_001")
    rule_type: str = Field(default="custom")
    family: Any = Field(default=RuleFamily.CUSTOM)
    target_column: Optional[str] = Field(default=None)
    target_field: Optional[str] = Field(default=None)
    column: Optional[str] = Field(default=None)
    action: str = Field(default="quarantine")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    params: Dict[str, Any] = Field(default_factory=dict)
    severity: str = Field(default="medium")
    description: str = Field(default="")

    def model_post_init(self, __context: Any) -> None:
        if not self.target_field:
            self.target_field = self.target_column or self.column
        if not self.target_column:
            self.target_column = self.target_field or self.column
        if not self.column:
            self.column = self.target_column or self.target_field
        if not self.parameters and self.params:
            self.parameters = self.params
        elif not self.params and self.parameters:
            self.params = self.parameters


class QualityRule(BaseModel):
    rule_id: str = Field(..., description="Unique ID for the rule")
    column: Optional[str] = Field(default="")
    target_column: Optional[str] = Field(default="")
    field: Optional[str] = Field(default="")
    name: Optional[str] = Field(default="")
    rule_type: str = Field(default="custom", description="Type of quality rule")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the rule")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the rule")
    severity: str = Field(default="medium", description="Severity level")
    risk_level: Optional[str] = Field(default="MEDIUM")
    confidence: Optional[float] = Field(default=1.0)
    precision_pct: Optional[float] = Field(default=95.0)
    evidence: Optional[str] = Field(default="")
    description: str = Field(default="", description="Human-readable description")
    sql_expression: str = Field(default="", description="Generated SQL expression for execution")
    expression: Optional[str] = Field(default="")
    action: Optional[str] = Field(default="quarantine")
    decision: Optional[str] = Field(default="pending")

    def model_post_init(self, __context: Any) -> None:
        if not self.column:
            self.column = self.target_column or self.field or ""
        if not self.target_column:
            self.target_column = self.column or self.field or ""
        if not self.parameters and self.params:
            self.parameters = self.params
        elif not self.params and self.parameters:
            self.params = self.parameters


class TransformSpec(BaseModel):
    transform_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    operation: str = Field(default="custom")
    source_field: Optional[str] = Field(default=None)
    target_field: Optional[str] = Field(default=None)
    column: Optional[str] = Field(default=None)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    params: Dict[str, Any] = Field(default_factory=dict)


class FieldMapping(BaseModel):
    source_field: str = ""
    target_field: str = ""
    confidence: float = 1.0
    reasoning: str = ""


class Proposal(BaseModel):
    proposal_id: str = Field(default="prop_001")
    run_id: str = Field(default="run_001")
    rules: List[RuleSpec] = Field(default_factory=list)
    transforms: List[TransformSpec] = Field(default_factory=list)
    mappings: List[FieldMapping] = Field(default_factory=list)
    reasoning: str = Field(default="")
    confidence: float = Field(default=1.0)


class RuleProposal(BaseModel):
    proposal_id: Optional[str] = Field(default="", description="ID of the proposal")
    rule_id: Optional[str] = None
    name: Optional[str] = None
    field: Optional[str] = None
    description: Optional[str] = None
    expression: Optional[str] = None
    risk_level: Optional[str] = None
    confidence: Optional[float] = 1.0
    precision_pct: Optional[float] = None
    evidence: Optional[str] = None
    baseline_origin: Optional[str] = None
    action: Optional[str] = None
    decision: Optional[str] = None
    rules: List[QualityRule] = Field(default_factory=list, description="List of proposed data quality rules")
    reasoning: str = Field(default="", description="Rationale behind proposed rules")


class ExecutionStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    instruction_id: Optional[str] = Field(default=None)
    rule_id: str = Field(default="rule_001")
    operation: str = Field(default="quarantine")
    action: str = Field(default="quarantine")
    action_type: Optional[str] = Field(default=None)
    target_column: Optional[str] = Field(default=None)
    column: Optional[str] = Field(default=None)
    target_field: Optional[str] = Field(default=None)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    params: Dict[str, Any] = Field(default_factory=dict)
    order: int = Field(default=1)

    def model_post_init(self, __context: Any) -> None:
        if not self.instruction_id:
            self.instruction_id = self.step_id
        if not self.action_type:
            self.action_type = self.action or self.operation
        if not self.operation:
            self.operation = self.action_type or self.action
        if not self.target_column and self.target_field:
            self.target_column = self.target_field
        if not self.target_field and self.target_column:
            self.target_field = self.target_column
        if not self.parameters and self.params:
            self.parameters = self.params
        elif not self.params and self.parameters:
            self.params = self.parameters


Instruction = ExecutionStep
ExecutableInstruction = ExecutionStep


class ExecutionPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    instructions: List[ExecutionStep] = Field(default_factory=list)
    steps: List[ExecutionStep] = Field(default_factory=list)
    estimated_rows: int = Field(default=0)
    compiled_successfully: bool = Field(default=True)
    compilation_errors: List[str] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if not self.instructions and self.steps:
            self.instructions = self.steps
        elif not self.steps and self.instructions:
            self.steps = self.instructions


ExecutableTransformPlan = ExecutionPlan


class RunManifest(BaseModel):
    plan_id: str = Field(default="plan_001")
    run_id: str = Field(default="run_001")
    snapshot_id: str = Field(default="snap_001")
    initial_rows: int = Field(default=0)
    clean_rows: int = Field(default=0)
    quarantine_rows: int = Field(default=0)
    execution_time_sec: float = Field(default=0.0)
    applied_instructions: List[str] = Field(default_factory=list)
    quarantine_summary: Dict[str, int] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    plan_id: str = ""
    clean_df: Any = None
    quarantine_df: Any = None
    manifest: Optional[RunManifest] = None
    clean_rows: int = 0
    clean_count: int = 0
    quarantined_rows: int = 0
    quarantine_rows: int = 0
    quarantine_count: int = 0
    execution_time_sec: float = 0.0
    duration_ms: int = 0
    output_checksum: str = ""
    manifest_hash: str = ""
    dropped_rows: int = 0
    errors: List[str] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if self.quarantined_rows and not self.quarantine_rows:
            self.quarantine_rows = self.quarantined_rows
        elif self.quarantine_rows and not self.quarantined_rows:
            self.quarantined_rows = self.quarantine_rows
        if self.clean_rows and not self.clean_count:
            self.clean_count = self.clean_rows
        elif self.clean_count and not self.clean_rows:
            self.clean_rows = self.clean_count
        if self.output_checksum and not self.manifest_hash:
            self.manifest_hash = self.output_checksum
        elif self.manifest_hash and not self.output_checksum:
            self.output_checksum = self.manifest_hash

    def __getitem__(self, item):
        items = [self.clean_df, self.quarantine_df, self.manifest]
        return items[item]

    def __iter__(self):
        return iter([self.clean_df, self.quarantine_df, self.manifest])


class RuleSchema(BaseModel):
    rule_id: str
    rule_type: str
    target_column: Optional[str] = None
    action: str = "quarantine"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    severity: str = "medium"
    description: str = ""


# --- Validation Result Schema ---
class ValidationResult(BaseModel):
    is_valid: bool = Field(default=True, description="True if proposal passes all validation checks")
    valid: bool = Field(default=True)
    rules_evaluated: int = Field(default=0)
    passed_rules: List[str] = Field(default_factory=list)
    failed_rules: List[str] = Field(default_factory=list)
    violations: List[Dict[str, Any]] = Field(default_factory=list)
    invalid_indices: List[int] = Field(default_factory=list)
    total_rows: int = Field(default=0)
    invalid_rows_count: int = Field(default=0)
    error_summary: Dict[str, int] = Field(default_factory=dict)
    errors: List[Any] = Field(default_factory=list)
    warnings: List[Any] = Field(default_factory=list)
    error_message: str = Field(default="")


# --- Audit Record Schema ---
class AuditRecord(BaseModel):
    audit_id: str = ""
    timestamp: Any = ""
    run_id: str = ""
    state_from: str = ""
    state_to: str = ""
    event_type: str = ""
    actor: str = "system"
    details: Dict[str, Any] = Field(default_factory=dict)


# --- REST API DTO Request/Response Schemas ---
class ProfileRequest(BaseModel):
    data: List[Dict[str, Any]] = Field(default_factory=list)


class ProfileResponse(BaseModel):
    snapshot_id: str = ""
    row_count: int = 0
    column_count: int = 0
    duplicate_count: int = 0
    columns: List[Dict[str, Any]] = Field(default_factory=list)


class ProposeRulesRequest(BaseModel):
    data: Optional[List[Dict[str, Any]]] = None
    variant: str = "A1"


class ProposeRulesResponse(BaseModel):
    variant: str
    rules: List[RuleSchema]
    reasoning: str


class ExecuteTransformRequest(BaseModel):
    data: List[Dict[str, Any]]
    rules: List[RuleSchema]


class ExecuteTransformResponse(BaseModel):
    initial_rows: int
    clean_rows: int
    quarantine_rows: int
    execution_time_sec: float
    quarantine_summary: Dict[str, int] = Field(default_factory=dict)


class ResetResponse(BaseModel):
    status: str
    reset_time_sec: float
    rows_reseeded: int = 0
    message: str


class TestResult(BaseModel):
    __test__ = False
    test_name: str
    passed: bool
    message: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)


class TestSuiteResult(BaseModel):
    __test__ = False
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    results: List[TestResult] = Field(default_factory=list)


# --- Anomaly & Diagnosis Schemas ---
class AnomalyItem(BaseModel):
    column: str = Field(default="", description="Column where anomaly was detected")
    anomaly_type: str = Field(default="outlier", description="Type of anomaly (e.g. null_spike, range_shift, duplicate_spike)")
    description: str = Field(default="", description="Detailed description of the anomaly")
    severity: str = Field(default="medium", description="Severity level (low, medium, high, critical)")
    metric_shift: Dict[str, Any] = Field(default_factory=dict, description="Observed baseline vs current metric shift")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")


class AnomalyReport(BaseModel):
    report_id: str = Field(default_factory=lambda: f"anom_{uuid.uuid4().hex[:8]}")
    dataset_name: str = Field(default="dataset", description="Name of dataset analyzed")
    detected_anomalies: List[AnomalyItem] = Field(default_factory=list, description="List of detected anomalies")
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Aggregate anomaly score")
    summary: str = Field(default="", description="High-level summary of anomaly findings")
    status: str = Field(default="ANOMALY_DETECTED", description="Status of anomaly detection run")


class DiagnosisReport(BaseModel):
    diagnosis_id: str = Field(default_factory=lambda: f"diag_{uuid.uuid4().hex[:8]}")
    run_id: str = Field(default="run_001", description="Associated run ID")
    root_cause: str = Field(..., description="Root cause explanation")
    category: str = Field(default="data_corruption", description="Category of failure or anomaly")
    affected_columns: List[str] = Field(default_factory=list, description="Columns impacted by root cause")
    evidence: List[str] = Field(default_factory=list, description="Supporting evidence for diagnosis")
    impact_level: str = Field(default="high", description="Impact level (low, medium, high, critical)")
    recommended_remediation: str = Field(default="", description="Actionable fix or remediation step")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score of diagnosis")


# --- Scheduler, Alert, & Anomaly API DTO Schemas ---
class ScheduleCreate(BaseModel):
    name: str = Field(..., description="Schedule name")
    dataset_name: str = Field(default="raw_taxi_trips.csv", description="Target dataset name")
    schedule_type: str = Field(default="interval", description="Schedule type: 'interval' or 'cron'")
    interval_seconds: Optional[int] = Field(default=3600, description="Interval in seconds")
    cron_expression: Optional[str] = Field(default=None, description="Cron string (e.g. '*/5 * * * *')")
    action: str = Field(default="profile", description="Action to run: 'profile', 'quality_check', 'full'")


class ScheduleResponse(BaseModel):
    schedule_id: str
    id: str
    name: str
    dataset_name: str
    schedule_type: str
    interval_seconds: Optional[int] = None
    cron_expression: Optional[str] = None
    action: str
    status: str
    created_at: str
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    run_count: int = 0


class AlertCreateRequest(BaseModel):
    title: str
    message: str
    severity: str = "MEDIUM"
    source: str = "DataTrust OS"
    webhook_url: Optional[str] = None
    root_cause: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WebhookDispatchRequest(BaseModel):
    webhook_url: Optional[str] = None
    alert_id: Optional[str] = None


class AnomalyDetectRequest(BaseModel):
    current_profile: Dict[str, Any]
    historical_profiles: List[Dict[str, Any]] = Field(default_factory=list)
    detector: str = "all"

