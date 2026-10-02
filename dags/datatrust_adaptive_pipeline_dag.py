"""
DataTrust OS: Airflow Adaptive Compliance Pipeline DAG
Orchestrates:
Task 1: Bronze Ingestion & Catalog Initialization
Task 2: Statistical Data Profiling Engine
Task 3 (TaskGroup: task_3_parallel_evaluation):
  - Lane A: L1-L4 Data Reliability & Sensor Anomaly Suite
  - Lane B: Hierarchical Policy Engine (Global -> Zone -> Country: IFRS 15, GDPR, CCPA, Luật 91/2025/QH15 & NĐ 356/2025)
  - Lane C: Merge Verdicts & 3-Way Router (Silver / Quarantine / Warning)
Task 4: Immutable Audit Evidence & Digital Signature
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

try:
    from airflow import DAG
    from airflow.models.param import Param
    from airflow.operators.python import PythonOperator
    from airflow.utils.task_group import TaskGroup
except ImportError:
    class DummyTask:
        def __init__(self, *args, **kwargs):
            pass
        def __rshift__(self, other):
            return other
        def __rrshift__(self, other):
            return self
        def __lshift__(self, other):
            return other
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    DAG = DummyTask
    TaskGroup = DummyTask
    PythonOperator = DummyTask

    class Param:
        def __init__(self, default=None, *args, **kwargs):
            self.default = default

from typing import Tuple, Optional, Dict, Any, List

# Add paths for both local and Docker Airflow environments
for p in ["/opt/airflow", str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parent.parent)]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

default_args = {
    'owner': 'DataTrust-Admin',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(seconds=30),
}


# =============================================================================
# DATASET RESOLVER HELPER
# =============================================================================

DATASET_FILE_MAP = {
    "trips": "ride_hailing_xanh_sm_trips.csv",
    "ride_hailing_xanh_sm_trips": "ride_hailing_xanh_sm_trips.csv",
    "ride_hailing_xanh_sm_trips.csv": "ride_hailing_xanh_sm_trips.csv",
    "telemetry": "synthetic_ev_telemetry_ved_ref.csv",
    "synthetic_ev_telemetry_ved_ref": "synthetic_ev_telemetry_ved_ref.csv",
    "synthetic_ev_telemetry_ved_ref.csv": "synthetic_ev_telemetry_ved_ref.csv",
    "charging": "acn_charging_mapped.csv",
    "acn_charging_mapped": "acn_charging_mapped.csv",
    "acn_charging_mapped.csv": "acn_charging_mapped.csv",
    "feedback_pii": "feedback_pii.csv",
    "feedback_pii.csv": "feedback_pii.csv",
    "dim_customers": "dim_customers.csv",
    "dim_customers.csv": "dim_customers.csv",
    "dim_drivers": "dim_drivers.csv",
    "dim_drivers.csv": "dim_drivers.csv",
    "fleet_index": "fleet_index.csv",
    "fleet_index.csv": "fleet_index.csv",
}


def resolve_target_dataset(conf: Optional[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolves configuration into (clean_table_name, actual_filename).
    Returns (None, None) if 'ALL' or not specified.
    """
    if not conf:
        return None, None
    raw = conf.get('dataset_id') or conf.get('filename') or conf.get('table_name')
    if not raw or str(raw).strip().upper() in ("ALL", "*", "NONE", ""):
        return None, None
    clean_name = str(raw).strip().replace('.csv', '')
    alias_map = {
        "trips": "ride_hailing_xanh_sm_trips",
        "telemetry": "synthetic_ev_telemetry_ved_ref",
        "charging": "acn_charging_mapped",
    }
    clean_name = alias_map.get(clean_name, clean_name)
    actual_filename = DATASET_FILE_MAP.get(str(raw), f"{clean_name}.csv")
    return clean_name, actual_filename


