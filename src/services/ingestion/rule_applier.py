"""
rule_applier.py — Giai đoạn 4: Row-level rule engine.
Lưu tại: src/services/ingestion/rule_applier.py

Hai nhánh:
- SUPPORTED (L1, L3 spatial): sync, inline với realtime loop
- LAZY (L2/L4): deferred sang batch processor
"""

from __future__ import annotations
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from src.db.connection import get_db
from src.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

# Layers that run synchronously in realtime (Single-row 1-table path)
SUPPORTED_REALTIME_LAYERS = {"L1", "L3"}


@dataclass
class RuleViolation:
    """Represents a single rule violation found during row-level scan."""
    rule_id: str
    rule_version_id: str
    source_table: str
    source_row_id: str
    reason: str
    severity: str
    original_data: dict
    layer: str
    lineage_hash: str = ""


@dataclass
class ApplyResult:
    """Result of applying rules to a batch of rows."""
    supported_violations: list[RuleViolation]
    rows_processed: int
    quarantined_count: int


def _compute_lineage_hash(row_data: dict, rule_id: str) -> str:
    """Compute SHA-256 lineage hash for audit trail."""
    import hashlib
    content = json.dumps(row_data, sort_keys=True, default=str)
    return hashlib.sha256(f"{content}|{rule_id}".encode()).hexdigest()[:16]


def apply_rule_row_level(
    rule: dict,
    row: pd.Series,
    history: Optional[pd.DataFrame] = None,
) -> Optional[RuleViolation]:
    """
    Apply a single rule to a single DataFrame row.
    Returns RuleViolation if rule is violated, None otherwise.
    Strictly single-row 1-table evaluation (L1 / single-row L3).
    """
    layer = rule.get("layer", "L1")
    rule_id = rule.get("rule_id", "UNKNOWN")
    rule_version_id = rule.get("rule_version_id", rule_id)
    source_table = rule.get("target_table", rule.get("source_table", "unknown"))
    severity = rule.get("severity", "MEDIUM")

    # Parse rule expression
    target_column = rule.get("target_column", "")

    # Row value extraction
    row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
    raw_id = row_dict.get("id")
    if pd.isna(raw_id) or raw_id is None or str(raw_id).lower() in ("nan", "none", "null", ""):
        raw_id = getattr(row, "name", 0)
    row_id = str(raw_id) if not pd.isna(raw_id) else "0"

    try:
        # L1: Range / null / arithmetic constraints
        if layer == "L1":
            return _apply_l1_rule(rule, row, row_dict, row_id, source_table, rule_id, rule_version_id, severity)

        # L3: Relational / cross-field single-row constraints
        elif layer == "L3":
            return _apply_l3_rule(rule, row, row_dict, row_id, source_table, rule_id, rule_version_id, severity)

    except Exception as exc:
        logger.debug(f"Rule {rule_id} evaluation error on row {row_id}: {exc}")

    return None


