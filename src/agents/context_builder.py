from typing import Any, Dict, Optional
from src.tools.profiler import ProfileReport


class ContextBuilder:
    def build_context(self, profile: ProfileReport, target_schema: Optional[Dict[str, Any]] = None) -> str:
        lines = [
            f"=== DATASET PROFILE SUMMARY (Snapshot: {profile.snapshot_id}) ===",
            f"Total Rows: {profile.row_count}",
            f"Total Columns: {profile.column_count}",
            f"Duplicate Rows: {profile.duplicate_count}",
            "\n--- Column Details ---",
        ]

        for col in profile.columns:
            lines.append(
                f"- Column '{col.name}' ({col.dtype}): Nulls={col.null_count} ({col.null_pct*100:.1f}%), "
                f"Uniques={col.unique_count}, Min={col.min_val}, Max={col.max_val}"
            )

        if profile.candidate_keys:
            lines.append(f"\nCandidate Primary Keys: {', '.join(profile.candidate_keys)}")

        if profile.cross_field_correlations:
            lines.append("\nCross-Field Correlations:")
            for pair, corr in profile.cross_field_correlations.items():
                lines.append(f"  {pair}: {corr}")

        if target_schema:
            lines.append("\n=== TARGET SCHEMA REQUIREMENT ===")
            for col_name, spec in target_schema.items():
                lines.append(f"- '{col_name}': {spec}")

        return "\n".join(lines)
