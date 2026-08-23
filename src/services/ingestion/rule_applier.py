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
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from src.db.connection import get_db
from src.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

# Layers that run synchronously in realtime (SUPPORTED path)
SUPPORTED_REALTIME_LAYERS = {"L1", "L3"}
# Layers that are deferred to batch processor (LAZY path)
LAZY_LAYERS = {"L2", "L4"}


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
    lazy_signals: list[dict]  # For L2/L4: signal dicts to pass to batch
    rows_processed: int
    quarantined_count: int
    deferred_count: int


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

    SUPPORTED layers (L1, L3 spatial): inline evaluation
    LAZY layers (L2, L4): returns violation with layer tag for deferred processing
    """
    layer = rule.get("layer", "L1")
    rule_id = rule.get("rule_id", "UNKNOWN")
    rule_version_id = rule.get("rule_version_id", rule_id)
    source_table = rule.get("target_table", rule.get("source_table", "unknown"))
    severity = rule.get("severity", "MEDIUM")

    # Parse rule expression
    rule_expression = rule.get("rule_expression", "")
    target_column = rule.get("target_column", "")

    # Row value extraction
    row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
    keys = list(row.keys())
    row_id = str(row.get("id", row.get(keys[0] if keys else "", "")))

    try:
        # L1: Range / null / arithmetic constraints
        if layer == "L1":
            return _apply_l1_rule(rule, row, row_dict, row_id, source_table, rule_id, rule_version_id, severity)

        # L2: Contextual drift (needs history)
        elif layer == "L2":
            return _apply_l2_signal(rule, row, row_dict, row_id, source_table, rule_id, rule_version_id, severity)

        # L3: Relational constraints
        elif layer == "L3":
            return _apply_l3_rule(rule, row, row_dict, row_id, source_table, rule_id, rule_version_id, severity)

        # L4: Changepoint detection (needs time series)
        elif layer == "L4":
            return _apply_l4_signal(rule, row, row_dict, row_id, source_table, rule_id, rule_version_id, severity)

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


def _apply_l2_signal(
    rule: dict,
    row: pd.Series,
    row_dict: dict,
    row_id: str,
    source_table: str,
    rule_id: str,
    rule_version_id: str,
    severity: str,
) -> Optional[RuleViolation]:
    """
    L2 contextual drift — returns a violation-like object tagged as L2
    for deferred batch processing. Cannot evaluate inline without history.
    """
    # Return a "LAZY" violation — marked for deferred processing
    return RuleViolation(
        rule_id=rule_id,
        rule_version_id=rule_version_id,
        source_table=source_table,
        source_row_id=row_id,
        reason=f"L2 contextual drift check deferred for entity {row_dict.get('vehicle_vin', row_id)}",
        severity=severity,
        original_data=row_dict,
        layer="L2",  # Tagged as L2 for filtering
        lineage_hash=_compute_lineage_hash(row_dict, rule_id),
    )


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
    """Evaluate L3 relational rule on a single row (SUPPORTED path)."""
    rule_expression = rule.get("rule_expression", "")
    target_column = rule.get("target_column", "")
    related_column = rule.get("related_column", "")

    if not target_column or target_column not in row_dict:
        return None

    val = row_dict.get(target_column)
    related_val = row_dict.get(related_column) if related_column else None

    # Check arithmetic consistency: e.g., fare_amount = trip_distance * rate
    if "arithmetic" in rule_expression.lower() or "+" in rule_expression or "-" in rule_expression:
        if related_val is not None and val is not None:
            try:
                fval = float(val)
                frel = float(related_val)
                # Simple cross-field check: if both non-zero, check ratio sanity
                if fval > 0 and frel > 0:
                    ratio = fval / frel
                    if ratio > 10 or ratio < 0.01:  # Unrealistic ratio
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


def _apply_l4_signal(
    rule: dict,
    row: pd.Series,
    row_dict: dict,
    row_id: str,
    source_table: str,
    rule_id: str,
    rule_version_id: str,
    severity: str,
) -> Optional[RuleViolation]:
    """
    L4 changepoint — returns a violation-like object tagged as L4
    for deferred batch processing. Cannot evaluate inline without time series.
    """
    return RuleViolation(
        rule_id=rule_id,
        rule_version_id=rule_version_id,
        source_table=source_table,
        source_row_id=row_id,
        reason=f"L4 changepoint check deferred for entity {row_dict.get('vehicle_vin', row_id)}",
        severity=severity,
        original_data=row_dict,
        layer="L4",  # Tagged as L4 for filtering
        lineage_hash=_compute_lineage_hash(row_dict, rule_id),
    )


def apply_rules_batch(
    rules: list[dict],
    df: pd.DataFrame,
    snapshot_id: str = "realtime",
) -> ApplyResult:
    """
    Apply all rules to a DataFrame batch.
    Returns ApplyResult with separated supported (L1/L3) and lazy (L2/L4) violations.
    """
    supported_violations: list[RuleViolation] = []
    lazy_signals: list[dict] = []
    quarantined_count = 0

    if df.empty or not rules:
        return ApplyResult(
            supported_violations=[],
            lazy_signals=[],
            rows_processed=0,
            quarantined_count=0,
            deferred_count=0,
        )

    # Group rules by layer for efficiency
    l1_l3_rules = [r for r in rules if r.get("layer", "L1") in SUPPORTED_REALTIME_LAYERS]
    l2_l4_rules = [r for r in rules if r.get("layer", "L1") in LAZY_LAYERS]

    # Process SUPPORTED rules (L1, L3) inline
    for _, row in df.iterrows():
        for rule in l1_l3_rules:
            violation = apply_rule_row_level(rule, row)
            if violation:
                supported_violations.append(violation)

    # LAZY rules (L2, L4): collect entity info for batch processor
    for _, row in df.iterrows():
        row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
        for rule in l2_l4_rules:
            violation = apply_rule_row_level(rule, row)
            if violation:
                lazy_signals.append({
                    "rule_id": violation.rule_id,
                    "rule_version_id": violation.rule_version_id,
                    "source_table": violation.source_table,
                    "source_row_id": violation.source_row_id,
                    "reason": violation.reason,
                    "severity": violation.severity,
                    "original_data": violation.original_data,
                    "layer": violation.layer,
                    "lineage_hash": violation.lineage_hash,
                    "event_time": datetime.now(timezone.utc).isoformat(),
                })

    return ApplyResult(
        supported_violations=supported_violations,
        lazy_signals=lazy_signals,
        rows_processed=len(df),
        quarantined_count=len(supported_violations),
        deferred_count=len(lazy_signals),
    )


def quarantine_violations(
    violations: list[RuleViolation],
    snapshot_id: str = "realtime",
) -> int:
    """
    Write violations to quarantine table.
    Returns count of rows written.
    """
    if not violations:
        return 0

    db = get_db()
    conn = db._get_master_conn()
    count = 0

    for v in violations:
        try:
            original_data_json = json.dumps(v.original_data, default=str)
            conn.execute(
                """
                INSERT INTO quarantine (
                    id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id,
                    reason, original_data, lineage_hash, status, user_action, quarantined_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'QUARANTINED', 'NONE', CURRENT_TIMESTAMP)
                """,
                [
                    f"q_{v.source_table}_{v.rule_id}_{v.source_row_id}",
                    snapshot_id,
                    v.source_table,
                    v.source_row_id,
                    v.rule_id,
                    v.rule_version_id,
                    v.reason,
                    original_data_json,
                    v.lineage_hash,
                ],
            )
            count += 1
        except Exception as exc:
            logger.warning(f"Failed to quarantine row {v.source_row_id}: {exc}")

    conn.commit()
    return count
