from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db.connection import get_db
from src.utils.table_utils import CANONICAL_DATA_TABLES, normalize_table_name

quarantine_router = APIRouter(prefix="/quarantine", tags=["Quarantine"])


class RemediateRequest(BaseModel):
    rule_id: str
    source_table: str
    sql_query: Optional[str] = None
    group_id: Optional[str] = None
    action: Optional[str] = "remediate"
    action_by: Optional[str] = "Human_Operator_HITL"


class BlockRequest(BaseModel):
    rule_id: str
    source_table: str
    group_id: Optional[str] = None
    reason: Optional[str] = "Operator confirmed permanent isolation"
    action_by: Optional[str] = "Human_Operator_HITL"


class RejectRequest(BaseModel):
    rule_id: str
    source_table: str
    group_id: Optional[str] = None
    reason: Optional[str] = "Operator rejected remediation suggestion"
    action_by: Optional[str] = "Human_Operator_HITL"


def _clean_json_val(obj: Any) -> Any:
    if isinstance(obj, float):
        return None if math.isnan(obj) or math.isinf(obj) else obj
    if isinstance(obj, dict):
        return {k: _clean_json_val(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_json_val(v) for v in obj]
    return obj


def _ensure_main_quarantine_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS main.quarantine (
            id VARCHAR PRIMARY KEY,
            snapshot_id VARCHAR,
            source_table VARCHAR,
            source_row_id INT,
            rule_id VARCHAR,
            rule_version_id VARCHAR,
            reason VARCHAR,
            original_data JSON,
            quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            lineage_hash VARCHAR,
            status VARCHAR DEFAULT 'QUARANTINED',
            user_action VARCHAR DEFAULT 'NONE',
            action_at TIMESTAMP,
            action_by VARCHAR
        )
    """)


def _this_run_quarantine_count(db) -> int:
    try:
        meta = db.execute("SELECT COALESCE(SUM(quarantine_rows), 0) FROM sandbox_preview_meta")
        n = int(meta[0][0]) if meta else 0
        if n:
            return n
    except Exception:
        pass
    try:
        tr = db.execute(
            "SELECT COUNT(*) FROM main.quarantine "
            "WHERE CAST(snapshot_id AS VARCHAR) LIKE 'sandbox:%' OR rule_version_id = 'sandbox'"
        )
        return int(tr[0][0]) if tr else 0
    except Exception:
        return 0


def _is_this_run_row(snapshot_id: Any, rule_version_id: Any) -> bool:
    snap = str(snapshot_id or "")
    ver = str(rule_version_id or "")
    return snap.startswith("sandbox:") or ver == "sandbox"


def _table_columns(db, schema: str, table: str) -> List[str]:
    res = db.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = ? AND table_name = ?
        ORDER BY ordinal_position
        """,
        [schema, table],
    )
    rows = res.fetchall() if hasattr(res, "fetchall") else res
    return [r[0] for r in rows] if rows else []


def _normalize_optional_table(source_table: Optional[str]) -> Optional[str]:
    if not source_table or source_table == "all":
        return None
    return normalize_table_name(source_table)


def synthesize_remediation_sql(rule_id: str, reason: str, source_table: str, db=None) -> Tuple[str, str, str]:
    table = normalize_table_name(source_table or "ev_telemetry")
    reason_lower = (reason or "").lower()
    severity = "CRITICAL" if any(k in reason_lower for k in ("soc", "voltage", "fare")) else "MEDIUM"
    
    remed_sql_expr = None
    strategy_desc = "Transfer reviewed rows into clean partition; main truth remains immutable."
    if db is None:
        try:
            db = get_db()
        except Exception:
            db = None

    if db is not None:
        try:
            res = db.execute("SELECT remediation_sql_expr, remediation_action FROM quality_rules WHERE id = ? OR id = ?", [rule_id, f"{table}__{rule_id}"])
            rows = res.fetchall() if hasattr(res, "fetchall") else res
            if rows and rows[0][0]:
                remed_sql_expr = rows[0][0]
                action = rows[0][1] or "REMEDIATE"
                strategy_desc = f"Apply {action} transformation ({remed_sql_expr}) to clean table."
        except Exception:
            pass

    cols = _table_columns(db, "main", table) if db is not None else []
    if cols and remed_sql_expr:
        col_exprs = []
        for c in cols:
            if c in remed_sql_expr:
                remed_src_expr = remed_sql_expr.replace(c, f"src.{c}")
                col_exprs.append(f"{remed_src_expr} AS {c}")
            else:
                col_exprs.append(f"src.{c}")
        select_clause = ", ".join(col_exprs)
    else:
        select_clause = "src.*"

    sql = (
        f"INSERT INTO clean.{table} SELECT {select_clause} FROM ("
        f"SELECT *, row_number() OVER () AS _dt_rownum FROM main.{table}"
        f") src JOIN main.quarantine q ON q.source_row_id = src._dt_rownum "
        f"WHERE q.rule_id = '{rule_id}' AND q.source_table = '{table}';"
    )
    return sql, strategy_desc, severity


