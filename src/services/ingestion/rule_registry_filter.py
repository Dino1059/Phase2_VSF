"""
rule_registry_filter.py — Giai đoạn 4: Filter approved rules by dataset_key.
Lưu tại: src/services/ingestion/rule_registry_filter.py

Responsibilities:
1. JOIN quality_rules WHERE status='approved' AND dataset_key=?
2. Group rules by layer + target_table for efficient batch processing
3. Cache rules in-memory with TTL to avoid repeated DB queries
"""

from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from src.db.connection import get_db

logger = logging.getLogger(__name__)


def _infer_layer(rule_expression: str, rule_type: str) -> str:
    """Infer layer from rule expression or rule type."""
    expr_lower = rule_expression.lower()
    type_lower = rule_type.lower()

    if "between" in expr_lower or "<" in expr_lower or ">" in expr_lower or "range" in type_lower:
        return "L1"
    if "unique" in expr_lower or "duplicate" in expr_lower:
        return "L1"
    if "null" in expr_lower or "not_null" in type_lower:
        return "L1"
    if "context" in expr_lower or "drift" in type_lower:
        return "L2"
    if "join" in expr_lower or "relate" in type_lower:
        return "L3"
    if "change" in expr_lower or "shift" in type_lower:
        return "L4"
    return "L1"


def _parse_rule_expression(rule_expression: str) -> tuple:
    """Parse target_table and target_column from rule expression."""
    import re
    expr = rule_expression.strip()

    # Pattern: table.column >= value
    match = re.match(r"([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)", expr)
    if match:
        return match.group(1), match.group(2)

    # Pattern: column >= value (no table)
    match = re.match(r"([a-zA-Z0-9_]+)\s*[<>=]", expr)
    if match:
        return "unknown", match.group(1)

    return "unknown", ""

# In-memory rule cache with TTL
_RULE_CACHE: dict[str, tuple[list[dict], float]] = {}
_CACHE_TTL_SECONDS = 60.0  # Refresh every 60 seconds


@dataclass
class RuleGroup:
    """Grouped rules by layer and target table."""
    layer: str
    target_table: str
    rules: list[dict] = field(default_factory=list)


@dataclass
class FilteredRules:
    """Result of filtering rules for a dataset."""
    all_rules: list[dict]
    by_layer: dict[str, list[dict]]
    by_table: dict[str, list[dict]]
    by_group: list[RuleGroup]  # Grouped by (layer, target_table)
    dataset_key: str
    cached_at: float
    is_cached: bool


def get_approved_rules(
    dataset_key: str,
    layer: Optional[str] = None,
    target_table: Optional[str] = None,
    use_cache: bool = True,
    cache_ttl: float = _CACHE_TTL_SECONDS,
) -> FilteredRules:
    """
    Fetch approved quality rules for a given dataset_key.
    
    Args:
        dataset_key: Dataset identifier (e.g. "vingroup_pilot")
        layer: Optional filter by layer (L1, L2, L3, L4)
        target_table: Optional filter by target table name
        use_cache: Whether to use in-memory cache
        cache_ttl: Cache TTL in seconds
    
    Returns:
        FilteredRules with all_rules, by_layer, by_table, and grouped rules
    """
    cache_key = f"{dataset_key}:{layer}:{target_table}"
    now = time.time()

    # Check cache
    if use_cache and cache_key in _RULE_CACHE:
        cached_rules, cached_at = _RULE_CACHE[cache_key]
        if now - cached_at < cache_ttl:
            return FilteredRules(
                all_rules=cached_rules,
                by_layer=_group_by_layer(cached_rules),
                by_table=_group_by_table(cached_rules),
                by_group=_group_rules(cached_rules),
                dataset_key=dataset_key,
                cached_at=cached_at,
                is_cached=True,
            )

    # Fetch from database
    try:
        db = get_db()
        conn = db._get_master_conn()

        # Try quality_rules table first
        query = """
            SELECT id, rule_name, rule_type, dataset_key, rule_expression, confidence,
                   status, proposed_by, approved_by, created_at, approved_at
            FROM quality_rules
            WHERE status = 'approved'
        """
        params: list = []

        try:
            result = conn.execute(query, params)
            rows = result.fetchall() if hasattr(result, 'fetchall') else result
        except Exception as exc:
            logger.warning(f"Failed to query quality_rules: {exc}")
            rows = []

        # Build rule dicts (schema: id, rule_name, rule_type, dataset_key, rule_expression,
        # confidence, status, proposed_by, approved_by, created_at, approved_at)
        rules: list[dict] = []
        for row in rows:
            if len(row) >= 5:
                rule_expr = str(row[4]) if len(row) > 4 and row[4] else ""
                # Parse layer from rule_expression or rule_type
                layer = _infer_layer(rule_expr, str(row[2]) if len(row) > 2 else "")
                # Parse target_table/column from rule_expression
                target_table, target_column = _parse_rule_expression(rule_expr)
                rule = {
                    "rule_id": str(row[0]),
                    "rule_name": str(row[1]) if len(row) > 1 and row[1] else str(row[0]),
                    "layer": layer,
                    "target_table": target_table,
                    "target_column": target_column,
                    "rule_expression": rule_expr,
                    "severity": "MEDIUM",
                    "status": str(row[6]) if len(row) > 6 and row[6] else "approved",
                    "dataset_key": str(row[3]) if len(row) > 3 and row[3] else dataset_key,
                    "created_at": str(row[9]) if len(row) > 9 and row[9] else "",
                    "approved_at": str(row[10]) if len(row) > 10 and row[10] else "",
                    "approved_by": str(row[8]) if len(row) > 8 and row[8] else "",
                    "rule_version_id": str(row[0]),
                    "rule_type": str(row[2]) if len(row) > 2 else "range",
                }
                rules.append(rule)

        # Update cache
        if use_cache:
            _RULE_CACHE[cache_key] = (rules, now)

        # Prune old cache entries
        _prune_cache(now)

        return FilteredRules(
            all_rules=rules,
            by_layer=_group_by_layer(rules),
            by_table=_group_by_table(rules),
            by_group=_group_rules(rules),
            dataset_key=dataset_key,
            cached_at=now,
            is_cached=False,
        )

    except Exception as exc:
        logger.warning(f"Failed to fetch rules for {dataset_key}: {exc}")
        return FilteredRules(
            all_rules=[],
            by_layer={},
            by_table={},
            by_group=[],
            dataset_key=dataset_key,
            cached_at=now,
            is_cached=False,
        )


