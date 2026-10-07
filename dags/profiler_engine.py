"""
DataTrust OS: Data Profiling Engine for Airflow DAGs (Task 2)
Statistical profiling, signal extraction, configurable health score, and catalog persistence.
"""

import os
import json
import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("profiler_engine")


@dataclass
class HealthScoreWeights:
    """Configurable weights for Data Quality Dimensions (DAMA / ISO 25012)"""
    completeness: float = 0.40  # Trọng số tính đầy đủ (dựa trên null rate)
    validity: float = 0.35      # Trọng số tính hợp lệ (dựa trên tỷ lệ tín hiệu bất thường)
    uniqueness: float = 0.25    # Trọng số tính đa dạng & phân biệt (không bị hằng số)


@dataclass
class ProfilingConfig:
    """Configurable parameters for statistical signals and health scoring"""
    weights: HealthScoreWeights = field(default_factory=HealthScoreWeights)
    null_tolerance_pct: float = 0.0          # Ngưỡng null chấp nhận được (0.0 - 1.0)
    top_values_limit: int = 5                # Số lượng giá trị phổ biến trích xuất
    min_score: float = 0.0
    max_score: float = 100.0


_cached_db_host = None


def get_db_connection():
    """Establish PostgreSQL connection with automatic fallback for Docker and host environments."""
    global _cached_db_host
    env_host = os.getenv("POSTGRES_HOST")

    if _cached_db_host:
        hosts = [_cached_db_host]
    elif env_host:
        hosts = [env_host, "127.0.0.1", "localhost", "postgres"]
    else:
        # Default priority: 127.0.0.1 / localhost first for local execution, then postgres for docker
        hosts = ["127.0.0.1", "localhost", "postgres"]

    port = int(os.getenv("POSTGRES_PORT", "5432"))
    user = os.getenv("POSTGRES_USER", "airflow")
    password = os.getenv("POSTGRES_PASSWORD", "airflow")
    dbname = os.getenv("POSTGRES_DB", "airflow")

    last_error = None
    for host in hosts:
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                dbname=dbname,
                connect_timeout=2
            )
            _cached_db_host = host
            return conn
        except Exception as e:
            last_error = e
            if _cached_db_host == host:
                _cached_db_host = None
            continue

    # Fallback retry all hosts if cached host failed
    fallback_hosts = ["127.0.0.1", "localhost", "postgres"]
    for host in fallback_hosts:
        if host in hosts:
            continue
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                dbname=dbname,
                connect_timeout=2
            )
            _cached_db_host = host
            return conn
        except Exception as e:
            last_error = e
            continue

    raise ConnectionError(f"Could not connect to PostgreSQL on any host: {last_error}")