@quarantine_router.get("/")
async def list_quarantine(
    limit: int = 100,
    offset: int = 0,
    source_table: Optional[str] = None,
    rule_id: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
):
    db = get_db()
    _ensure_main_quarantine_table(db)
    try:
        table_filter = _normalize_optional_table(source_table)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    query = """
        SELECT id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id, reason, original_data,
               quarantined_at, lineage_hash, COALESCE(status, 'QUARANTINED'), COALESCE(user_action, 'NONE'), action_at, action_by
        FROM main.quarantine
        WHERE 1=1
    """
    params: List[Any] = []
    if table_filter:
        query += " AND source_table = ?"
        params.append(table_filter)
    if rule_id and rule_id != "all":
        query += " AND rule_id = ?"
        params.append(rule_id)
    if status and status != "all":
        query += " AND COALESCE(status, 'QUARANTINED') = ?"
        params.append(status)
    if search:
        s = f"%{search.lower()}%"
        query += " AND (LOWER(reason) LIKE ? OR LOWER(rule_id) LIKE ? OR LOWER(source_table) LIKE ? OR LOWER(CAST(id AS VARCHAR)) LIKE ? OR LOWER(CAST(lineage_hash AS VARCHAR)) LIKE ?)"
        params.extend([s, s, s, s, s])
    query += " ORDER BY quarantined_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    try:
        rows = db.execute(query, params)
        total_res = db.execute("SELECT COUNT(*) FROM main.quarantine")
        total_count = int(total_res[0][0]) if total_res else 0
    except Exception:
        rows, total_count = [], 0

    items = []
    for r in rows:
        try:
            orig = json.loads(r[7]) if isinstance(r[7], str) else r[7]
        except Exception:
            orig = str(r[7])
        items.append({
            "id": r[0],
            "snapshot_id": r[1],
            "source_table": r[2],
            "source_row_id": r[3],
            "rule_id": r[4],
            "rule_version_id": r[5],
            "reason": r[6],
            "original_data": _clean_json_val(orig),
            "quarantined_at": str(r[8]) if r[8] else None,
            "lineage_hash": r[9],
            "status": r[10],
            "user_action": r[11],
            "action_at": str(r[12]) if r[12] else None,
            "action_by": r[13],
            "this_run": _is_this_run_row(r[1], r[5]),
        })

    return {
        "quarantine": items,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "this_run": _this_run_quarantine_count(db),
    }


