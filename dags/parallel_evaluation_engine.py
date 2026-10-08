"""
DataTrust OS: Parallel Evaluation Engine (Airflow Task 3 Execution Core)
Orchestrates:
Lane A (L1-L4 Reliability Suite) // Lane B (Hierarchical Policy Processor)
-> Lane C (Merge Verdicts & Database Persistence: Silver / Quarantine / Warning).
"""

import os
import sys
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values, Json

# Add workspace and dags to path
workspace_dir = Path(__file__).resolve().parent.parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))
if str(workspace_dir / "dags") not in sys.path:
    sys.path.insert(0, str(workspace_dir / "dags"))

from src.detectors.detector_suite import L1toL4DetectorSuite
from backend.engine.jurisdiction_config import JurisdictionHierarchyConfig
from backend.engine.hierarchical_policy_processor import (
    HierarchicalPolicyProcessor,
    LaneBVerdict,
    PolicyViolation,
)
from backend.engine.verdict_merger_and_router import VerdictMergerAndRouter, ConsolidatedRunResult
from decimal import Decimal


def _json_safe(val: Any) -> Any:
    """Recursively converts Decimals and datetime objects to JSON-serializable primitives."""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.isoformat()
    if isinstance(val, dict):
        return {k: _json_safe(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_json_safe(v) for v in val]
    return val


def _normalize_jurisdiction(value: Any, default: str = "GLOBAL") -> str:
    """Return a stable jurisdiction key for persistence and aggregation."""
    normalized = str(value or "").strip().upper()
    return normalized or default


def _policy_snapshot_from_verdict(verdict: Optional[LaneBVerdict]) -> Optional[Dict[str, Any]]:
    """Select the most-specific explicit policy snapshot carried by Lane B.

    Missing metadata stays missing: legal bases are never guessed from a
    column name and no cross-zone law is substituted.
    """
    if verdict is None:
        return None

    if verdict.violations:
        violation = verdict.violations[0]
        return {
            "policy_id": violation.policy_id,
            "policy_name": violation.policy_name,
            "law_ref": violation.law_ref,
            "jurisdiction": _normalize_jurisdiction(violation.jurisdiction),
            "country": None,
            "rule_id": violation.rule_id,
            "rule_name": None,
        }

    chain = [_normalize_jurisdiction(item) for item in verdict.jurisdiction_chain]
    candidates: List[Dict[str, Any]] = []
    for treatment in verdict.required_treatments:
        if not treatment.get("policy_id") and not treatment.get("law_ref"):
            continue
        jurisdiction = _normalize_jurisdiction(treatment.get("jurisdiction"))
        snapshot = {
            "policy_id": treatment.get("policy_id"),
            "policy_name": treatment.get("policy_name"),
            "law_ref": treatment.get("law_ref"),
            "jurisdiction": jurisdiction,
            "country": treatment.get("country"),
            "rule_id": treatment.get("rule_id"),
            "rule_name": treatment.get("rule_name") or treatment.get("treatment_name"),
        }
        specificity = chain.index(jurisdiction) if jurisdiction in chain else -1
        candidates.append({"specificity": specificity, "snapshot": snapshot})

    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            item["specificity"],
            str(item["snapshot"].get("policy_id") or ""),
            str(item["snapshot"].get("rule_id") or ""),
        ),
        reverse=True,
    )
    return candidates[0]["snapshot"]


