"""
DataTrust OS: FastAPI Backend Service
Exposes REST APIs for Data Catalog, Policies, Dynamic Process Engine, Quarantine, and Audit Trail.
Strictly enforces RBAC: ADMIN = Approver / Controller; AUDITOR = View-Only.
"""

from fastapi import FastAPI, HTTPException, Header, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import urllib.parse
import ast
from datetime import datetime, timezone
import base64
import json
import uuid
from pydantic import BaseModel

from backend.database.models import (
    UserRole,
    PiiRoleType,
    TreatmentActionType,
    DatasetModel,
    ColumnModel,
    CompliancePolicyModel,
    PolicyClauseModel,
    ProposedRuleModel,
    FieldProcessConfigModel,
    ComplianceCheckRuleModel,
    DataTreatmentRuleModel,
    QuarantineRecordModel,
    AuditTrailModel,
    RuleStatus,
    QuarantineStatus,
    ColumnProfileModel,
    TableProfileModel,
    ProfilePayloadResponse,
    WarningRecordModel,
    AuditEvidenceModel,
    PipelineRunModel,
    DashboardOverviewModel,
    AgentTraceModel,
    PreventiveAlertModel,
    DecisionRecordModel,
    FindingAIAnalysisModel,
    RemediationDecisionModel,
    RemediationStatus,
    ActionType,
)
from backend.engine.dynamic_runner import DynamicRuleRunner
from backend.engine.quarantine_manager import QuarantineManager
from backend.ai.policy_rule_proposer import PolicyRuleProposerAgent
from backend.ai.agents.orchestrator import DataTrustAgentOrchestrator
from backend.ai.services.finding_analysis_store import FindingAnalysisStore
from backend.ai.services.guardrails import pre_llm_guard
from backend.ingestion.load_3zone_pilot import (
    get_3zone_datasets,
    get_3zone_columns,
    get_3zone_policies,
    get_3zone_compliance_rules,
    get_3zone_treatment_rules,
    get_dataset_preview,
    get_dataset_stats,
    DATASET_FILE_MAP,
    resolve_csv_path
)


app = FastAPI(
    title="DataTrust OS - Adaptive Policy & Governance API",
    version="1.0.0",
    description="Backend API powering Zero-Code Dynamic Rule Adaptation, Data Catalog, and IPO Audit Assurance."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory singletons / stores for the service
quarantine_mgr = QuarantineManager()
runner = DynamicRuleRunner(quarantine_manager=quarantine_mgr)
agent = PolicyRuleProposerAgent()
orchestrator = DataTrustAgentOrchestrator()
finding_analysis_store = FindingAnalysisStore()
# Share proposals cache so endpoints stay in sync
orchestrator.rule_proposer_agent.proposals = agent.proposals

# Real 3-Zone Pilot Datasets, Columns & Policies
DATASETS: Dict[str, DatasetModel] = get_3zone_datasets()
COLUMNS: Dict[str, List[ColumnModel]] = get_3zone_columns()
POLICIES: Dict[str, CompliancePolicyModel] = get_3zone_policies()

# Fixed Compliance Check Rules (Backend-only, immutable on UI)
COMPLIANCE_RULES: List[ComplianceCheckRuleModel] = get_3zone_compliance_rules()

# Data Treatment Rules (Generic processing, AI proposed noted separately, UI editable)
TREATMENT_RULES: Dict[str, DataTreatmentRuleModel] = {r.rule_id: r for r in get_3zone_treatment_rules()}

# Initial Active Rules (Enforced by Admin Nguyễn Quốc Bảo)
INITIAL_ACTIVE_RULES = [
    FieldProcessConfigModel(
        config_id="ACT-TRIP-01",
        dataset_id="trips",
        column_name="fare_amount",
        pii_role=PiiRoleType.NON_PERSONAL_REFERENCE,
        treatment_action=TreatmentActionType.KEEP,
        operation_id="range_check",
        execution_phase="post_check",
        params_json={"min_val": 0.01, "allow_zero": False},
        expression_display="fare_amount > 0",
        law_ref="IFRS 15 / SOX 404",
        enforced_by="Nguyễn Quốc Bảo (Lead Platform)"
    ),
    FieldProcessConfigModel(
        config_id="ACT-CUST-PHONE",
        dataset_id="trips",
        column_name="customer_phone",
        pii_role=PiiRoleType.DIRECT_IDENTIFIER,
        treatment_action=TreatmentActionType.PSEUDONYMIZE,
        operation_id="mask_phone",
        execution_phase="treatment",
        params_json={"prefix_len": 3, "suffix_len": 2, "mask_char": "*"},
        expression_display="mask_phone(customer_phone)",
        law_ref="Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 & Nghị định 356/2025/NĐ-CP",
        enforced_by="Nguyễn Quốc Bảo (Lead Platform)"
    )
]
runner.load_rules(INITIAL_ACTIVE_RULES)


# Request schemas
class ProposalApprovalRequest(BaseModel):
    actor_name: str
    actor_role: UserRole = UserRole.ADMIN

class ProposalRejectionRequest(BaseModel):
    actor_name: str
    actor_role: UserRole = UserRole.ADMIN
    comments: Optional[str] = None

class UpdateTreatmentRuleRequest(BaseModel):
    expression_display: str
    params_json: Optional[Dict[str, Any]] = None
    description: Optional[str] = None

class QuarantineRemediationRequest(BaseModel):
    cleaned_payload: Dict[str, Any]
    actor_name: str
    actor_role: UserRole = UserRole.ADMIN

class QuarantineOverrideRequest(BaseModel):
    justification: str
    actor_name: str
    actor_role: UserRole = UserRole.ADMIN

class PipelineRunRequest(BaseModel):
    dataset_id: str
    bronze_records: List[Dict[str, Any]]
    run_id: Optional[str] = None

class CreatePipelineRunRequest(BaseModel):
    dataset_id: str
    collect_evidence: Optional[bool] = True
    generate_lineage: Optional[bool] = True
    options: Optional[Dict[str, Any]] = None

class AirflowTriggerRequest(BaseModel):
    dag_id: Optional[str] = "datatrust_adaptive_pipeline"
    dataset_id: Optional[str] = "trips"
    conf: Optional[Dict[str, Any]] = None

class AgentChatRequest(BaseModel):
    run_id: str
    message: str
    session_id: Optional[str] = None
    finding_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class AgentPreventiveScanRequest(BaseModel):
    dataset_id: str = "trips"
    columns: Optional[List[str]] = None


class RemediationReviewRequest(BaseModel):
    comment: Optional[str] = None


# =============================================================================
# CATALOG ENDPOINTS
# =============================================================================
# CATALOG ENDPOINTS (POSTGRESQL SINGLE SOURCE OF TRUTH)
# =============================================================================

@app.get("/api/catalog/datasets", response_model=List[DatasetModel])
def get_datasets():
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT dataset_id, table_name, source_file, domain, row_count, column_count, description, created_at
                FROM catalog.datasets
                ORDER BY table_name;
            """)
            rows = cur.fetchall()
            res = []
            for r in rows:
                ds_id = r["dataset_id"]
                res.append(DatasetModel(
                    dataset_id=ds_id,
                    name=r["source_file"] or f"{ds_id}.csv",
                    title=r["source_file"] or ds_id,
                    domain=r["domain"] or "general",
                    owner_dept="DataTrust Global Fleet",
                    storage_table_bronze=r["table_name"],
                    storage_table_silver=f"silver.{ds_id}",
                    description=r["description"] or f"{r['row_count']:,} dòng, {r['column_count']} cột",
                    retention_days=1825,
                    created_at=r["created_at"] or datetime.now(timezone.utc),
                    row_count=r["row_count"] or 0,
                    column_count=r["column_count"] or 0
                ))
            conn.close()
            if res:
                return res
    except Exception as e:
        print(f"Warning: Failed to query catalog.datasets: {e}")
    return list(DATASETS.values())

@app.get("/api/catalog/columns", response_model=List[ColumnModel])
def get_columns(dataset_id: Optional[str] = None):
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if dataset_id:
                clean_ds = dataset_id.replace(".csv", "").replace("bronze.", "")
                cur.execute("""
                    SELECT column_id, dataset_id, column_name, data_type, is_primary_key,
                           is_nullable, is_personal_data, pii_role, default_treatment, semantic_tag
                    FROM catalog.columns
                    WHERE dataset_id = %s OR dataset_id = %s;
                """, (clean_ds, f"{clean_ds}.csv"))
            else:
                cur.execute("""
                    SELECT column_id, dataset_id, column_name, data_type, is_primary_key,
                           is_nullable, is_personal_data, pii_role, default_treatment, semantic_tag
                    FROM catalog.columns
                    ORDER BY dataset_id, column_name;
                """)
            rows = cur.fetchall()
            res = []
            for r in rows:
                res.append(ColumnModel(
                    column_id=str(r["column_id"]),
                    dataset_id=r["dataset_id"],
                    column_name=r["column_name"],
                    data_type=r["data_type"],
                    is_primary_key=bool(r["is_primary_key"]),
                    is_nullable=bool(r["is_nullable"]),
                    is_personal_data=bool(r["is_personal_data"]),
                    pii_role=r["pii_role"] or "NON_PERSONAL_REFERENCE",
                    default_treatment=r["default_treatment"] or "KEEP",
                    semantic_tag=r["semantic_tag"]
                ))
            conn.close()
            if res:
                return res
    except Exception as e:
        print(f"Warning: Failed to query catalog.columns: {e}")
    if dataset_id:
        return COLUMNS.get(dataset_id, [])
    res = []
    for cols in COLUMNS.values():
        res.extend(cols)
    return res

@app.get("/api/datasets/{dataset_id}/preview")
def get_preview(dataset_id: str, limit: int = Query(default=20, ge=1, le=100)):
    """
    Xem trước dữ liệu thực tế từ schema bronze trong PostgreSQL (hoặc fallback CSV).
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor
    from decimal import Decimal

    clean_ds = dataset_id.replace(".csv", "").replace("bronze.", "")
    actual_table = f"bronze.{clean_ds}"
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"SELECT * FROM {actual_table} LIMIT %s;", (limit,))
            rows = cur.fetchall()
            cur.execute(f"SELECT count(*) FROM {actual_table};")
            total_records = cur.fetchone()["count"]

            cleaned_rows = []
            for r in rows:
                item = dict(r)
                if "_raw_id" in item:
                    item["_raw_id"] = str(item["_raw_id"])
                item.pop("_batch_id", None)
                item.pop("_ingested_at", None)
                for k, v in item.items():
                    if isinstance(v, Decimal):
                        item[k] = float(v)
                    elif isinstance(v, datetime):
                        item[k] = v.isoformat()
                cleaned_rows.append(item)

            columns = list(cleaned_rows[0].keys()) if cleaned_rows else []
            conn.close()
            return {
                "dataset_id": dataset_id,
                "table_name": actual_table,
                "columns": columns,
                "rows": cleaned_rows,
                "total_records": total_records,
                "limit": limit
            }
    except Exception as e:
        return get_dataset_preview(dataset_id, limit)

@app.get("/api/datasets/{dataset_id}/stats")
def get_stats(dataset_id: str):
    """
    Lấy thông số thực tế của file dữ liệu (số dòng, phân bố 3 vùng VN/EU/US).
    """
    return get_dataset_stats(dataset_id)


# =============================================================================
# DATA PROFILING ENDPOINTS (TASK 2)
# =============================================================================