def _apply_l1_rule(
    rule: dict,
    row: pd.Series,
    row_dict: dict,
    row_id: str,
    source_table: str,
    rule_id: str,
    rule_version_id: str,
    severity: str,
) -> Optional[RuleViolation]:
    """Evaluate L1 constraint rule on a single row."""
    target_column = rule.get("target_column", "")
    rule_expression = rule.get("rule_expression", "")

    if not target_column or target_column not in row_dict:
        return None

    val = row_dict.get(target_column)

    # Check null violation
    if "not_null" in rule_expression.lower() or "NOT NULL" in rule_expression.upper():
        if pd.isna(val) or val == "" or val is None:
            return RuleViolation(
                rule_id=rule_id,
                rule_version_id=rule_version_id,
                source_table=source_table,
                source_row_id=row_id,
                reason=f"NOT NULL violation on column '{target_column}'",
                severity=severity,
                original_data=row_dict,
                layer="L1",
                lineage_hash=_compute_lineage_hash(row_dict, rule_id),
            )

    # Check range violations from rule_expression
    # Format: "column BETWEEN min AND max" or "column < min" or "column > max"
    import re

    # Extract min/max from expressions like "battery_soc >= 0 AND battery_soc <= 100"
    if ">=" in rule_expression or "<=" in rule_expression or ">" in rule_expression or "<" in rule_expression:
        # Parse range from expression
        ge_match = re.search(rf"{target_column}\s*>=\s*([-\d.]+)", rule_expression, re.IGNORECASE)
        le_match = re.search(rf"{target_column}\s*<=\s*([-\d.]+)", rule_expression, re.IGNORECASE)
        gt_match = re.search(rf"{target_column}\s*>\s*([-\d.]+)", rule_expression, re.IGNORECASE)
        lt_match = re.search(rf"{target_column}\s*<\s*([-\d.]+)", rule_expression, re.IGNORECASE)

        min_val = float(ge_match.group(1)) if ge_match else None
        max_val = float(le_match.group(1)) if le_match else None
        if gt_match:
            min_val = float(gt_match.group(1)) + 0.0001  # exclusive
        if lt_match:
            max_val = float(lt_match.group(1)) - 0.0001  # exclusive

        if min_val is not None and val is not None:
            try:
                fval = float(val)
                if fval < min_val:
                    return RuleViolation(
                        rule_id=rule_id,
                        rule_version_id=rule_version_id,
                        source_table=source_table,
                        source_row_id=row_id,
                        reason=f"{target_column} ({fval}) < min_val ({min_val})",
                        severity=severity,
                        original_data=row_dict,
                        layer="L1",
                        lineage_hash=_compute_lineage_hash(row_dict, rule_id),
                    )
            except (ValueError, TypeError):
                pass

        if max_val is not None and val is not None:
            try:
                fval = float(val)
                if fval > max_val:
                    return RuleViolation(
                        rule_id=rule_id,
                        rule_version_id=rule_version_id,
                        source_table=source_table,
                        source_row_id=row_id,
                        reason=f"{target_column} ({fval}) > max_val ({max_val})",
                        severity=severity,
                        original_data=row_dict,
                        layer="L1",
                        lineage_hash=_compute_lineage_hash(row_dict, rule_id),
                    )
            except (ValueError, TypeError):
                pass

    return None


def _apply_l3_rule(
    rule: dict,
    row: pd.Series,
    row_dict: dict,
    row_id: str,
    source_table: str,
    rule_id: str,
    rule_version_id: str,
    severity: str,
) -> Optional[RuleViolation]:
    """Evaluate L3 single-row cross-field rule (e.g. ratio/arithmetic on 1 row)."""
    rule_expression = rule.get("rule_expression", "")
    target_column = rule.get("target_column", "")
    related_column = rule.get("related_column", "")

    if not target_column or target_column not in row_dict:
        return None

    val = row_dict.get(target_column)
    related_val = row_dict.get(related_column) if related_column else None

    if "arithmetic" in rule_expression.lower() or "+" in rule_expression or "-" in rule_expression:
        if related_val is not None and val is not None:
            try:
                fval = float(val)
                frel = float(related_val)
                if fval > 0 and frel > 0:
                    ratio = fval / frel
                    if ratio > 10 or ratio < 0.01:
                        return RuleViolation(
                            rule_id=rule_id,
                            rule_version_id=rule_version_id,
                            source_table=source_table,
                            source_row_id=row_id,
                            reason=f"Arithmetic inconsistency: {target_column}={fval}, {related_column}={frel} (ratio={ratio:.2f})",
                            severity=severity,
                            original_data=row_dict,
                            layer="L3",
                            lineage_hash=_compute_lineage_hash(row_dict, rule_id),
                        )
            except (ValueError, TypeError, ZeroDivisionError):
                pass

    return None