def _group_by_layer(rules: list[dict]) -> dict[str, list[dict]]:
    """Group rules by layer (L1, L2, L3, L4)."""
    grouped: dict[str, list[dict]] = {}
    for rule in rules:
        layer = rule.get("layer", "L1")
        if layer not in grouped:
            grouped[layer] = []
        grouped[layer].append(rule)
    return grouped


def _group_by_table(rules: list[dict]) -> dict[str, list[dict]]:
    """Group rules by target_table."""
    grouped: dict[str, list[dict]] = {}
    for rule in rules:
        table = rule.get("target_table", "unknown")
        if table not in grouped:
            grouped[table] = []
        grouped[table].append(rule)
    return grouped


def _group_rules(rules: list[dict]) -> list[RuleGroup]:
    """Group rules by (layer, target_table) for efficient batch processing."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for rule in rules:
        key = (rule.get("layer", "L1"), rule.get("target_table", "unknown"))
        if key not in groups:
            groups[key] = []
        groups[key].append(rule)

    return [
        RuleGroup(layer=k[0], target_table=k[1], rules=v)
        for k, v in groups.items()
    ]


def _prune_cache(now: float) -> None:
    """Remove expired entries from rule cache."""
    global _RULE_CACHE
    expired = [k for k, (_, cached_at) in _RULE_CACHE.items() if now - cached_at > _CACHE_TTL_SECONDS * 2]
    for k in expired:
        del _RULE_CACHE[k]


def invalidate_cache(dataset_key: Optional[str] = None) -> None:
    """
    Invalidate rule cache.
    If dataset_key is provided, only invalidate that key's cache.
    Otherwise, invalidate all caches.
    """
    global _RULE_CACHE
    if dataset_key:
        keys_to_remove = [k for k in _RULE_CACHE if k.startswith(f"{dataset_key}:")]
        for k in keys_to_remove:
            del _RULE_CACHE[k]
    else:
        _RULE_CACHE.clear()
    logger.debug(f"Rule cache invalidated for {dataset_key or 'ALL'}")


def get_rules_for_realtime(
    dataset_key: str,
    include_layers: Optional[list[str]] = None,
) -> FilteredRules:
    """
    Get rules specifically for realtime processing.
    Only returns SUPPORTED layers (L1, L3 spatial) by default.
    """
    if include_layers is None:
        include_layers = ["L1", "L3"]  # SUPPORTED path only

    # Fetch all approved rules and filter
    all_rules = get_approved_rules(dataset_key)

    filtered_rules = [
        r for r in all_rules.all_rules
        if r.get("layer") in include_layers
    ]

    return FilteredRules(
        all_rules=filtered_rules,
        by_layer=_group_by_layer(filtered_rules),
        by_table=_group_by_table(filtered_rules),
        by_group=_group_rules(filtered_rules),
        dataset_key=dataset_key,
        cached_at=all_rules.cached_at,
        is_cached=all_rules.is_cached,
    )