@quarantine_router.get("/groups")
async def get_quarantine_groups(source_table: Optional[str] = None, status: Optional[str] = None):
    db = get_db()
    _ensure_main_quarantine_table(db)
    try:
        table_filter = _normalize_optional_table(source_table)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    query = """
        SELECT source_table, rule_id, COALESCE(status, 'QUARANTINED'), COUNT(*), MIN(reason), MIN(quarantined_at), MAX(quarantined_at)
        FROM main.quarantine
        WHERE 1=1
    """
    params: List[Any] = []
    if table_filter:
        query += " AND source_table = ?"
        params.append(table_filter)
    if status and status != "all":
        query += " AND COALESCE(status, 'QUARANTINED') = ?"
        params.append(status)
    query += " GROUP BY source_table, rule_id, COALESCE(status, 'QUARANTINED') ORDER BY COUNT(*) DESC"

    try:
        group_rows = db.execute(query, params)
    except Exception:
        group_rows = []

    groups = []
    for idx, g in enumerate(group_rows):
        table = normalize_table_name(g[0] or "ev_telemetry")
        rule = g[1]
        clean_reason = re.sub(r"\(-?\d+(?:\.\d+)?\)", "", g[4] or "").strip()
        sql_cmd, strategy, severity = synthesize_remediation_sql(rule, clean_reason, table, db=db)
        try:
            samples = db.execute(
                """
                SELECT id, source_row_id, reason, original_data, quarantined_at, lineage_hash, COALESCE(status, 'QUARANTINED')
                FROM main.quarantine
                WHERE rule_id = ? AND source_table = ?
                LIMIT 10
                """,
                [rule, table],
            )
        except Exception:
            samples = []

        sample_items = []
        for s in samples:
            try:
                orig = json.loads(s[3]) if isinstance(s[3], str) else s[3]
            except Exception:
                orig = str(s[3])
            sample_items.append({
                "id": s[0],
                "source_row_id": s[1],
                "reason": s[2],
                "original_data": _clean_json_val(orig),
                "quarantined_at": str(s[4]) if s[4] else None,
                "lineage_hash": s[5],
                "status": s[6],
            })

        groups.append({
            "group_id": f"grp_{table}_{rule}_{idx}",
            "rule_id": rule,
            "rule_name": rule,
            "source_table": table,
            "total_rows": int(g[3]),
            "severity": severity,
            "reason_summary": clean_reason,
            "ai_suggested_sql": sql_cmd,
            "remediation_strategy": strategy,
            "sample_records": sample_items,
            "earliest_time": str(g[5]) if g[5] else None,
            "latest_time": str(g[6]) if g[6] else None,
            "status": g[2],
        })

    return {"groups": groups, "total_quarantined": sum(g["total_rows"] for g in groups), "groups_count": len(groups)}


@quarantine_router.get("/count")
async def quarantine_count():
    db = get_db()
    _ensure_main_quarantine_table(db)
    this_run = _this_run_quarantine_count(db)
    try:
        rows = db.execute("SELECT source_table, COUNT(*) FROM main.quarantine GROUP BY source_table")
        counts = {}
        for r in rows or []:
            try:
                counts[normalize_table_name(r[0])] = r[1]
            except Exception:
                counts[str(r[0] or "unknown")] = r[1]
        return {"counts": counts, "this_run": this_run}
    except Exception:
        return {"counts": {}, "this_run": this_run}