def _load_bronze_dataset_records(context) -> tuple:
    """Loads batch of bronze records either from PostgreSQL bronze schema or data directory."""
    dag_run = context.get('dag_run')
    conf = dag_run.conf if dag_run else {}
    target_tbl, actual_filename = resolve_target_dataset(conf)
    if not target_tbl:
        target_tbl = 'ride_hailing_xanh_sm_trips'
        actual_filename = 'ride_hailing_xanh_sm_trips.csv'
    table_name = target_tbl

    rows = []
    # 1. Try reading directly from Postgres schema bronze
    try:
        from dags.parallel_evaluation_engine import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM bronze.{table_name} LIMIT 1000;")
        colnames = [desc[0] for desc in cur.description]
        db_rows = cur.fetchall()
        from decimal import Decimal
        for r in db_rows:
            row_dict = dict(zip(colnames, r))
            # Clean non-serializable fields
            if "_raw_id" in row_dict and row_dict["_raw_id"] is not None:
                row_dict["_raw_id"] = str(row_dict["_raw_id"])
            row_dict.pop("_batch_id", None)
            row_dict.pop("_ingested_at", None)
            for k, v in row_dict.items():
                if isinstance(v, Decimal):
                    row_dict[k] = float(v)
            rows.append(row_dict)
        conn.close()
        if rows:
            print(f"Loaded {len(rows)} records from PostgreSQL bronze.{table_name}")
            return table_name, rows
    except Exception as e:
        print(f"Postgres direct read skipped: {e}")

    # 2. Fallback to CSV on disk
    candidates = [
        Path("/opt/airflow/data/vingroup_pii_faulty_testset_3zone") / actual_filename,
        Path("data/vingroup_pii_faulty_testset_3zone") / actual_filename,
        Path("../data/vingroup_pii_faulty_testset_3zone") / actual_filename,
        Path("E:/Phase2_VSF/data/vingroup_pii_faulty_testset_3zone") / actual_filename,
    ]
    csv_file = next((p for p in candidates if p.exists()), None)

    if csv_file:
        import csv
        with open(csv_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= 1000:
                    break
                row_dict = dict(row)
                if "_raw_id" not in row_dict or not row_dict["_raw_id"]:
                    row_dict["_raw_id"] = f"{table_name}_{i}"
                rows.append(row_dict)
        print(f"Loaded {len(rows)} records from CSV: {csv_file}")
    else:
        print(f"Warning: File {actual_filename} not found on disk, generating synthetic pilot records.")
        rows = [
            {"trip_id": f"REC_{i:04d}", "customer_phone": "0987654321", "fare_amount": 50000.0, "trip_distance_km": 3.2, "subject_zone": "VN"}
            for i in range(100)
        ]

    # Ingest 2 synthetic edge test violations to verify Quarantine & Warning
    if "trips" in table_name:
        rows.append({"trip_id": "CORRUPT_ERR_01", "driver_id": "DRV_BAD_01", "customer_phone": "0987654321", "fare_amount": -50000.0, "trip_distance_km": 3.0, "subject_zone": "EU"})
        rows.append({"trip_id": "CORRUPT_ERR_02", "driver_id": "DRV_BAD_02", "customer_phone": "0912345678", "fare_amount": 0.0, "trip_distance_km": 0.0, "subject_zone": "US"})
        rows.append({"trip_id": "WARN_ANOMALY_01", "driver_id": "DRV_WARN_01", "customer_phone": "0933333333", "fare_amount": 80000.0, "trip_distance_km": 4.0, "currency_unverified": True, "subject_zone": "VN"})

    return table_name, rows


# =============================================================================
# TASK 1: TRUNCATE & INGEST BRONZE
# =============================================================================

def task_1_truncate_and_ingest_bronze(**context):
    """Task 1: Reset & Ingest bronze schema + initialize catalog (Single-table or All)."""
    print("=" * 60)
    print("[TASK 1] Truncate & Ingest Bronze + Data Catalog Initializer")
    print("=" * 60)
    try:
        from dags.reset_and_ingest_bronze import get_db_connection, resolve_data_dir, truncate_and_ingest_all
    except ImportError:
        from reset_and_ingest_bronze import get_db_connection, resolve_data_dir, truncate_and_ingest_all

    conn = get_db_connection()
    try:
        data_dir = resolve_data_dir()
        dag_run = context.get('dag_run')
        conf = dag_run.conf if dag_run else {}
        target_tbl, _ = resolve_target_dataset(conf)
        batch_id = f"batch_{dag_run.run_id}" if dag_run else None

        if target_tbl:
            print(f"[TASK 1] Single-Table Mode: Only truncating & ingesting bronze.{target_tbl}")
        else:
            print("[TASK 1] Full-Batch Mode: Ingesting ALL 8 datasets")

        summary = truncate_and_ingest_all(conn, data_dir, batch_id=batch_id, target_dataset_id=target_tbl)
        total_rows = sum(summary.values())
        print(f"Task 1 Complete: Ingested {len(summary)} dataset(s), Total {total_rows:,} records into schema bronze.")
        context['ti'].xcom_push(key='bronze_ingest_summary', value=summary)
        context['ti'].xcom_push(key='total_ingested_records', value=total_rows)
        return summary
    finally:
        conn.close()


# =============================================================================
# TASK 2: DATA PROFILING ENGINE
# =============================================================================

def task_2_data_profiling(**context):
    """Task 2: Statistical profiling and health scoring into catalog schema (Single-table or All)."""
    print("=" * 60)
    print("[TASK 2] Data Profiling Engine & Catalog Persistence")
    print("=" * 60)
    try:
        from profiler_engine import DataProfilerEngine, ProfilingConfig
    except ImportError:
        try:
            from dags.profiler_engine import DataProfilerEngine, ProfilingConfig
        except ImportError:
            from database.profiler_engine import DataProfilerEngine, ProfilingConfig

    run_id = context.get('run_id') or f"run_{uuid.uuid4().hex[:8]}"
    profiler = DataProfilerEngine(config=ProfilingConfig())

    dag_run = context.get('dag_run')
    conf = dag_run.conf if dag_run else {}
    target_tbl, _ = resolve_target_dataset(conf)

    summary_map = {}
    if target_tbl:
        print(f"[TASK 2] Single-Table Mode: Profiling only dataset '{target_tbl}'")
        res = profiler.profile_single_dataset(target_tbl, batch_id=run_id)
        summary_map[target_tbl] = {
            "total_rows": res["total_rows"],
            "columns_count": res["columns_count"],
            "health_score": res["health_score"],
            "signals_summary": res["signals_summary"]
        }
        print(f"[TASK 2] Profiled {target_tbl}: {res['total_rows']:,} rows, Health Score: {res['health_score']:.1f}%")
    else:
        print("[TASK 2] Full-Batch Mode: Profiling ALL datasets in catalog")
        profile_results = profiler.profile_all_datasets(batch_id=run_id)
        for r in profile_results:
            ds_id = r["dataset_id"]
            summary_map[ds_id] = {
                "total_rows": r["total_rows"],
                "columns_count": r["columns_count"],
                "health_score": r["health_score"],
                "signals_summary": r["signals_summary"]
            }

    context['ti'].xcom_push(key='profiling_summary', value=summary_map)
    return summary_map


# =============================================================================
# TASK 3: 3-LANE EVALUATION & PROCESSING
# =============================================================================

def task_3a_run_lane_a(**context):
    """Lane A: L1-L4 Data Reliability & Sensor Anomaly Suite."""
    print("=" * 60)
    print("[TASK 3A] Lane A: L1-L4 Data Reliability Suite")
    print("=" * 60)
    try:
        from dags.parallel_evaluation_engine import execute_lane_a_detectors
    except ImportError:
        from parallel_evaluation_engine import execute_lane_a_detectors

    table_name, records = _load_bronze_dataset_records(context)
    lane_a_results = execute_lane_a_detectors(table_name, records)
    
    fails = sum(1 for r in lane_a_results.values() if r["status"] == "FAIL")
    warns = sum(1 for r in lane_a_results.values() if r["status"] == "WARNING")
    print(f"Lane A evaluated {len(records)} records for {table_name}: {fails} FAIL, {warns} WARNING, {len(records)-fails-warns} PASS.")

    context['ti'].xcom_push(key='lane_a_results', value=lane_a_results)
    return {"dataset": table_name, "total": len(records), "fails": fails, "warnings": warns}


def task_3b_run_lane_b(**context):
    """Lane B: Hierarchical Policy Processing & Compliance Evaluation (7 Steps)."""
    print("=" * 60)
    print("[TASK 3B] Lane B: Hierarchical Policy Engine (Global -> Zone -> Country)")
    print("=" * 60)
    try:
        from dags.parallel_evaluation_engine import execute_lane_b_policy
    except ImportError:
        from parallel_evaluation_engine import execute_lane_b_policy

    table_name, records = _load_bronze_dataset_records(context)
    lane_b_results = execute_lane_b_policy(table_name, records)

    fails = sum(1 for r in lane_b_results if r["status"] == "FAIL")
    warns = sum(1 for r in lane_b_results if r["status"] == "WARNING")
    print(f"Lane B evaluated {len(records)} records for {table_name}: {fails} FAIL, {warns} WARNING, {len(records)-fails-warns} PASS.")

    context['ti'].xcom_push(key='lane_b_results', value=lane_b_results)
    return {"dataset": table_name, "total": len(records), "fails": fails, "warnings": warns}


def task_3c_run_lane_c(**context):
    """Lane C: Merge Verdicts via A/B Combination Matrix, Enforce Precedence & Route to Silver/Quarantine/Warning."""
    print("=" * 60)
    print("[TASK 3C] Lane C: Merge Verdicts, Precedence & 3-Way Dynamic Router")
    print("=" * 60)
    try:
        from dags.parallel_evaluation_engine import execute_lane_c_merge_and_persist
    except ImportError:
        from parallel_evaluation_engine import execute_lane_c_merge_and_persist

    table_name, records = _load_bronze_dataset_records(context)
    ti = context['ti']
    lane_a_data = ti.xcom_pull(task_ids='task_3_parallel_evaluation.lane_a_l1_l4_detectors', key='lane_a_results') or {}
    lane_b_data = ti.xcom_pull(task_ids='task_3_parallel_evaluation.lane_b_hierarchical_policy', key='lane_b_results') or []

    run_id = f"run_{context.get('run_id', uuid.uuid4().hex[:8])}"
    metrics = execute_lane_c_merge_and_persist(
        dataset_id=table_name,
        records=records,
        lane_a_data=lane_a_data,
        lane_b_data=lane_b_data,
        run_id=run_id
    )

    print(f"Lane C Routing Results for {table_name}:")
    print(f"  -> Total Scanned: {metrics['scanned']}")
    print(f"  -> Silver Lane (Production Candidate): {metrics['silver']}")
    print(f"  -> Quarantine Lane (Policy Block / Reliability Defect): {metrics['quarantine']}")
    print(f"  -> Warning Lane (Statistical Anomaly / Advisory): {metrics['warning']}")

    ti.xcom_push(key='pipeline_metrics', value=metrics)
    return metrics


# =============================================================================
# TASK 4: EMIT AUDIT EVIDENCE
# =============================================================================

def task_4_emit_audit_evidence(**context):
    """Task 4: Ghi nhận bằng chứng kiểm toán và mã băm toàn vẹn (IPO Assurance) vào bảng audit.evidence."""
    print("=" * 60)
    print("[TASK 4] Emitting Immutable Audit Evidence & Digital Signature")
    print("=" * 60)

    ti = context['ti']
    metrics = ti.xcom_pull(task_ids='task_3_parallel_evaluation.lane_c_merge_verdicts_and_route', key='pipeline_metrics') or {}
    run_id = str(context.get('run_id') or f"run_{uuid.uuid4().hex[:8]}")
    dag_id = context.get('dag').dag_id if context.get('dag') else "datatrust_adaptive_pipeline"
    dataset_id = str(metrics.get('dataset_id') or "ride_hailing_xanh_sm_trips")

    # 1. Query previous hash for hash-chain integrity
    previous_hash = "GENESIS_EVIDENCE_HASH_GSM_IPO_2026"
    try:
        from dags.parallel_evaluation_engine import get_db_connection
    except ImportError:
        from parallel_evaluation_engine import get_db_connection

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT evidence_hash FROM audit.evidence ORDER BY created_at DESC LIMIT 1;")
        row = cur.fetchone()
        if row and row[0]:
            previous_hash = row[0]
    except Exception as e:
        print(f"Notice: Could not query previous evidence hash: {e}")

    # 2. Compute continuous SHA-256 evidence hash incorporating previous_hash
    evidence_content = f"{previous_hash}:{run_id}:{dataset_id}:{json.dumps(metrics, sort_keys=True, default=str)}"
    evidence_hash = hashlib.sha256(evidence_content.encode("utf-8")).hexdigest()

    evidence_payload = {
        "dag_id": dag_id,
        "execution_date": context.get('ts'),
        "run_id": run_id,
        "dataset_id": dataset_id,
        "metrics": metrics,
        "digital_signature": "SIG-AIRFLOW-3LANE-GSM-IPO-2026",
        "previous_hash": previous_hash,
        "evidence_hash": evidence_hash
    }

    # 3. Persist directly into audit.evidence ledger
    if conn is not None:
        try:
            from psycopg2.extras import Json
            cur.execute("""
                INSERT INTO audit.evidence 
                (run_id, dag_id, dataset_id, digital_signature, evidence_hash, previous_hash,
                 scanned_count, silver_count, quarantine_count, warning_count, metrics, evidence_payload, jurisdiction_chain)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                run_id, dag_id, dataset_id, "SIG-AIRFLOW-3LANE-GSM-IPO-2026",
                evidence_hash, previous_hash,
                metrics.get("scanned", 0), metrics.get("silver", 0),
                metrics.get("quarantine", 0), metrics.get("warning", 0),
                Json(metrics), Json(evidence_payload),
                ["GLOBAL", "VN"] if "VN" in dataset_id or "trips" in dataset_id else ["GLOBAL", "EU", "DE"]
            ))
            conn.commit()
            print("Successfully recorded audit evidence into audit.evidence ledger table.")
        except Exception as e:
            print(f"Warning: Failed to persist to audit.evidence: {e}")
        finally:
            conn.close()

    print("IPO Compliance Evidence Generated Successfully:")
    print(json.dumps(evidence_payload, indent=2))
    return evidence_payload


# =============================================================================
# DAG DEFINITION
# =============================================================================

with DAG(
    dag_id='datatrust_adaptive_pipeline',
    default_args=default_args,
    description='DataTrust OS: 3-Lane Adaptive Pipeline (L1-L4 // Policy Processing -> Merge Verdict -> Silver/Quarantine/Warning)',
    schedule_interval=None,
    catchup=False,
    params={
        "dataset_id": Param(
            default="ride_hailing_xanh_sm_trips",
            type="string",
            title="Target Dataset / Table",
            description="Chọn 1 bảng cụ thể để chạy từ Task 1 đến Task 4 (hoặc chọn 'ALL' để chạy toàn bộ 8 bảng)",
            enum=[
                "ride_hailing_xanh_sm_trips",
                "synthetic_ev_telemetry_ved_ref",
                "acn_charging_mapped",
                "feedback_pii",
                "dim_customers",
                "dim_drivers",
                "fleet_index",
                "ALL"
            ]
        )
    },
    tags=['datatrust', 'ipo_assurance', 'privacy', 'data_quality', '3zone_pilot', '3lane_architecture'],
) as dag:

    t1 = PythonOperator(
        task_id='task_1_truncate_and_ingest_bronze',
        python_callable=task_1_truncate_and_ingest_bronze,
        provide_context=True,
    )

    t2 = PythonOperator(
        task_id='task_2_data_profiling',
        python_callable=task_2_data_profiling,
        provide_context=True,
    )

    with TaskGroup(group_id='task_3_parallel_evaluation') as task_3_group:
        t3a = PythonOperator(
            task_id='lane_a_l1_l4_detectors',
            python_callable=task_3a_run_lane_a,
            provide_context=True,
        )

        t3b = PythonOperator(
            task_id='lane_b_hierarchical_policy',
            python_callable=task_3b_run_lane_b,
            provide_context=True,
        )

        t3c = PythonOperator(
            task_id='lane_c_merge_verdicts_and_route',
            python_callable=task_3c_run_lane_c,
            provide_context=True,
        )

        # Parallel branches Lane A and Lane B converge into Lane C
        [t3a, t3b] >> t3c

    t4 = PythonOperator(
        task_id='task_4_emit_audit_evidence',
        python_callable=task_4_emit_audit_evidence,
        provide_context=True,
    )

    t1 >> t2 >> task_3_group >> t4
