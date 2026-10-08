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

                # ============================================================
                # A. INTENT: RUN_OVERVIEW
                # ============================================================
                if intent == UserIntent.RUN_OVERVIEW:
                    # Load steps summary
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

                    # Aggregate finding counts
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

                # ============================================================
                # B. INTENT: ROOT_CAUSE_ONLY
                # ============================================================
                elif intent == UserIntent.ROOT_CAUSE_ONLY:
                    # Load specific or top finding
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
                        # Load up to 3 sanitized quarantine records (NO raw unmasked records)
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

                        # Load snapshot table profile (created_at <= run.started_at)
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

                # ============================================================
                # C. INTENT: REMEDIATION_ONLY
                # ============================================================
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

                    # Load active rules snapshot at run.started_at
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

                # ============================================================
                # D. INTENT: BOTH_RCA_AND_REMEDIATION
                # ============================================================
                elif intent == UserIntent.BOTH_RCA_AND_REMEDIATION:
                    # Combine finding, up to 3 masked samples, and snapshot rules
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

                # ============================================================
                # E. INTENT: PIPELINE_ERROR_OR_PROGRESS
                # ============================================================
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