def apply_rules_batch(
    rules: list[dict],
    df: pd.DataFrame,
    snapshot_id: str = "realtime",
) -> ApplyResult:
    """
    Apply single-row rules (L1/L3) to a DataFrame batch in realtime.
    Returns ApplyResult with single-row violations for quarantine.
    """
    supported_violations: list[RuleViolation] = []

    if df.empty or not rules:
        return ApplyResult(
            supported_violations=[],
            rows_processed=0,
            quarantined_count=0,
        )

    # Filter single-row rules (L1, L3)
    l1_l3_rules = [r for r in rules if r.get("layer", "L1") in SUPPORTED_REALTIME_LAYERS]

    # Process single-row rules inline
    for _, row in df.iterrows():
        for rule in l1_l3_rules:
            violation = apply_rule_row_level(rule, row)
            if violation:
                supported_violations.append(violation)

    return ApplyResult(
        supported_violations=supported_violations,
        rows_processed=len(df),
        quarantined_count=len(supported_violations),
    )


def quarantine_violations(
    violations: list[RuleViolation],
    snapshot_id: str = "realtime",
) -> int:
    """
    Write violations to quarantine tables.
    Returns count of rows written.
    """
    if not violations:
        return 0

    db = get_db()
    conn = db._get_master_conn()
    count = 0

    for v in violations:
        try:
            try:
                row_id_int = int(float(v.source_row_id)) if (v.source_row_id and v.source_row_id.lower() not in ("nan", "none", "null", "")) else 0
            except (ValueError, TypeError):
                row_id_int = 0

            original_data_json = json.dumps(v.original_data, default=str)
            raw_id = f"q_{v.source_table}_{v.rule_id}_{row_id_int}_{uuid.uuid4().hex[:6]}"

            # 1. Insert into main.quarantine (explicit main schema table)
            try:
                conn.execute(
                    """
                    INSERT INTO main.quarantine (
                        id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id,
                        reason, original_data, lineage_hash, status, user_action, quarantined_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'QUARANTINED', 'NONE', CURRENT_TIMESTAMP)
                    """,
                    [
                        raw_id,
                        snapshot_id,
                        v.source_table,
                        row_id_int,
                        v.rule_id,
                        v.rule_version_id,
                        v.reason,
                        original_data_json,
                        v.lineage_hash,
                    ],
                )
            except Exception as e_main:
                logger.debug(f"main.quarantine insert warning: {e_main}")

            # 2. Insert into specific quarantine schema table (e.g. quarantine.ev_telemetry)
            target_table_name = "ev_telemetry"
            st_lower = (v.source_table or "").lower()
            if "charging" in st_lower or "station" in st_lower:
                target_table_name = "charging_sessions"
            elif "trip" in st_lower:
                target_table_name = "trips"
            elif "nlp" in st_lower or "feedback" in st_lower:
                target_table_name = "nlp_feedback"

            day_idx = 0
            try:
                day_idx = int(v.original_data.get("day_idx", v.original_data.get("assigned_day_index", 0)))
            except Exception:
                day_idx = 0

            vin = str(v.original_data.get("vehicle_vin", v.original_data.get("vin", v.original_data.get("vehicle_id", "UNKNOWN"))))

            try:
                conn.execute(
                    f"""
                    INSERT INTO quarantine.{target_table_name} (
                        quarantine_id, source_ingestion_run_id, day_idx, vehicle_vin,
                        rule_id, rule_layer, rule_name, reason, raw_row,
                        detected_at, detected_via, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, 'OPEN')
                    """,
                    [
                        raw_id,
                        snapshot_id,
                        day_idx,
                        vin,
                        v.rule_id,
                        v.layer,
                        v.rule_id,
                        v.reason,
                        original_data_json,
                        "REALTIME" if "realtime" in snapshot_id.lower() else "BATCH",
                    ],
                )
            except Exception as e_schema:
                logger.debug(f"quarantine.{target_table_name} insert warning: {e_schema}")

            count += 1
        except Exception as exc:
            logger.warning(f"Failed to quarantine row {v.source_row_id}: {exc}")

    try:
        conn.commit()
    except Exception:
        pass
    return count

