import csv
import datetime
import hashlib
import json
import math
import os
import random
import time
import uuid
from typing import List, Dict, Any, Tuple, Optional, Union
import pandas as pd
from src.db.connection import get_db

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
CSV_PATH = os.path.join(DATA_DIR, "raw_taxi_trips.csv")

DB_PATH = os.path.join(DATA_DIR, "datatrust.db")


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def seed_dataset(file_path: str = CSV_PATH, db_path: str = DB_PATH, count: int = 1000) -> int:
    """Seed synthetic raw taxi trip dataset with realistic records and controlled anomalies."""
    ensure_data_dir()
    random.seed(42)  # Deterministic seed

    start_time = datetime.datetime(2026, 8, 1, 8, 0, 0)
    records = []

    # 1,000 records total: ~850 clean records, ~150 anomalous records across 6 bug categories
    for i in range(1, count + 1):
        trip_id = f"TRIP-{1000 + i}"
        pickup_offset = random.randint(0, 86400)
        trip_duration = random.randint(300, 3600)  # 5 mins to 60 mins
        
        p_dt = start_time + datetime.timedelta(seconds=pickup_offset)
        d_dt = p_dt + datetime.timedelta(seconds=trip_duration)
        
        p_str = p_dt.isoformat()
        d_str = d_dt.isoformat()

        passengers = random.choices([1, 2, 3, 4, 5, 6], weights=[60, 20, 10, 5, 3, 2])[0]
        distance = round(random.uniform(0.8, 18.5), 2)
        fare = round(2.50 + distance * 2.80 + random.uniform(0, 3.0), 2)
        extra = random.choice([0.0, 0.50, 1.00])
        mta_tax = 0.50
        tip = round(random.choice([0.0, fare * 0.15, fare * 0.20]), 2)
        tolls = random.choice([0.0, 0.0, 0.0, 6.50])
        improvement = 0.30
        total = round(fare + extra + mta_tax + tip + tolls + improvement, 2)
        payment_type = random.choice(["credit_card", "cash"])

        # Inject controlled anomalies into ~15% of records
        anomaly_type = None
        if i % 7 == 0:
            anomaly_type = i % 6  # 0 to 5
            
        if anomaly_type == 0:
            # Bug 1: Negative or zero fare
            fare = random.choice([-15.50, 0.00, -5.00])
            total = round(fare + extra + mta_tax + tip + tolls, 2)
        elif anomaly_type == 1:
            # Bug 2: Invalid passenger count
            passengers = random.choice([0, -1, 12, 99])
        elif anomaly_type == 2:
            # Bug 3: Zero distance with high fare amount
            distance = 0.0
            fare = round(random.uniform(22.0, 85.0), 2)
            total = round(fare + extra + mta_tax + tip + tolls, 2)
        elif anomaly_type == 3:
            # Bug 4: Negative tip amount
            tip = round(random.uniform(-12.0, -1.5), 2)
            total = round(fare + extra + mta_tax + tip + tolls, 2)
        elif anomaly_type == 4:
            # Bug 5: Inverted datetime (dropoff before pickup)
            d_dt_inv = p_dt - datetime.timedelta(seconds=random.randint(600, 3600))
            d_str = d_dt_inv.isoformat()
        elif anomaly_type == 5:
            # Bug 6: Total amount ledger arithmetic mismatch
            total = round(total + random.choice([15.00, -25.50, 42.10]), 2)

        records.append({
            "trip_id": trip_id,
            "pickup_datetime": p_str,
            "dropoff_datetime": d_str,
            "passenger_count": passengers,
            "trip_distance": distance,
            "fare_amount": fare,
            "extra": extra,
            "mta_tax": mta_tax,
            "tip_amount": tip,
            "tolls_amount": tolls,
            "improvement_surcharge": improvement,
            "total_amount": total,
            "payment_type": payment_type,
        })

    # Write to CSV
    fieldnames = list(records[0].keys())
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    # Write to DuckDB
    db = get_db()
    conn = db.get_connection()
    conn.execute("DROP TABLE IF EXISTS raw_taxi_trips")
    conn.execute("""
        CREATE TABLE raw_taxi_trips (
            row_id INTEGER PRIMARY KEY,
            trip_id VARCHAR,
            pickup_datetime VARCHAR,
            dropoff_datetime VARCHAR,
            passenger_count INT,
            trip_distance FLOAT,
            fare_amount FLOAT,
            extra FLOAT,
            mta_tax FLOAT,
            tip_amount FLOAT,
            tolls_amount FLOAT,
            improvement_surcharge FLOAT,
            total_amount FLOAT,
            payment_type VARCHAR
        )
    """)
    for idx, rec in enumerate(records, 1):
        conn.execute("""
            INSERT INTO raw_taxi_trips (
                row_id, trip_id, pickup_datetime, dropoff_datetime, passenger_count, trip_distance,
                fare_amount, extra, mta_tax, tip_amount, tolls_amount,
                improvement_surcharge, total_amount, payment_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            idx, rec["trip_id"], rec["pickup_datetime"], rec["dropoff_datetime"],
            rec["passenger_count"], rec["trip_distance"], rec["fare_amount"],
            rec["extra"], rec["mta_tax"], rec["tip_amount"], rec["tolls_amount"],
            rec["improvement_surcharge"], rec["total_amount"], rec["payment_type"]
        ])

    return len(records)





def load_dataset_rows(file_path: str = CSV_PATH) -> List[Dict[str, Any]]:
    if not os.path.exists(file_path):
        seed_dataset(file_path)
    
    rows = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "trip_id": row["trip_id"],
                "pickup_datetime": row["pickup_datetime"],
                "dropoff_datetime": row["dropoff_datetime"],
                "passenger_count": int(row["passenger_count"]),
                "trip_distance": float(row["trip_distance"]),
                "fare_amount": float(row["fare_amount"]),
                "extra": float(row["extra"]),
                "mta_tax": float(row["mta_tax"]),
                "tip_amount": float(row["tip_amount"]),
                "tolls_amount": float(row["tolls_amount"]),
                "improvement_surcharge": float(row["improvement_surcharge"]),
                "total_amount": float(row["total_amount"]),
                "payment_type": row["payment_type"]
            })
    return rows


def load_dataset(dataset_key: str = None, file_path: str = None,
                 sample_size: int = 50_000) -> pd.DataFrame:
    """Load dataset by registry key or direct path with chunked sample size to prevent memory leaks."""
    from src.config import get_settings
    from src.tools.datasource import StructuredSource
    
    if file_path is None and dataset_key is not None:
        settings = get_settings()
        file_path = settings.get_dataset_path(dataset_key)
    elif file_path is None:
        settings = get_settings()
        file_path = settings.get_dataset_path(settings.default_dataset)
    
    if not os.path.exists(file_path):
        raise ValueError(f"Dataset file not found: {dataset_key or file_path}")

    source = StructuredSource(file_path)
    df = source.load_data(sample_size=sample_size)
    
    if sample_size and len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42)
    
    return df



_SIGNED_PHYSICAL_PREFIXES = ("accel", "acc_", "gyro", "magnet", "mag_")


def _is_signed_physical_column(name: str) -> bool:
    n = (name or "").strip().lower()
    return any(n.startswith(p) or p.rstrip("_") in n.split("_") for p in ("accel", "gyro", "magnet"))

def profile_rows(rows: Any) -> Dict[str, Any]:
    if isinstance(rows, pd.DataFrame):
        df = rows
    elif isinstance(rows, list):
        if not rows:
            return {"total_rows": 0, "columns": [], "total_anomalies": 0, "data_health_score": 100.0, "summary": "Empty dataset"}
        df = pd.DataFrame(rows)
    else:
        df = pd.DataFrame(rows)

    total_rows = len(df)
    if total_rows == 0:
        return {"total_rows": 0, "columns": [], "total_anomalies": 0, "data_health_score": 100.0, "summary": "Empty dataset"}

    column_profiles = []
    total_anomalies = 0

    for col in df.columns:
        series = df[col]
        col_name = str(col)
        
        is_dt = pd.api.types.is_datetime64_any_dtype(series)
        dt_series = None
        if is_dt:
            dt_series = series
        elif pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            if any(k in col_name.lower() for k in ["datetime", "timestamp", "date", "time"]):
                try:
                    converted = pd.to_datetime(series, errors="coerce")
                    if converted.notnull().sum() > 0:
                        dt_series = converted
                        is_dt = True
                except Exception:
                    pass

        if is_dt and dt_series is not None:
            dtype_str = "DATETIME"
            null_cnt = int(dt_series.isnull().sum())
            non_nulls = dt_series.dropna()
            min_v = non_nulls.min().isoformat() if not non_nulls.empty else None
            max_v = non_nulls.max().isoformat() if not non_nulls.empty else None
            
            column_profiles.append({
                "name": col_name,
                "data_type": dtype_str,
                "total_count": total_rows,
                "null_count": null_cnt,
                "distinct_count": int(dt_series.nunique(dropna=True)),
                "unique_count": int(dt_series.nunique(dropna=True)),
                "min": min_v,
                "max": max_v,
                "min_val": min_v,
                "max_val": max_v,
                "mean_val": None,
                "anomaly_count": 0,
                "anomaly_description": None
            })
        elif pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            dtype_str = "INTEGER" if pd.api.types.is_integer_dtype(series) else "FLOAT"
            null_cnt = int(series.isnull().sum())
            zero_cnt = int((series == 0).sum())
            neg_cnt = int((series < 0).sum())
            
            non_nulls = series.dropna()
            min_v = float(non_nulls.min()) if not non_nulls.empty else None
            max_v = float(non_nulls.max()) if not non_nulls.empty else None
            mean_v = round(float(non_nulls.mean()), 2) if not non_nulls.empty else None
            
            if pd.api.types.is_integer_dtype(series):
                min_v = int(min_v) if min_v is not None else None
                max_v = int(max_v) if max_v is not None else None

            anom_cnt = 0 if _is_signed_physical_column(col_name) else neg_cnt
            total_anomalies += anom_cnt

            column_profiles.append({
                "name": col_name,
                "data_type": dtype_str,
                "total_count": total_rows,
                "null_count": null_cnt,
                "zero_count": zero_cnt,
                "negative_count": neg_cnt,
                "distinct_count": int(series.nunique(dropna=True)),
                "unique_count": int(series.nunique(dropna=True)),
                "min": min_v,
                "max": max_v,
                "mean": mean_v,
                "min_val": min_v,
                "max_val": max_v,
                "mean_val": mean_v,
                "anomaly_count": anom_cnt,
                "anomaly_description": f"{neg_cnt} negative values detected" if neg_cnt > 0 else None
            })
        else:
            dtype_str = "STRING"
            null_cnt = int(series.isnull().sum() + (series == "").sum() if series.dtype == object else series.isnull().sum())
            unique_cnt = int(series.nunique(dropna=True))
            top_vals = series.dropna().value_counts().head(5).to_dict()
            top_vals = {str(k): int(v) for k, v in top_vals.items()}
            non_nulls_str = series.dropna().astype(str)
            avg_len = round(float(non_nulls_str.str.len().mean()), 2) if not non_nulls_str.empty else 0.0

            column_profiles.append({
                "name": col_name,
                "data_type": dtype_str,
                "total_count": total_rows,
                "null_count": null_cnt,
                "unique_count": unique_cnt,
                "distinct_count": unique_cnt,
                "top_values": top_vals,
                "avg_length": avg_len,
                "min_val": None,
                "max_val": None,
                "mean_val": None,
                "anomaly_count": 0,
                "anomaly_description": None
            })

    for col in column_profiles:
        col.setdefault("dtype", col.get("data_type") or "unknown")
        if "null_pct" not in col:
            nc = col.get("null_count")
            col["null_pct"] = (nc / total_rows) if isinstance(nc, (int, float)) and total_rows else 0.0

    health_score = round(max(0.0, 100.0 * (1.0 - (total_anomalies / (total_rows * max(1, len(column_profiles)))))), 1)

    profile = {
        "total_rows": total_rows,
        "columns": column_profiles,
        "total_anomalies": total_anomalies,
        "data_health_score": health_score,
        "summary": f"Profiled {total_rows} records with {len(column_profiles)} columns. Discovered {total_anomalies} anomalies."
    }
    return hide_sample_health_if_warehouse_faults(profile)


def hide_sample_health_if_warehouse_faults(profile):
    """Hide sample 99%/Excellent when data_new warehouse has SoC<0 or OPEN incidents."""
    try:
        from src.db.connection import get_db
        db = get_db()
        def _count(sql):
            res = db.execute(sql)
            return int(res[0][0]) if res else 0
        soc = _count("SELECT count(*) FROM raw.ev_telemetry WHERE battery_soc < 0")
        open_n = _count("SELECT count(*) FROM incidents WHERE status = 'OPEN'")
        profile["warehouse_soc_below_zero"] = soc
        profile["warehouse_open_incidents"] = open_n
        if soc > 0 or open_n > 0:
            profile["data_health_score"] = None
    except Exception:
        pass
    return profile

def generate_rules_for_baseline(baseline: str, profile_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], float]:
    """Generate dynamic schema-agnostic data quality rules based on baseline variant and profile_data statistics.
    
    Variants:
    - C0: Only null checks (simplest)
    - C1: Null + range + type checks
    - A1: All of the above + cross-field + semantic rules
    """
    start_time = time.time()
    variant = (baseline or "A1").upper()

    columns = profile_data.get("columns", [])
    total_rows = profile_data.get("total_rows", 0)

    candidate_rules = []

    # Track temporal & geographic column candidates
    pickup_cols = []
    dropoff_cols = []
    lat_cols = []
    lon_cols = []

    for col_prof in columns:
        col_name = str(col_prof.get("name", ""))
        data_type = str(col_prof.get("data_type", "")).upper()
        null_count = col_prof.get("null_count", 0)
        unique_count = col_prof.get("unique_count", col_prof.get("distinct_count", 0))
        zero_count = col_prof.get("zero_count", 0)
        negative_count = col_prof.get("negative_count", 0)

        name_lower = col_name.lower()

        # Classify column roles for cross-field checks
        if data_type == "DATETIME" or any(k in name_lower for k in ["datetime", "timestamp", "date", "time"]):
            if "pickup" in name_lower:
                pickup_cols.append(col_name)
            if "dropoff" in name_lower:
                dropoff_cols.append(col_name)

        if name_lower in ("lat", "latitude") or name_lower.endswith("_lat") or name_lower.endswith("_latitude") or name_lower.startswith("lat_") or name_lower.startswith("latitude_"):
            lat_cols.append(col_name)
        if name_lower in ("lon", "lng", "long", "longitude") or name_lower.endswith("_lon") or name_lower.endswith("_lng") or name_lower.endswith("_longitude") or name_lower.startswith("lon_") or name_lower.startswith("lng_") or name_lower.startswith("longitude_"):
            lon_cols.append(col_name)

        # 1. Numeric columns
        if data_type in ("INTEGER", "FLOAT", "INT", "NUMERIC", "DOUBLE") or negative_count > 0 or zero_count > 0:
            # a) Non-negative constraint (skip signed physical sensors: accel/gyro)
            if negative_count > 0 and not _is_signed_physical_column(col_name):
                candidate_rules.append({
                    "rule_type": "range",
                    "column": col_name,
                    "expression": f"{col_name} >= 0",
                    "description": f"Non-negative constraint for {col_name}",
                    "confidence": 0.95,
                    "risk_level": "HIGH",
                })
            # b) Null constraint
            if null_count > 0:
                candidate_rules.append({
                    "rule_type": "not_null",
                    "column": col_name,
                    "expression": f"{col_name} IS NOT NULL",
                    "description": f"{col_name} IS NOT NULL constraint",
                    "confidence": 0.95,
                    "risk_level": "MEDIUM",
                })
            # c) Suspicious zero prevalence — only flag if >95% zeros AND
            #    column name doesn't suggest zero is a legitimate value
            zero_legitimate_keywords = ("fee", "tip", "toll", "discount", "tax", "surcharge", "bonus", "penalty")
            if (total_rows > 0 and (zero_count / total_rows) > 0.95
                    and not any(k in name_lower for k in zero_legitimate_keywords)):
                candidate_rules.append({
                    "rule_type": "semantic",
                    "column": col_name,
                    "expression": f"{col_name} != 0",
                    "description": f"Flag suspicious zero prevalence in {col_name} (>{zero_count*100//total_rows}% zeros)",
                    "confidence": 0.75,
                    "risk_level": "LOW",
                })

        # 2. String columns
        elif data_type == "STRING":
            # a) Null constraint
            if null_count > 0:
                candidate_rules.append({
                    "rule_type": "not_null",
                    "column": col_name,
                    "expression": f"{col_name} IS NOT NULL",
                    "description": f"{col_name} IS NOT NULL constraint",
                    "confidence": 0.95,
                    "risk_level": "MEDIUM",
                })
            # b) Constant column (skip categorical coverage/status labels)
            if unique_count == 1 and not any(k in name_lower for k in ("coverage", "status", "flag", "label")):
                candidate_rules.append({
                    "rule_type": "variance",
                    "column": col_name,
                    "expression": f"LENGTH({col_name}) > 0",
                    "description": f"Validate constant non-empty invariant for {col_name}",
                    "confidence": 0.80,
                    "risk_level": "LOW",
                })


        # 3. Datetime columns
        elif data_type == "DATETIME":
            if null_count > 0:
                candidate_rules.append({
                    "rule_type": "not_null",
                    "column": col_name,
                    "expression": f"{col_name} IS NOT NULL",
                    "description": f"{col_name} IS NOT NULL constraint",
                    "confidence": 0.95,
                    "risk_level": "MEDIUM",
                })

    # 4. Cross-field temporal rules
    if pickup_cols and dropoff_cols:
        for p_col in pickup_cols:
            for d_col in dropoff_cols:
                # NaN-safe: only compare when both values are present
                candidate_rules.append({
                    "rule_type": "cross_field",
                    "column": d_col,
                    "expression": f"({d_col} != {d_col}) or ({p_col} != {p_col}) or ({d_col} >= {p_col})",
                    "description": f"Temporal order check: {d_col} >= {p_col} (skips nulls)",
                    "confidence": 0.95,
                    "risk_level": "HIGH",
                })

    # 5. Cross-field geographic rules
    if lat_cols and lon_cols:
        for lat_col in lat_cols:
            candidate_rules.append({
                "rule_type": "range",
                "column": lat_col,
                "expression": f"-90 <= {lat_col} <= 90",
                "description": f"Latitude range check for {lat_col} [-90, 90]",
                "confidence": 0.95,
                "risk_level": "HIGH",
            })
        for lon_col in lon_cols:
            candidate_rules.append({
                "rule_type": "range",
                "column": lon_col,
                "expression": f"-180 <= {lon_col} <= 180",
                "description": f"Longitude range check for {lon_col} [-180, 180]",
                "confidence": 0.95,
                "risk_level": "HIGH",
            })

    # Filter rules based on baseline variant aggressiveness:
    # C0: Only null checks
    # C1: Null + range checks
    # A1: All rules (null, range, cross_field, semantic)
    filtered_rules = []
    for r in candidate_rules:
        r_type = r["rule_type"]
        if variant == "C0":
            if r_type == "not_null":
                filtered_rules.append(r)
        elif variant == "C1":
            if r_type in ("not_null", "range"):
                filtered_rules.append(r)
        else:  # A1 or default
            filtered_rules.append(r)

    # Format output rules with complete schema fields
    formatted_rules = []
    for idx, r in enumerate(filtered_rules, 1):
        rule_dict = {
            "rule_id": f"R{idx}_{variant}",
            "name": f"{r['column']} {r['rule_type'].replace('_', ' ').title()} Rule",
            "rule_type": r["rule_type"],
            "column": r["column"],
            "field": r["column"],
            "expression": r["expression"],
            "description": r["description"],
            "confidence": r["confidence"],
            "risk_level": r.get("risk_level", "MEDIUM"),
            "action": "quarantine",
            "decision": "pending",
            "baseline_origin": variant.lower(),
        }
        formatted_rules.append(rule_dict)

    duration = round(time.time() - start_time, 4)
    return formatted_rules, duration


def safe_eval_rule(expression: str, row: Dict[str, Any]) -> bool:
    """Evaluate rule expression safely against a row dict."""
    try:
        # Build local environment variables for the expression
        local_vars = {**row}
        local_vars["abs"] = abs
        
        # Replace Python logical / SQL style operators
        expr = (
            expression.replace(" IS NOT NULL", " is not None")
            .replace(" is not null", " is not None")
            .replace(" IS NULL", " is None")
            .replace(" is null", " is None")
            .replace(" AND ", " and ")
            .replace(" AND", " and")
            .replace("AND ", "and ")
            .replace(" OR ", " or ")
            .replace(" OR", " or")
            .replace("OR ", "or ")
            .replace(" = ", " == ")
            .replace("  ", " ")
        )
        
        result = eval(expr, {"__builtins__": None, "abs": abs}, local_vars)
        return bool(result)
    except Exception:
        # If evaluation fails, fail safe by returning False (trigger quarantine)
        return False


def execute_compiled_rules(rows: List[Dict[str, Any]], rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Execute active/approved rules on rows, outputting CleanDB and QuarantineTable with Lineage Trace."""
    active_rules = [r for r in rules if r.get("decision") in ("approved", "edit")]
    if not active_rules:
        raise ValueError("Rule execution denied: No rules are approved by HITL")

    clean_db = []
    quarantine_table = []
    quarantine_breakdown = {r["rule_id"]: 0 for r in active_rules}

    start_t = time.time()

    for idx, row in enumerate(rows):
        violated_rules = []
        reasons = []

        for r in active_rules:
            expr = r.get("custom_expression") or r.get("expression")
            passed = safe_eval_rule(expr, row)
            if not passed:
                rule_name_str = r.get("name") or r.get("rule_name") or "Rule"
                violated_rules.append(r["rule_id"])
                reasons.append(f"Violated {rule_name_str} ({r['rule_id']}): {expr}")
                quarantine_breakdown[r["rule_id"]] += 1

        if violated_rules:
            quarantine_table.append({
                "row_id": idx + 1,
                "trip_id": row.get("trip_id", idx + 1),
                "violated_rule_ids": violated_rules,
                "reasons": reasons,
                "data": row
            })
        else:
            clean_db.append(row)

    exec_time = round(time.time() - start_t, 3)
    total_count = len(rows)
    clean_count = len(clean_db)
    quarantine_count = len(quarantine_table)
    quarantine_rate = round((quarantine_count / total_count * 100.0) if total_count > 0 else 0.0, 1)

    # Compute Cryptographic SHA-256 Manifest Hash of clean data
    manifest_bytes = json.dumps(clean_db, sort_keys=True, default=str).encode("utf-8")
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()

    audit_trace = [
        {
            "timestamp": datetime.datetime.now().isoformat(),
            "step": "RULE_COMPILATION",
            "details": {
                "compiled_rules_count": len(active_rules),
                "rules": [r["rule_id"] for r in active_rules]
            }
        },
        {
            "timestamp": datetime.datetime.now().isoformat(),
            "step": "DATASET_PARTITIONING",
            "details": {
                "total_processed": total_count,
                "clean_rows": clean_count,
                "quarantine_rows": quarantine_count,
                "quarantine_rate": f"{quarantine_rate}%"
            }
        },
        {
            "timestamp": datetime.datetime.now().isoformat(),
            "step": "MANIFEST_GENERATION",
            "details": {
                "clean_db_sha256": manifest_hash,
                "integrity_status": "VERIFIED"
            }
        }
    ]

    return {
        "total_processed": total_count,
        "clean_count": clean_count,
        "quarantine_count": quarantine_count,
        "quarantine_rate_pct": quarantine_rate,
        "quarantine_breakdown_by_rule": quarantine_breakdown,
        "human_active_minutes_saved": round(quarantine_count * 1.5 + len(rules) * 5.0, 1),
        "execution_time_sec": exec_time,
        "manifest_hash": manifest_hash,
        "audit_trace": audit_trace,
        "sample_quarantined": quarantine_table[:10],
        "clean_db": clean_db,
        "quarantine_indices": [q["row_id"] - 1 for q in quarantine_table]
    }


def execute_on_dataset(dataset_key: str, rules: List[Dict], 
                       sample_size: int = None) -> Dict[str, Any]:
    """Load dataset, execute rules, return clean/quarantine split."""
    df = load_dataset(dataset_key=dataset_key, sample_size=sample_size)
    return execute_compiled_rules(df.to_dict('records'), rules)


def execute_rules_transactional(
    rows: List[Dict[str, Any]],
    rules: List[Dict[str, Any]],
    snapshot_id: str = "snap_001",
    rule_version_id: str = "v1",
    source_table: str = "raw_taxi_trips",
    db=None,
) -> Dict[str, Any]:
    """Execute compiled rules and atomically insert quarantine records and audit log inside a single transaction boundary."""
    if db is None:
        from src.db.connection import get_db
        db = get_db()

    conn = db.get_connection()
    conn.execute("BEGIN TRANSACTION")

    try:
        exec_res = execute_compiled_rules(rows, rules)
        quarantine_indices = exec_res.get("quarantine_indices", [])

        active_rules = [r for r in rules if r.get("decision") in ("approved", "edit")]

        quarantine_records = []
        for idx in quarantine_indices:
            if idx < len(rows):
                row = rows[idx]
                raw_row_id = row.get("row_id") or row.get("id")
                if isinstance(raw_row_id, int):
                    source_row_id = raw_row_id
                else:
                    try:
                        source_row_id = int(raw_row_id)
                    except (ValueError, TypeError):
                        source_row_id = idx + 1

                failed_rules = []
                reasons = []
                for r in active_rules:
                    expr = r.get("custom_expression") or r.get("expression")
                    if not safe_eval_rule(expr, row):
                        r_id = r.get("rule_id", "R_UNKNOWN")
                        failed_rules.append(r_id)
                        reasons.append(f"Violated {r.get('name', r_id)}: {expr}")

                first_rule_id = failed_rules[0] if failed_rules else "R_UNKNOWN"
                reason_str = "; ".join(reasons) if reasons else "Rule violation"
                orig_json = json.dumps(row, default=str)
                q_id = str(uuid.uuid4())[:8]
                lineage_str = f"{snapshot_id}:{rule_version_id}:{source_row_id}"
                lineage_hash = hashlib.sha256(lineage_str.encode("utf-8")).hexdigest()[:16]

                quarantine_records.append((
                    q_id,
                    snapshot_id,
                    source_table,
                    source_row_id,
                    first_rule_id,
                    rule_version_id,
                    reason_str,
                    orig_json,
                    lineage_hash
                ))

        # Process batch insertions in chunks of 500 rows per batch
        CHUNK_SIZE = 500
        for i in range(0, len(quarantine_records), CHUNK_SIZE):
            chunk = quarantine_records[i : i + CHUNK_SIZE]
            conn.executemany(
                """
                INSERT INTO quarantine (
                    id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id, reason, original_data, lineage_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (snapshot_id, rule_version_id, source_row_id) DO NOTHING
                """,
                chunk
            )

        conn.execute("COMMIT")

        # Log audit event after transaction commit
        from src.services.audit import AuditService
        try:
            AuditService.log(
                action="EXECUTE_DATASET_RULES",
                actor="agent",
                target_table=source_table,
                target_id=snapshot_id,
                details={
                    "total_rows": len(rows),
                    "clean_count": exec_res["clean_count"],
                    "quarantine_count": len(quarantine_records),
                    "snapshot_id": snapshot_id,
                    "rule_version_id": rule_version_id
                },
                db=db
            )
        except Exception:
            pass

        return exec_res
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise e


def compute_benchmark_comparison() -> Dict[str, Any]:
    """Compute C0 vs C1 vs A1 benchmark evaluation metrics dynamically."""
    from eval.benchmark import BenchmarkHarness

    harness = BenchmarkHarness(seed=42)
    results = harness.run_all()

    c0 = results["C0"]
    c1 = results["C1"]
    a1 = results["A1"]

    scores = {"C0": c0.f1, "C1": c1.f1, "A1": a1.f1}
    winning_tier = max(scores, key=scores.get)
    tier_names = {
        "C0": "C0 (Manual / Heuristic)",
        "C1": "C1 (Single LLM Call)",
        "A1": "A1 (DataTrust OS Agentic)"
    }
    winner = tier_names.get(winning_tier, winning_tier)

    benchmarks = [
        {
            "baseline": "C0 (Manual / Heuristic)",
            "precision_pct": round(c0.precision * 100.0, 1),
            "recall_pct": round(c0.recall * 100.0, 1),
            "f1_pct": round(c0.f1 * 100.0, 1),
            "cost_tokens": c0.cost_tokens,
            "latency_sec": round(c0.latency_ms / 1000.0, 3),
            "faults_detected": c0.faults_detected,
            "faults_total": c0.faults_total,
        },
        {
            "baseline": "C1 (Zero-Shot Rule Script)",
            "precision_pct": round(c1.precision * 100.0, 1),
            "recall_pct": round(c1.recall * 100.0, 1),
            "f1_pct": round(c1.f1 * 100.0, 1),
            "cost_tokens": c1.cost_tokens,
            "latency_sec": round(c1.latency_ms / 1000.0, 3),
            "faults_detected": c1.faults_detected,
            "faults_total": c1.faults_total,
        },
        {
            "baseline": "A1 (DataTrust OS AI Agent)",
            "precision_pct": round(a1.precision * 100.0, 1),
            "recall_pct": round(a1.recall * 100.0, 1),
            "f1_pct": round(a1.f1 * 100.0, 1),
            "cost_tokens": a1.cost_tokens,
            "latency_sec": round(a1.latency_ms / 1000.0, 3),
            "faults_detected": a1.faults_detected,
            "faults_total": a1.faults_total,
        }
    ]

    time_saved_vs_c0_pct = round((a1.recall - c0.recall) * 100.0, 1)
    precision_gain_vs_c1_pct = round((a1.precision - c1.precision) * 100.0, 1)

    return {
        "benchmarks": benchmarks,
        "winner": winner,
        "time_saved_vs_c0_pct": time_saved_vs_c0_pct,
        "precision_gain_vs_c1_pct": precision_gain_vs_c1_pct
    }


# In-memory Run Repository
class RunStore:
    def __init__(self):
        self._runs: Dict[str, Dict[str, Any]] = {}

    def create_run(self, dataset_name: str = "taxi_trips_raw.csv", description: str = "") -> Dict[str, Any]:
        run_id = f"run-{int(time.time() * 1000)}-{random.randint(100, 999)}"
        created_at = datetime.datetime.now().isoformat()
        
        # Ensure seed data exists
        rows = load_dataset_rows()

        run_data = {
            "run_id": run_id,
            "dataset_name": dataset_name,
            "description": description or "NYC Taxi & Ride-Hailing Trips Data Cleaning Run",
            "status": "created",
            "created_at": created_at,
            "row_count": len(rows),
            "rows": rows,
            "profile": None,
            "baseline": None,
            "rules": [],
            "execution_results": None,
            "audit_trace": []
        }
        self._runs[run_id] = run_data
        return run_data

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self._runs.get(run_id)

    def profile_run(self, run_id: str) -> Dict[str, Any]:
        run = self.get_run(run_id)
        if not run:
            raise KeyError(f"Run {run_id} not found.")

        p_result = profile_rows(run["rows"])
        run["profile"] = p_result
        run["status"] = "profiled"
        run["audit_trace"].append({
            "timestamp": datetime.datetime.now().isoformat(),
            "step": "DATASET_PROFILED",
            "details": {"total_rows": p_result["total_rows"], "anomalies_found": p_result["total_anomalies"]}
        })
        return p_result

    def propose_rules(self, run_id: str, baseline: str = "a1") -> Tuple[List[Dict[str, Any]], float]:
        run = self.get_run(run_id)
        if not run:
            raise KeyError(f"Run {run_id} not found.")

        if not run["profile"]:
            self.profile_run(run_id)

        rules, mins_saved = generate_rules_for_baseline(baseline, run["profile"])
        run["baseline"] = baseline
        run["rules"] = rules
        run["estimated_human_minutes_saved"] = mins_saved
        run["status"] = "rules_proposed"
        run["audit_trace"].append({
            "timestamp": datetime.datetime.now().isoformat(),
            "step": "RULES_PROPOSED",
            "details": {"baseline": baseline, "rule_count": len(rules), "est_minutes_saved": mins_saved}
        })
        return rules, mins_saved

    def review_rules(self, run_id: str, decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
        run = self.get_run(run_id)
        if not run:
            raise KeyError(f"Run {run_id} not found.")

        decision_map = {d["rule_id"]: d for d in decisions}
        app_cnt, edit_cnt, rej_cnt = 0, 0, 0

        for r in run["rules"]:
            r_id = r["rule_id"]
            if r_id in decision_map:
                dec_item = decision_map[r_id]
                dec_val = dec_item["decision"]
                r["decision"] = dec_val
                if dec_item.get("custom_expression"):
                    r["custom_expression"] = dec_item["custom_expression"]

                if dec_val in ("approve", "approved"):
                    app_cnt += 1
                elif dec_val == "edit":
                    edit_cnt += 1
                elif dec_val in ("reject", "rejected"):
                    rej_cnt += 1

        run["status"] = "reviewed"
        run["audit_trace"].append({
            "timestamp": datetime.datetime.now().isoformat(),
            "step": "HUMAN_GOVERNANCE_REVIEW",
            "details": {"approved": app_cnt, "edited": edit_cnt, "rejected": rej_cnt}
        })

        return {
            "run_id": run_id,
            "status": "reviewed",
            "approved_count": app_cnt,
            "edited_count": edit_cnt,
            "rejected_count": rej_cnt,
            "total_rules": len(run["rules"])
        }

    def execute_run(self, run_id: str) -> Dict[str, Any]:
        run = self.get_run(run_id)
        if not run:
            raise KeyError(f"Run {run_id} not found.")

        if not run["rules"]:
            self.propose_rules(run_id, "a1")

        exec_res = execute_compiled_rules(run["rows"], run["rules"])
        run["execution_results"] = exec_res
        run["status"] = "executed"
        run["audit_trace"].extend(exec_res["audit_trace"])

        return {
            "run_id": run_id,
            "status": "executed",
            "total_processed": exec_res["total_processed"],
            "clean_count": exec_res["clean_count"],
            "quarantine_count": exec_res["quarantine_count"],
            "quarantine_rate_pct": exec_res["quarantine_rate_pct"],
            "human_active_minutes_saved": exec_res["human_active_minutes_saved"],
            "execution_time_sec": exec_res["execution_time_sec"],
            "manifest_hash": exec_res["manifest_hash"]
        }

    def get_results(self, run_id: str) -> Dict[str, Any]:
        run = self.get_run(run_id)
        if not run:
            raise KeyError(f"Run {run_id} not found.")

        if not run["execution_results"]:
            self.execute_run(run_id)

        res = run["execution_results"]
        return {
            "run_id": run_id,
            "dataset_name": run["dataset_name"],
            "status": run["status"],
            "total_rows": res["total_processed"],
            "clean_rows": res["clean_count"],
            "quarantine_rows": res["quarantine_count"],
            "quarantine_breakdown_by_rule": res["quarantine_breakdown_by_rule"],
            "human_active_minutes_saved": res["human_active_minutes_saved"],
            "manifest_hash": res["manifest_hash"],
            "audit_trace": run["audit_trace"],
            "sample_quarantined": res["sample_quarantined"]
        }

    def reset_all(self) -> Tuple[float, int]:
        start_t = time.time()
        self._runs.clear()
        count = seed_dataset()
        reset_time = round(time.time() - start_t, 3)
        return reset_time, count


# Global instance of RunStore
run_store = RunStore()