class DataProfilerEngine:
    """
    Statistical Data Profiler Engine:
    - Pure descriptive statistics and signal extraction (NOT Pass/Fail rule evaluation).
    - Sensitivity risk indicators for personal data governance.
    - Configurable Data Health Score based on Data Quality dimensions.
    """

    def __init__(self, config: Optional[ProfilingConfig] = None):
        self.config = config or ProfilingConfig()

    def profile_all_datasets(self, batch_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Profile all active datasets registered in catalog.datasets."""
        batch = batch_id or f"batch_{uuid.uuid4().hex[:8]}"
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT dataset_id, table_name FROM catalog.datasets ORDER BY dataset_id;")
                datasets = cur.fetchall()

            results = []
            for ds in datasets:
                dataset_id = ds["dataset_id"]
                table_name = ds["table_name"]
                logger.info(f"--- Profiling dataset: {dataset_id} (table: {table_name}) ---")
                res = self.profile_single_dataset(dataset_id, batch_id=batch, conn=conn)
                results.append(res)

            conn.commit()
            return results
        finally:
            conn.close()

    def profile_single_dataset(
        self,
        dataset_id: str,
        batch_id: Optional[str] = None,
        conn: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Compute column statistics, descriptive signals, and health score for a single dataset.
        Persists results into catalog.table_profiles and catalog.column_profiles.
        """
        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True

        batch = batch_id or f"batch_{uuid.uuid4().hex[:8]}"

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. Get dataset info
                cur.execute(
                    "SELECT dataset_id, table_name FROM catalog.datasets WHERE dataset_id = %s;",
                    (dataset_id,)
                )
                ds_row = cur.fetchone()
                if not ds_row:
                    raise ValueError(f"Dataset '{dataset_id}' not found in catalog.datasets")

                table_name = ds_row["table_name"]
                # Extract schema and raw table name
                if "." in table_name:
                    schema_name, raw_tbl = table_name.split(".", 1)
                else:
                    schema_name, raw_tbl = "bronze", table_name

                # 2. Get registered columns with metadata
                cur.execute(
                    """
                    SELECT column_id, column_name, data_type, is_personal_data, pii_role, semantic_tag
                    FROM catalog.columns
                    WHERE dataset_id = %s
                    ORDER BY ordinal_position;
                    """,
                    (dataset_id,)
                )
                catalog_cols = cur.fetchall()

                # 3. Get total rows count from physical table
                cur.execute(f'SELECT COUNT(*) AS total_rows FROM "{schema_name}"."{raw_tbl}";')
                total_rows = cur.fetchone()["total_rows"]

                # 4. Get physical column types from postgres information_schema
                cur.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s;
                    """,
                    (schema_name, raw_tbl)
                )
                pg_types = {r["column_name"]: r["data_type"] for r in cur.fetchall()}

                # 5. Profile each column
                column_profiles = []
                validity_issues_count = 0
                constant_cols_count = 0
                total_null_pct_sum = 0.0
                signals_summary = {
                    "total_columns": len(catalog_cols),
                    "missing_value_columns": 0,
                    "negative_value_signals": 0,
                    "constant_columns": 0,
                    "pii_risk_columns": 0,
                }

                for col in catalog_cols:
                    c_id = col["column_id"]
                    c_name = str(col["column_name"]).strip()
                    is_pii = col["is_personal_data"]
                    pii_role = col["pii_role"]
                    sem_tag = col["semantic_tag"]
                    pg_type = pg_types.get(c_name, "character varying").lower()

                    is_numeric = pg_type in (
                        "integer", "numeric", "double precision", "real", "bigint", "smallint"
                    )

                    # Compute basic counts
                    if is_numeric:
                        agg_sql = f"""
                            SELECT 
                                COUNT(*) - COUNT("{c_name}") AS null_count,
                                COUNT(DISTINCT "{c_name}") AS unique_count,
                                MIN("{c_name}")::text AS min_val,
                                MAX("{c_name}")::text AS max_val,
                                AVG("{c_name}") AS mean_val,
                                STDDEV("{c_name}") AS std_val,
                                COUNT(*) FILTER (WHERE "{c_name}" = 0) AS zeros_count,
                                COUNT(*) FILTER (WHERE "{c_name}" < 0) AS negative_count
                            FROM "{schema_name}"."{raw_tbl}";
                        """
                    else:
                        agg_sql = f"""
                            SELECT 
                                COUNT(*) - COUNT("{c_name}") AS null_count,
                                COUNT(DISTINCT "{c_name}") AS unique_count,
                                MIN(LENGTH("{c_name}"::text))::text AS min_val,
                                MAX(LENGTH("{c_name}"::text))::text AS max_val,
                                NULL::numeric AS mean_val,
                                NULL::numeric AS std_val,
                                0 AS zeros_count,
                                0 AS negative_count
                            FROM "{schema_name}"."{raw_tbl}";
                        """

                    cur.execute(agg_sql)
                    stats = cur.fetchone()

                    null_cnt = stats["null_count"] or 0
                    null_pct = float(null_cnt / total_rows) if total_rows > 0 else 0.0
                    uniq_cnt = stats["unique_count"] or 0
                    dist_pct = float(uniq_cnt / total_rows) if total_rows > 0 else 0.0
                    min_v = stats["min_val"]
                    max_v = stats["max_val"]
                    mean_v = float(stats["mean_val"]) if stats["mean_val"] is not None else None
                    std_v = float(stats["std_val"]) if stats["std_val"] is not None else None
                    zeros_cnt = stats["zeros_count"] or 0
                    neg_cnt = stats["negative_count"] or 0

                    total_null_pct_sum += null_pct

                    # Extract Top Frequent Values
                    top_vals = []
                    try:
                        cur.execute(
                            f"""
                            SELECT "{c_name}"::text AS val, COUNT(*) AS cnt
                            FROM "{schema_name}"."{raw_tbl}"
                            WHERE "{c_name}" IS NOT NULL
                            GROUP BY "{c_name}"
                            ORDER BY cnt DESC
                            LIMIT %s;
                            """,
                            (self.config.top_values_limit,)
                        )
                        for tv in cur.fetchall():
                            top_vals.append({"value": tv["val"], "count": tv["cnt"]})
                    except Exception as e:
                        logger.debug(f"Top values query failed for {c_name}: {e}")

                    # Statistical Signals & Sensitivity Indicators (NOT Pass/Fail verdicts)
                    col_signals = []
                    has_validity_signal = False

                    if null_cnt > 0:
                        signals_summary["missing_value_columns"] += 1
                        col_signals.append({
                            "signal_type": "missing_values",
                            "category": "completeness",
                            "null_count": null_cnt,
                            "null_pct": round(null_pct, 4),
                            "detail": f"{null_cnt} missing values ({null_pct:.1%})"
                        })

                    if uniq_cnt == total_rows and total_rows > 1:
                        col_signals.append({
                            "signal_type": "all_unique",
                            "category": "uniqueness",
                            "unique_count": uniq_cnt,
                            "detail": "Candidate unique identifier (100% distinct)"
                        })

                    if uniq_cnt == 1 and total_rows > 1:
                        constant_cols_count += 1
                        signals_summary["constant_columns"] += 1
                        col_signals.append({
                            "signal_type": "zero_variance",
                            "category": "distribution",
                            "value": min_v,
                            "detail": "Single constant value across all rows"
                        })

                    if is_numeric and neg_cnt > 0:
                        signals_summary["negative_value_signals"] += 1
                        has_validity_signal = True
                        col_signals.append({
                            "signal_type": "negative_values_observed",
                            "category": "distribution",
                            "count": neg_cnt,
                            "min_val": min_v,
                            "detail": f"{neg_cnt} negative value(s) observed (minimum: {min_v})"
                        })

                    if is_pii:
                        signals_summary["pii_risk_columns"] += 1
                        col_signals.append({
                            "signal_type": "pii_risk_indicator",
                            "category": "sensitivity",
                            "role": pii_role,
                            "semantic_tag": sem_tag,
                            "detail": f"Contains personal data classified as {pii_role}"
                        })

                    if has_validity_signal:
                        validity_issues_count += 1

                    column_profiles.append({
                        "column_id": c_id,
                        "column_name": c_name,
                        "data_type": pg_type,
                        "null_count": null_cnt,
                        "null_pct": round(null_pct, 4),
                        "unique_count": uniq_cnt,
                        "distinct_pct": round(dist_pct, 4),
                        "min_val": min_v,
                        "max_val": max_v,
                        "mean_val": round(mean_v, 4) if mean_v is not None else None,
                        "std_val": round(std_v, 4) if std_v is not None else None,
                        "zeros_count": zeros_cnt,
                        "negative_count": neg_cnt,
                        "top_values": top_vals,
                        "signals": col_signals,
                    })

                # 6. Calculate Configurable Health Score
                health_score = self._compute_health_score(
                    num_cols=len(catalog_cols),
                    total_null_pct_sum=total_null_pct_sum,
                    validity_issues_count=validity_issues_count,
                    constant_cols_count=constant_cols_count
                )

                # 7. Summary text
                summary_text = (
                    f"Profiled {total_rows:,} rows across {len(catalog_cols)} columns. "
                    f"Health score: {health_score:.1f}%. "
                    f"Detected {signals_summary['missing_value_columns']} missing cols, "
                    f"{signals_summary['negative_value_signals']} negative value signals, "
                    f"{signals_summary['pii_risk_columns']} PII sensitivity flags."
                )

                # 8. Persist to catalog.table_profiles
                profile_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO catalog.table_profiles (
                        profile_id, dataset_id, batch_id, total_rows, total_columns,
                        health_score, signals_summary, summary, profiled_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
                    """,
                    (
                        profile_id,
                        dataset_id,
                        batch,
                        total_rows,
                        len(catalog_cols),
                        health_score,
                        json.dumps(signals_summary),
                        summary_text,
                    )
                )

                # 9. Persist to catalog.column_profiles (referencing column_id directly)
                for cp in column_profiles:
                    cur.execute(
                        """
                        INSERT INTO catalog.column_profiles (
                            profile_id, column_id, null_count, null_pct,
                            unique_count, distinct_pct, min_val, max_val,
                            mean_val, std_val, zeros_count, negative_count,
                            top_values, signals
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """,
                        (
                            profile_id,
                            cp["column_id"],
                            cp["null_count"],
                            cp["null_pct"],
                            cp["unique_count"],
                            cp["distinct_pct"],
                            cp["min_val"],
                            cp["max_val"],
                            cp["mean_val"],
                            cp["std_val"],
                            cp["zeros_count"],
                            cp["negative_count"],
                            json.dumps(cp["top_values"]),
                            json.dumps(cp["signals"]),
                        )
                    )

                # 10. Update catalog.datasets with latest row_count and updated_at
                cur.execute(
                    """
                    UPDATE catalog.datasets
                    SET row_count = %s, column_count = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE dataset_id = %s;
                    """,
                    (total_rows, len(catalog_cols), dataset_id)
                )

                logger.info(
                    f"Successfully profiled {dataset_id}: {total_rows:,} rows, "
                    f"{len(catalog_cols)} cols, Health Score: {health_score:.1f}%"
                )

                if should_close:
                    conn.commit()

                return {
                    "profile_id": profile_id,
                    "dataset_id": dataset_id,
                    "table_name": table_name,
                    "total_rows": total_rows,
                    "columns_count": len(catalog_cols),
                    "health_score": health_score,
                    "signals_summary": signals_summary,
                    "summary": summary_text,
                    "columns": column_profiles,
                }

        finally:
            if should_close and conn:
                conn.close()

    def _compute_health_score(
        self,
        num_cols: int,
        total_null_pct_sum: float,
        validity_issues_count: int,
        constant_cols_count: int
    ) -> float:
        """
        Compute Data Health Score based on standardized Data Quality Dimensions:
        - Completeness: 1.0 - average null percentage
        - Validity: 1.0 - ratio of columns with statistical irregularities
        - Uniqueness: 1.0 - ratio of non-constant columns
        Weights are configurable via ProfilingConfig.
        """
        if num_cols == 0:
            return 100.0

        w = self.config.weights

        # 1. Completeness dimension (0.0 to 100.0)
        avg_null_pct = total_null_pct_sum / num_cols
        effective_null = max(0.0, avg_null_pct - self.config.null_tolerance_pct)
        s_completeness = max(0.0, 1.0 - effective_null) * 100.0

        # 2. Validity dimension (0.0 to 100.0)
        s_validity = max(0.0, 1.0 - (validity_issues_count / num_cols)) * 100.0

        # 3. Uniqueness dimension (0.0 to 100.0)
        s_uniqueness = max(0.0, 1.0 - (constant_cols_count / num_cols)) * 100.0

        # Overall weighted composite score
        composite = (
            w.completeness * s_completeness +
            w.validity * s_validity +
            w.uniqueness * s_uniqueness
        )

        return round(min(self.config.max_score, max(self.config.min_score, composite)), 2)


if __name__ == "__main__":
    logger.info("Running DataProfilerEngine standalone...")
    profiler = DataProfilerEngine()
    results = profiler.profile_all_datasets()
    print(f"\nCompleted profiling {len(results)} datasets:")
    for r in results:
        print(f" - {r['dataset_id']:<35}: {r['total_rows']:>6} rows, {r['columns_count']:>2} cols, Health: {r['health_score']}%")