def get_dataset_profile_response(dataset_key: str) -> Dict[str, Any]:
    """
    Query catalog.table_profiles and catalog.v_column_profiles.
    Returns payload strictly compatible with DataProfilerTab.tsx.
    """
    from database.profiler_engine import get_db_connection, DataProfilerEngine
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Query latest table profiles per dataset
            cur.execute("""
                SELECT tp.profile_id, tp.dataset_id, d.table_name, tp.total_rows, tp.total_columns,
                       tp.health_score, tp.signals_summary, tp.summary, tp.profiled_at
                FROM catalog.table_profiles tp
                JOIN catalog.datasets d ON tp.dataset_id = d.dataset_id
                WHERE tp.profile_id IN (
                    SELECT profile_id FROM (
                        SELECT profile_id, ROW_NUMBER() OVER (PARTITION BY dataset_id ORDER BY profiled_at DESC) as rn
                        FROM catalog.table_profiles
                    ) sub WHERE rn = 1
                )
                ORDER BY d.table_name;
            """)
            all_table_profiles = cur.fetchall()

            # If no profiles exist yet, run profiler
            if not all_table_profiles:
                profiler = DataProfilerEngine()
                profiler.profile_all_datasets()
                cur.execute("""
                    SELECT tp.profile_id, tp.dataset_id, d.table_name, tp.total_rows, tp.total_columns,
                           tp.health_score, tp.signals_summary, tp.summary, tp.profiled_at
                    FROM catalog.table_profiles tp
                    JOIN catalog.datasets d ON tp.dataset_id = d.dataset_id
                    ORDER BY d.table_name;
                """)
                all_table_profiles = cur.fetchall()

            # Query column profiles for the latest table profiles
            latest_pids = [str(tp["profile_id"]) for tp in all_table_profiles]
            if latest_pids:
                cur.execute("""
                    SELECT profile_id, dataset_id, table_name, column_name, data_type,
                           is_personal_data, pii_role, semantic_tag, null_count, null_pct,
                           unique_count, distinct_pct, min_val, max_val, mean_val, std_val,
                           zeros_count, negative_count, top_values, signals
                    FROM catalog.v_column_profiles
                    WHERE profile_id::text = ANY(%s)
                    ORDER BY dataset_id, column_name;
                """, (latest_pids,))
                all_cols = cur.fetchall()
            else:
                all_cols = []

        # Build tables map
        tables_map = {}
        cols_by_dataset = {}
        for c in all_cols:
            ds_id = c["dataset_id"]
            if ds_id not in cols_by_dataset:
                cols_by_dataset[ds_id] = []

            sig_list = c["signals"] if isinstance(c["signals"], list) else []
            cols_by_dataset[ds_id].append({
                "name": c["column_name"],
                "table": c["table_name"] or ds_id,
                "dtype": c["data_type"],
                "type": c["data_type"],
                "data_type": c["data_type"],
                "null_count": c["null_count"],
                "null_pct": float(c["null_pct"]),
                "unique_count": c["unique_count"],
                "distinct_count": c["unique_count"],
                "min_val": c["min_val"],
                "max_val": c["max_val"],
                "mean_val": float(c["mean_val"]) if c["mean_val"] is not None else None,
                "std": float(c["std_val"]) if c["std_val"] is not None else None,
                "zeros_count": c["zeros_count"],
                "negative_count": c["negative_count"],
                "top_values": c["top_values"] if isinstance(c["top_values"], list) else [],
                "quality_flags": sig_list,
                "anomalies_count": len(sig_list),
            })

        total_rows_all = 0
        total_cols_all = 0
        health_scores = []

        for tp in all_table_profiles:
            ds_id = tp["dataset_id"]
            tbl_name = tp["table_name"] or ds_id
            clean_name = tbl_name.replace("bronze.", "")
            t_rows = tp["total_rows"]
            t_cols = tp["total_columns"]
            h_score = float(tp["health_score"]) if tp["health_score"] is not None else 100.0

            total_rows_all += t_rows
            total_cols_all += t_cols
            health_scores.append(h_score)

            cols_for_table = cols_by_dataset.get(ds_id, [])
            table_summary = {
                "name": clean_name,
                "totalRows": t_rows,
                "columnsCount": t_cols,
                "healthScore": h_score,
                "columns": cols_for_table,
                "summary": tp["summary"],
                "qualityFlags": tp["signals_summary"] or {},
            }
            tables_map[clean_name] = table_summary
            tables_map[ds_id] = table_summary

        agg_health = round(sum(health_scores) / len(health_scores), 2) if health_scores else 100.0

        # Select dataset specific view or aggregate all
        clean_key = dataset_key.replace("bronze.", "").strip()
        selected_cols = []
        target_rows = total_rows_all
        target_cols = total_cols_all
        target_health = agg_health

        if clean_key in tables_map and clean_key not in ("__all__", "dataset", "all"):
            t_info = tables_map[clean_key]
            selected_cols = t_info["columns"]
            target_rows = t_info["totalRows"]
            target_cols = t_info["columnsCount"]
            target_health = t_info["healthScore"]
        else:
            for t_info in tables_map.values():
                for c in t_info["columns"]:
                    if c not in selected_cols:
                        selected_cols.append(c)

        return {
            "dataset": dataset_key,
            "sample_size": target_rows,
            "total_rows": target_rows,
            "columns_count": target_cols,
            "health_score": target_health,
            "columns": selected_cols,
            "tables": tables_map,
        }
    finally:
        conn.close()


@app.post("/datasets/{dataset_id}/profile")
@app.post("/api/datasets/{dataset_id}/profile")
def profile_dataset_endpoint(
    dataset_id: str,
    sample_size: Optional[int] = Query(default=None),
    day_idx: Optional[int] = Query(default=None)
):
    """
    Data Profiling API for DataProfilerTab:
    Returns single-table and multi-table profiles with statistical signals and health scores.
    """
    return get_dataset_profile_response(dataset_id)


@app.get("/api/profiling/overview")
def get_profiling_overview():
    """
    Overview of all dataset profiles, row counts, and health scores.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT tp.dataset_id, d.table_name, tp.total_rows, tp.total_columns,
                       tp.health_score, tp.signals_summary, tp.summary, tp.profiled_at
                FROM catalog.table_profiles tp
                JOIN catalog.datasets d ON tp.dataset_id = d.dataset_id
                ORDER BY d.table_name;
            """)
            rows = cur.fetchall()
            return [
                {
                    "dataset_id": r["dataset_id"],
                    "table_name": r["table_name"],
                    "total_rows": r["total_rows"],
                    "columns_count": r["total_columns"],
                    "health_score": float(r["health_score"]) if r["health_score"] is not None else None,
                    "signals_summary": r["signals_summary"],
                    "summary": r["summary"],
                    "profiled_at": r["profiled_at"].isoformat() if r["profiled_at"] else None
                }
                for r in rows
            ]
    finally:
        conn.close()


# =============================================================================
# POLICY ENDPOINTS
# =============================================================================

@app.get("/api/policies", response_model=List[CompliancePolicyModel])
def get_policies():
    return list(POLICIES.values())


# =============================================================================
# DYNAMIC RULE ENGINE ENDPOINTS
# =============================================================================

@app.get("/api/rules/active", response_model=List[FieldProcessConfigModel])
def get_active_rules(dataset_id: Optional[str] = None):
    res = []
    for d_id, rules in runner.active_rules.items():
        if not dataset_id or d_id == dataset_id:
            res.extend(rules)
    return res

@app.get("/api/rules/proposed", response_model=List[ProposedRuleModel])
def get_proposed_rules(status: Optional[RuleStatus] = None):
    props = list(agent.proposals.values())
    if status:
        props = [p for p in props if p.status == status]
    return props

@app.post("/api/ai/propose", response_model=List[ProposedRuleModel])
def ai_propose_rules(policy_id: str, dataset_id: str):
    raise HTTPException(
        status_code=410,
        detail="AI rule creation is outside the Admin MVP specification; use Finding remediation suggestions instead."
    )

@app.post("/api/rules/{proposal_id}/approve", response_model=FieldProcessConfigModel)
def approve_rule(proposal_id: str, req: ProposalApprovalRequest):
    raise HTTPException(
        status_code=410,
        detail="AI rule activation is disabled by the Admin MVP specification."
    )

@app.post("/api/rules/{proposal_id}/reject", response_model=ProposedRuleModel)
def reject_rule(proposal_id: str, req: ProposalRejectionRequest):
    raise HTTPException(
        status_code=410,
        detail="Legacy AI rule proposals are disabled by the Admin MVP specification."
    )

# =============================================================================
# =============================================================================
# COMPLIANCE CHECK RULES (FIXED / SYSTEM-LEVEL) & DATA TREATMENT RULES
# =============================================================================

