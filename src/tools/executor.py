import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from src.models.schemas import (
    ExecutionPlan,
    ExecutionResult,
    RawSnapshot,
    RunManifest,
)
from src.tools.connector import SourceConnector
from src.tools.transforms import TransformLibrary

ExecutionManifest = RunManifest


class Executor:
    """
    Executor runs a compiled ExecutionPlan against a RawSnapshot or DataFrame,
    producing CleanDB output, Quarantine output, output SHA-256 checksum,
    and a RunManifest.
    """

    def __init__(self, connector: Optional[SourceConnector] = None):
        self.connector = connector or SourceConnector()

    @staticmethod
    def compute_df_checksum(df: pd.DataFrame) -> str:
        """Compute SHA-256 checksum of DataFrame CSV representation."""
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        return hashlib.sha256(csv_bytes).hexdigest()

    def execute(
        self,
        arg1: Any,
        arg2: Any = None,
        data_df: Optional[pd.DataFrame] = None,
    ) -> ExecutionResult:
        start_time = time.time()

        if isinstance(arg1, pd.DataFrame):
            current_clean = arg1.copy()
            plan = arg2
            snapshot = RawSnapshot(checksum_sha256=self.compute_df_checksum(current_clean), row_count=len(current_clean))
        elif isinstance(arg1, ExecutionPlan):
            plan = arg1
            if isinstance(arg2, RawSnapshot):
                snapshot = arg2
                if data_df is not None:
                    current_clean = data_df.copy()
                elif snapshot.file_path:
                    current_clean = self.connector.read_dataframe(snapshot.file_path)
                else:
                    current_clean = pd.DataFrame()
            elif isinstance(arg2, pd.DataFrame):
                current_clean = arg2.copy()
                snapshot = RawSnapshot(checksum_sha256=self.compute_df_checksum(current_clean), row_count=len(current_clean))
            elif data_df is not None:
                current_clean = data_df.copy()
                snapshot = RawSnapshot(checksum_sha256=self.compute_df_checksum(current_clean), row_count=len(current_clean))
            else:
                current_clean = pd.DataFrame()
                snapshot = RawSnapshot(checksum_sha256="empty", row_count=0)
        else:
            current_clean = pd.DataFrame()
            plan = ExecutionPlan()
            snapshot = RawSnapshot(checksum_sha256="empty", row_count=0)

        total_rows = len(current_clean)
        quarantined_dfs: List[pd.DataFrame] = []
        operations_run: List[str] = []
        quarantine_summary: Dict[str, int] = {}

        steps = plan.instructions if plan and plan.instructions else (plan.steps if plan else [])
        for step in steps:
            op = getattr(step, "action_type", None) or getattr(step, "operation", None) or getattr(step, "action", "")
            params = getattr(step, "parameters", None) or getattr(step, "params", None) or {}
            action_param = params.get("action")
            act_name = (action_param or op or "").lower()
            target_field = (
                getattr(step, "target_column", None)
                or getattr(step, "target_field", None)
                or getattr(step, "column", None)
                or params.get("target_field")
                or params.get("target_column")
            )
            action = getattr(step, "action", None) or action_param or "quarantine"

            operations_run.append(f"{step.order if hasattr(step, 'order') else 1}:{act_name}:{target_field or ''}")

            if act_name in ("not_null", "fill_null", "fill"):
                fill_val = params.get("fill_value", params.get("value", 0))
                if target_field and target_field in current_clean.columns:
                    current_clean[target_field] = current_clean[target_field].fillna(fill_val)
            elif act_name in ("unique", "drop_duplicates", "duplicate"):
                subset = params.get("subset", [target_field] if target_field else None)
                if subset:
                    subset = [c for c in subset if c in current_clean.columns]
                dup_mask = current_clean.duplicated(subset=subset if subset else None, keep="first")
                quar = current_clean[dup_mask].copy()
                current_clean = current_clean[~dup_mask].copy()
                if not quar.empty:
                    quarantined_dfs.append(quar)
                    quarantine_summary["duplicate"] = quarantine_summary.get("duplicate", 0) + len(quar)
            elif act_name in ("range", "range_check", "quarantine_range", "outlier_range"):
                min_v = params.get("min")
                max_v = params.get("max")
                if target_field and target_field in current_clean.columns:
                    series = pd.to_numeric(current_clean[target_field], errors="coerce")
                    mask = pd.Series(False, index=current_clean.index)
                    if min_v is not None:
                        mask |= series < min_v
                    if max_v is not None:
                        mask |= series > max_v
                    mask |= series.isna() & current_clean[target_field].notna()

                    quar = current_clean[mask].copy()
                    current_clean = current_clean[~mask].copy()
                    if not quar.empty:
                        quarantined_dfs.append(quar)
                        key = f"outlier_range_{target_field}"
                        quarantine_summary[key] = quarantine_summary.get(key, 0) + len(quar)

        clean_rows = len(current_clean)
        if quarantined_dfs:
            quarantined_df = pd.concat(quarantined_dfs, ignore_index=True)
            quarantined_rows = len(quarantined_df)
        else:
            quarantined_df = pd.DataFrame()
            quarantined_rows = 0

        duration_sec = round(time.time() - start_time, 4)
        output_checksum = self.compute_df_checksum(current_clean) if not current_clean.empty else "empty"

        manifest = RunManifest(
            plan_id=plan.plan_id if plan else "plan_001",
            run_id=plan.run_id if plan else "run_001",
            snapshot_id=snapshot.snapshot_id if hasattr(snapshot, "snapshot_id") else "snap_001",
            initial_rows=total_rows,
            clean_rows=clean_rows,
            quarantine_rows=quarantined_rows,
            execution_time_sec=duration_sec,
            applied_instructions=operations_run,
            quarantine_summary=quarantine_summary,
        )

        return ExecutionResult(
            clean_df=current_clean,
            quarantine_df=quarantined_df,
            manifest=manifest,
            clean_rows=clean_rows,
            quarantine_rows=quarantined_rows,
            execution_time_sec=duration_sec,
        )
