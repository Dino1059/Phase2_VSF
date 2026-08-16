import json
from typing import Any, Dict, Optional, Union

from src.models.schemas import ColumnProfile, DataProfile


class ContextBuilder:
    """Assembles data profile and target schema into structured prompts for LLM agents.
    
    GUARANTEE: Sends metadata and aggregate statistics ONLY. Strips all raw data records
    to eliminate raw data leakage.
    """

    FORBIDDEN_RAW_KEYS = {
        "raw_rows",
        "rows",
        "samples",
        "sample_rows",
        "records",
        "raw_data",
        "data_samples",
    }

    @classmethod
    def sanitize_profile(cls, profile: Union[DataProfile, Dict[str, Any]]) -> Dict[str, Any]:
        """Strips any potential raw row data keys from the profile."""
        if isinstance(profile, DataProfile):
            prof_dict = profile.model_dump()
        elif hasattr(profile, "model_dump"):
            prof_dict = profile.model_dump()
        elif isinstance(profile, dict):
            prof_dict = dict(profile)
        else:
            prof_dict = {"table_name": "dataset", "columns": {}}

        # Remove raw keys at top level
        for key in list(prof_dict.keys()):
            if key in cls.FORBIDDEN_RAW_KEYS:
                prof_dict.pop(key, None)

        # Sanitize column entries
        columns = prof_dict.get("columns", {})
        if isinstance(columns, dict):
            for col_name, col_info in columns.items():
                if isinstance(col_info, dict):
                    for key in list(col_info.keys()):
                        if key in cls.FORBIDDEN_RAW_KEYS:
                            col_info.pop(key, None)

        return prof_dict

    @classmethod
    def build_context(
        cls,
        data_profile: Optional[Union[DataProfile, Dict[str, Any]]] = None,
        target_schema: Optional[Union[Dict[str, Any], str]] = None,
        task_description: str = "",
        profile: Optional[Union[DataProfile, Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> str:
        """Assembles data profile + target schema into a formatted prompt context."""
        target_profile = data_profile if data_profile is not None else profile
        if target_profile is None:
            target_profile = {"table_name": "dataset", "total_rows": 0, "columns": {}}

        sanitized = cls.sanitize_profile(target_profile)
        
        table_name = sanitized.get("table_name", "dataset")
        total_rows = sanitized.get("total_rows", 0)
        schema_summary = sanitized.get("schema_summary", "")

        lines = [
            "=== DATASET PROFILE METADATA & AGGREGATES ===",
            "[SECURITY NOTICE: Metadata and aggregate statistics ONLY. Zero raw records attached.]",
            f"Table Name: {table_name}",
            f"Total Row Count: {total_rows}",
        ]
        if schema_summary:
            lines.append(f"Summary: {schema_summary}")

        lines.append("\n--- COLUMN METRICS & STATISTICS ---")
        columns = sanitized.get("columns", {})

        if isinstance(columns, dict):
            col_items = columns.items()
        elif isinstance(columns, list):
            col_items = [(c.get("name", f"col_{idx}"), c) for idx, c in enumerate(columns)]
        else:
            col_items = []

        for col_name, col_data in col_items:
            if isinstance(col_data, ColumnProfile):
                c_dict = col_data.model_dump()
            elif hasattr(col_data, "model_dump"):
                c_dict = col_data.model_dump()
            elif isinstance(col_data, dict):
                c_dict = col_data
            else:
                continue

            dtype = c_dict.get("data_type") or c_dict.get("dtype") or "UNKNOWN"
            total = c_dict.get("total_count", total_rows)
            null_cnt = c_dict.get("null_count", 0)
            null_pct = c_dict.get("null_percentage") or c_dict.get("null_pct") or 0.0
            distinct_cnt = c_dict.get("distinct_count") or c_dict.get("unique_count") or 0
            min_v = c_dict.get("min_val") if c_dict.get("min_val") is not None else c_dict.get("min")
            max_v = c_dict.get("max_val") if c_dict.get("max_val") is not None else c_dict.get("max")
            stats = c_dict.get("stats", {})

            col_str = f"• Column: '{col_name}' | Type: {dtype} | Total: {total} | Nulls: {null_cnt} ({null_pct:.1f}%) | Distinct: {distinct_cnt}"
            if min_v is not None or max_v is not None:
                col_str += f" | Range: [{min_v} .. {max_v}]"
            if stats:
                col_str += f" | Aggregates: {json.dumps(stats)}"
            lines.append(col_str)

        if target_schema:
            lines.append("\n=== TARGET SCHEMA & CONSTRAINTS ===")
            if isinstance(target_schema, dict):
                lines.append(json.dumps(target_schema, indent=2))
            else:
                lines.append(str(target_schema))

        if task_description:
            lines.append(f"\n=== TASK INSTRUCTIONS ===\n{task_description}")

        return "\n".join(lines)
