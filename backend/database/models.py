"""
DataTrust OS: Database Models & Schema Definitions
Supports PostgreSQL (with schemas) and SQLite fallback for local test execution.
"""

from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


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