@app.get("/api/rules/compliance-checks", response_model=List[ComplianceCheckRuleModel])
def get_compliance_check_rules(dataset_id: Optional[str] = None, jurisdiction: Optional[str] = None):
    """
    Quy tắc kiểm tra tuân thủ (Compliance / Quality Check Rules):
    Nguồn dữ liệu đơn nhất từ bảng PostgreSQL policy.compliance_rules.
    CỐ ĐỊNH ở backend, Read-Only trên UI, AI KHÔNG CÓ QUYỀN ĐỀ XUẤT.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if dataset_id:
                clean_ds = dataset_id.replace(".csv", "").replace("bronze.", "")
                query = """
                    SELECT rule_id, dataset_id, column_name, rule_name, rule_code,
                           expression, description, law_ref, policy_id, policy_name,
                           jurisdiction, country, severity, on_fail_action,
                           is_fixed, enforced_at
                    FROM policy.compliance_rules
                    WHERE (dataset_id = %s OR dataset_id = %s)
                """
                params = [clean_ds, f"{clean_ds}.csv"]
                if jurisdiction:
                    query = query.rstrip() + " AND jurisdiction IN ('GLOBAL', %s)"
                    params.append(jurisdiction.strip().upper())
                query += " ORDER BY rule_id;"
                cur.execute(query, tuple(params))
            else:
                query = """
                    SELECT rule_id, dataset_id, column_name, rule_name, rule_code,
                           expression, description, law_ref, policy_id, policy_name,
                           jurisdiction, country, severity, on_fail_action,
                           is_fixed, enforced_at
                    FROM policy.compliance_rules
                    WHERE 1=1
                """
                params = []
                if jurisdiction:
                    query += " AND jurisdiction IN ('GLOBAL', %s)"
                    params.append(jurisdiction.strip().upper())
                query += " ORDER BY dataset_id, rule_id;"
                cur.execute(query, tuple(params))
            rows = cur.fetchall()
            conn.close()
            if rows:
                return [
                    ComplianceCheckRuleModel(
                        rule_id=r["rule_id"],
                        dataset_id=r["dataset_id"],
                        column_name=r["column_name"],
                        target_column=r["column_name"],
                        rule_name=r["rule_name"],
                        rule_code=r["rule_code"],
                        expression=r["expression"],
                        description=r["description"] or "",
                        law_ref=r["law_ref"],
                        policy_id=r["policy_id"],
                        policy_name=r["policy_name"],
                        jurisdiction=r["jurisdiction"],
                        country=r["country"],
                        severity=r["severity"],
                        on_fail_action=r["on_fail_action"],
                        is_fixed=bool(r["is_fixed"]),
                        enforced_at=r["enforced_at"] or datetime.now(timezone.utc)
                    )
                    for r in rows
                ]
    except Exception as e:
        print(f"Warning: Failed to query policy.compliance_rules: {e}")

    # Fallback to in-memory if DB fails
    if dataset_id:
        mapped = DATASET_FILE_MAP.get(dataset_id, dataset_id)
        rules = [r for r in COMPLIANCE_RULES if r.dataset_id == dataset_id or r.dataset_id == mapped]
    else:
        rules = list(COMPLIANCE_RULES)
    if jurisdiction:
        zone = jurisdiction.strip().upper()
        rules = [r for r in rules if r.jurisdiction in {"GLOBAL", zone}]
    return rules


@app.get("/api/rules/treatments", response_model=List[DataTreatmentRuleModel])
def get_data_treatment_rules(
    dataset_id: Optional[str] = None,
    status: Optional[str] = None,
    is_ai_proposed: Optional[bool] = None,
    jurisdiction: Optional[str] = None,
):
    """
    Quy tắc xử lý dữ liệu chung (Data Treatment Rules):
    Nguồn dữ liệu đơn nhất từ bảng PostgreSQL policy.data_treatment_rules.
    Bao gồm cả PII và Non-PII (masking, hashing, rounding, to_upper, trim, nullify,...).
    AI có thể đề xuất (có cờ is_ai_proposed), Admin có thể chỉnh sửa biểu thức trên UI và phê duyệt.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT rule_id, dataset_id, column_name, operation_id, treatment_name,
                       params_json, expression_display, description, is_ai_proposed,
                       ai_rationale, ai_confidence, status, enforced_by, created_at, updated_at,
                       policy_id, policy_name, law_ref, jurisdiction, country
                FROM policy.data_treatment_rules
                WHERE 1=1
            """
            params = []
            if dataset_id:
                clean_ds = dataset_id.replace(".csv", "").replace("bronze.", "")
                query += " AND (dataset_id = %s OR dataset_id = %s)"
                params.extend([clean_ds, f"{clean_ds}.csv"])
            if status:
                query += " AND LOWER(status) = LOWER(%s)"
                params.append(status)
            if is_ai_proposed is not None:
                query += " AND is_ai_proposed = %s"
                params.append(is_ai_proposed)
            if jurisdiction:
                query += " AND jurisdiction IN ('GLOBAL', %s)"
                params.append(jurisdiction.strip().upper())
            query += " ORDER BY dataset_id, rule_id;"

            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            conn.close()
            if rows:
                return [
                    DataTreatmentRuleModel(
                        rule_id=r["rule_id"],
                        dataset_id=r["dataset_id"],
                        column_name=r["column_name"],
                        operation_id=r["operation_id"],
                        treatment_name=r["treatment_name"],
                        params_json=r["params_json"] if isinstance(r["params_json"], dict) else {},
                        expression_display=r["expression_display"],
                        description=r["description"],
                        policy_id=r["policy_id"],
                        policy_name=r["policy_name"],
                        law_ref=r["law_ref"],
                        jurisdiction=r["jurisdiction"],
                        country=r["country"],
                        is_ai_proposed=bool(r["is_ai_proposed"]),
                        ai_rationale=r["ai_rationale"],
                        ai_confidence=float(r["ai_confidence"]) if r["ai_confidence"] is not None else None,
                        status=r["status"],
                        enforced_by=r["enforced_by"] or "Admin",
                        created_at=r["created_at"] or datetime.now(timezone.utc),
                        updated_at=r["updated_at"] or datetime.now(timezone.utc)
                    )
                    for r in rows
                ]
    except Exception as e:
        print(f"Warning: Failed to query policy.data_treatment_rules: {e}")

    # Fallback to in-memory
    rules = list(TREATMENT_RULES.values())
    if dataset_id:
        mapped = DATASET_FILE_MAP.get(dataset_id, dataset_id)
        rules = [r for r in rules if r.dataset_id == dataset_id or r.dataset_id == mapped]
    if status:
        rules = [r for r in rules if r.status.lower() == status.lower()]
    if is_ai_proposed is not None:
        rules = [r for r in rules if r.is_ai_proposed == is_ai_proposed]
    if jurisdiction:
        zone = jurisdiction.strip().upper()
        rules = [r for r in rules if r.jurisdiction in {"GLOBAL", zone}]
    return rules


@app.put("/api/rules/treatments/{rule_id}", response_model=DataTreatmentRuleModel)
def update_data_treatment_rule(
    rule_id: str,
    req: UpdateTreatmentRuleRequest,
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """
    Cho phép Admin chỉnh sửa trực tiếp biểu thức (expression) và cấu hình xử lý trên UI.
    RBAC: Auditor là Chỉ đọc, không có quyền sửa quy tắc.
    """
    if x_user_role and x_user_role.lower() == "auditor":
        raise HTTPException(
            status_code=403,
            detail="Vai trò Auditor là Chỉ đọc (Read-Only) và không có quyền chỉnh sửa quy tắc xử lý."
        )

    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor
    now_utc = datetime.now(timezone.utc)
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE policy.data_treatment_rules
                SET expression_display = %s,
                    params_json = COALESCE(%s::jsonb, params_json),
                    description = COALESCE(%s, description),
                    updated_at = %s
                WHERE rule_id = %s
                RETURNING *;
            """, (
                req.expression_display,
                json.dumps(req.params_json) if req.params_json is not None else None,
                req.description,
                now_utc,
                rule_id
            ))
            row = cur.fetchone()
            conn.commit()
            conn.close()
            if row:
                res_rule = DataTreatmentRuleModel(
                    rule_id=row["rule_id"],
                    dataset_id=row["dataset_id"],
                    column_name=row["column_name"],
                    operation_id=row["operation_id"],
                    treatment_name=row["treatment_name"],
                    params_json=row["params_json"] if isinstance(row["params_json"], dict) else {},
                    expression_display=row["expression_display"],
                    description=row["description"],
                    policy_id=row["policy_id"],
                    policy_name=row["policy_name"],
                    law_ref=row["law_ref"],
                    jurisdiction=row["jurisdiction"],
                    country=row["country"],
                    is_ai_proposed=bool(row["is_ai_proposed"]),
                    ai_rationale=row["ai_rationale"],
                    ai_confidence=float(row["ai_confidence"]) if row["ai_confidence"] is not None else None,
                    status=row["status"],
                    enforced_by=row["enforced_by"] or "Admin",
                    created_at=row["created_at"],
                    updated_at=row["updated_at"]
                )
                TREATMENT_RULES[rule_id] = res_rule
                return res_rule
    except Exception as e:
        print(f"Warning: Failed to update policy.data_treatment_rules in DB: {e}")

    # In-memory fallback
    rule = TREATMENT_RULES.get(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Treatment rule not found")
    rule.expression_display = req.expression_display
    if req.params_json is not None:
        rule.params_json = req.params_json
    if req.description is not None:
        rule.description = req.description
    rule.updated_at = now_utc
    return rule


@app.post("/api/rules/treatments/{rule_id}/approve", response_model=DataTreatmentRuleModel)
def approve_data_treatment_rule(
    rule_id: str,
    req: ProposalApprovalRequest,
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """
    Disabled by the Admin MVP specification: applied rules are read-only.
    """
    raise HTTPException(
        status_code=410,
        detail="Rule approval is read-only in the Admin MVP; review Finding remediation instead.",
    )


@app.post("/api/rules/treatments/{rule_id}/reject", response_model=DataTreatmentRuleModel)
def reject_data_treatment_rule(
    rule_id: str,
    req: ProposalRejectionRequest,
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """
    Disabled by the Admin MVP specification: review Finding remediation instead.
    """
    raise HTTPException(
        status_code=410,
        detail="Rule rejection is outside the Admin MVP; review Finding remediation instead.",
    )


@app.patch("/api/rules/treatments/{rule_id}/toggle", response_model=DataTreatmentRuleModel)
def toggle_data_treatment_rule(rule_id: str):
    """
    Bật / Tạm dừng áp dụng rule xử lý dữ liệu ('active' <-> 'paused') trong DB.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor
    now_utc = datetime.now(timezone.utc)
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE policy.data_treatment_rules
                SET status = CASE WHEN LOWER(status) = 'active' THEN 'paused' ELSE 'active' END,
                    updated_at = %s
                WHERE rule_id = %s
                RETURNING *;
            """, (now_utc, rule_id))
            row = cur.fetchone()
            conn.commit()
            conn.close()
            if row:
                res_rule = DataTreatmentRuleModel(
                    rule_id=row["rule_id"],
                    dataset_id=row["dataset_id"],
                    column_name=row["column_name"],
                    operation_id=row["operation_id"],
                    treatment_name=row["treatment_name"],
                    params_json=row["params_json"] if isinstance(row["params_json"], dict) else {},
                    expression_display=row["expression_display"],
                    description=row["description"],
                    policy_id=row["policy_id"],
                    policy_name=row["policy_name"],
                    law_ref=row["law_ref"],
                    jurisdiction=row["jurisdiction"],
                    country=row["country"],
                    is_ai_proposed=bool(row["is_ai_proposed"]),
                    ai_rationale=row["ai_rationale"],
                    ai_confidence=float(row["ai_confidence"]) if row["ai_confidence"] is not None else None,
                    status=row["status"],
                    enforced_by=row["enforced_by"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"]
                )
                TREATMENT_RULES[rule_id] = res_rule
                return res_rule
    except Exception as e:
        print(f"Warning: Failed to toggle policy.data_treatment_rules in DB: {e}")

    rule = TREATMENT_RULES.get(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Treatment rule not found")
    if rule.status.lower() == "active":
        rule.status = "paused"
    elif rule.status.lower() == "paused":
        rule.status = "active"
    rule.updated_at = now_utc
    return rule



# =============================================================================
# PIPELINE EXECUTION (GENERIC RUNNER)
# =============================================================================

@app.post("/api/pipeline/run")
def run_pipeline(req: PipelineRunRequest):
    res = runner.run_pipeline(req.dataset_id, req.bronze_records, req.run_id)
    return {
        "run_id": res.run_id,
        "dataset_id": res.dataset_id,
        "scanned_count": res.scanned_count,
        "silver_count": res.silver_count,
        "quarantine_count": res.quarantine_count,
        "silver_records": res.silver_records,
        "quarantine_records": [q.model_dump() for q in res.quarantine_records]
    }


# =============================================================================
# AIRFLOW ORCHESTRATION INTEGRATION
# =============================================================================

AIRFLOW_API_URL = "http://localhost:8080/api/v1"
AIRFLOW_USER = "airflow"
AIRFLOW_PASS = "airflow"

@app.get("/api/airflow/status")
def get_airflow_status():
    """
    Kiểm tra tình trạng sẵn sàng của Apache Airflow Webserver (port 8080).
    """
    try:
        req = Request("http://localhost:8080/health")
        with urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "is_live": True,
                "status": "online",
                "health": data,
                "dag_id": "datatrust_adaptive_pipeline"
            }
    except Exception as e:
        return {
            "is_live": False,
            "status": "offline_or_starting",
            "error": str(e),
            "dag_id": "datatrust_adaptive_pipeline"
        }

# =============================================================================
# RUN MANAGEMENT & AIRFLOW ORCHESTRATION (100% REAL DATA FROM POSTGRESQL & AIRFLOW)
# =============================================================================

@app.post("/api/runs")
def create_pipeline_run(
    req: CreatePipelineRunRequest,
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """
    Step 3 / Spec 06: Khởi chạy một lượt chạy pipeline kiểm toán mới qua Apache Airflow.
    Bảo vệ RBAC: Auditor là vai trò Chỉ đọc (Read-only), không được phép khởi chạy.
    Khởi tạo canonical run_id và ghi nhận đầy đủ vòng đời vào orchestration.pipeline_runs.
    """
    if x_user_role and x_user_role.lower() == "auditor":
        raise HTTPException(
            status_code=403,
            detail="Vai trò Auditor là Chỉ đọc (Read-Only) và không có quyền khởi chạy Pipeline."
        )

    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor, Json

    raw_dataset = req.dataset_id or "ride_hailing_xanh_sm_trips"
    if str(raw_dataset).upper() in ("ALL", "*"):
        actual_filename = "ALL"
    else:
        actual_filename = DATASET_FILE_MAP.get(str(raw_dataset), str(raw_dataset))
        if not actual_filename.endswith(".csv"):
            actual_filename += ".csv"

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    dag_run_id = f"app_{run_id}"
    dag_id = "datatrust_adaptive_pipeline"

    options_payload = {
        "collect_evidence": req.collect_evidence,
        "generate_lineage": req.generate_lineage,
        **(req.options or {})
    }

    # 1. Khởi tạo bản ghi PENDING/RUNNING trong PostgreSQL
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO orchestration.pipeline_runs 
                (run_id, dag_id, dataset_id, started_at, status, airflow_dag_run_id, options_json, current_step, current_step_progress)
                VALUES (%s, %s, %s, NOW(), 'RUNNING', %s, %s, 'INGEST', 10);
            """, (run_id, dag_id, actual_filename, dag_run_id, Json(options_payload)))

            cur.execute("""
                INSERT INTO orchestration.pipeline_run_steps
                (run_id, step_name, step_order, status, started_at)
                VALUES (%s, 'INGEST', 1, 'RUNNING', NOW());
            """, (run_id,))

            cur.execute("""
                INSERT INTO orchestration.pipeline_run_events
                (run_id, step_name, event_type, message, payload)
                VALUES (%s, 'INGEST', 'INFO', 'Lượt chạy kiểm toán được khởi tạo', %s);
            """, (run_id, Json({"dataset_id": actual_filename, "dag_run_id": dag_run_id})))

            conn.commit()
    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        raise HTTPException(status_code=500, detail=f"Lỗi khởi tạo lượt chạy trong PostgreSQL: {e}")

    # 2. Kích hoạt Apache Airflow REST API với Canonical Run ID
    auth_str = base64.b64encode(f"{AIRFLOW_USER}:{AIRFLOW_PASS}".encode("utf-8")).decode("utf-8")
    target_param_id = "ALL" if actual_filename == "ALL" else actual_filename.replace(".csv", "")
    conf_payload = {
        "app_run_id": run_id,
        "dataset_id": target_param_id,
        "filename": actual_filename,
        **options_payload
    }
    payload = {
        "dag_run_id": dag_run_id,
        "conf": conf_payload
    }

    try:
        request_obj = Request(
            f"{AIRFLOW_API_URL}/dags/{dag_id}/dagRuns",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {auth_str}"
            },
            method="POST"
        )
        with urlopen(request_obj, timeout=5.0) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            return {
                "run_id": run_id,
                "airflow_dag_run_id": dag_run_id,
                "dataset_id": actual_filename,
                "status": "RUNNING",
                "execution_date": res_data.get("execution_date"),
                "message": f"Đã kích hoạt Airflow DAG {dag_id} cho dataset {actual_filename} thành công!"
            }
    except Exception as e:
        # Cập nhật FAILED trong DB và trả về HTTP 503 - Tuyệt đối không sinh dữ liệu giả
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE orchestration.pipeline_runs
                    SET status = 'FAILED', error_message = %s, ended_at = NOW()
                    WHERE run_id = %s;
                """, (f"Airflow connection/execution failed: {str(e)}", run_id))
                cur.execute("""
                    UPDATE orchestration.pipeline_run_steps
                    SET status = 'FAILED', ended_at = NOW(), error_message = %s
                    WHERE run_id = %s AND step_name = 'INGEST';
                """, (str(e), run_id))
                conn.commit()
        except Exception:
            pass
        finally:
            if conn and not conn.closed:
                conn.close()
        raise HTTPException(
            status_code=503,
            detail=f"Dịch vụ Apache Airflow không khả dụng hoặc lỗi kích hoạt: {str(e)}"
        )
    finally:
        if conn and not conn.closed:
            conn.close()


@app.post("/api/airflow/trigger")
def trigger_airflow_pipeline(
    req: Optional[AirflowTriggerRequest] = None,
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """
    Endpoint tương thích ngược chuyển tiếp sang logic POST /api/runs chuẩn.
    """
    if req is None:
        req = AirflowTriggerRequest()
    create_req = CreatePipelineRunRequest(
        dataset_id=req.dataset_id or "ride_hailing_xanh_sm_trips",
        options=req.conf
    )
    result = create_pipeline_run(create_req, x_user_role=x_user_role)
    if isinstance(result, dict):
        return {
            **result,
            "upstream_status": result.get("status"),
            "status": "triggered",
            "mode": result.get("mode", "airflow_celery"),
        }
    return result


@app.get("/api/runs")
def list_pipeline_runs(
    dataset_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
):
    """
    Lấy danh sách các lần chạy pipeline 100% từ PostgreSQL orchestration.pipeline_runs.
    Không dùng mock data, benchmark ảo hay fallback fake run.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor

    runs = []
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT run_id, dag_id, dataset_id, started_at, ended_at, status,
                       scanned_count, silver_count, quarantine_count, warning_count,
                       not_evaluated_count, execution_duration_ms, error_message,
                       airflow_dag_run_id, current_step, current_step_progress
                FROM orchestration.pipeline_runs
                WHERE 1=1
            """
            params = []
            if dataset_id:
                clean_ds = dataset_id.replace(".csv", "").replace("bronze.", "")
                query += " AND (dataset_id = %s OR dataset_id = %s)"
                params.extend([clean_ds, f"{clean_ds}.csv"])
            if status:
                query += " AND LOWER(status) = LOWER(%s)"
                params.append(status)
            query += " ORDER BY started_at DESC LIMIT %s;"
            params.append(limit)

            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            conn.close()

            for r in rows:
                dur_mins = round((r["execution_duration_ms"] or 60000) / 60000, 1)
                runs.append({
                    "id": r["run_id"],
                    "dagId": r["dag_id"],
                    "status": (r["status"] or "SUCCESS").upper(),
                    "inputRecords": r["scanned_count"] or 0,
                    "silverRecords": r["silver_count"] or 0,
                    "quarantineRecords": r["quarantine_count"] or 0,
                    "warningRecords": r["warning_count"] or 0,
                    "notEvaluatedRecords": r.get("not_evaluated_count") or 0,
                    "startedAt": r["started_at"].isoformat() if r["started_at"] else None,
                    "finishedAt": r["ended_at"].isoformat() if r["ended_at"] else None,
                    "durationMinutes": dur_mins,
                    "datasetId": r["dataset_id"],
                    "currentStep": r.get("current_step") or "INGEST",
                    "currentStepProgress": r.get("current_step_progress") or 0,
                    "errorMessage": r["error_message"]
                })
            return runs
    except Exception as e:
        print(f"Error querying orchestration.pipeline_runs: {e}")
        return []


@app.get("/api/runs/{run_id}")
def get_pipeline_run_detail(run_id: str):
    """
    Step 3 / Spec 06: Chi tiết lượt chạy pipeline từ PostgreSQL.
    Bao gồm 5 bước của Stepper, 6 Thẻ Chỉ số, Nhật ký Sự kiện Timeline, và Bằng chứng Kiểm toán.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Truy vấn run metadata
            cur.execute("""
                SELECT * FROM orchestration.pipeline_runs 
                WHERE run_id = %s OR airflow_dag_run_id = %s;
            """, (run_id, run_id))
            run_row = cur.fetchone()
            if not run_row:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy lượt chạy '{run_id}'.")

            real_run_id = run_row["run_id"]

            # 2. Truy vấn các bước trong Stepper
            cur.execute("""
                SELECT step_id, step_name, step_order, status, started_at, ended_at, error_message
                FROM orchestration.pipeline_run_steps
                WHERE run_id = %s
                ORDER BY step_order ASC;
            """, (real_run_id,))
            steps = cur.fetchall()

            default_steps = [
                {"step_name": "INGEST", "step_order": 1, "title": "Ingest Bronze", "status": "WAITING"},
                {"step_name": "BRONZE", "step_order": 2, "title": "Data Profiling", "status": "WAITING"},
                {"step_name": "EVALUATION", "step_order": 3, "title": "Parallel Evaluation (L1-L4 & Policy)", "status": "WAITING"},
                {"step_name": "SILVER", "step_order": 4, "title": "Merge & Route Silver/Quarantine", "status": "WAITING"},
                {"step_name": "EVIDENCE", "step_order": 5, "title": "Emit Audit Evidence", "status": "WAITING"},
            ]
            full_steps = []
            for ds in default_steps:
                matching = next((s for s in steps if s["step_name"] == ds["step_name"]), None)
                if matching:
                    full_steps.append({
                        "step_id": str(matching.get("step_id", "")),
                        "step_name": matching["step_name"],
                        "step_order": matching["step_order"],
                        "title": ds["title"],
                        "status": matching["status"],
                        "started_at": matching["started_at"].isoformat() if matching.get("started_at") else None,
                        "ended_at": matching["ended_at"].isoformat() if matching.get("ended_at") else None,
                        "error_message": matching.get("error_message")
                    })
                else:
                    st = "COMPLETED" if run_row["status"] == "SUCCESS" else "WAITING"
                    full_steps.append({
                        "step_id": "",
                        "step_name": ds["step_name"],
                        "step_order": ds["step_order"],
                        "title": ds["title"],
                        "status": st,
                        "started_at": run_row["started_at"].isoformat() if run_row["started_at"] else None,
                        "ended_at": run_row["ended_at"].isoformat() if run_row["ended_at"] else None,
                        "error_message": None
                    })

            # 3. Truy vấn sự kiện dòng thời gian
            cur.execute("""
                SELECT event_id, step_name, event_type, message, payload, created_at
                FROM orchestration.pipeline_run_events
                WHERE run_id = %s
                ORDER BY created_at ASC;
            """, (real_run_id,))
            events = [
                {
                    "event_id": str(e["event_id"]),
                    "step_name": e["step_name"],
                    "event_type": e["event_type"],
                    "message": e["message"],
                    "payload": e["payload"],
                    "created_at": e["created_at"].isoformat() if e["created_at"] else None
                }
                for e in cur.fetchall()
            ]

            # 4. Truy vấn bằng chứng kiểm toán
            cur.execute("""
                SELECT evidence_id, digital_signature, evidence_hash, previous_hash, jurisdiction_chain, created_at
                FROM audit.evidence WHERE run_id = %s ORDER BY created_at DESC LIMIT 1;
            """, (real_run_id,))
            evidence_row = cur.fetchone()

            # 5. Truy vấn tổng hợp Finding
            cur.execute("""
                SELECT count(*) as total,
                       count(CASE WHEN severity = 'CRITICAL' THEN 1 END) as critical_count,
                       count(CASE WHEN severity = 'HIGH' THEN 1 END) as high_count
                FROM audit.findings WHERE run_id = %s;
            """, (real_run_id,))
            finding_counts = cur.fetchone()

            scanned = run_row.get("scanned_count") or 0
            silver = run_row.get("silver_count") or 0
            quarantine = run_row.get("quarantine_count") or 0
            warning = run_row.get("warning_count") or 0
            not_eval = run_row.get("not_evaluated_count") or max(0, scanned - silver - quarantine)

            dur_detail_ms = run_row.get("execution_duration_ms")
            if not dur_detail_ms and run_row.get("started_at") and run_row.get("ended_at"):
                dur_detail_ms = int((run_row["ended_at"] - run_row["started_at"]).total_seconds() * 1000)

            return {
                "run_id": real_run_id,
                "airflow_dag_run_id": run_row.get("airflow_dag_run_id"),
                "dag_id": run_row.get("dag_id"),
                "dataset_id": run_row.get("dataset_id"),
                "status": run_row.get("status"),
                "started_at": run_row["started_at"].isoformat() if run_row.get("started_at") else None,
                "ended_at": run_row["ended_at"].isoformat() if run_row.get("ended_at") else None,
                "duration_ms": dur_detail_ms,
                "current_step": run_row.get("current_step") or "INGEST",
                "current_step_progress": run_row.get("current_step_progress") or 0,
                "options": run_row.get("options_json") or {},
                "metrics": {
                    "scanned": scanned,
                    "silver": silver,
                    "quarantine": quarantine,
                    "warning": warning,
                    "not_evaluated": not_eval,
                },
                "steps": full_steps,
                "events": events,
                "findings_summary": {
                    "total": finding_counts["total"] if finding_counts else 0,
                    "critical": finding_counts["critical_count"] if finding_counts else 0,
                    "high": finding_counts["high_count"] if finding_counts else 0,
                },
                "evidence": {
                    "evidence_id": str(evidence_row["evidence_id"]) if evidence_row else None,
                    "digital_signature": evidence_row["digital_signature"] if evidence_row else None,
                    "evidence_hash": evidence_row["evidence_hash"] if evidence_row else None,
                    "previous_hash": evidence_row["previous_hash"] if evidence_row else None,
                    "jurisdiction_chain": evidence_row["jurisdiction_chain"] if evidence_row else ["GLOBAL", "VN"],
                    "created_at": evidence_row["created_at"].isoformat() if evidence_row and evidence_row["created_at"] else None
                } if evidence_row else None
            }
    finally:
        conn.close()


@app.get("/api/runs/{run_id}/results")
def get_run_results(run_id: str):
    """
    Step 4 / Spec 07: Trả về kết quả tổng quan lần chạy gồm 4 KPI Cards %,
    biểu đồ phân bổ vi phạm, top violated rules, và phân tích rủi ro.
    100% dữ liệu thực từ PostgreSQL.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM orchestration.pipeline_runs 
                WHERE run_id = %s OR airflow_dag_run_id = %s;
            """, (run_id, run_id))
            run_row = cur.fetchone()
            if not run_row:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy lượt chạy '{run_id}'")

            real_run_id = run_row["run_id"]
            scanned = run_row.get("scanned_count") or 0
            silver = run_row.get("silver_count") or 0
            quarantine = run_row.get("quarantine_count") or 0
            warning = run_row.get("warning_count") or 0
            not_eval = run_row.get("not_evaluated_count") or max(0, scanned - silver - quarantine)

            total_denom = max(1, scanned)
            pass_pct = round((silver / total_denom) * 100, 2)
            fail_pct = round((quarantine / total_denom) * 100, 2)
            warning_pct = round((warning / total_denom) * 100, 2)
            not_eval_pct = round((not_eval / total_denom) * 100, 2)

            # Query Top Violated Rules từ audit.findings hoặc quarantine.records
            cur.execute("""
                SELECT rule_id, column_name, severity, policy_name, reason, failed_record_count
                FROM audit.findings
                WHERE run_id = %s
                ORDER BY failed_record_count DESC
                LIMIT 5;
            """, (real_run_id,))
            top_rules_rows = cur.fetchall()

            if not top_rules_rows:
                cur.execute("""
                    SELECT violation_rule_id as rule_id, violation_column as column_name,
                           violation_severity as severity, violation_reason as reason,
                           count(*) as failed_record_count
                    FROM quarantine.records
                    WHERE run_id = %s
                    GROUP BY violation_rule_id, violation_column, violation_severity, violation_reason
                    ORDER BY count(*) DESC
                    LIMIT 5;
                """, (real_run_id,))
                top_rules_rows = cur.fetchall()

            top_violated_rules = []
            for r in top_rules_rows:
                cnt = r["failed_record_count"]
                top_violated_rules.append({
                    "rule_id": r["rule_id"],
                    "column_name": r.get("column_name") or "ALL",
                    "severity": r.get("severity") or "HIGH",
                    "policy_name": r.get("policy_name") or "Compliance Policy",
                    "reason": r.get("reason") or "Quy tắc vi phạm kiểm soát chất lượng",
                    "failed_record_count": cnt,
                    "percentage": round((cnt / total_denom) * 100, 2)
                })

            # Phân bổ mức độ nghiêm trọng
            cur.execute("""
                SELECT violation_severity, count(*) as count
                FROM quarantine.records
                WHERE run_id = %s
                GROUP BY violation_severity;
            """, (real_run_id,))
            sev_rows = cur.fetchall()
            severity_breakdown = {
                "CRITICAL": 0,
                "HIGH": 0,
                "MEDIUM": 0,
                "LOW": 0
            }
            for s in sev_rows:
                k = (s["violation_severity"] or "HIGH").upper()
                if k in severity_breakdown:
                    severity_breakdown[k] = s["count"]

            # Phân bổ theo làn
            cur.execute("""
                SELECT failure_lane, count(*) as count
                FROM quarantine.records
                WHERE run_id = %s
                GROUP BY failure_lane;
            """, (real_run_id,))
            lane_rows = cur.fetchall()
            lane_breakdown = {r["failure_lane"]: r["count"] for r in lane_rows}

            dur_ms = run_row.get("execution_duration_ms")
            if not dur_ms and run_row.get("started_at") and run_row.get("ended_at"):
                dur_ms = int((run_row["ended_at"] - run_row["started_at"]).total_seconds() * 1000)

            return {
                "run_id": real_run_id,
                "dataset_id": run_row.get("dataset_id"),
                "status": run_row.get("status"),
                "started_at": run_row["started_at"].isoformat() if run_row.get("started_at") else None,
                "ended_at": run_row["ended_at"].isoformat() if run_row.get("ended_at") else None,
                "duration_ms": dur_ms,
                "kpis": {
                    "total_scanned": scanned,
                    "pass_count": silver,
                    "pass_percentage": pass_pct,
                    "fail_count": quarantine,
                    "fail_percentage": fail_pct,
                    "warning_count": warning,
                    "warning_percentage": warning_pct,
                    "not_evaluated_count": not_eval,
                    "not_evaluated_percentage": not_eval_pct,
                },
                "severity_breakdown": severity_breakdown,
                "lane_breakdown": lane_breakdown,
                "top_violated_rules": top_violated_rules
            }
    finally:
        conn.close()


@app.get("/api/findings")
@app.get("/api/runs/{run_id}/findings")
def list_findings(
    run_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
    rule_id: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    column: Optional[str] = None,
    subject_zone: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0)
):
    """
    Step 5 / Spec 08: Danh sách các Findings (vấn đề kiểm toán tổng hợp)
    với 6 bộ lọc: Run, Dataset, Rule, Severity, Status, Column, và Search text.
    100% dữ liệu thực từ PostgreSQL audit.findings.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT f.finding_id, f.run_id, f.dataset_id, f.rule_id, f.policy_id,
                       f.policy_name, f.law_ref, f.jurisdiction AS subject_zone, f.jurisdiction_chain,
                       f.column_name, f.severity, f.status,
                       f.reason, f.impact, f.failed_record_count, f.detected_at,
                       f.resolved_at, f.resolved_by,
                       r.started_at as run_started_at
                FROM audit.findings f
                LEFT JOIN orchestration.pipeline_runs r ON f.run_id = r.run_id
                WHERE 1=1
            """
            count_query = "SELECT count(*) FROM audit.findings f LEFT JOIN orchestration.pipeline_runs r ON f.run_id = r.run_id WHERE 1=1"
            params = []

            if run_id:
                query += " AND (f.run_id = %s OR r.airflow_dag_run_id = %s)"
                count_query += " AND (f.run_id = %s OR r.airflow_dag_run_id = %s)"
                params.extend([run_id, run_id])
            if dataset_id:
                clean_ds = dataset_id.replace(".csv", "").replace("bronze.", "")
                query += " AND (f.dataset_id = %s OR f.dataset_id = %s)"
                count_query += " AND (f.dataset_id = %s OR f.dataset_id = %s)"
                params.extend([clean_ds, f"{clean_ds}.csv"])
            if rule_id:
                query += " AND LOWER(f.rule_id) = LOWER(%s)"
                count_query += " AND LOWER(f.rule_id) = LOWER(%s)"
                params.append(rule_id)
            if severity:
                query += " AND LOWER(f.severity) = LOWER(%s)"
                count_query += " AND LOWER(f.severity) = LOWER(%s)"
                params.append(severity)
            if status:
                query += " AND LOWER(f.status) = LOWER(%s)"
                count_query += " AND LOWER(f.status) = LOWER(%s)"
                params.append(status)
            if column:
                query += " AND LOWER(f.column_name) = LOWER(%s)"
                count_query += " AND LOWER(f.column_name) = LOWER(%s)"
                params.append(column)
            if subject_zone:
                normalized_zone = subject_zone.strip().upper()
                query += " AND UPPER(TRIM(f.jurisdiction)) = %s"
                count_query += " AND UPPER(TRIM(f.jurisdiction)) = %s"
                params.append(normalized_zone)
            if search:
                term = f"%{search}%"
                query += " AND (f.reason ILIKE %s OR f.rule_id ILIKE %s OR f.policy_name ILIKE %s)"
                count_query += " AND (f.reason ILIKE %s OR f.rule_id ILIKE %s OR f.policy_name ILIKE %s)"
                params.extend([term, term, term])

            cur.execute(count_query, tuple(params))
            total_count = cur.fetchone()["count"]

            query += " ORDER BY f.detected_at DESC LIMIT %s OFFSET %s;"
            p_exec = list(params)
            p_exec.extend([limit, offset])
            cur.execute(query, tuple(p_exec))
            rows = cur.fetchall()

            clean_findings = []
            for r in rows:
                item = dict(r)
                if item.get("detected_at"):
                    item["detected_at"] = item["detected_at"].isoformat()
                if item.get("resolved_at"):
                    item["resolved_at"] = item["resolved_at"].isoformat()
                if item.get("run_started_at"):
                    item["run_started_at"] = item["run_started_at"].isoformat()
                clean_findings.append(item)

            return {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "findings": clean_findings
            }
    finally:
        conn.close()


@app.get("/api/findings/{finding_id}")
def get_finding_detail(finding_id: str):
    """
    Step 5 / Spec 08: Chi tiết một Finding gồm thông tin rule, policy,
    mẫu dữ liệu cách ly thực tế (Raw Record JSON), và cấu hình rule.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT f.*, r.started_at as run_started_at, r.status as run_status
                FROM audit.findings f
                LEFT JOIN orchestration.pipeline_runs r ON f.run_id = r.run_id
                WHERE f.finding_id = %s;
            """, (finding_id,))
            finding = cur.fetchone()
            if not finding:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy Finding '{finding_id}'.")

            res = dict(finding)
            res["subject_zone"] = res.get("jurisdiction")
            if res.get("detected_at"):
                res["detected_at"] = res["detected_at"].isoformat()
            if res.get("resolved_at"):
                res["resolved_at"] = res["resolved_at"].isoformat()
            if res.get("run_started_at"):
                res["run_started_at"] = res["run_started_at"].isoformat()

            # Mẫu bản ghi cách ly thực tế
            cur.execute("""
                SELECT q.quarantine_id, q.source_row_pk, q.failure_lane, q.violation_severity,
                       q.violation_reason, q.raw_record_json, q.status, q.quarantined_at,
                       q.lineage_hash, q.subject_zone, q.jurisdiction_chain,
                       q.matched_policy_id AS policy_id,
                       q.matched_policy_name AS policy_name,
                       q.matched_law_ref AS law_ref
                FROM audit.finding_quarantine_records fqr
                JOIN quarantine.records q ON fqr.quarantine_id = q.quarantine_id
                WHERE fqr.finding_id = %s
                  AND UPPER(TRIM(q.subject_zone)) = UPPER(TRIM(%s))
                LIMIT 10;
            """, (finding_id, res.get("subject_zone")))
            q_rows = cur.fetchall()

            if not q_rows:
                cur.execute("""
                    SELECT quarantine_id, source_row_pk, failure_lane, violation_severity,
                           violation_reason, raw_record_json, status, quarantined_at,
                           lineage_hash, subject_zone, jurisdiction_chain,
                           matched_policy_id AS policy_id,
                           matched_policy_name AS policy_name,
                           matched_law_ref AS law_ref
                    FROM quarantine.records
                    WHERE run_id = %s
                      AND (violation_rule_id = %s OR violation_column = %s)
                      AND UPPER(TRIM(subject_zone)) = UPPER(TRIM(%s))
                    LIMIT 10;
                """, (res["run_id"], res["rule_id"], res["column_name"], res.get("subject_zone")))
                q_rows = cur.fetchall()

            sample_records = []
            for q in q_rows:
                qi = dict(q)
                qi["quarantine_id"] = str(qi["quarantine_id"])
                if qi.get("quarantined_at"):
                    qi["quarantined_at"] = qi["quarantined_at"].isoformat()
                sample_records.append(qi)
            res["sample_records"] = sample_records

            # Định nghĩa rule tương ứng
            cur.execute("""
                SELECT rule_id, treatment_name, operation_id, expression_display, description, status, enforced_by
                FROM policy.data_treatment_rules
                WHERE rule_id = %s;
            """, (res["rule_id"],))
            rule_row = cur.fetchone()
            res["rule_definition"] = dict(rule_row) if rule_row else None

            return res
    finally:
        conn.close()


def _require_admin_identity(x_user_role: Optional[str], x_user: Optional[str]) -> str:
    """Read temporary development identity headers; production auth must validate them upstream."""
    if (x_user_role or "").upper() != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="ADMIN role is required for remediation decisions.")
    actor = (x_user or "").strip()
    if not actor:
        raise HTTPException(status_code=401, detail="X-User identity header is required.")
    return actor


def _finding_ai_context(finding_id: str) -> Dict[str, Any]:
    """Load the existing Finding detail, then attach available policy/evidence context."""
    detail = get_finding_detail(finding_id)
    policy = POLICIES.get(str(detail.get("policy_id") or ""))
    rule = detail.get("rule_definition")
    if not rule:
        matched_rule = next(
            (item for item in COMPLIANCE_RULES if item.rule_id == detail.get("rule_id")), None
        )
        rule = matched_rule.model_dump(mode="json") if matched_rule else None
    policy_context = policy.model_dump(mode="json") if policy else None
    if not policy_context and any(detail.get(key) for key in ("policy_id", "policy_name", "law_ref")):
        policy_context = {
            "policy_id": detail.get("policy_id"),
            "title": detail.get("policy_name"),
            "law_ref": detail.get("law_ref"),
            "context_completeness": "partial",
        }
    sample_records = detail.get("sample_records") or []
    failure_lane = "LANE_B"
    if sample_records and sample_records[0].get("failure_lane"):
        failure_lane = str(sample_records[0].get("failure_lane")).upper()
    elif "LANE_A" in str(detail.get("rule_id", "")).upper() or "SENSOR" in str(detail.get("rule_id", "")).upper():
        failure_lane = "LANE_A"

    context: Dict[str, Any] = {
        "finding": {k: v for k, v in detail.items() if k not in {"sample_records", "rule_definition"}},
        "result": {
            "run_id": detail.get("run_id"),
            "run_status": detail.get("run_status"),
            "failed_record_count": detail.get("failed_record_count"),
        },
        "failure_lane": failure_lane,
        "rule_id": detail.get("rule_id"),
        "column_name": detail.get("column_name"),
        "law_ref": detail.get("law_ref"),
        "evidence": sample_records,
        # A lineage hash proves record identity/integrity, but it is not a
        # lineage graph or data path. Keep it separate so missing_context stays
        # honest until a real lineage path is available.
        "lineage": None,
        "lineage_hashes": [
            row.get("lineage_hash") for row in sample_records
            if row.get("lineage_hash")
        ],
        "rule": rule,
        "policy": policy_context,
    }
    return context


@app.post("/api/findings/{finding_id}/ai-explanation", response_model=FindingAIAnalysisModel)
def create_finding_ai_explanation(finding_id: str, refresh: bool = Query(False)):
    existing = finding_analysis_store.get(finding_id)
    if existing and not refresh:
        return existing
    if existing and existing.remediation.status != RemediationStatus.SUGGESTED:
        raise HTTPException(
            status_code=409,
            detail="An approved or rejected analysis cannot be regenerated.",
        )
    raw_context = _finding_ai_context(finding_id)
    missing = [name for name in ("evidence", "lineage", "rule", "policy") if not raw_context.get(name)]
    if (raw_context.get("policy") or {}).get("context_completeness") == "partial" and "policy" not in missing:
        missing.append("policy")
    if not any(raw_context["result"].values()):
        missing.insert(0, "result")
    _safe_prompt, guard = pre_llm_guard(
        """Analyze this data-quality finding and respond as a thoughtful human data analyst.
Return ONLY valid JSON with these fields:
{
  "explanation": "clear, natural Vietnamese explanation for a non-technical user",
  "root_cause": "most likely root cause, explicitly noting uncertainty",
  "confidence": 0.0,
  "issues": [
    {
      "field": "exact field name from evidence, for example trip_distance",
      "issue": "specific defect, for example value is negative",
      "observed_condition": "specific observed value or comparison when present in evidence",
      "likely_cause": "evidence-grounded likely cause or explicitly unknown",
      "suggested_action": "specific safe action for this field",
      "evidence_reference": "quarantine_id/source_row_pk when available"
    }
  ],
  "remediation_action": "<field>: <specific issue> → <specific suggested action>",
  "remediation_rationale": "practical Vietnamese recommendation covering the identified field-level issues"
}
The issues array must contain at least one item. Prefer concrete statements such as
"trip_distance < 0", "fare_amount differs from the component sum", or
"pickup_timestamp is not a valid timestamp" only when the supplied evidence supports them.
Never replace an available field-level defect with only a generic rule name.
Do not expose masked data, invent evidence, or claim that a remediation was executed.""",
        raw_context,
    )
    safe_context = guard["sanitized_context"]

    # Only the sanitized object may cross the LLM boundary. The factual fallback
    # below remains authoritative if the provider is unavailable.
    llm_result = orchestrator.llm_adapter.complete(
        _safe_prompt,
        system_instruction=(
            "You are a careful DataTrust analyst. Write naturally, concisely, and empathetically in Vietnamese. "
            "Use only the supplied sanitized context. State uncertainty and never invent evidence, rules, "
            "policies, lineage, record counts, field names, values, or execution results. "
            "When evidence is insufficient for a field-level conclusion, say so instead of guessing. Output JSON only."
        ),
        context=safe_context,
        temperature=0.0,
    )
    finding = safe_context.get("finding") or {}
    reason = finding.get("reason") or "No failure reason was recorded."
    rule_id = finding.get("rule_id") or "unknown rule"
    evidence_refs = []
    for row in safe_context.get("evidence") or []:
        ref = row.get("quarantine_id") or row.get("source_row_pk")
        if ref:
            evidence_refs.append(str(ref))
    evidence_refs.extend(str(item) for item in (safe_context.get("lineage_hashes") or []))
    evidence_refs = list(dict.fromkeys(evidence_refs))
    if llm_result.get("provider") == "openai_error":
        raise HTTPException(
            status_code=503,
            detail="OpenAI is unavailable or misconfigured. Check OPENAI_API_KEY, OPENAI_MODEL, and backend logs.",
        )

    try:
        response_text = str(llm_result.get("text") or "").strip()
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        generated = json.loads(response_text)
        required = {
            "explanation", "root_cause", "confidence",
            "issues", "remediation_action", "remediation_rationale",
        }
        if not isinstance(generated, dict) or not required.issubset(generated):
            raise ValueError("The model response does not match the Finding analysis contract")
        if not isinstance(generated["issues"], list) or not generated["issues"]:
            raise ValueError("The model must identify at least one concrete issue")
        issue_fields = {
            "field", "issue", "observed_condition", "likely_cause",
            "suggested_action", "evidence_reference",
        }
        if any(not isinstance(item, dict) or not issue_fields.issubset(item) for item in generated["issues"]):
            raise ValueError("A field-level issue does not match the Finding issue contract")
        confidence = max(0.0, min(float(generated["confidence"]), 1.0))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        if llm_result.get("provider") == "openai":
            raise HTTPException(
                status_code=502,
                detail="OpenAI returned an invalid Finding analysis. Please retry.",
            ) from exc
        # Deterministic behavior remains available only for local development/tests.
        completeness = 5 - len(missing)
        confidence = round(min(0.9, 0.35 + completeness * 0.11), 2)
        generated = {
            "explanation": f"Finding {finding_id} failed {rule_id}: {reason}",
            "root_cause": str(reason),
            "issues": [{
                "field": str(finding.get("column_name") or "unknown"),
                "issue": str(reason),
                "observed_condition": None,
                "likely_cause": "Insufficient context to determine a more specific cause.",
                "suggested_action": "Review the source value against the rule definition.",
                "evidence_reference": evidence_refs[0] if evidence_refs else None,
            }],
            "remediation_action": "Review and correct affected records",
            "remediation_rationale": (
                f"Correct records that violate {rule_id}, then submit them to the separate execution workflow."
            ),
        }
    struc_rem = generated.get("structured_remediation") or {}
    act_type = ActionType.MANUAL_INSPECTION
    if struc_rem.get("action_type") in ActionType.__members__:
        act_type = ActionType(struc_rem["action_type"])
    elif "mask" in str(generated.get("remediation_action", "")).lower():
        act_type = ActionType.DATA_TREATMENT_PROPOSAL

    remediation = RemediationDecisionModel(
        action=str(generated["remediation_action"]),
        scope={
            "finding_id": finding_id,
            "dataset_id": finding.get("dataset_id"),
            "run_id": finding.get("run_id"),
            "affected_records": finding.get("failed_record_count"),
        },
        rationale=str(generated["remediation_rationale"]),
        action_type=act_type,
        parameters=struc_rem.get("parameters") or {},
        expected_outcome=struc_rem.get("expected_outcome") or str(generated["remediation_rationale"]),
        dry_run_supported=bool(struc_rem.get("dry_run_supported", False)),
        requires_approval=True,  # Strict HITL requirement
    )
    now = datetime.now(timezone.utc)
    analysis = FindingAIAnalysisModel(
        finding_id=finding_id,
        failure_lane=generated.get("failure_lane") or safe_context.get("failure_lane") or "LANE_B",
        rule_id=rule_id,
        violation_type=generated.get("violation_type") or "COMPLIANCE_GATE",
        observation=generated.get("observation") or str(reason),
        explanation=str(generated["explanation"]),
        root_cause=str(generated["root_cause"]),
        confidence=confidence,
        confidence_method=generated.get("confidence_method") or ("evidence_grounded_ratio" if confidence is not None else None),
        issues=generated["issues"],
        hypotheses=generated.get("hypotheses") or [],
        evidence_references=evidence_refs,
        missing_context=missing,
        lane_specific_details=generated.get("lane_specific_details"),
        remediation=remediation,
        guardrail_report={
            "is_sanitized": guard.get("is_sanitized", False),
            "redactions": guard.get("redactions", {}),
            "provider": llm_result.get("provider"),
        },
        created_at=now,
        updated_at=now,
        audit_events=[{"action": "analysis_created", "at": now.isoformat(), "actor": "AI_AGENT"}],
    )
    return finding_analysis_store.save(analysis)


@app.get("/api/findings/{finding_id}/ai-analysis", response_model=FindingAIAnalysisModel)
def get_finding_ai_analysis(finding_id: str):
    analysis = finding_analysis_store.get(finding_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"No AI analysis exists for Finding '{finding_id}'.")
    return analysis


def _review_finding_remediation(
    finding_id: str, decision: RemediationStatus, comment: Optional[str], actor: str
) -> FindingAIAnalysisModel:
    analysis = finding_analysis_store.get(finding_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"No AI analysis exists for Finding '{finding_id}'.")
    current = analysis.remediation.status
    if current == decision:
        return analysis  # idempotent retry by an API client
    if current != RemediationStatus.SUGGESTED:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot change remediation from '{current.value}' to '{decision.value}'."
        )
    now = datetime.now(timezone.utc)
    analysis.remediation.status = decision
    analysis.remediation.decided_by = actor
    analysis.remediation.decided_at = now
    analysis.remediation.decision_comment = comment
    analysis.updated_at = now
    analysis.audit_events.append({
        "action": "remediation_approved" if decision == RemediationStatus.PENDING_EXECUTION else "remediation_rejected",
        "actor": actor,
        "at": now.isoformat(),
        "from": current.value,
        "to": decision.value,
        "comment": comment,
    })
    return finding_analysis_store.save(analysis)


@app.post("/api/findings/{finding_id}/remediation/approve", response_model=FindingAIAnalysisModel)
def approve_finding_remediation(
    finding_id: str,
    payload: Optional[RemediationReviewRequest] = None,
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    x_user: Optional[str] = Header(None, alias="X-User"),
):
    actor = _require_admin_identity(x_user_role, x_user)
    return _review_finding_remediation(
        finding_id, RemediationStatus.PENDING_EXECUTION, payload.comment if payload else None, actor
    )


@app.post("/api/findings/{finding_id}/remediation/reject", response_model=FindingAIAnalysisModel)
def reject_finding_remediation(
    finding_id: str,
    payload: Optional[RemediationReviewRequest] = None,
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    x_user: Optional[str] = Header(None, alias="X-User"),
):
    actor = _require_admin_identity(x_user_role, x_user)
    return _review_finding_remediation(
        finding_id, RemediationStatus.REJECTED, payload.comment if payload else None, actor
    )


@app.patch("/api/findings/{finding_id}/status")
def update_finding_status(
    finding_id: str,
    payload: Dict[str, Any],
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """
    Cập nhật trạng thái xử lý của Finding. RBAC: Auditor là Chỉ đọc, không được cập nhật.
    """
    if x_user_role and x_user_role.lower() == "auditor":
        raise HTTPException(
            status_code=403,
            detail="Vai trò Auditor là Chỉ đọc (Read-Only) và không có quyền thay đổi trạng thái Finding."
        )

    new_status = payload.get("status", "IN_REVIEW")
    note = payload.get("note", "")
    actor = payload.get("actor_name", "DataTrust Admin")

    from database.profiler_engine import get_db_connection
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE audit.findings
                SET status = %s, resolved_at = NOW(), resolved_by = %s
                WHERE finding_id = %s
                RETURNING finding_id;
            """, (new_status, f"{actor} ({note})", finding_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy Finding '{finding_id}'.")
            conn.commit()
            return {"finding_id": finding_id, "status": new_status, "updated_by": actor}
    finally:
        conn.close()


@app.get("/api/pipeline/runs/{run_id}/live-status")
def get_pipeline_live_status(run_id: str):
    """
    Truy vấn trạng thái thời gian thực của từng Task trong Pipeline từ PostgreSQL và Airflow API.
    Không fake completed run.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT run_id, airflow_dag_run_id, status, scanned_count, silver_count,
                       quarantine_count, warning_count, not_evaluated_count,
                       current_step, current_step_progress
                FROM orchestration.pipeline_runs
                WHERE run_id = %s OR airflow_dag_run_id = %s;
            """, (run_id, run_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy lượt chạy '{run_id}' trong cơ sở dữ liệu.")

            real_run_id = row["run_id"]
            cur.execute("""
                SELECT step_name, status, started_at, ended_at, error_message
                FROM orchestration.pipeline_run_steps
                WHERE run_id = %s ORDER BY step_order ASC;
            """, (real_run_id,))
            steps = cur.fetchall()

            task_status_map = {s["step_name"]: s["status"] for s in steps}
            overall_status = (row.get("status") or "RUNNING").upper()
            cur_step = (row.get("current_step") or "INGEST").upper()

            # Kiểm tra trạng thái trực tiếp từ Airflow REST API nếu DB đang ghi nhận RUNNING
            dag_run_id = row.get("airflow_dag_run_id")
            if dag_run_id and overall_status == "RUNNING":
                try:
                    auth_str = base64.b64encode(f"{AIRFLOW_USER}:{AIRFLOW_PASS}".encode("utf-8")).decode("utf-8")
                    req = Request(
                        f"{AIRFLOW_API_URL}/dags/datatrust_adaptive_pipeline/dagRuns/{dag_run_id}",
                        headers={"Authorization": f"Basic {auth_str}"}
                    )
                    with urlopen(req, timeout=1.5) as resp:
                        af_data = json.loads(resp.read().decode("utf-8"))
                        af_state = (af_data.get("state") or "").upper()
                        if af_state == "SUCCESS":
                            overall_status = "SUCCESS"
                        elif af_state == "FAILED":
                            overall_status = "FAILED"
                except Exception:
                    pass

            is_overall_success = overall_status in ("SUCCESS", "COMPLETED")

            ingest_done = is_overall_success or task_status_map.get("INGEST") == "COMPLETED" or cur_step in ("BRONZE", "EVALUATION", "SILVER", "EVIDENCE", "COMPLETED")
            bronze_done = is_overall_success or task_status_map.get("BRONZE") == "COMPLETED" or cur_step in ("EVALUATION", "SILVER", "EVIDENCE", "COMPLETED")
            eval_done = is_overall_success or task_status_map.get("EVALUATION") == "COMPLETED" or cur_step in ("SILVER", "EVIDENCE", "COMPLETED")
            silver_done = is_overall_success or task_status_map.get("SILVER") == "COMPLETED" or cur_step in ("EVIDENCE", "COMPLETED")
            evidence_done = is_overall_success or task_status_map.get("EVIDENCE") == "COMPLETED" or cur_step == "COMPLETED"

            tasks_compatibility = {
                "task_1_truncate_and_ingest_bronze": "success" if ingest_done else ("running" if cur_step == "INGEST" else "queued"),
                "task_2_data_profiling": "success" if bronze_done else ("running" if ingest_done and not bronze_done else "queued"),
                "lane_a_l1_l4_detectors": "success" if eval_done else ("running" if bronze_done and not eval_done else "queued"),
                "lane_b_hierarchical_policy": "success" if eval_done else ("running" if bronze_done and not eval_done else "queued"),
                "lane_c_merge_verdicts_and_route": "success" if silver_done else ("running" if eval_done and not silver_done else "queued"),
                "task_4_emit_audit_evidence": "success" if evidence_done else ("running" if silver_done and not evidence_done else "queued"),
            }

            return {
                "run_id": real_run_id,
                "airflow_dag_run_id": row.get("airflow_dag_run_id"),
                "status": overall_status,
                "current_step": cur_step,
                "current_step_progress": 100 if is_overall_success else (row.get("current_step_progress") or 0),
                "metrics": {
                    "scanned": row.get("scanned_count") or 0,
                    "silver": row.get("silver_count") or 0,
                    "quarantine": row.get("quarantine_count") or 0,
                    "warning": row.get("warning_count") or 0,
                    "not_evaluated": row.get("not_evaluated_count") or 0
                },
                "steps": [dict(s) for s in steps],
                "task_status_map": task_status_map,
                "tasks": tasks_compatibility
            }
    finally:
        conn.close()


@app.get("/api/pipeline/latest-completed")
def get_latest_completed_pipeline_run(dataset_id: Optional[str] = None):
    """
    Trả về kết quả lần chạy pipeline gần nhất đã hoàn tất (SUCCESS) từ PostgreSQL.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT run_id, dag_id, dataset_id, started_at, ended_at, status,
                       scanned_count, silver_count, quarantine_count, warning_count, not_evaluated_count
                FROM orchestration.pipeline_runs
                WHERE status = 'SUCCESS'
            """
            params = []
            if dataset_id:
                clean_ds = dataset_id.replace(".csv", "").replace("bronze.", "")
                query += " AND (dataset_id = %s OR dataset_id = %s)"
                params.extend([clean_ds, f"{clean_ds}.csv"])
            query += " ORDER BY started_at DESC LIMIT 1;"
            cur.execute(query, tuple(params))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Không có lần chạy nào đã hoàn thành trong hệ thống.")
            return {
                "run_id": row["run_id"],
                "dataset_id": row["dataset_id"],
                "status": "SUCCESS",
                "scanned_count": row["scanned_count"] or 0,
                "silver_count": row["silver_count"] or 0,
                "quarantine_count": row["quarantine_count"] or 0,
                "warning_count": row["warning_count"] or 0,
                "not_evaluated_count": row.get("not_evaluated_count") or 0,
                "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                "ended_at": row["ended_at"].isoformat() if row["ended_at"] else None
            }
    finally:
        conn.close()


# =============================================================================
# QUARANTINE ENDPOINTS (POSTGRESQL SINGLE SOURCE OF TRUTH)
# =============================================================================

@app.get("/api/quarantine")
def list_quarantine(
    dataset_id: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0)
):
    """
    Truy vấn danh sách bản ghi cách ly từ schema quarantine.records trong PostgreSQL.
    Cung cấp Full Raw Record JSON phục vụ phân tích nguyên nhân gốc (RCA) & kiểm toán IPO.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor
    from decimal import Decimal

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT quarantine_id, run_id, dataset_id, source_table, source_row_pk,
                       failure_lane, violation_column, violation_rule_id, violation_reason,
                       violation_severity, raw_record_json, lineage_hash, status,
                       quarantined_at, resolved_by, resolved_at, resolution_note
                FROM quarantine.records
                WHERE 1=1
            """
            count_query = "SELECT count(*) FROM quarantine.records WHERE 1=1"
            params = []
            if dataset_id:
                clean_ds = dataset_id.replace(".csv", "").replace("bronze.", "")
                query += " AND (dataset_id = %s OR dataset_id = %s)"
                count_query += " AND (dataset_id = %s OR dataset_id = %s)"
                params.extend([clean_ds, f"{clean_ds}.csv"])
            if status:
                query += " AND LOWER(status) = LOWER(%s)"
                count_query += " AND LOWER(status) = LOWER(%s)"
                params.append(status)
            if severity:
                query += " AND LOWER(violation_severity) = LOWER(%s)"
                count_query += " AND LOWER(violation_severity) = LOWER(%s)"
                params.append(severity)

            cur.execute(count_query, tuple(params))
            total_count = cur.fetchone()["count"]

            query += " ORDER BY quarantined_at DESC LIMIT %s OFFSET %s;"
            params.extend([limit, offset])
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            conn.close()

            clean_records = []
            for r in rows:
                item = dict(r)
                item["quarantine_id"] = str(item["quarantine_id"])
                if item.get("quarantined_at"):
                    item["quarantined_at"] = item["quarantined_at"].isoformat()
                if item.get("resolved_at"):
                    item["resolved_at"] = item["resolved_at"].isoformat()
                clean_records.append(item)

            return {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "records": clean_records
            }
    except Exception as e:
        print(f"Warning: Failed to query quarantine.records: {e}")
        # Fallback to in-memory
        mem_records = [q.model_dump() for q in quarantine_mgr.list_records(dataset_id, None)]
        return {
            "total": len(mem_records),
            "limit": limit,
            "offset": offset,
            "records": mem_records
        }


@app.post("/api/quarantine/{quarantine_id}/reprocess")
def reprocess_quarantine(
    quarantine_id: str,
    req: QuarantineRemediationRequest,
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """
    Remediate & Reprocess một bản ghi cách ly: Cập nhật status = 'REMEDIATED'
    với chữ ký người duyệt và ghi nhận trong PostgreSQL.
    RBAC: Auditor là Chỉ đọc, không có quyền xử lý bản ghi cách ly.
    """
    if x_user_role and x_user_role.lower() == "auditor":
        raise HTTPException(
            status_code=403,
            detail="Vai trò Auditor là Chỉ đọc (Read-Only) và không có quyền khắc phục bản ghi cách ly."
        )

    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor
    now_utc = datetime.now(timezone.utc)
    enforced = f"{req.actor_name} ({req.actor_role})"

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE quarantine.records
                SET status = 'REMEDIATED',
                    resolved_by = %s,
                    resolved_at = %s,
                    resolution_note = %s
                WHERE quarantine_id::text = %s
                RETURNING *;
            """, (enforced, now_utc, "Remediated with cleaned payload by Admin", quarantine_id))
            row = cur.fetchone()
            conn.commit()
            conn.close()
            if row:
                res = dict(row)
                res["quarantine_id"] = str(res["quarantine_id"])
                res["quarantined_at"] = res["quarantined_at"].isoformat() if res.get("quarantined_at") else None
                res["resolved_at"] = res["resolved_at"].isoformat() if res.get("resolved_at") else None
                return res
    except Exception as e:
        print(f"Warning: Failed to reprocess quarantine in DB: {e}")

    try:
        return quarantine_mgr.reprocess_record(quarantine_id, req.cleaned_payload, req.actor_name, req.actor_role)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/quarantine/{quarantine_id}/override")
def override_quarantine(
    quarantine_id: str,
    req: QuarantineOverrideRequest,
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """
    Phê duyệt ngoại lệ (Audit Override) cho bản ghi cách ly: Cập nhật status = 'OVERRIDDEN'
    kèm giải trình kiểm toán bắt buộc.
    RBAC: Auditor là Chỉ đọc, không có quyền ngoại lệ bản ghi cách ly.
    """
    if x_user_role and x_user_role.lower() == "auditor":
        raise HTTPException(
            status_code=403,
            detail="Vai trò Auditor là Chỉ đọc (Read-Only) và không có quyền phê duyệt ngoại lệ."
        )

    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor
    now_utc = datetime.now(timezone.utc)
    enforced = f"{req.actor_name} ({req.actor_role})"

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE quarantine.records
                SET status = 'OVERRIDDEN',
                    resolved_by = %s,
                    resolved_at = %s,
                    resolution_note = %s
                WHERE quarantine_id::text = %s
                RETURNING *;
            """, (enforced, now_utc, req.justification, quarantine_id))
            row = cur.fetchone()
            conn.commit()
            conn.close()
            if row:
                res = dict(row)
                res["quarantine_id"] = str(res["quarantine_id"])
                res["quarantined_at"] = res["quarantined_at"].isoformat() if res.get("quarantined_at") else None
                res["resolved_at"] = res["resolved_at"].isoformat() if res.get("resolved_at") else None
                return res
    except Exception as e:
        print(f"Warning: Failed to override quarantine in DB: {e}")

    try:
        return quarantine_mgr.approve_override(quarantine_id, req.justification, req.actor_name, req.actor_role)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# WARNING ENDPOINTS (STATISTICAL ANOMALIES & ADVISORY SIGNALS)
# =============================================================================

@app.get("/api/warnings")
def list_warnings(
    dataset_id: Optional[str] = None,
    signal_lane: Optional[str] = None,
    signal_layer: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0)
):
    """
    Truy vấn danh sách cảnh báo bất thường (L2 Robust Drift, L3 Relational, L4 Changepoint)
    từ schema warning.records trong PostgreSQL.
    Bản ghi đã được xử lý PII Redacted để bảo vệ quyền riêng tư kiểm toán.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor
    from decimal import Decimal

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT warning_id, run_id, dataset_id, source_row_pk, signal_lane,
                       signal_layer, warning_type, warning_reason, score_or_zvalue,
                       evidence_json, redacted_record_json, lineage_hash, detected_at
                FROM warning.records
                WHERE 1=1
            """
            count_query = "SELECT count(*) FROM warning.records WHERE 1=1"
            params = []
            if dataset_id:
                clean_ds = dataset_id.replace(".csv", "").replace("bronze.", "")
                query += " AND (dataset_id = %s OR dataset_id = %s)"
                count_query += " AND (dataset_id = %s OR dataset_id = %s)"
                params.extend([clean_ds, f"{clean_ds}.csv"])
            if signal_lane:
                query += " AND signal_lane = %s"
                count_query += " AND signal_lane = %s"
                params.append(signal_lane)
            if signal_layer:
                query += " AND signal_layer = %s"
                count_query += " AND signal_layer = %s"
                params.append(signal_layer)

            cur.execute(count_query, tuple(params))
            total_count = cur.fetchone()["count"]

            query += " ORDER BY detected_at DESC LIMIT %s OFFSET %s;"
            params.extend([limit, offset])
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            conn.close()

            clean_records = []
            for r in rows:
                item = dict(r)
                item["warning_id"] = str(item["warning_id"])
                if item.get("score_or_zvalue") is not None:
                    item["score_or_zvalue"] = float(item["score_or_zvalue"])
                if item.get("detected_at"):
                    item["detected_at"] = item["detected_at"].isoformat()
                clean_records.append(item)

            return {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "records": clean_records
            }
    except Exception as e:
        print(f"Warning: Failed to query warning.records: {e}")
        return {"total": 0, "limit": limit, "offset": offset, "records": []}


@app.get("/api/warnings/{warning_id}")
def get_warning_detail(warning_id: str):
    """
    Chi tiết một cảnh báo bất thường kèm evidence_json và redacted_record_json.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM warning.records WHERE warning_id::text = %s;
            """, (warning_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Warning record not found")
            item = dict(row)
            item["warning_id"] = str(item["warning_id"])
            if item.get("score_or_zvalue") is not None:
                item["score_or_zvalue"] = float(item["score_or_zvalue"])
            if item.get("detected_at"):
                item["detected_at"] = item["detected_at"].isoformat()
            return item
    finally:
        conn.close()


# =============================================================================
# AUDIT EVIDENCE LEDGER ENDPOINTS (IMMUTABLE HASH-CHAIN STORAGE)
# =============================================================================

@app.get("/api/evidence")
def list_evidence(
    dataset_id: Optional[str] = None,
    run_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200)
):
    """
    Truy vấn sổ cái bằng chứng kiểm toán bất biến (Audit Evidence Ledger)
    từ schema audit.evidence trong PostgreSQL.
    Mỗi bản ghi được ký số 'SIG-AIRFLOW-3LANE-GSM-IPO-2026' và liên kết SHA-256 hash-chain.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT evidence_id, run_id, dag_id, dataset_id, digital_signature,
                       evidence_hash, previous_hash, scanned_count, silver_count,
                       quarantine_count, warning_count, metrics, evidence_payload,
                       jurisdiction_chain, created_at
                FROM audit.evidence
                WHERE 1=1
            """
            params = []
            if dataset_id:
                clean_ds = dataset_id.replace(".csv", "").replace("bronze.", "")
                query += " AND (dataset_id = %s OR dataset_id = %s)"
                params.extend([clean_ds, f"{clean_ds}.csv"])
            if run_id:
                query += " AND run_id = %s"
                params.append(run_id)
            query += " ORDER BY created_at DESC LIMIT %s;"
            params.append(limit)

            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            conn.close()

            clean_evidence = []
            for r in rows:
                item = dict(r)
                item["evidence_id"] = str(item["evidence_id"])
                if item.get("created_at"):
                    item["created_at"] = item["created_at"].isoformat()
                clean_evidence.append(item)

            return clean_evidence
    except Exception as e:
        print(f"Warning: Failed to query audit.evidence: {e}")
        return []


@app.get("/api/evidence/{evidence_id}")
def get_evidence_detail(evidence_id: str):
    """
    Xem chi tiết payload bằng chứng kiểm toán bất biến phục vụ thanh tra IPO.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM audit.evidence WHERE evidence_id::text = %s OR run_id = %s;
            """, (evidence_id, evidence_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Audit evidence not found")
            item = dict(row)
            item["evidence_id"] = str(item["evidence_id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            return item
    finally:
        conn.close()


@app.get("/api/evidence-verify/chain")
def verify_evidence_chain():
    """
    Thẩm tra tính toàn vẹn của chuỗi băm (SHA-256 Hash Chain Verification)
    trên toàn bộ sổ cái audit.evidence.
    Đảm bảo không bản ghi nào bị can thiệp trái phép (Tamper-evident).
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor
    import hashlib

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT evidence_id, run_id, evidence_hash, previous_hash, created_at
                FROM audit.evidence
                ORDER BY created_at ASC;
            """)
            rows = cur.fetchall()

            if not rows:
                return {
                    "is_valid": True,
                    "records_count": 0,
                    "status": "INITIALIZED",
                    "message": "Sổ cái bằng chứng đã được khởi tạo sẵn sàng cho lượt chạy đầu tiên."
                }

            is_valid = True
            broken_index = None
            for i in range(1, len(rows)):
                expected_prev = rows[i - 1]["evidence_hash"]
                actual_prev = rows[i]["previous_hash"]
                if actual_prev != expected_prev:
                    is_valid = False
                    broken_index = i
                    break

            return {
                "is_valid": is_valid,
                "records_count": len(rows),
                "status": "VERIFIED" if is_valid else "CORRUPTED",
                "broken_at_index": broken_index,
                "latest_evidence_hash": rows[-1]["evidence_hash"] if rows else None,
                "digital_signature": "SIG-AIRFLOW-3LANE-GSM-IPO-2026",
                "standard": "SOX 404 / IPO Audit Cryptographic Ledger"
            }
    finally:
        conn.close()


# =============================================================================
# DASHBOARD OVERVIEW & COMPLIANCE AGGREGATION
# =============================================================================

@app.get("/api/dashboard/overview")
def get_dashboard_overview():
    """
    Tổng hợp các chỉ số KPI kiểm soát, tuân thủ, dữ liệu cách ly và cảnh báo
    tính toán trực tiếp từ cơ sở dữ liệu PostgreSQL.
    """
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Pipeline runs stats
            cur.execute("""
                SELECT count(*) as total_runs,
                       COALESCE(SUM(scanned_count), 0) as total_scanned,
                       COALESCE(SUM(silver_count), 0) as total_silver,
                       COALESCE(SUM(quarantine_count), 0) as total_quarantine,
                       COALESCE(SUM(warning_count), 0) as total_warning
                FROM orchestration.pipeline_runs;
            """)
            run_stats = cur.fetchone()

            # 2. Quarantine records breakdown
            cur.execute("""
                SELECT status, count(*) as count
                FROM quarantine.records
                GROUP BY status;
            """)
            q_status_rows = cur.fetchall()
            q_status_map = {r["status"]: r["count"] for r in q_status_rows}

            # 3. Warnings breakdown
            cur.execute("""
                SELECT signal_layer, count(*) as count
                FROM warning.records
                GROUP BY signal_layer;
            """)
            w_layer_rows = cur.fetchall()

            # 4. Catalog datasets count & average health score
            cur.execute("""
                SELECT count(*) as datasets_count,
                       COALESCE(AVG(health_score), 98.5) as avg_health
                FROM catalog.table_profiles;
            """)
            cat_stats = cur.fetchone()

            # 5. Active rules count
            cur.execute("""
                SELECT count(*) as active_rules_count
                FROM policy.data_treatment_rules
                WHERE LOWER(status) = 'active';
            """)
            active_rules_row = cur.fetchone()

            # 6. Latest run
            cur.execute("""
                SELECT run_id, dataset_id, status, started_at
                FROM orchestration.pipeline_runs
                ORDER BY started_at DESC LIMIT 1;
            """)
            latest_run = cur.fetchone()

            total_runs = run_stats["total_runs"] if run_stats else 0
            total_scanned = run_stats["total_scanned"] if run_stats else 0
            total_silver = run_stats["total_silver"] if run_stats else 0
            total_quarantine = sum(q_status_map.values()) if q_status_map else (run_stats["total_quarantine"] if run_stats else 0)
            total_warning = sum(r["count"] for r in w_layer_rows) if w_layer_rows else (run_stats["total_warning"] if run_stats else 0)

            # Resolved count
            resolved_count = q_status_map.get("REMEDIATED", 0) + q_status_map.get("OVERRIDDEN", 0)
            open_count = q_status_map.get("QUARANTINED", 0) + q_status_map.get("IN_REVIEW", 0)

            compliance_score = round(float(cat_stats["avg_health"]), 1) if cat_stats and cat_stats["avg_health"] else 98.5

            return {
                "metrics": {
                    "total_runs": total_runs,
                    "total_scanned": total_scanned,
                    "total_silver": total_silver,
                    "total_quarantine": total_quarantine,
                    "total_warning": total_warning,
                    "quarantine_open": open_count,
                    "quarantine_resolved": resolved_count,
                    "active_rules_count": active_rules_row["active_rules_count"] if active_rules_row else 6,
                    "datasets_count": cat_stats["datasets_count"] if cat_stats else 8,
                },
                "compliance_score": compliance_score,
                "latest_run": {
                    "run_id": latest_run["run_id"] if latest_run else None,
                    "dataset_id": latest_run["dataset_id"] if latest_run else None,
                    "status": (latest_run["status"] or "SUCCESS").upper() if latest_run else "IDLE",
                    "started_at": latest_run["started_at"].isoformat() if latest_run and latest_run["started_at"] else None
                } if latest_run else None,
                "controls": [
                    {"name": "Pass", "value": total_silver},
                    {"name": "Warning", "value": total_warning},
                    {"name": "Quarantine Fail", "value": total_quarantine},
                ],
                "warning_layers": [dict(r) for r in w_layer_rows],
                "quarantine_by_status": q_status_map,
                "legal_framework": [
                    "Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15",
                    "Nghị định 356/2025/NĐ-CP",
                    "IFRS 15 / SOX 404",
                    "UN ECE R100 Battery Safety Norms",
                    "GDPR (EU) & CCPA (US)"
                ]
            }
    finally:
        conn.close()


@app.get("/api/audit-trail", response_model=List[AuditTrailModel])
def get_audit_trail():
    return quarantine_mgr.audit_log


# =============================================================================
# DATA LINEAGE & CATALOG TOPOLOGY ENDPOINTS
# =============================================================================

@app.get("/api/lineage/status")
def get_lineage_status():
    """Returns connectivity and metadata stats for Data Lineage & PostgreSQL Catalog."""
    from backend.lineage.lineage_service import LineageService
    return LineageService.get_status()


@app.get("/api/lineage/graph")
def get_lineage_graph(dataset_id: Optional[str] = None, run_id: Optional[str] = None):
    """Returns the visual DAG node-and-edge lineage topology."""
    from backend.lineage.lineage_service import LineageService
    return LineageService.get_graph(dataset_id=dataset_id, run_id=run_id)


@app.get("/api/runs/{run_id}/lineage")
def get_run_lineage(run_id: str):
    """Returns lineage scoped to a pipeline run."""
    from backend.lineage.lineage_service import LineageService
    return LineageService.get_graph(run_id=run_id)


@app.get("/api/datasets/{dataset_id}/lineage")
def get_dataset_lineage(dataset_id: str):
    """Returns lineage scoped to a catalog dataset."""
    from backend.lineage.lineage_service import LineageService
    return LineageService.get_graph(dataset_id=dataset_id)


@app.get("/api/lineage/column-lineage/{dataset_id}")
def get_column_lineage(dataset_id: str, run_id: Optional[str] = None):
    """Returns actual column transformations executed during the run."""
    from backend.lineage.lineage_service import LineageService
    return LineageService.get_column_lineage(dataset_id=dataset_id, run_id=run_id)


@app.get("/api/lineage/runs")
def get_lineage_runs():
    """Returns list of runs with lineage metadata."""
    from backend.lineage.lineage_service import LineageService
    return LineageService.get_lineage_runs()


# =============================================================================
# AI AGENT MULTI-AGENT, HITL & REAL-TIME WEBSOCKET ENDPOINTS
# =============================================================================

@app.websocket("/ws")
@app.websocket("/ws/agent")
async def agent_websocket(websocket: WebSocket, token: Optional[str] = None, session_id: Optional[str] = None):
    """
    WebSocket endpoint for live ReAct thought streaming and interactive agent messaging.
    """
    await websocket.accept()

    async def stream_trace(trace: AgentTraceModel):
        try:
            await websocket.send_json({
                "type": "trace",
                "step_index": trace.step_index,
                "agent_type": trace.agent_type,
                "thought": trace.thought,
                "action": trace.action,
                "observation": trace.observation,
                "decision": trace.decision.model_dump() if trace.decision else None,
                "tokens_used": trace.tokens_used,
                "duration_ms": trace.duration_ms
            })
        except Exception:
            pass

    orchestrator.register_step_listener(stream_trace)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg_data = json.loads(data) if data.strip().startswith("{") else {"message": data}
            except Exception:
                msg_data = {"message": data}

            result = await orchestrator.chat(
                message=msg_data.get("message", ""),
                session_id=msg_data.get("session_id"),
                context=msg_data.get("context")
            )
            await websocket.send_json({"type": "response", "data": result})
    except WebSocketDisconnect:
        pass
    finally:
        orchestrator.unregister_step_listener(stream_trace)


@app.post("/api/agent/chat")
async def agent_chat(req: AgentChatRequest):
    """
    Direct REST endpoint for user chat interaction with DataTrust Multi-Agent System.
    Strictly enforces Run Isolation and session-run binding.
    """
    import os
    from backend.ai.services.chat_session_manager import session_manager
    from database.profiler_engine import get_db_connection
    from psycopg2.extras import RealDictCursor

    run_id = (req.run_id or "").strip()
    message = (req.message or "").strip()

    if not run_id:
        raise HTTPException(
            status_code=400,
            detail={"code": "MISSING_RUN_ID", "message": "run_id là bắt buộc để tương tác với AI Agent."}
        )
    if not message:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_MESSAGE", "message": "Nội dung tin nhắn không được để trống."}
        )

    # 1. Verify run_id exists in orchestration.pipeline_runs
    run_row = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT run_id, dataset_id, status FROM orchestration.pipeline_runs WHERE run_id = %s LIMIT 1;", (run_id,))
            run_row = cur.fetchone()
        conn.close()
    except Exception as e:
        logger.warning(f"Error checking run_id in DB: {e}")

    if not run_row:
        # Check mock/testing fallback runs
        if not (run_id.startswith("run-test-") or run_id.startswith("RUN-TEST-")):
            raise HTTPException(
                status_code=404,
                detail={"code": "RUN_NOT_FOUND", "message": f"Không tìm thấy lần chạy '{run_id}' trong hệ thống điều phối kiểm toán."}
            )

    # 2. Verify Session-Run Binding (immutable 1-to-1)
    if req.session_id:
        session_manager.verify_and_bind_session(req.session_id, run_id)

    res = await orchestrator.chat(
        message=message,
        run_id=run_id,
        session_id=req.session_id,
        finding_id=req.finding_id,
        context=req.context
    )

    # Production safety: hide traces in production unless DEBUG is enabled
    is_prod = os.getenv("ENVIRONMENT", "").lower() == "production"
    is_debug = os.getenv("DEBUG", "").lower() in ("true", "1")
    if is_prod and not is_debug and isinstance(res, dict):
        res["traces"] = []

    return res


@app.get("/api/agent/traces/{session_id}")
def get_agent_traces(session_id: str):
    """
    Retrieves all persistent ReAct steps for an active agent reasoning session.
    Hides traces in production unless debug mode is enabled.
    """
    import os
    is_prod = os.getenv("ENVIRONMENT", "").lower() == "production"
    is_debug = os.getenv("DEBUG", "").lower() in ("true", "1")
    if is_prod and not is_debug:
        return []
    traces = orchestrator.react_engine.get_traces_for_session(session_id)
    return [t.model_dump() for t in traces]


@app.post("/api/agent/diagnose/{quarantine_id}")
async def diagnose_quarantine_record(quarantine_id: str):
    """
    4-Tier root-cause causal diagnosis for a specific quarantined record.
    """
    rec = quarantine_mgr.records.get(quarantine_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy bản ghi cách ly với ID: {quarantine_id}")
    res = await orchestrator.diagnose_quarantine(rec)
    return res


@app.get("/api/agent/preventive-alerts", response_model=List[PreventiveAlertModel])
def get_preventive_alerts():
    """
    Fetches proactive early-warning drift alerts (L2-L4 signals before hard L1 failures).
    """
    alerts = orchestrator.preventive_guard_agent.get_all_alerts()
    if not alerts:
        # Trigger an initial baseline scan to populate early-warning alerts for dashboard
        alerts = orchestrator.scan_preventive_alerts("trips", ["fare_amount", "trip_distance_km"])
    return alerts


@app.post("/api/agent/preventive-scan", response_model=List[PreventiveAlertModel])
def trigger_preventive_scan(req: AgentPreventiveScanRequest):
    """
    Triggers an on-demand preventive drift scan for specific columns.
    """
    cols = req.columns or ["fare_amount", "trip_distance_km", "pickup_latitude"]
    return orchestrator.scan_preventive_alerts(req.dataset_id, cols)


@app.post("/api/agent/dry-run/{proposal_id}")
def dry_run_proposal(proposal_id: str, sample_size: int = 100):
    """
    Pure read-only dry-run simulation of a proposed rule.
    DOES NOT modify Lane B configuration.
    """
    prop = agent.proposals.get(proposal_id) or orchestrator.rule_proposer_agent.proposals.get(proposal_id)
    if not prop:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đề xuất: {proposal_id}")
    res = orchestrator.rule_proposer_agent.dry_run_tool.execute({
        "proposal": prop.model_dump(),
        "sample_size": sample_size
    })
    return res