@quarantine_router.post("/remediate")
async def remediate_quarantine_group(request: RemediateRequest):
    try:
        table = normalize_table_name(request.source_table)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db = get_db()
    _ensure_main_quarantine_table(db)
    actor = request.action_by or "Human_Operator_HITL"
    rule = request.rule_id
    sql_to_run, _, _ = synthesize_remediation_sql(rule, "", table, db=db)

    try:
        count_res = db.execute("SELECT COUNT(*) FROM main.quarantine WHERE source_table = ? AND rule_id = ?", [table, rule])
        affected_rows = int(count_res[0][0]) if count_res else 0

        clean_inserted = 0
        columns = _table_columns(db, "main", table)
        if columns:
            before = db.execute(f"SELECT COUNT(*) FROM clean.{table}")
            before_count = int(before[0][0]) if before else 0

            remed_expr = None
            try:
                r_rows = db.execute("SELECT remediation_sql_expr FROM quality_rules WHERE id = ? OR id = ?", [rule, f"{table}__{rule}"])
                if r_rows and r_rows[0][0]:
                    remed_expr = r_rows[0][0]
            except Exception:
                pass

            col_selects = []
            for c in columns:
                if remed_expr and c in remed_expr:
                    col_selects.append(f"({remed_expr.replace(c, 'src.' + c)}) AS {c}")
                else:
                    col_selects.append(f"src.{c}")

            select_cols = ", ".join(col_selects)
            insert_cols = ", ".join(columns)
            db.execute(
                f"""
                INSERT INTO clean.{table} ({insert_cols})
                SELECT {select_cols}
                FROM (SELECT *, row_number() OVER () AS _dt_rownum FROM main.{table}) src
                JOIN main.quarantine q
                  ON q.source_row_id = src._dt_rownum
                 AND q.source_table = ?
                 AND q.rule_id = ?
                """,
                [table, rule],
            )
            after = db.execute(f"SELECT COUNT(*) FROM clean.{table}")
            clean_inserted = max(0, int(after[0][0]) - before_count) if after else 0

        db.execute(
            """
            UPDATE main.quarantine
            SET status = 'RESOLVED', user_action = 'ACCEPT_REMEDIATE', action_at = CURRENT_TIMESTAMP, action_by = ?
            WHERE source_table = ? AND rule_id = ?
            """,
            [actor, table, rule],
        )

        for schema_tbl in CANONICAL_DATA_TABLES:
            try:
                db.execute(
                    f"UPDATE quarantine.{schema_tbl} SET status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP, resolution_action = 'ACCEPT_REMEDIATE' WHERE rule_id = ?",
                    [rule],
                )
            except Exception:
                pass

        audit_id = f"aud_{uuid.uuid4().hex[:8]}"
        audit_details = json.dumps({
            "action": "QUARANTINE_REMEDIATE",
            "rule_id": rule,
            "source_table": table,
            "sql_applied": sql_to_run,
            "remediated_rows": affected_rows,
            "clean_inserted": clean_inserted,
            "status": "RESOLVED_TO_CLEAN_DB",
        })
        event_hash = hashlib.sha256(audit_details.encode("utf-8")).hexdigest()
        try:
            db.execute(
                "INSERT INTO audit_log (id, action, actor, target_table, target_id, details, event_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [audit_id, "QUARANTINE_REMEDIATE", actor, table, rule, audit_details, event_hash],
            )
        except Exception:
            pass

        return {
            "status": "success",
            "remediated_count": affected_rows,
            "clean_inserted": clean_inserted,
            "rule_id": rule,
            "source_table": table,
            "applied_sql": sql_to_run,
            "message": f"Resolved {affected_rows:,} quarantine records from {table}; inserted {clean_inserted:,} rows into clean.{table}.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Remediation failed: {str(e)}")


@quarantine_router.post("/reject")
async def reject_quarantine_group(request: RejectRequest):
    try:
        table = normalize_table_name(request.source_table)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db = get_db()
    _ensure_main_quarantine_table(db)
    actor = request.action_by or "Human_Operator_HITL"
    rule = request.rule_id
    try:
        count_res = db.execute("SELECT COUNT(*) FROM main.quarantine WHERE source_table = ? AND rule_id = ?", [table, rule])
        affected_rows = int(count_res[0][0]) if count_res else 0
        db.execute(
            """
            UPDATE main.quarantine
            SET status = 'REJECTED_HELD', user_action = 'REJECTED', action_at = CURRENT_TIMESTAMP, action_by = ?
            WHERE source_table = ? AND rule_id = ?
            """,
            [actor, table, rule],
        )
        audit_id = f"aud_{uuid.uuid4().hex[:8]}"
        audit_details = json.dumps({"action": "QUARANTINE_REJECT", "rule_id": rule, "source_table": table, "rejected_rows": affected_rows, "reason": request.reason})
        event_hash = hashlib.sha256(audit_details.encode("utf-8")).hexdigest()
        try:
            db.execute(
                "INSERT INTO audit_log (id, action, actor, target_table, target_id, details, event_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [audit_id, "QUARANTINE_REJECT", actor, table, rule, audit_details, event_hash],
            )
        except Exception:
            pass
        return {"status": "success", "rejected_count": affected_rows, "rule_id": rule, "source_table": table, "group_status": "REJECTED_HELD"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reject failed: {str(e)}")


@quarantine_router.post("/block")
async def block_quarantine_group(request: BlockRequest):
    return await reject_quarantine_group(
        RejectRequest(rule_id=request.rule_id, source_table=request.source_table, group_id=request.group_id, reason=request.reason, action_by=request.action_by)
    )