def _attach_policy_context_to_quarantine(
    quarantine_records: List[Dict[str, Any]],
    verdicts: List[LaneBVerdict],
) -> None:
    """Attach record jurisdiction and the exact Lane B policy snapshot."""
    verdict_by_record = {str(verdict.record_id): verdict for verdict in verdicts}
    hierarchy = JurisdictionHierarchyConfig()
    for record in quarantine_records:
        raw = record.get("raw_record_json") or {}
        verdict = verdict_by_record.get(str(record.get("source_row_pk")))
        chain = list(verdict.jurisdiction_chain) if verdict else hierarchy.resolve_chain(
            raw.get("subject_zone") or raw.get("zone"),
            raw.get("country") or raw.get("subject_jurisdiction"),
        )
        record["subject_zone"] = _normalize_jurisdiction(
            raw.get("subject_zone") or raw.get("zone") or (chain[1] if len(chain) > 1 else "GLOBAL")
        )
        record["country"] = chain[-1] if len(chain) > 2 else None
        record["jurisdiction_chain"] = [_normalize_jurisdiction(item) for item in chain]

        snapshot = (
            _policy_snapshot_from_verdict(verdict)
            if record.get("failure_lane") in {"LANE_B", "BOTH"}
            else None
        )
        record["matched_policy_id"] = snapshot.get("policy_id") if snapshot else None
        record["matched_policy_name"] = snapshot.get("policy_name") if snapshot else None
        record["matched_law_ref"] = snapshot.get("law_ref") if snapshot else None
        record["policy_snapshot"] = snapshot
        if verdict and verdict.violations and record.get("failure_lane") in {"LANE_B", "BOTH"}:
            violation = verdict.violations[0]
            record["violation_rule_id"] = violation.rule_id
            record["violation_column"] = violation.column_name
            record["violation_reason"] = violation.reason
            record["violation_severity"] = violation.severity


def get_db_connection():
    """Returns database connection handling Docker and local environments."""
    host = os.getenv("POSTGRES_HOST", "postgres" if os.path.exists("/opt/airflow") else "localhost")
    port = int(os.getenv("POSTGRES_PORT", 5432))
    dbname = os.getenv("POSTGRES_DB", "airflow")
    user = os.getenv("POSTGRES_USER", "airflow")
    password = os.getenv("POSTGRES_PASSWORD", "airflow")

    try:
        return psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
    except psycopg2.OperationalError:
        # Fallback to localhost if host='postgres' failed locally
        return psycopg2.connect(host="localhost", port=port, dbname=dbname, user=user, password=password)


# =============================================================================
# LANE A: DATA RELIABILITY & SENSOR ANOMALY SUITE (L1-L4)
# =============================================================================

