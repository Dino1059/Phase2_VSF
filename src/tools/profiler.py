from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from src.models.schemas import ColumnProfile, Profile, ProfileReport, ProfileResult, QualityFlag, RuleSeverity
from src.tools.datasource import DataSource
from src.tools.base import BaseTool
from src.db.connection import get_db


class Profiler:
    """
    Profiler computes deterministic statistical profiles and metadata for a DataFrame or DataSource.
    """

    def __init__(self, snapshot_id: str = "snap_001"):
        self.snapshot_id = snapshot_id

    def profile_source(self, source: DataSource, snapshot_id: Optional[str] = None) -> ProfileResult:
        """Profiles a DataSource directly, incorporating source metadata."""
        meta = source.get_metadata()
        try:
            df = source.load_data()
            if not isinstance(df, pd.DataFrame):
                df = pd.DataFrame()
        except NotImplementedError:
            df = pd.DataFrame()

        return self.profile(
            data=df,
            snapshot_id=snapshot_id,
            source_type=meta.get("source_type", "structured"),
            file_format=meta.get("file_format", "csv"),
            checksum_sha256=meta.get("checksum_sha256", ""),
            file_path=meta.get("file_path", ""),
            metadata=meta,
        )

    def profile(
        self,
        data: pd.DataFrame,
        snapshot_id: Optional[str] = None,
        source_type: str = "structured",
        file_format: str = "csv",
        checksum_sha256: str = "",
        file_path: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProfileResult:
        snap_id = snapshot_id or self.snapshot_id or "snap_001"
        row_count = len(data) if not data.empty else 0
        duplicate_count = int(data.duplicated().sum()) if not data.empty else 0

        column_profiles: List[ColumnProfile] = []
        candidate_keys: List[str] = []
        quality_flags: List[QualityFlag] = []

        for col in data.columns:
            col_series = data[col]
            null_cnt = int(col_series.isna().sum())
            null_pct = float(null_cnt / row_count) if row_count > 0 else 0.0
            unique_cnt = int(col_series.nunique(dropna=True))
            cardinality = float(unique_cnt / row_count) if row_count > 0 else 0.0

            if unique_cnt == row_count and null_cnt == 0 and row_count > 0:
                candidate_keys.append(col)

            if null_pct > 0.2:
                quality_flags.append(
                    QualityFlag(
                        column=col,
                        flag_type="high_nulls",
                        message=f"Column '{col}' has {null_pct:.1%} null values.",
                        severity=RuleSeverity.WARNING if null_pct < 0.5 else RuleSeverity.ERROR,
                    )
                )

            if unique_cnt == 1 and row_count > 1:
                quality_flags.append(
                    QualityFlag(
                        column=col,
                        flag_type="constant_column",
                        message=f"Column '{col}' has a single constant value.",
                        severity=RuleSeverity.INFO,
                    )
                )

            col_min: Optional[Any] = None
            col_max: Optional[Any] = None
            col_mean: Optional[float] = None
            col_median: Optional[float] = None
            col_std: Optional[float] = None

            if pd.api.types.is_numeric_dtype(col_series):
                non_nulls = col_series.dropna()
                if len(non_nulls) > 0:
                    col_min = float(non_nulls.min()) if not pd.isna(non_nulls.min()) else None
                    col_max = float(non_nulls.max()) if not pd.isna(non_nulls.max()) else None
                    col_mean = float(non_nulls.mean()) if not pd.isna(non_nulls.mean()) else None
                    col_median = float(non_nulls.median()) if not pd.isna(non_nulls.median()) else None
                    col_std = float(non_nulls.std()) if not pd.isna(non_nulls.std()) else None
            elif pd.api.types.is_datetime64_any_dtype(col_series):
                non_nulls = col_series.dropna()
                if len(non_nulls) > 0:
                    col_min = str(non_nulls.min())
                    col_max = str(non_nulls.max())
            else:
                non_nulls = col_series.dropna()
                if len(non_nulls) > 0:
                    try:
                        col_min = str(non_nulls.min())
                        col_max = str(non_nulls.max())
                    except Exception:
                        pass

            top_counts = col_series.value_counts(dropna=False).head(5)
            top_values = [
                {"value": str(val) if not pd.isna(val) else None, "count": int(cnt)}
                for val, cnt in top_counts.items()
            ]

            pattern_summary = f"dtype={col_series.dtype}, unique={unique_cnt}, nulls={null_cnt}"

            column_profiles.append(
                ColumnProfile(
                    name=col,
                    dtype=str(col_series.dtype),
                    null_count=null_cnt,
                    null_pct=null_pct,
                    unique_count=unique_cnt,
                    cardinality=cardinality,
                    min=col_min,
                    max=col_max,
                    mean=col_mean,
                    median=col_median,
                    std=col_std,
                    top_values=top_values,
                    pattern_summary=pattern_summary,
                )
            )

        return ProfileResult(
            snapshot_id=snap_id,
            source_type=source_type,
            file_format=file_format,
            checksum_sha256=checksum_sha256,
            file_path=file_path,
            columns=column_profiles,
            row_count=row_count,
            duplicate_count=duplicate_count,
            cross_field_correlations=[],
            candidate_keys=candidate_keys,
            quality_flags=quality_flags,
            metadata=metadata or {},
        )


class DataProfilerTool(BaseTool):
    name = "data_profiler"
    description = "Profile a DuckDB table to compute column-level statistics: data types, null rates, cardinality, min/max, mean, and standard deviation."
    input_schema = {
        "type": "object",
        "properties": {
            "table_name": {"type": "string", "description": "DuckDB table to profile"},
            "sample_size": {"type": "integer", "description": "Number of rows to sample", "default": 10000}
        },
        "required": ["table_name"]
    }

    ALLOWED_TABLES = {"vgreen_telemetry", "vinfast_bms", "xanhsm_trips", "xanhsm_feedback", "raw_snapshots", "quality_rules", "quarantine", "audit_log", "agent_traces", "profile_results"}

    def execute(self, input_data: dict) -> dict:
        table = input_data["table_name"]
        if table not in self.ALLOWED_TABLES:
            return {"error": f"Table '{table}' not allowed", "table_name": table, "row_count": 0, "columns": []}

        db = get_db()
        
        # Get row count
        count_result = db.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = count_result[0][0] if count_result else 0
        
        if row_count == 0:
            return {"table_name": table, "row_count": 0, "columns": []}

        # Get column info
        col_info = db.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}' AND table_schema = 'main' ORDER BY ordinal_position")
        
        columns = []
        for col_name, dtype in col_info:
            stats = {"name": col_name, "dtype": dtype}
            
            # Null count
            null_result = db.execute(f'SELECT COUNT(*) FROM {table} WHERE "{col_name}" IS NULL')
            null_count = null_result[0][0] if null_result else 0
            stats["null_count"] = null_count
            stats["null_pct"] = round(null_count / max(row_count, 1) * 100, 2)
            
            # Unique count
            uniq_result = db.execute(f'SELECT COUNT(DISTINCT "{col_name}") FROM {table}')
            stats["unique_count"] = uniq_result[0][0] if uniq_result else 0
            
            # Numeric stats
            if dtype in ('FLOAT', 'DOUBLE', 'INTEGER', 'BIGINT', 'DECIMAL', 'REAL'):
                try:
                    num_stats = db.execute(f'SELECT MIN("{col_name}"), MAX("{col_name}"), AVG("{col_name}"), STDDEV("{col_name}") FROM {table}')
                    if num_stats and num_stats[0]:
                        stats["min_val"] = num_stats[0][0]
                        stats["max_val"] = num_stats[0][1]
                        stats["mean_val"] = round(float(num_stats[0][2]), 4) if num_stats[0][2] is not None else None
                        stats["std_val"] = round(float(num_stats[0][3]), 4) if num_stats[0][3] is not None else None
                except Exception:
                    pass
            else:
                # For string columns, get min/max length
                try:
                    len_stats = db.execute(f'SELECT MIN(LENGTH("{col_name}")), MAX(LENGTH("{col_name}")) FROM {table} WHERE "{col_name}" IS NOT NULL')
                    if len_stats and len_stats[0]:
                        stats["min_len"] = len_stats[0][0]
                        stats["max_len"] = len_stats[0][1]
                except Exception:
                    pass
            
            columns.append(stats)

        return {"table_name": table, "row_count": row_count, "columns": columns}
