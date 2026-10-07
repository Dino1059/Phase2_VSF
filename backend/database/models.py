"""
DataTrust OS: Database Models & Schema Definitions
Supports PostgreSQL (with schemas) and SQLite fallback for local test execution.
"""

from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, model_validator


# =============================================================================
# ENUMS (6 PII Roles, 5 Treatment Actions)
# =============================================================================

class PiiRoleType(str, Enum):
    DIRECT_IDENTIFIER = "DIRECT_IDENTIFIER"
    LINKABLE_IDENTIFIER = "LINKABLE_IDENTIFIER"
    CONTEXTUAL_PERSONAL_DATA = "CONTEXTUAL_PERSONAL_DATA"
    NON_PERSONAL_REFERENCE = "NON_PERSONAL_REFERENCE"
    TECHNICAL_METADATA = "TECHNICAL_METADATA"
    AMBIGUOUS_UNSTRUCTURED_DATA = "AMBIGUOUS_UNSTRUCTURED_DATA"


class TreatmentActionType(str, Enum):
    REMOVE = "REMOVE"
    PSEUDONYMIZE = "PSEUDONYMIZE"
    KEEP_RESTRICTED = "KEEP_RESTRICTED"
    GENERALIZE = "GENERALIZE"
    KEEP = "KEEP"


class ExecutionPhase(str, Enum):
    PRE_CHECK = "pre_check"
    TREATMENT = "treatment"
    POST_CHECK = "post_check"


class OnFailAction(str, Enum):
    QUARANTINE = "QUARANTINE"
    DROP_FIELD = "DROP_FIELD"
    REJECT_BATCH = "REJECT_BATCH"
    WARN = "WARN"


class RuleSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RuleStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class QuarantineStatus(str, Enum):
    QUARANTINED = "QUARANTINED"
    IN_REVIEW = "IN_REVIEW"
    REMEDIATED = "REMEDIATED"
    OVERRIDDEN = "OVERRIDDEN"
    DISCARDED = "DISCARDED"


class UserRole(str, Enum):
    ADMIN = "ADMIN"      # Lead Data Platform / Approver
    AUDITOR = "AUDITOR"  # IPO Inspector / View-Only


# =============================================================================
# DATA CATALOG MODELS
# =============================================================================

class DatasetModel(BaseModel):
    dataset_id: str
    name: str
    title: str
    domain: str
    owner_dept: str
    storage_table_bronze: str
    storage_table_silver: str
    description: Optional[str] = None
    retention_days: int = 365
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    row_count: int = 0
    column_count: int = 0


class ColumnModel(BaseModel):
    column_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dataset_id: str
    column_name: str
    data_type: str
    is_primary_key: bool = False
    is_nullable: bool = True
    is_personal_data: bool = False
    pii_role: PiiRoleType = PiiRoleType.NON_PERSONAL_REFERENCE
    default_treatment: TreatmentActionType = TreatmentActionType.KEEP
    semantic_tag: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# POLICY MODELS
# =============================================================================

class PolicyClauseModel(BaseModel):
    clause_id: str
    policy_id: str
    clause_number: str
    requirement_summary: str
    target_pii_roles: List[PiiRoleType]
    mandated_action: TreatmentActionType
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CompliancePolicyModel(BaseModel):
    policy_id: str
    title: str
    jurisdiction: str  # 'VN', 'EU', 'US', 'GLOBAL'
    legal_framework: str
    version: str = "1.0"
    raw_policy_text: str
    effective_date: str
    status: str = "active"
    clauses: List[PolicyClauseModel] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# ENGINE & DYNAMIC RULE MODELS
# =============================================================================

class OperationRegistryModel(BaseModel):
    operation_id: str
    operation_name: str
    treatment_action: TreatmentActionType
    python_handler: str
    parameter_schema: Dict[str, Any] = {}
    description: str
    is_active: bool = True