def execute_lane_a_detectors(dataset_id: str, records: List[Dict[str, Any]], pk_col: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes Lane A detectors on records DataFrame.
    Returns serializable dictionary for XCom.
    """
    if not records:
        return {}

    df = pd.DataFrame(records)
    suite = L1toL4DetectorSuite(project_id="gsm_3zone_pilot")
    raw_results = suite.evaluate_records(dataset_id, df, pk_col=pk_col)

    # Serialize for XCom
    serializable: Dict[str, Any] = {}
    for pk, res in raw_results.items():
        serializable[pk] = {
            "status": res["status"],
            "evidence": res["evidence"],
            "signals": [
                {
                    "signal_id": s.signal_id,
                    "layer": s.layer,
                    "signal_type": s.signal_type,
                    "score": s.score,
                    "severity": s.severity,
                    "evidence_refs": s.evidence_refs
                }
                for s in res["signals"]
            ]
        }
    return _json_safe(serializable)


# =============================================================================
# LANE B: HIERARCHICAL POLICY & COMPLIANCE EVALUATION (7 STEPS)
# =============================================================================

def load_active_treatments_from_db(dataset_id: str) -> List[Dict[str, Any]]:
    """Loads active treatments for dataset from policy.data_treatment_rules."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        clean_ds = dataset_id.replace(".csv", "").replace("bronze.", "")
        cur.execute("""
            SELECT rule_id, column_name, operation_id, params_json,
                   treatment_name, description, policy_id, policy_name,
                   law_ref, jurisdiction, country
            FROM policy.data_treatment_rules
            WHERE status = 'active' AND (dataset_id = %s OR dataset_id = %s OR dataset_id = %s);
        """, (clean_ds, f"{clean_ds}.csv", f"bronze.{clean_ds}"))
        rows = cur.fetchall()
        treatments = []
        for r in rows:
            treatments.append({
                "rule_id": r[0],
                "column": r[1],
                "operation_id": r[2],
                "params": r[3] if isinstance(r[3], dict) else {},
                "treatment_name": r[4],
                "description": r[5],
                "policy_id": r[6],
                "policy_name": r[7],
                "law_ref": r[8],
                "jurisdiction": _normalize_jurisdiction(r[9]),
                "country": r[10],
            })
        return treatments
    except Exception:
        return []
    finally:
        if conn is not None:
            conn.close()


def execute_lane_b_policy(dataset_id: str, records: List[Dict[str, Any]], pk_col: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Executes Lane B: Resolve -> Policy -> Pre-check -> Treatment -> Process -> Post-check -> Verdict.
    Returns serializable verdicts for XCom.
    """
    if not records:
        return []

    active_treatments = load_active_treatments_from_db(dataset_id)
    processor = HierarchicalPolicyProcessor(active_treatments=active_treatments)
    verdicts = processor.process_records(dataset_id, records, pk_col=pk_col)

    serializable: List[Dict[str, Any]] = []
    for v in verdicts:
        serializable.append({
            "record_id": v.record_id,
            "status": v.status,
            "treated_record": v.treated_record,
            "raw_record": v.raw_record,
            "compliance_evidence": v.compliance_evidence,
            "required_treatments": v.required_treatments,
            "failure_reasons": v.failure_reasons,
            "jurisdiction_chain": v.jurisdiction_chain,
            "normalized_zone": v.normalized_zone,
            "applied_policy_ids": v.applied_policy_ids,
            "violations": [item.to_dict() for item in v.violations],
        })
    return _json_safe(serializable)


# =============================================================================
# LANE C: MERGE VERDICTS, ROUTE & PERSIST (SILVER / QUARANTINE / WARNING)
# =============================================================================

def execute_lane_c_merge_and_persist(
    dataset_id: str,
    records: List[Dict[str, Any]],
    lane_a_data: Dict[str, Any],
    lane_b_data: List[Dict[str, Any]],
    run_id: str,
    conn = None
) -> Dict[str, Any]:
    """
    Merges Lane A and Lane B verdicts via A/B combination matrix,
    enforces precedence, and persists to PostgreSQL.
    """
    # Reconstruct LaneBVerdict objects
    reconstructed_b: List[LaneBVerdict] = [
        LaneBVerdict(
            record_id=d["record_id"],
            status=d["status"],
            treated_record=d["treated_record"],
            raw_record=d["raw_record"],
            compliance_evidence=d.get("compliance_evidence", []),
            required_treatments=d.get("required_treatments", []),
            failure_reasons=d.get("failure_reasons", []),
            jurisdiction_chain=d.get("jurisdiction_chain", []),
            normalized_zone=d.get("normalized_zone", "GLOBAL"),
            applied_policy_ids=d.get("applied_policy_ids", []),
            violations=[PolicyViolation(**item) for item in d.get("violations", [])],
        )
        for d in lane_b_data
    ]

    router = VerdictMergerAndRouter()
    result = router.merge_and_route(
        dataset_id=dataset_id,
        records=records,
        lane_a_results=lane_a_data,
        lane_b_verdicts=reconstructed_b,
        run_id=run_id
    )
    _attach_policy_context_to_quarantine(result.quarantine_records, reconstructed_b)

    # Persist to database if connection available
    should_close = False
    if conn is None:
        try:
            conn = get_db_connection()
            should_close = True
        except Exception as exc:
            print(f"Warning: Could not connect to Postgres for persistence: {exc}")
            conn = None

    if conn is not None:
        try:
            persist_consolidated_results(conn, result)
        finally:
            if should_close:
                conn.close()

    metrics = {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "scanned": result.scanned_count,
        "silver": result.silver_count,
        "quarantine": result.quarantine_count,
        "warning": result.warning_count,
        "quarantine_sample": result.quarantine_records[:3],
        "warning_sample": result.warning_records[:3]
    }
    return metrics


# =============================================================================
# DATABASE PERSISTENCE HELPERS
# =============================================================================

def persist_consolidated_results(conn, result: ConsolidatedRunResult):
    """Persists silver, quarantine, and warning records to PostgreSQL."""
    cur = conn.cursor()
    run_id = result.run_id
    dataset_id = result.dataset_id

    cur.execute("""
        SELECT table_schema, table_name, column_name
        FROM information_schema.columns
        WHERE (table_schema = 'quarantine' AND table_name = 'records')
           OR (table_schema = 'audit' AND table_name = 'findings');
    """)
    schema_columns: Dict[tuple, set] = {}
    for schema_name, table_name, column_name in cur.fetchall():
        schema_columns.setdefault((schema_name, table_name), set()).add(column_name)
    quarantine_columns = schema_columns.get(("quarantine", "records"), set())
    finding_columns = schema_columns.get(("audit", "findings"), set())
    jurisdiction_schema_ready = {
        "subject_zone", "country", "jurisdiction_chain", "matched_policy_id",
        "matched_policy_name", "matched_law_ref", "policy_snapshot",
        "applied_policy_ids", "policy_violations",
    } <= quarantine_columns and {
        "jurisdiction", "country", "jurisdiction_chain", "policy_snapshot",
    } <= finding_columns

    # 1. Persist Silver records
    if result.silver_records:
        if "trips" in dataset_id:
            table_name = "silver.ride_hailing_xanh_sm_trips"
            cols = ["trip_id", "vehicle_vin", "driver_id", "customer_id", "customer_contact",
                    "pickup_datetime", "dropoff_datetime", "trip_distance_km", "fare_amount",
                    "tip_amount", "total_fare", "pickup_latitude", "pickup_longitude",
                    "vehicle_type", "subject_zone", "country", "lineage_hash", "_run_id"]
            seen = {}
            for r in result.silver_records:
                tid = r.get("trip_id")
                if tid:
                    seen[tid] = (
                        tid, r.get("vehicle_vin"), r.get("driver_id"), r.get("customer_id"), r.get("customer_contact") or r.get("customer_phone"),
                        str(r.get("pickup_datetime") or ""), str(r.get("dropoff_datetime") or ""),
                        _float_or_none(r.get("trip_distance_km")), _float_or_none(r.get("fare_amount")),
                        _float_or_none(r.get("tip_amount")), _float_or_none(r.get("total_fare")),
                        _float_or_none(r.get("pickup_latitude")), _float_or_none(r.get("pickup_longitude")),
                        r.get("vehicle_type"), r.get("subject_zone"), r.get("country"),
                        r.get("lineage_hash"), run_id
                    )
            values = list(seen.values())
            sql = f"""
                INSERT INTO {table_name} ({', '.join(cols)})
                VALUES %s
                ON CONFLICT (trip_id) DO UPDATE SET
                    _run_id = EXCLUDED._run_id,
                    lineage_hash = EXCLUDED.lineage_hash,
                    _processed_at = CURRENT_TIMESTAMP
            """
            if values:
                execute_values(cur, sql, values)

        elif "telemetry" in dataset_id:
            table_name = "silver.synthetic_ev_telemetry_ved_ref"
            cols = ["record_id", "vehicle_vin", "timestamp", "speed_kmh", "motor_rpm", "battery_soc",
                    "battery_voltage", "battery_current", "battery_temp_c", "latitude", "longitude",
                    "subject_zone", "country", "lineage_hash", "_run_id"]
            seen = {}
            for r in result.silver_records:
                rid = r.get("record_id")
                if rid:
                    seen[rid] = (
                        rid, r.get("vehicle_vin"), str(r.get("timestamp") or ""),
                        _float_or_none(r.get("speed_kmh")), _int_or_none(r.get("motor_rpm")), _float_or_none(r.get("battery_soc")),
                        _float_or_none(r.get("battery_voltage")), _float_or_none(r.get("battery_current")), _float_or_none(r.get("battery_temp_c")),
                        _float_or_none(r.get("latitude")), _float_or_none(r.get("longitude")),
                        r.get("subject_zone"), r.get("country"), r.get("lineage_hash"), run_id
                    )
            values = list(seen.values())
            sql = f"""
                INSERT INTO {table_name} ({', '.join(cols)})
                VALUES %s
                ON CONFLICT (record_id) DO UPDATE SET
                    _run_id = EXCLUDED._run_id,
                    lineage_hash = EXCLUDED.lineage_hash,
                    _processed_at = CURRENT_TIMESTAMP
            """
            if values:
                execute_values(cur, sql, values)

        elif "charging" in dataset_id:
            table_name = "silver.acn_charging_mapped"
            cols = ["session_id", "vehicle_vin", "station_id", "charger_id", "start_time",
                    "duration_mins", "kwh_consumed", "power_kw", "station_temp_c", "cost_vnd",
                    "subject_zone", "country", "lineage_hash", "_run_id"]
            seen = {}
            for r in result.silver_records:
                sid = r.get("session_id")
                if sid:
                    seen[sid] = (
                        sid, r.get("vehicle_vin"), r.get("station_id"), r.get("charger_id"),
                        str(r.get("start_time") or ""),
                        _float_or_none(r.get("duration_mins")), _float_or_none(r.get("kwh_consumed")),
                        _float_or_none(r.get("power_kw")), _float_or_none(r.get("station_temp_c")),
                        _float_or_none(r.get("cost_vnd")),
                        r.get("subject_zone"), r.get("country"), r.get("lineage_hash"), run_id
                    )
            values = list(seen.values())
            sql = f"""
                INSERT INTO {table_name} ({', '.join(cols)})
                VALUES %s
                ON CONFLICT (session_id) DO UPDATE SET
                    _run_id = EXCLUDED._run_id,
                    lineage_hash = EXCLUDED.lineage_hash,
                    _processed_at = CURRENT_TIMESTAMP
            """
            if values:
                execute_values(cur, sql, values)

        elif "customers" in dataset_id:
            table_name = "silver.dim_customers"
            cols = ["customer_id", "first_name", "last_name", "email", "phone_number",
                    "created_at", "subject_zone", "country", "lineage_hash", "_run_id"]
            seen = {}
            for r in result.silver_records:
                cid = r.get("customer_id")
                if cid:
                    seen[cid] = (
                        cid, r.get("first_name"), r.get("last_name"), r.get("email"), r.get("phone_number"),
                        str(r.get("created_at") or ""),
                        r.get("subject_zone"), r.get("country"), r.get("lineage_hash"), run_id
                    )
            values = list(seen.values())
            sql = f"""
                INSERT INTO {table_name} ({', '.join(cols)})
                VALUES %s
                ON CONFLICT (customer_id) DO UPDATE SET
                    _run_id = EXCLUDED._run_id,
                    lineage_hash = EXCLUDED.lineage_hash,
                    _processed_at = CURRENT_TIMESTAMP
            """
            if values:
                execute_values(cur, sql, values)

        elif "drivers" in dataset_id:
            table_name = "silver.dim_drivers"
            cols = ["driver_id", "vehicle_vin", "first_name", "last_name", "email", "phone_number",
                    "created_at", "subject_zone", "country", "lineage_hash", "_run_id"]
            seen = {}
            for r in result.silver_records:
                did = r.get("driver_id")
                if did:
                    seen[did] = (
                        did, r.get("vehicle_vin"), r.get("first_name"), r.get("last_name"), r.get("email"), r.get("phone_number"),
                        str(r.get("created_at") or ""),
                        r.get("subject_zone"), r.get("country"), r.get("lineage_hash"), run_id
                    )
            values = list(seen.values())
            sql = f"""
                INSERT INTO {table_name} ({', '.join(cols)})
                VALUES %s
                ON CONFLICT (driver_id) DO UPDATE SET
                    _run_id = EXCLUDED._run_id,
                    lineage_hash = EXCLUDED.lineage_hash,
                    _processed_at = CURRENT_TIMESTAMP
            """
            if values:
                execute_values(cur, sql, values)

        elif "feedback_pii" in dataset_id:
            table_name = "silver.feedback_pii"
            cols = ["feedback_id", "vehicle_vin", "trip_id", "customer_id", "scenario_date",
                    "assigned_day_index", "topic", "sentiment", "raw_comment_text",
                    "subject_zone", "country", "lineage_hash", "_run_id"]
            seen = {}
            for r in result.silver_records:
                fid = r.get("feedback_id")
                if fid:
                    seen[fid] = (
                        fid, r.get("vehicle_vin"), r.get("trip_id"), r.get("customer_id"),
                        str(r.get("scenario_date") or ""), _int_or_none(r.get("assigned_day_index")),
                        r.get("topic"), _int_or_none(r.get("sentiment")), r.get("raw_comment_text"),
                        r.get("subject_zone"), r.get("country"), r.get("lineage_hash"), run_id
                    )
            values = list(seen.values())
            sql = f"""
                INSERT INTO {table_name} ({', '.join(cols)})
                VALUES %s
                ON CONFLICT (feedback_id) DO UPDATE SET
                    _run_id = EXCLUDED._run_id,
                    lineage_hash = EXCLUDED.lineage_hash,
                    _processed_at = CURRENT_TIMESTAMP
            """
            if values:
                execute_values(cur, sql, values)

        elif "fleet" in dataset_id:
            table_name = "silver.fleet_index"
            cols = ["vehicle_vin", "vehicle_type", "telemetry_equipped",
                    "subject_zone", "country", "lineage_hash", "_run_id"]
            seen = {}
            for r in result.silver_records:
                vin = r.get("vehicle_vin")
                if vin:
                    seen[vin] = (
                        vin, r.get("vehicle_type"),
                        bool(r.get("telemetry_equipped")) if r.get("telemetry_equipped") is not None else None,
                        r.get("subject_zone"), r.get("country"), r.get("lineage_hash"), run_id
                    )
            values = list(seen.values())
            sql = f"""
                INSERT INTO {table_name} ({', '.join(cols)})
                VALUES %s
                ON CONFLICT (vehicle_vin) DO UPDATE SET
                    _run_id = EXCLUDED._run_id,
                    lineage_hash = EXCLUDED.lineage_hash,
                    _processed_at = CURRENT_TIMESTAMP
            """
            if values:
                execute_values(cur, sql, values)

        elif "synthetic_feedback" in dataset_id or "feedback_scenario" in dataset_id:
            table_name = "silver.synthetic_feedback_scenario_driven"
            cols = ["feedback_id", "vehicle_vin", "scenario_date",
                    "assigned_day_index", "topic", "sentiment", "raw_comment_text",
                    "subject_zone", "country", "lineage_hash", "_run_id"]
            seen = {}
            for r in result.silver_records:
                fid = r.get("feedback_id")
                if fid:
                    seen[fid] = (
                        fid, r.get("vehicle_vin"), str(r.get("scenario_date") or ""),
                        _int_or_none(r.get("assigned_day_index")), r.get("topic"),
                        _int_or_none(r.get("sentiment")), r.get("raw_comment_text"),
                        r.get("subject_zone"), r.get("country"), r.get("lineage_hash"), run_id
                    )
            values = list(seen.values())
            sql = f"""
                INSERT INTO {table_name} ({', '.join(cols)})
                VALUES %s
                ON CONFLICT (feedback_id) DO UPDATE SET
                    _run_id = EXCLUDED._run_id,
                    lineage_hash = EXCLUDED.lineage_hash,
                    _processed_at = CURRENT_TIMESTAMP
            """
            if values:
                execute_values(cur, sql, values)

        else:
            # Generic Silver persistence
            table_name = "silver.generic_clean_records"
            seen = {}
            for r in result.silver_records:
                pk = str(
                    r.get("_raw_id")
                    or (f"{r.get('session_id')}_{r.get('event_sequence_index')}" if r.get("event_sequence_index") is not None and r.get("session_id") else None)
                    or r.get("id")
                    or r.get("session_id")
                    or r.get("feedback_id")
                    or uuid.uuid4()
                )
                seen[pk] = (
                    pk, dataset_id, Json(r), r.get("subject_zone"), r.get("country"), r.get("lineage_hash"), run_id
                )
            values = list(seen.values())
            sql = f"""
                INSERT INTO {table_name} (record_pk, dataset_id, treated_payload, subject_zone, country, lineage_hash, _run_id)
                VALUES %s
                ON CONFLICT (dataset_id, record_pk) DO UPDATE SET
                    _run_id = EXCLUDED._run_id,
                    treated_payload = EXCLUDED.treated_payload,
                    lineage_hash = EXCLUDED.lineage_hash,
                    _processed_at = CURRENT_TIMESTAMP
            """
            if values:
                execute_values(cur, sql, values)

    # 2. Persist Quarantine records (Full Raw)
    if result.quarantine_records:
        q_cols = ["quarantine_id", "run_id", "dataset_id", "source_table", "source_row_pk",
                  "failure_lane", "violation_column", "violation_rule_id", "violation_reason",
                  "violation_severity", "raw_record_json", "lineage_hash", "status"]
        if jurisdiction_schema_ready:
            q_cols.extend([
                "subject_zone", "country", "jurisdiction_chain", "matched_policy_id",
                "matched_policy_name", "matched_law_ref", "policy_snapshot",
                "applied_policy_ids", "policy_violations",
            ])
        q_values = []
        for r in result.quarantine_records:
            values = [
                r["quarantine_id"], r["run_id"], r["dataset_id"], r.get("source_table"), r.get("source_row_pk"),
                r["failure_lane"], r.get("violation_column"), r.get("violation_rule_id"), r["violation_reason"],
                r.get("violation_severity", "CRITICAL"), Json(r["raw_record_json"]), r["lineage_hash"], r.get("status", "QUARANTINED"),
            ]
            if jurisdiction_schema_ready:
                values.extend([
                    r.get("subject_zone"), r.get("country"), r.get("jurisdiction_chain", []),
                    r.get("matched_policy_id"), r.get("matched_policy_name"), r.get("matched_law_ref"),
                    Json(r["policy_snapshot"]) if r.get("policy_snapshot") else None,
                    Json(r.get("applied_policy_ids", [])), Json(r.get("policy_violations", [])),
                ])
            q_values.append(tuple(values))
        q_sql = f"""
            INSERT INTO quarantine.records ({', '.join(q_cols)})
            VALUES %s
            ON CONFLICT (quarantine_id) DO NOTHING
        """
        execute_values(cur, q_sql, q_values)

    # 3. Persist Warning records (PII-controlled / redacted)
    if result.warning_records:
        w_cols = ["warning_id", "run_id", "dataset_id", "source_row_pk", "signal_lane",
                  "signal_layer", "warning_type", "warning_reason", "score_or_zvalue",
                  "evidence_json", "redacted_record_json", "lineage_hash"]
        w_values = [
            (
                r["warning_id"], r["run_id"], r["dataset_id"], r.get("source_row_pk"), r["signal_lane"],
                r.get("signal_layer"), r["warning_type"], r["warning_reason"], _float_or_none(r.get("score_or_zvalue")),
                Json(r.get("evidence_json", {})), Json(r["redacted_record_json"]), r["lineage_hash"]
            )
            for r in result.warning_records
        ]
        w_sql = f"""
            INSERT INTO warning.records ({', '.join(w_cols)})
            VALUES %s
            ON CONFLICT (warning_id) DO NOTHING
        """
        execute_values(cur, w_sql, w_values)

    # 4. Upsert Pipeline Run tracking with not_evaluated_count
    not_eval = max(0, result.scanned_count - result.silver_count - result.quarantine_count)
    cur.execute("""
        INSERT INTO orchestration.pipeline_runs 
        (run_id, dag_id, dataset_id, started_at, ended_at, status, scanned_count, silver_count, quarantine_count, warning_count, not_evaluated_count, current_step, current_step_progress)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (run_id) DO UPDATE SET
            ended_at = EXCLUDED.ended_at,
            status = EXCLUDED.status,
            scanned_count = EXCLUDED.scanned_count,
            silver_count = EXCLUDED.silver_count,
            quarantine_count = EXCLUDED.quarantine_count,
            warning_count = EXCLUDED.warning_count,
            not_evaluated_count = EXCLUDED.not_evaluated_count,
            current_step = EXCLUDED.current_step,
            current_step_progress = EXCLUDED.current_step_progress;
    """, (
        run_id, "datatrust_adaptive_pipeline", dataset_id,
        datetime.now(timezone.utc), datetime.now(timezone.utc), "SUCCESS",
        result.scanned_count, result.silver_count, result.quarantine_count, result.warning_count,
        not_eval, "SILVER", 100
    ))

    # 5. Aggregate Findings into audit.findings & audit.finding_quarantine_records
    if result.quarantine_records and jurisdiction_schema_ready:
        try:
            cur.execute("""
                INSERT INTO audit.findings (
                    finding_id, run_id, dataset_id, rule_id, policy_id, policy_name, law_ref,
                    jurisdiction, country, jurisdiction_chain, policy_snapshot,
                    column_name, severity, status, reason, impact, failed_record_count, detected_at
                )
                SELECT 
                    'F-' || substring(md5(concat_ws('|', q.run_id, q.dataset_id,
                        coalesce(q.violation_rule_id, 'UNKNOWN_RULE'),
                        coalesce(q.violation_column, 'DATA_INTEGRITY'),
                        coalesce(q.violation_severity, 'HIGH'),
                        q.normalized_zone,
                        coalesce(q.normalized_country, ''),
                        coalesce(q.matched_policy_id, ''),
                        coalesce(q.matched_law_ref, ''),
                        coalesce(md5(q.policy_snapshot::text), ''))) from 1 for 10) as finding_id,
                    q.run_id,
                    q.dataset_id,
                    coalesce(q.violation_rule_id, 'UNKNOWN_RULE') as rule_id,
                    q.matched_policy_id as policy_id,
                    q.matched_policy_name as policy_name,
                    q.matched_law_ref as law_ref,
                    q.normalized_zone as jurisdiction,
                    q.normalized_country as country,
                    q.jurisdiction_chain,
                    q.policy_snapshot,
                    coalesce(q.violation_column, 'DATA_INTEGRITY') as column_name,
                    coalesce(q.violation_severity, 'HIGH') as severity,
                    'OPEN' as status,
                    min(q.violation_reason) as reason,
                    'Vi phạm an toàn dữ liệu và kiểm toán IPO: ' || min(q.violation_reason) as impact,
                    count(*) as failed_record_count,
                    CURRENT_TIMESTAMP as detected_at
                FROM (
                    SELECT source.*,
                           upper(trim(coalesce(source.subject_zone, 'GLOBAL'))) AS normalized_zone,
                           nullif(upper(trim(source.country)), '') AS normalized_country
                    FROM quarantine.records source
                ) q
                WHERE q.run_id = %s
                GROUP BY q.run_id, q.dataset_id, q.violation_rule_id, q.violation_column,
                    q.violation_severity, q.normalized_zone, q.normalized_country, q.jurisdiction_chain,
                    q.matched_policy_id, q.matched_policy_name, q.matched_law_ref, q.policy_snapshot
                ON CONFLICT (finding_id) DO UPDATE SET
                    failed_record_count = EXCLUDED.failed_record_count,
                    reason = EXCLUDED.reason,
                    policy_id = EXCLUDED.policy_id,
                    policy_name = EXCLUDED.policy_name,
                    law_ref = EXCLUDED.law_ref,
                    jurisdiction = EXCLUDED.jurisdiction,
                    country = EXCLUDED.country,
                    jurisdiction_chain = EXCLUDED.jurisdiction_chain,
                    policy_snapshot = EXCLUDED.policy_snapshot;
            """, (run_id,))

            # Link individual quarantine records
            cur.execute("""
                INSERT INTO audit.finding_quarantine_records (finding_id, quarantine_id)
                SELECT 
                    f.finding_id,
                    q.quarantine_id
                FROM quarantine.records q
                JOIN audit.findings f 
                    ON f.finding_id = 'F-' || substring(md5(concat_ws('|', q.run_id, q.dataset_id,
                        coalesce(q.violation_rule_id, 'UNKNOWN_RULE'),
                        coalesce(q.violation_column, 'DATA_INTEGRITY'),
                        coalesce(q.violation_severity, 'HIGH'),
                        upper(trim(coalesce(q.subject_zone, 'GLOBAL'))),
                        coalesce(upper(trim(q.country)), ''),
                        coalesce(q.matched_policy_id, ''),
                        coalesce(q.matched_law_ref, ''),
                        coalesce(md5(q.policy_snapshot::text), ''))) from 1 for 10)
                WHERE q.run_id = %s
                ON CONFLICT (finding_id, quarantine_id) DO NOTHING;
            """, (run_id,))
        except Exception as e_find:
            print(f"Notice: Findings aggregation: {e_find}")
    elif result.quarantine_records:
        print("Notice: jurisdiction migration is pending; Findings aggregation was skipped to avoid cross-zone attribution")

    # 6. Update step states in orchestration.pipeline_run_steps
    try:
        cur.execute("""
            INSERT INTO orchestration.pipeline_run_steps (run_id, step_name, step_order, status, started_at, ended_at)
            VALUES (%s, 'EVALUATION', 3, 'COMPLETED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (run_id, step_name) DO UPDATE SET status = 'COMPLETED', ended_at = CURRENT_TIMESTAMP;
        """, (run_id,))
        cur.execute("""
            INSERT INTO orchestration.pipeline_run_steps (run_id, step_name, step_order, status, started_at, ended_at)
            VALUES (%s, 'SILVER', 4, 'COMPLETED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (run_id, step_name) DO UPDATE SET status = 'COMPLETED', ended_at = CURRENT_TIMESTAMP;
        """, (run_id,))
    except Exception as e_step:
        print(f"Notice: Step tracking: {e_step}")

    conn.commit()


def _float_or_none(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _int_or_none(val: Any) -> Optional[int]:
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None
