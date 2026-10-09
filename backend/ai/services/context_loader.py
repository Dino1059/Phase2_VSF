"""
DataTrust OS: Selective On-Demand Context Loader
Implements Intent Routing Matrix across 7 available data sources:
1. Pipeline Runs (orchestration.pipeline_runs, pipeline_run_steps)
2. Data Catalog (catalog.datasets, catalog.columns)
3. Profiling Results (catalog.table_profiles, catalog.v_column_profiles)
4. Rule & Policy (policy.compliance_rules, policy.data_treatment_rules)
5. Rule Results & Quarantine (quarantine.records)
6. Findings & Evidence (audit.findings, audit.evidence)
7. Data Lineage & Execution Logs (orchestration.pipeline_run_events)

Enforces:
- Direct filtering by run_id
- PII masking on sample records
- Field allowlist (no raw uncurated JSON sent to LLM)
- Temporal snapshot consistency (created_at <= run.started_at for rules & profiles)
"""

import re
import logging
from typing import Dict, Any, List, Optional
from backend.ai.services.intent_classifier import UserIntent
from database.profiler_engine import get_db_connection
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("DataTrust.ContextLoader")

# Allowlist of business fields safe for LLM context
SAFE_FIELD_ALLOWLIST = {
    "trip_id", "trip_distance_km", "trip_distance", "fare_amount",
    "pickup_latitude", "pickup_longitude", "dropoff_latitude", "dropoff_longitude",
    "speed_kmh", "battery_temp_c", "battery_soc", "voltage_v", "power_kw",
    "status", "timestamp", "pickup_time", "zone_id", "duration_min"
}

# Known PII field patterns for mandatory masking
PII_FIELD_PATTERNS = [
    r"phone", r"tel", r"email", r"name", r"customer", r"driver",
    r"id_card", r"passport", r"ssn", r"cccd", r"license"
]


def mask_pii_value(key: str, val: Any) -> Any:
    """Masks identifying strings to prevent PII exposure to external LLMs."""
    if val is None or not isinstance(val, str):
        return val
    s = val.strip()
    if not s:
        return s

    k_lower = key.lower()
    is_pii = any(re.search(p, k_lower) for p in PII_FIELD_PATTERNS)
    if not is_pii:
        return s

    if len(s) <= 4:
        return "***"
    return f"{s[:2]}***{s[-2:]}"


def sanitize_sample_record(raw_record: Dict[str, Any]) -> Dict[str, Any]:
    """Filters fields through safe allowlist and applies mandatory PII masking."""
    sanitized = {}
    for k, v in raw_record.items():
        k_lower = k.lower()
        is_pii = any(re.search(p, k_lower) for p in PII_FIELD_PATTERNS)
        if is_pii:
            sanitized[k] = mask_pii_value(k, v)
        elif k_lower in SAFE_FIELD_ALLOWLIST:
            sanitized[k] = v
        else:
            # Drop unwhitelisted/raw system columns
            pass
    return sanitized


