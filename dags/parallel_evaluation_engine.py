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
from backend.engine.hierarchical_policy_processor import HierarchicalPolicyProcessor, LaneBVerdict
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
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        clean_ds = dataset_id.replace(".csv", "").replace("bronze.", "")
        cur.execute("""
            SELECT column_name, operation_id, params_json, description
            FROM policy.data_treatment_rules
            WHERE status = 'active' AND (dataset_id = %s OR dataset_id = %s OR dataset_id = %s);
        """, (clean_ds, f"{clean_ds}.csv", f"bronze.{clean_ds}"))
        rows = cur.fetchall()
        treatments = []
        for r in rows:
            treatments.append({
                "column": r[0],
                "operation_id": r[1],
                "params": r[2] if isinstance(r[2], dict) else {},
                "law_ref": r[3] or "Luật 91/2025/QH15 & NĐ 356/2025/NĐ-CP"
            })
        conn.close()
        return treatments
    except Exception as e:
        return []


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
            "jurisdiction_chain": v.jurisdiction_chain
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
            jurisdiction_chain=d.get("jurisdiction_chain", [])
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
        q_values = [
            (
                r["quarantine_id"], r["run_id"], r["dataset_id"], r.get("source_table"), r.get("source_row_pk"),
                r["failure_lane"], r.get("violation_column"), r.get("violation_rule_id"), r["violation_reason"],
                r.get("violation_severity", "CRITICAL"), Json(r["raw_record_json"]), r["lineage_hash"], r.get("status", "QUARANTINED")
            )
            for r in result.quarantine_records
        ]
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

    # 4. Upsert Pipeline Run tracking
    cur.execute("""
        INSERT INTO orchestration.pipeline_runs 
        (run_id, dag_id, dataset_id, started_at, ended_at, status, scanned_count, silver_count, quarantine_count, warning_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (run_id) DO UPDATE SET
            ended_at = EXCLUDED.ended_at,
            status = EXCLUDED.status,
            scanned_count = EXCLUDED.scanned_count,
            silver_count = EXCLUDED.silver_count,
            quarantine_count = EXCLUDED.quarantine_count,
            warning_count = EXCLUDED.warning_count;
    """, (
        run_id, "datatrust_adaptive_pipeline", dataset_id,
        datetime.now(timezone.utc), datetime.now(timezone.utc), "SUCCESS",
        result.scanned_count, result.silver_count, result.quarantine_count, result.warning_count
    ))

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
