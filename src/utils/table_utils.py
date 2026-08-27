from __future__ import annotations
import re
from typing import Optional, Any

CANONICAL_DATA_TABLES = ("ev_telemetry", "charging_sessions", "trips", "nlp_feedback")
CANONICAL_DATA_SCHEMAS = ("main", "clean", "quarantine")
CANONICAL_TABLES = set(CANONICAL_DATA_TABLES)
SKIP_PIPELINE_SCHEMAS = frozenset({"clean", "quarantine"})


def normalize_table_name(table_name: Optional[str]) -> str:
    """
    Validate a table name against the canonical dataset contract:
    - ev_telemetry
    - charging_sessions
    - trips
    - nlp_feedback

    Qualified names may use main/clean/quarantine prefixes. Legacy aliases are
    intentionally rejected instead of mapped.
    """
    if not table_name:
        return "ev_telemetry"

    raw = str(table_name).strip()
    raw_lower = raw.lower()

    if "." in raw_lower:
        schema, name = raw_lower.split(".", 1)
        if schema in CANONICAL_DATA_SCHEMAS and name in CANONICAL_TABLES:
            return name

    # Handle composite rule prefixes e.g. ev_telemetry__rule_anom_raw...
    if "__rule_" in raw_lower:
        prefix = raw_lower.split("__rule_")[0]
        if prefix in CANONICAL_TABLES:
            return prefix

    if raw_lower in CANONICAL_TABLES:
        return raw_lower

    raise ValueError(f"Unknown canonical data table: {table_name}")


def canonical_pipeline_table(name: Optional[str]) -> Optional[str]:
    """Unqualified canonical table, or None. Maps clean.*/main.* and synthetic_feedback."""
    raw = (name or "").strip()
    if not raw:
        return None
    try:
        return normalize_table_name(raw)
    except ValueError:
        leaf = raw.split(".")[-1].strip().lower()
        if leaf == "synthetic_feedback":
            return "nlp_feedback"
        return None


def pipeline_target_tables(dataset_key: str, listed: Optional[list] = None) -> list[str]:
    """Tables for Run All / L1-L4 / propose. Never clean.* or quarantine.*."""
    key = (dataset_key or "").strip()
    listed = list(listed or [])
    if "::" in key:
        c = canonical_pipeline_table(key.rsplit("::", 1)[1])
        return [c] if c else []
    c = canonical_pipeline_table(key)
    if c:
        return [c]
    out: list[str] = []
    seen: set[str] = set()
    for t in listed:
        raw = str(t)
        schema = raw.split(".", 1)[0].lower() if "." in raw else "main"
        if schema in SKIP_PIPELINE_SCHEMAS:
            continue
        canon = canonical_pipeline_table(raw)
        if not canon or canon in seen:
            continue
        seen.add(canon)
        out.append(canon)
    return out


def _exec_fetch(db: Any, sql: str, params: list = None) -> list:
    res = db.execute(sql, params or [])
    if hasattr(res, "fetchall"):
        return res.fetchall()
    return res


def resolve_db_table_name(table_name: Optional[str], db: Any = None) -> str:
    """
    Resolves the actual existing canonical DB table name in main schema.
    Supports both DuckDBManager wrapper and raw DuckDBPyConnection objects.
    """
    canonical = normalize_table_name(table_name)
    if not db:
        return canonical

    raw = str(table_name).strip() if table_name else canonical
    try:
        # Check canonical table in main schema
        res_can = _exec_fetch(
            db,
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'main' AND LOWER(table_name) = ?",
            [canonical.lower()]
        )
        if res_can and res_can[0][0] > 0:
            return canonical
    except Exception:
        pass

    return canonical