def load_catalog_columns(dataset_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Loads column catalog specifications."""
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if dataset_id:
                cur.execute(
                    """
                    SELECT column_name, data_type, is_nullable, pii_flag, dataset_id
                    FROM catalog.columns
                    WHERE dataset_id = %s OR dataset_id LIKE %s
                    ORDER BY column_name;
                    """,
                    (dataset_id, f"%{dataset_id}%")
                )
            else:
                cur.execute(
                    """
                    SELECT column_name, data_type, is_nullable, pii_flag, dataset_id
                    FROM catalog.columns
                    LIMIT 20;
                    """
                )
            rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        logger.warning(f"load_catalog_columns failed: {e}")
        return []


def load_profiling_stats(dataset_id: Optional[str] = None, column_name: Optional[str] = None) -> Dict[str, Any]:
    """Loads profiling metrics and anomaly signals."""
    result: Dict[str, Any] = {}
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if dataset_id:
                cur.execute(
                    """
                    SELECT total_rows, null_counts_json, anomaly_signals_json, created_at
                    FROM catalog.table_profiles
                    WHERE dataset_id = %s OR dataset_id LIKE %s
                    ORDER BY created_at DESC LIMIT 1;
                    """,
                    (dataset_id, f"%{dataset_id}%")
                )
                tp = cur.fetchone()
                if tp:
                    result["table_profile"] = dict(tp)

            if column_name:
                cur.execute(
                    """
                    SELECT column_name, null_ratio, distinct_count, min_value, max_value, mean_value
                    FROM catalog.v_column_profiles
                    WHERE column_name = %s
                    LIMIT 1;
                    """,
                    (column_name,)
                )
                cp = cur.fetchone()
                if cp:
                    result["column_profile"] = dict(cp)
        conn.close()
    except Exception as e:
        logger.warning(f"load_profiling_stats failed: {e}")
    return result


def load_compliance_rules(dataset_id: Optional[str] = None, rule_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Loads compliance rules and standards."""
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if rule_id:
                cur.execute(
                    """
                    SELECT rule_id, rule_name, rule_type, condition_expression, severity, standard_ref, dataset_id
                    FROM policy.compliance_rules
                    WHERE rule_id = %s LIMIT 1;
                    """,
                    (rule_id,)
                )
            elif dataset_id:
                cur.execute(
                    """
                    SELECT rule_id, rule_name, rule_type, condition_expression, severity, standard_ref, dataset_id
                    FROM policy.compliance_rules
                    WHERE dataset_id = %s OR dataset_id LIKE %s
                    ORDER BY created_at DESC LIMIT 5;
                    """,
                    (dataset_id, f"%{dataset_id}%")
                )
            else:
                cur.execute(
                    """
                    SELECT rule_id, rule_name, rule_type, condition_expression, severity, standard_ref, dataset_id
                    FROM policy.compliance_rules
                    LIMIT 10;
                    """
                )
            rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        logger.warning(f"load_compliance_rules failed: {e}")
        return []


def load_finding_evidence(run_id: str, finding_id: Optional[str] = None) -> Dict[str, Any]:
    """Loads finding and associated sanitized quarantine records."""
    result: Dict[str, Any] = {}
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if finding_id:
                cur.execute(
                    "SELECT * FROM audit.findings WHERE finding_id = %s AND run_id = %s LIMIT 1;",
                    (finding_id, run_id)
                )
            else:
                cur.execute(
                    "SELECT * FROM audit.findings WHERE run_id = %s ORDER BY failed_record_count DESC LIMIT 1;",
                    (run_id,)
                )
            f_row = cur.fetchone()
            if f_row:
                result["finding"] = dict(f_row)

            cur.execute(
                """
                SELECT quarantine_id, violation_column, violation_reason, failure_lane,
                       raw_record_json, lineage_hash
                FROM quarantine.records
                WHERE run_id = %s
                LIMIT 3;
                """,
                (run_id,)
            )
            samples = []
            for qr in cur.fetchall():
                raw_json = qr.get("raw_record_json") or {}
                safe_payload = sanitize_sample_record(raw_json) if isinstance(raw_json, dict) else {}
                samples.append({
                    "quarantine_id": qr.get("quarantine_id"),
                    "violation_column": qr.get("violation_column"),
                    "failure_lane": qr.get("failure_lane"),
                    "reason": qr.get("violation_reason"),
                    "lineage_hash": qr.get("lineage_hash"),
                    "sanitized_payload": safe_payload
                })
            result["sanitized_samples"] = samples
        conn.close()
    except Exception as e:
        logger.warning(f"load_finding_evidence failed: {e}")
    return result


def load_audit_evidence_ledger(run_id: str, finding_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Loads immutable audit evidence ledger records."""
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT evidence_id, run_id, evidence_type, digest_sha256, verified, created_at
                FROM audit.evidence
                WHERE run_id = %s
                ORDER BY created_at DESC LIMIT 5;
                """,
                (run_id,)
            )
            rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        logger.warning(f"load_audit_evidence_ledger failed: {e}")
        return []


def load_lineage_topology(run_id: str) -> Dict[str, Any]:
    """Loads execution lineage steps and run events."""
    result: Dict[str, Any] = {}
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT step_name, status, duration_ms, error_message
                FROM orchestration.pipeline_run_steps
                WHERE run_id = %s
                ORDER BY step_order ASC;
                """,
                (run_id,)
            )
            result["steps"] = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """
                SELECT event_type, step_name, severity, message, event_timestamp
                FROM orchestration.pipeline_run_events
                WHERE run_id = %s
                ORDER BY event_timestamp DESC LIMIT 10;
                """,
                (run_id,)
            )
            result["events"] = [dict(r) for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        logger.warning(f"load_lineage_topology failed: {e}")
    return result


def resolve_on_demand_context(
    message: str,
    run_id: str,
    state: Optional[Dict[str, Any]] = None,
    user_intent: Optional[UserIntent] = None
) -> Dict[str, Any]:
    """
    Dynamically loads only the necessary context slice based on intent and session state,
    avoiding unnecessary data dumps (e.g., Run Overview for general chat).
    """
    state = state or {}
    intent = user_intent or UserIntent.GENERAL_CONVERSATION
    context: Dict[str, Any] = {"run_id": run_id, "intent": intent.value}

    # 1. GENERAL_CONVERSATION or TOPIC_SWITCH: Minimal context needed
    if intent in (UserIntent.GENERAL_CONVERSATION, UserIntent.TOPIC_SWITCH):
        context["active_entities"] = {
            "finding_id": state.get("active_finding_id"),
            "dataset_id": state.get("active_dataset_id"),
            "column_name": state.get("active_column"),
        }
        return context

    # 2. RCA or REMEDIATION: Load finding evidence, rules, samples
    if intent in (UserIntent.ROOT_CAUSE_ONLY, UserIntent.REMEDIATION_ONLY, UserIntent.BOTH_RCA_AND_REMEDIATION):
        target_finding = state.get("active_finding_id")
        f_match = re.search(r'\b(FND-[a-zA-Z0-9_-]+|F-[a-zA-Z0-9_-]+)\b', message)
        if f_match:
            target_finding = f_match.group(1)

        fe = load_finding_evidence(run_id, target_finding)
        context.update(fe)

        ds_id = state.get("active_dataset_id") or (fe.get("finding") or {}).get("dataset_id")
        rule_id = (fe.get("finding") or {}).get("rule_id")
        if ds_id or rule_id:
            context["rules"] = load_compliance_rules(dataset_id=ds_id, rule_id=rule_id)
        return context

    # 3. DATA_OR_CATALOG_INQUIRY: Load catalog columns & profiling
    if intent == UserIntent.DATA_OR_CATALOG_INQUIRY:
        ds_id = state.get("active_dataset_id")
        col_name = state.get("active_column")
        context["catalog_columns"] = load_catalog_columns(ds_id)
        context["profiling"] = load_profiling_stats(ds_id, col_name)
        return context

    # 4. POLICY_OR_LEGAL_INQUIRY: Load compliance rules
    if intent == UserIntent.POLICY_OR_LEGAL_INQUIRY:
        context["compliance_rules"] = load_compliance_rules()
        return context

    # 5. PIPELINE_ERROR_OR_PROGRESS: Load lineage & execution events
    if intent == UserIntent.PIPELINE_ERROR_OR_PROGRESS:
        context.update(load_lineage_topology(run_id))
        return context

    # 6. RUN_OVERVIEW: Full overview metrics
    if intent == UserIntent.RUN_OVERVIEW:
        return RunContextLoader.load_context(run_id, intent)

    return context


class RunContextLoader:
    """Loads minimal, intent-specific context for an AI reasoning turn."""

    @classmethod
    def load_context(
        cls,
        run_id: str,
        intent: UserIntent,
        finding_id: Optional[str] = None
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {"run_id": run_id, "intent": intent.value}

        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. Base Pipeline Run info
                cur.execute(
                    """
                    SELECT run_id, dag_id, dataset_id, started_at, ended_at, status,
                           scanned_count, silver_count, quarantine_count, warning_count,
                           execution_duration_ms, error_message
                    FROM orchestration.pipeline_runs
                    WHERE run_id = %s LIMIT 1;
                    """,
                    (run_id,)
                )
                run_row = cur.fetchone()
                if not run_row:
                    conn.close()
                    return context
                context["pipeline_run"] = dict(run_row)
                dataset_id = run_row.get("dataset_id")
                started_at = run_row.get("started_at")

                # A. INTENT: RUN_OVERVIEW
                if intent == UserIntent.RUN_OVERVIEW:
                    cur.execute(
                        """
                        SELECT step_name, status, duration_ms, error_message
                        FROM orchestration.pipeline_run_steps
                        WHERE run_id = %s
                        ORDER BY step_order ASC;
                        """,
                        (run_id,)
                    )
                    context["steps"] = [dict(r) for r in cur.fetchall()]

                    cur.execute(
                        """
                        SELECT severity, count(*) as cnt, sum(failed_record_count) as total_failed
                        FROM audit.findings
                        WHERE run_id = %s
                        GROUP BY severity;
                        """,
                        (run_id,)
                    )
                    context["findings_summary"] = [dict(r) for r in cur.fetchall()]

                # B. INTENT: ROOT_CAUSE_ONLY
                elif intent == UserIntent.ROOT_CAUSE_ONLY:
                    finding_row = None
                    if finding_id:
                        cur.execute(
                            "SELECT * FROM audit.findings WHERE finding_id = %s AND run_id = %s LIMIT 1;",
                            (finding_id, run_id)
                        )
                        finding_row = cur.fetchone()
                    else:
                        cur.execute(
                            "SELECT * FROM audit.findings WHERE run_id = %s ORDER BY failed_record_count DESC LIMIT 1;",
                            (run_id,)
                        )
                        finding_row = cur.fetchone()

                    if finding_row:
                        context["finding"] = dict(finding_row)
                        cur.execute(
                            """
                            SELECT quarantine_id, violation_column, violation_reason, failure_lane,
                                   raw_record_json, lineage_hash
                            FROM quarantine.records
                            WHERE run_id = %s
                            LIMIT 3;
                            """,
                            (run_id,)
                        )
                        q_records = cur.fetchall()
                        sanitized_samples = []
                        for qr in q_records:
                            raw_json = qr.get("raw_record_json") or {}
                            safe_payload = sanitize_sample_record(raw_json) if isinstance(raw_json, dict) else {}
                            sanitized_samples.append({
                                "quarantine_id": qr.get("quarantine_id"),
                                "violation_column": qr.get("violation_column"),
                                "failure_lane": qr.get("failure_lane"),
                                "reason": qr.get("violation_reason"),
                                "lineage_hash": qr.get("lineage_hash"),
                                "sanitized_payload": safe_payload
                            })
                        context["sanitized_samples"] = sanitized_samples

                        if dataset_id and started_at:
                            cur.execute(
                                """
                                SELECT total_rows, null_counts_json, anomaly_signals_json
                                FROM catalog.table_profiles
                                WHERE dataset_id = %s AND created_at <= %s
                                ORDER BY created_at DESC LIMIT 1;
                                """,
                                (dataset_id, started_at)
                            )
                            prof = cur.fetchone()
                            if prof:
                                context["profile_snapshot"] = dict(prof)

                # C. INTENT: REMEDIATION_ONLY
                elif intent == UserIntent.REMEDIATION_ONLY:
                    if finding_id:
                        cur.execute(
                            "SELECT * FROM audit.findings WHERE finding_id = %s AND run_id = %s LIMIT 1;",
                            (finding_id, run_id)
                        )
                    else:
                        cur.execute(
                            "SELECT * FROM audit.findings WHERE run_id = %s ORDER BY failed_record_count DESC LIMIT 1;",
                            (run_id,)
                        )
                    finding_row = cur.fetchone()
                    if finding_row:
                        context["finding"] = dict(finding_row)

                    if dataset_id and started_at:
                        cur.execute(
                            """
                            SELECT rule_id, rule_name, rule_type, condition_expression, severity, standard_ref
                            FROM policy.compliance_rules
                            WHERE dataset_id = %s AND created_at <= %s
                            ORDER BY created_at DESC LIMIT 5;
                            """,
                            (dataset_id, started_at)
                        )
                        context["rules_snapshot"] = [dict(r) for r in cur.fetchall()]

                # D. INTENT: BOTH_RCA_AND_REMEDIATION
                elif intent == UserIntent.BOTH_RCA_AND_REMEDIATION:
                    if finding_id:
                        cur.execute(
                            "SELECT * FROM audit.findings WHERE finding_id = %s AND run_id = %s LIMIT 1;",
                            (finding_id, run_id)
                        )
                    else:
                        cur.execute(
                            "SELECT * FROM audit.findings WHERE run_id = %s ORDER BY failed_record_count DESC LIMIT 1;",
                            (run_id,)
                        )
                    finding_row = cur.fetchone()
                    if finding_row:
                        context["finding"] = dict(finding_row)
                        cur.execute(
                            """
                            SELECT quarantine_id, violation_column, violation_reason, failure_lane,
                                   raw_record_json, lineage_hash
                            FROM quarantine.records
                            WHERE run_id = %s
                            LIMIT 3;
                            """,
                            (run_id,)
                        )
                        sanitized_samples = [
                            {
                                "quarantine_id": qr.get("quarantine_id"),
                                "violation_column": qr.get("violation_column"),
                                "failure_lane": qr.get("failure_lane"),
                                "reason": qr.get("violation_reason"),
                                "lineage_hash": qr.get("lineage_hash"),
                                "sanitized_payload": sanitize_sample_record(qr.get("raw_record_json") or {})
                            }
                            for qr in cur.fetchall()
                        ]
                        context["sanitized_samples"] = sanitized_samples

                    if dataset_id and started_at:
                        cur.execute(
                            """
                            SELECT rule_id, rule_name, rule_type, condition_expression, severity, standard_ref
                            FROM policy.compliance_rules
                            WHERE dataset_id = %s AND created_at <= %s
                            ORDER BY created_at DESC LIMIT 5;
                            """,
                            (dataset_id, started_at)
                        )
                        context["rules_snapshot"] = [dict(r) for r in cur.fetchall()]

                # E. INTENT: PIPELINE_ERROR_OR_PROGRESS
                elif intent == UserIntent.PIPELINE_ERROR_OR_PROGRESS:
                    cur.execute(
                        """
                        SELECT step_name, status, duration_ms, error_message
                        FROM orchestration.pipeline_run_steps
                        WHERE run_id = %s
                        ORDER BY step_order ASC;
                        """,
                        (run_id,)
                    )
                    context["steps"] = [dict(r) for r in cur.fetchall()]

                    cur.execute(
                        """
                        SELECT event_type, step_name, severity, message, event_timestamp
                        FROM orchestration.pipeline_run_events
                        WHERE run_id = %s
                        ORDER BY event_timestamp DESC
                        LIMIT 10;
                        """,
                        (run_id,)
                    )
                    context["recent_events"] = [dict(r) for r in cur.fetchall()]

            conn.close()
        except Exception as e:
            logger.warning(f"Error loading selective context for run {run_id}: {e}")

        return context