class ComplianceCheckRuleModel(BaseModel):
    rule_id: str
    dataset_id: str
    target_column: str
    column_name: Optional[str] = None
    rule_name: str
    rule_code: str
    expression: str
    description: str
    law_ref: str
    severity: RuleSeverity = RuleSeverity.CRITICAL
    on_fail_action: OnFailAction = OnFailAction.QUARANTINE
    is_fixed: bool = True  # Cố định, không thể sửa trên UI, AI không có quyền đề xuất
    enforced_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="before")
    @classmethod
    def populate_column(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "target_column" in data and not data.get("column_name"):
                data["column_name"] = data["target_column"]
            elif "column_name" in data and not data.get("target_column"):
                data["target_column"] = data["column_name"]
        return data


class DataTreatmentRuleModel(BaseModel):
    rule_id: str
    dataset_id: str
    column_name: str
    operation_id: str
    treatment_name: str
    params_json: Dict[str, Any] = {}
    expression_display: str
    description: Optional[str] = None
    is_ai_proposed: bool = False
    ai_rationale: Optional[str] = None
    ai_confidence: Optional[float] = None
    status: str = "active"  # "active", "pending", "rejected", "paused"
    enforced_by: str = "Admin"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FieldProcessConfigModel(BaseModel):
    config_id: str
    dataset_id: str
    column_name: str
    pii_role: PiiRoleType
    treatment_action: TreatmentActionType
    operation_id: str
    execution_phase: ExecutionPhase = ExecutionPhase.TREATMENT
    execution_order: int = 1
    params_json: Dict[str, Any] = {}
    expression_display: Optional[str] = None
    on_fail_action: OnFailAction = OnFailAction.QUARANTINE
    severity: RuleSeverity = RuleSeverity.HIGH
    policy_id: Optional[str] = None
    law_ref: Optional[str] = None
    enforced_by: str  # Must be Admin
    enforced_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    version: int = 1


class ProposedRuleModel(BaseModel):
    proposal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dataset_id: str
    column_name: str
    pii_role: PiiRoleType
    treatment_action: TreatmentActionType
    operation_id: str
    execution_phase: ExecutionPhase = ExecutionPhase.TREATMENT
    params_json: Dict[str, Any] = {}
    expression_display: str
    rationale: str
    domain: str
    severity: RuleSeverity = RuleSeverity.HIGH
    confidence: float = 0.95
    law_ref: str
    policy_id: Optional[str] = None
    status: RuleStatus = RuleStatus.PENDING
    simulated_pass_rows: int = 0
    simulated_quarantine_rows: int = 0
    reviewed_by: Optional[str] = None  # Admin only
    reviewed_at: Optional[datetime] = None
    review_comments: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# QUARANTINE & AUDIT MODELS
# =============================================================================

class QuarantineRecordModel(BaseModel):
    quarantine_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    dataset_id: str
    source_table: str
    source_row_pk: Optional[str] = None
    violation_column: Optional[str] = None
    violation_rule_id: Optional[str] = None
    violation_reason: str
    violation_severity: RuleSeverity = RuleSeverity.HIGH
    raw_record_json: Dict[str, Any]
    lineage_hash: str  # SHA-256
    quarantined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: QuarantineStatus = QuarantineStatus.QUARANTINED
    resolution_note: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None


class AuditTrailModel(BaseModel):
    audit_id: Optional[int] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str
    actor_role: UserRole
    action_type: str
    entity_type: str
    entity_id: str
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    record_hash: str
    previous_hash: str


# =============================================================================
# DATA PROFILING MODELS (TASK 2)
# =============================================================================

class ColumnProfileModel(BaseModel):
    name: str
    table: Optional[str] = None
    dtype: str
    null_count: int = 0
    null_pct: float = 0.0
    unique_count: int = 0
    distinct_pct: float = 0.0
    min_val: Optional[Any] = None
    max_val: Optional[Any] = None
    mean_val: Optional[float] = None
    std: Optional[float] = None
    zeros_count: Optional[int] = 0
    negative_count: Optional[int] = 0
    top_values: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    quality_flags: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    anomalies_count: Optional[int] = 0


class TableProfileModel(BaseModel):
    dataset: str
    table_name: Optional[str] = None
    total_rows: int = 0
    columns_count: int = 0
    health_score: Optional[float] = None
    signals_summary: Optional[Dict[str, Any]] = Field(default_factory=dict)
    summary: Optional[str] = None
    columns: List[ColumnProfileModel] = Field(default_factory=list)


class ProfilePayloadResponse(BaseModel):
    dataset: str
    sample_size: Optional[int] = None
    total_rows: int = 0
    columns_count: int = 0
    health_score: Optional[float] = None
    columns: List[ColumnProfileModel] = Field(default_factory=list)
    tables: Optional[Dict[str, Any]] = Field(default_factory=dict)


# =============================================================================
# WARNING, EVIDENCE & RUN MODELS
# =============================================================================

class WarningRecordModel(BaseModel):
    warning_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    dataset_id: str
    source_row_pk: Optional[str] = None
    signal_lane: str = "LANE_A"
    signal_layer: Optional[str] = None
    warning_type: str
    warning_reason: str
    score_or_zvalue: Optional[float] = None
    evidence_json: Dict[str, Any] = Field(default_factory=dict)
    redacted_record_json: Dict[str, Any] = Field(default_factory=dict)
    lineage_hash: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditEvidenceModel(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    dag_id: str = "datatrust_adaptive_pipeline"
    dataset_id: str
    digital_signature: str = "SIG-AIRFLOW-3LANE-GSM-IPO-2026"
    evidence_hash: str
    previous_hash: Optional[str] = None
    scanned_count: int = 0
    silver_count: int = 0
    quarantine_count: int = 0
    warning_count: int = 0
    metrics: Dict[str, Any] = Field(default_factory=dict)
    evidence_payload: Dict[str, Any] = Field(default_factory=dict)
    jurisdiction_chain: Optional[List[str]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PipelineRunModel(BaseModel):
    run_id: str
    dag_id: str = "datatrust_adaptive_pipeline"
    dataset_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str
    scanned_count: int = 0
    silver_count: int = 0
    quarantine_count: int = 0
    warning_count: int = 0
    execution_duration_ms: Optional[int] = None
    error_message: Optional[str] = None


class DashboardOverviewModel(BaseModel):
    total_runs: int = 0
    total_scanned: int = 0
    total_silver: int = 0
    total_quarantine: int = 0
    total_warning: int = 0
    average_health_score: float = 100.0
    datasets_count: int = 0
    active_rules_count: int = 0
    latest_run_status: Optional[str] = None
    ledger_integrity: str = "VERIFIED"
    last_evidence_hash: Optional[str] = None


# =============================================================================
# AI AGENT TRACE, DECISION RECORD & PREVENTIVE ALERT MODELS
# =============================================================================

class DecisionRecordModel(BaseModel):
    """Căn cứ quyết định của Agent trong từng bước ReAct (Chuẩn SOX-404 / IPO Audit)."""
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    selected_action: str
    claim: str = ""
    evidence_refs: List[str] = Field(default_factory=list)
    contradicting_evidence_refs: List[str] = Field(default_factory=list)
    source_query_hashes: List[str] = Field(default_factory=list)
    confidence_method: str = "heuristic_grounding"
    confidence: float = 1.0
    alternative_considered: Optional[str] = None
    stop_continue_reason: str = ""


class AgentTraceModel(BaseModel):
    """Bản ghi vết từng bước suy nghĩ ReAct của Agent (Thay thế DuckDB agent_traces)."""
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    agent_type: str
    step_index: int
    thought: str
    action: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    tokens_used: int = 0
    duration_ms: int = 0
    decision: Optional[DecisionRecordModel] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PreventiveAlertModel(BaseModel):
    """Cảnh báo xu hướng trôi dữ liệu sớm và đề xuất phòng ngừa theo chuẩn HITL."""
    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dataset_id: str
    column_name: str
    signal_layer: str = "L2"  # L2, L3, L4
    drift_metric: str = "robust_zscore_drift"
    current_value: float
    warning_threshold: float
    predicted_risk: str = "Nguy cơ vi phạm L1 Sensor trong các chu kỳ vận hành tới"
    recommended_proposal_id: Optional[str] = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


