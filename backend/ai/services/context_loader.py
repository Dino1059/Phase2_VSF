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

# Allowlist of business & technical fields safe for LLM context
SAFE_FIELD_ALLOWLIST = {
    "trip_id", "record_id", "session_id", "feedback_id",
    "trip_distance_km", "trip_distance", "fare_amount", "tip_amount", "total_fare",
    "pickup_latitude", "pickup_longitude", "dropoff_latitude", "dropoff_longitude",
    "speed_kmh", "motor_rpm", "battery_temp_c", "battery_soc", "battery_voltage", "voltage_v",
    "battery_current", "power_kw", "duration_mins", "duration_min", "kwh_consumed", "cost_vnd",
    "subject_zone", "country", "status", "timestamp", "start_time"
}

# Known PII field patterns
PII_FIELD_PATTERNS = [
    r"phone", r"tel", r"email", r"name", r"customer", r"driver",
    r"id_card", r"passport", r"ssn", r"cccd", r"license", r"address"
]


def mask_pii_value(key: str, val: Any) -> Any:
    """Masks identifying strings to prevent PII exposure to external LLMs."""
    if val is None or not isinstance(val, str):
        return val
    s = val.strip()
    if not s:
        return s

    k_lower = key.lower()
    if "email" in k_lower or "@" in s:
        parts = s.split("@", 1)
        return f"{parts[0][:1]}***@{parts[1]}" if len(parts) == 2 else "***@***"
    if "phone" in k_lower or "tel" in k_lower or re.match(r"^\+?\d{9,12}$", s):
        if len(s) >= 7:
            return f"{s[:3]}*****{s[-2:]}"
        return "***"
    if any(p in k_lower for p in ("cccd", "id_card", "passport", "ssn", "license")):
        return "[REDACTED_IDENTIFIER]"
    if "address" in k_lower:
        return "[REDACTED_ADDRESS]"
    if "name" in k_lower:
        tokens = s.split()
        return " ".join(t[:1] + "***" for t in tokens) if tokens else "***"

    if len(s) <= 4:
        return "***"
    return f"{s[:2]}***{s[-2:]}"


def sanitize_sample_record(raw_record: Dict[str, Any], target_column: Optional[str] = None) -> Dict[str, Any]:
    """
    Enforces Strict Field Allowlist and Isolated Token Masking (Privacy-First).
    Avoids sending unneeded PII fields into LLM context.
    - If target_column is specified: only keeps allowlisted fields plus isolated masked target_column.
    - If target_column is not specified: keeps allowlisted fields and masks any detected PII fields.
    """
    if not isinstance(raw_record, dict):
        return {}
    sanitized = {}
    target_lower = target_column.lower().strip() if target_column else None

    for k, v in raw_record.items():
        k_lower = k.lower().strip()
        if k_lower in SAFE_FIELD_ALLOWLIST:
            sanitized[k] = v
        elif target_lower:
            if k_lower == target_lower:
                sanitized[k] = mask_pii_value(k, v)
        else:
            # When target_column is not specified, mask recognized PII fields
            is_pii = any(re.search(p, k_lower) for p in PII_FIELD_PATTERNS)
            if is_pii:
                sanitized[k] = mask_pii_value(k, v)
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


def fetch_grounded_quarantine_samples(
    cur,
    run_id: str,
    finding_id: Optional[str] = None,
    rule_id: Optional[str] = None,
    column_name: Optional[str] = None,
    limit: int = 3
) -> List[Dict[str, Any]]:
    """
    Evidence-or-Abstain: Fetches quarantine records strictly grounded to the given finding.
    1. Priority 1: JOIN audit.finding_quarantine_records by finding_id AND run_id.
    2. Priority 2: Strict composite match on run_id AND rule_id AND column_name (all three).
    3. Abstain: If no grounded record matches, returns [] (never pulls arbitrary records).
    """
    samples: List[Dict[str, Any]] = []

    # 1. Primary: FK Junction Table
    if finding_id:
        cur.execute(
            """
            SELECT q.quarantine_id, q.source_row_pk, q.failure_lane, q.violation_reason,
                   q.violation_column, q.violation_rule_id, q.raw_record_json, q.lineage_hash
            FROM quarantine.records q
            JOIN audit.finding_quarantine_records fqr ON q.quarantine_id = fqr.quarantine_id
            WHERE fqr.finding_id = %s AND q.run_id = %s
            LIMIT %s;
            """,
            (finding_id, run_id, limit)
        )
        rows = cur.fetchall()
        if rows:
            for r in rows:
                raw_json = r.get("raw_record_json") or {}
                safe_payload = sanitize_sample_record(raw_json, target_column=column_name or r.get("violation_column"))
                samples.append({
                    "quarantine_id": str(r.get("quarantine_id")),
                    "source_row_pk": r.get("source_row_pk"),
                    "violation_column": r.get("violation_column"),
                    "violation_rule_id": r.get("violation_rule_id"),
                    "failure_lane": r.get("failure_lane"),
                    "reason": r.get("violation_reason"),
                    "lineage_hash": r.get("lineage_hash"),
                    "sanitized_payload": safe_payload
                })
            return samples

    # 2. Strict Composite Fallback: Must match run_id AND rule_id AND column_name
    if rule_id and column_name:
        cur.execute(
            """
            SELECT quarantine_id, source_row_pk, failure_lane, violation_reason,
                   violation_column, violation_rule_id, raw_record_json, lineage_hash
            FROM quarantine.records
            WHERE run_id = %s AND violation_rule_id = %s AND violation_column = %s
            LIMIT %s;
            """,
            (run_id, rule_id, column_name, limit)
        )
        rows = cur.fetchall()
        for r in rows:
            raw_json = r.get("raw_record_json") or {}
            safe_payload = sanitize_sample_record(raw_json, target_column=column_name)
            samples.append({
                "quarantine_id": str(r.get("quarantine_id")),
                "source_row_pk": r.get("source_row_pk"),
                "violation_column": r.get("violation_column"),
                "violation_rule_id": r.get("violation_rule_id"),
                "failure_lane": r.get("failure_lane"),
                "reason": r.get("violation_reason"),
                "lineage_hash": r.get("lineage_hash"),
                "sanitized_payload": safe_payload
            })
        return samples

    # 3. Abstain: Never guess or pick unrelated records
    return []


def load_finding_evidence(run_id: str, finding_id: Optional[str] = None) -> Dict[str, Any]:
    """Loads finding and associated sanitized quarantine records via Evidence-or-Abstain."""
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
                fid = f_row.get("finding_id")
                rid = f_row.get("rule_id")
                col = f_row.get("column_name")
                samples = fetch_grounded_quarantine_samples(
                    cur, run_id=run_id, finding_id=fid, rule_id=rid, column_name=col, limit=3
                )
                result["sanitized_samples"] = samples
            else:
                result["sanitized_samples"] = []
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


def load_warning_evidence(run_id: str) -> Dict[str, Any]:
    """
    Loads warning record counts, grouped distributions, and sanitized sample records.
    Implements:
    - Dedicated SELECT COUNT(*) for 100% accurate reconciliation (avoiding GROUP BY LIMIT distortion)
    - Safe fallback on DB errors or missing tables
    - PII-controlled sample payloads
    """
    result: Dict[str, Any] = {
        "run_id": run_id,
        "pipeline_warning_count": 0,
        "actual_records_count": 0,
        "is_reconciled": True,
        "discrepancy_note": None,
        "grouped_warnings": [],
        "sanitized_samples": [],
        "db_error": False,
    }
    try:
        from database.profiler_engine import get_db_connection
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Pipeline Run warning count
            cur.execute(
                "SELECT warning_count FROM orchestration.pipeline_runs WHERE run_id = %s LIMIT 1;",
                (run_id,)
            )
            run_row = cur.fetchone()
            pipeline_warn_count = (run_row.get("warning_count") if run_row else 0) or 0
            result["pipeline_warning_count"] = pipeline_warn_count

            # 2. Independent, exact COUNT(*) from warning.records
            cur.execute(
                "SELECT COUNT(*) AS total_records FROM warning.records WHERE run_id = %s;",
                (run_id,)
            )
            count_row = cur.fetchone()
            actual_count = (count_row.get("total_records") if count_row else 0) or 0
            result["actual_records_count"] = actual_count

            # 3. Reconciliation check
            if pipeline_warn_count != actual_count:
                result["is_reconciled"] = False
                result["discrepancy_note"] = (
                    f"Ghi nhận độ lệch: Chỉ số pipeline báo {pipeline_warn_count:,} cảnh báo, "
                    f"nhưng bảng warning.records hiện lưu trữ {actual_count:,} bản ghi."
                )

            # 4. Grouped distributions for display (Top 10 groups by frequency)
            cur.execute(
                """
                SELECT warning_type, signal_lane, signal_layer, warning_reason, count(*) as count
                FROM warning.records
                WHERE run_id = %s
                GROUP BY warning_type, signal_lane, signal_layer, warning_reason
                ORDER BY count DESC
                LIMIT 10;
                """,
                (run_id,)
            )
            result["grouped_warnings"] = [dict(r) for r in cur.fetchall()]

            # 5. Sanitized sample records with evidence parsing
            cur.execute(
                """
                SELECT warning_id, source_row_pk, signal_lane, signal_layer, warning_type,
                       warning_reason, score_or_zvalue, evidence_json, redacted_record_json
                FROM warning.records
                WHERE run_id = %s
                LIMIT 5;
                """,
                (run_id,)
            )
            samples = []
            for wr in cur.fetchall():
                redacted_json = wr.get("redacted_record_json") or {}
                safe_payload = sanitize_sample_record(redacted_json) if isinstance(redacted_json, dict) else {}
                samples.append({
                    "warning_id": str(wr.get("warning_id")),
                    "source_row_pk": str(wr.get("source_row_pk") or "").strip(),
                    "signal_lane": wr.get("signal_lane"),
                    "signal_layer": wr.get("signal_layer"),
                    "warning_type": wr.get("warning_type"),
                    "warning_reason": wr.get("warning_reason"),
                    "score_or_zvalue": float(wr["score_or_zvalue"]) if wr.get("score_or_zvalue") is not None else None,
                    "evidence_json": wr.get("evidence_json"),
                    "sanitized_payload": safe_payload,
                })
            result["sanitized_samples"] = samples

            # 6. Deep Quantitative Changepoint Extraction for L4 warnings
            cur.execute(
                """
                SELECT warning_id, source_row_pk, score_or_zvalue, warning_reason, evidence_json
                FROM warning.records
                WHERE run_id = %s AND warning_type = 'CHANGEPOINT_SHIFT';
                """,
                (run_id,)
            )
            cp_rows = cur.fetchall()
            if cp_rows:
                # Query governing rule from engine.reliability_rules
                cur.execute(
                    """
                    SELECT rule_id, detector_id, layer, target_fields, params_json, status, version
                    FROM engine.reliability_rules
                    WHERE detector_id = 'CHANGEPOINT' AND status = 'ACTIVE'
                    LIMIT 1;
                    """
                )
                cp_rule = cur.fetchone()

                cp_scores = []
                cp_mags = []
                cp_dirs = {"UP": 0, "DOWN": 0}
                events_map = {}

                for r in cp_rows:
                    reason = r.get("warning_reason") or ""
                    sc = float(r["score_or_zvalue"]) if r.get("score_or_zvalue") is not None else None
                    if sc is not None:
                        cp_scores.append(sc)

                    t_match = re.search(r'change_time=([^;]+)', reason)
                    m_match = re.search(r'change_magnitude=([-\d.]+)', reason)
                    d_match = re.search(r'shift_direction=([A-Z]+)', reason)
                    p_match = re.search(r'pelt_penalty=([-\d.]+)', reason)
                    pre_m = re.search(r'pre_window_mean=([-\d.]+)', reason)
                    post_m = re.search(r'post_window_mean=([-\d.]+)', reason)

                    c_time = t_match.group(1) if t_match else "UNKNOWN"
                    c_mag = float(m_match.group(1)) if m_match else 0.0
                    c_dir = d_match.group(1) if d_match else "UNKNOWN"
                    p_pen = float(p_match.group(1)) if p_match else 3.0
                    pre_val = float(pre_m.group(1)) if pre_m else None
                    post_val = float(post_m.group(1)) if post_m else None

                    cp_mags.append(c_mag)
                    if c_dir in cp_dirs:
                        cp_dirs[c_dir] += 1

                    if c_time not in events_map:
                        events_map[c_time] = {
                            "event_time": c_time,
                            "direction": c_dir,
                            "magnitude": c_mag,
                            "pelt_penalty": p_pen,
                            "pre_mean": pre_val,
                            "post_mean": post_val,
                            "anchor_pk": str(r.get("source_row_pk") or "").strip(),
                            "affected_records": 0
                        }
                    events_map[c_time]["affected_records"] += 1

                result["changepoint_summary"] = {
                    "rule_id": cp_rule["rule_id"] if cp_rule else "L4-DEFAULT-METRICS",
                    "rule_version": cp_rule["version"] if cp_rule else 1,
                    "target_metric": "trip_distance_km",
                    "target_fields": cp_rule["target_fields"] if cp_rule else ["trip_distance_km"],
                    "penalty_threshold": 3.0,
                    "total_warnings": len(cp_rows),
                    "distinct_changepoint_events": len(events_map),
                    "shift_directions": cp_dirs,
                    "magnitude_range": {
                        "min": min(cp_mags) if cp_mags else 0.0,
                        "max": max(cp_mags) if cp_mags else 0.0
                    },
                    "score_range": {
                        "min": min(cp_scores) if cp_scores else 0.0,
                        "max": max(cp_scores) if cp_scores else 0.0,
                        "avg": round(sum(cp_scores) / len(cp_scores), 2) if cp_scores else 0.0
                    },
                    "events": list(events_map.values())[:5]
                }
        conn.close()
    except Exception as e:
        logger.warning(f"load_warning_evidence failed: {e}")
        result["db_error"] = True
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

    # 7. WARNING_INQUIRY: Load warning counts, grouped distribution, samples
    if intent == UserIntent.WARNING_INQUIRY:
        return load_warning_evidence(run_id)

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
                        fid = finding_row.get("finding_id")
                        rid = finding_row.get("rule_id")
                        col = finding_row.get("column_name")
                        context["sanitized_samples"] = fetch_grounded_quarantine_samples(
                            cur, run_id=run_id, finding_id=fid, rule_id=rid, column_name=col, limit=3
                        )

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
                        fid = finding_row.get("finding_id")
                        rid = finding_row.get("rule_id")
                        col = finding_row.get("column_name")
                        context["sanitized_samples"] = fetch_grounded_quarantine_samples(
                            cur, run_id=run_id, finding_id=fid, rule_id=rid, column_name=col, limit=3
                        )

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

                # F. INTENT: WARNING_INQUIRY
                elif intent == UserIntent.WARNING_INQUIRY:
                    we = load_warning_evidence(run_id)
                    context.update(we)

            conn.close()
        except Exception as e:
            logger.warning(f"Error loading selective context for run {run_id}: {e}")

        return context
