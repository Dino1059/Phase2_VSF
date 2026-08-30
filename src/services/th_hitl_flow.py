"""Thanh+Huyền HITL causal-flow helpers. Calendar day = ICT = jury run_id."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

ICT = timezone(timedelta(hours=7))
DEMO_EPOCH = date(2026, 1, 1)


def day_idx_to_calendar_day(day_idx: Optional[int]) -> Optional[str]:
    if day_idx is None:
        return None
    try:
        idx = int(day_idx)
    except (TypeError, ValueError):
        return None
    if idx < -10:
        return None
    if idx == -10:
        return "2026-01-01"
    return (DEMO_EPOCH + timedelta(days=idx)).isoformat()


def calendar_day_to_day_idx(calendar_day: Optional[str]) -> Optional[int]:
    raw = (calendar_day or "").strip()[:10]
    if not raw or raw.count("-") != 2:
        return None
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        return None
    return (d - DEMO_EPOCH).days


def today_ict() -> str:
    return datetime.now(ICT).date().isoformat()


def resolve_calendar_day(calendar_day: Optional[str] = None, day_idx: Optional[int] = None) -> Optional[str]:
    raw = (calendar_day or "").strip()[:10]
    if raw and raw.count("-") == 2:
        return raw
    return day_idx_to_calendar_day(day_idx)


def day_filter_sql(alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    return (
        f"(({prefix}assigned_day_index = ? OR {prefix}day_idx = ?) "
        f"OR CAST({prefix}source_ingestion_run_id AS VARCHAR) = ?)"
    )


def _sql_str(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def pass_all_sql(sql_exprs: list[tuple[str, str]]) -> str:
    """Clean iff every predicate is known-true. NULL is not a pass."""
    if not sql_exprs:
        return "TRUE"
    return " AND ".join(f"(({e}) IS TRUE)" for _, e in sql_exprs)


def exclusive_primary_rule_sql(sql_exprs: list[tuple[str, str]]) -> str:
    """First failing rule wins. NULL / unknown counts as fail so a row is not dropped."""
    if not sql_exprs:
        return "NULL"
    parts = " ".join(f"WHEN (({expr}) IS NOT TRUE) THEN {_sql_str(rid)}" for rid, expr in sql_exprs)
    return f"(CASE {parts} ELSE NULL END)"


def _expr_runnable(db, used: str, where: str, sep: str, expr: str, params: Optional[list] = None) -> bool:
    try:
        db.execute(f"SELECT COUNT(*) FROM {used}{where}{sep}(({expr}) IS TRUE)", params or None)
        return True
    except Exception:
        return False


def ensure_th_flow_tables(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id VARCHAR PRIMARY KEY,
            title VARCHAR,
            dataset_key VARCHAR,
            calendar_day VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS hitl_decisions (
            id VARCHAR PRIMARY KEY,
            dataset_key VARCHAR,
            calendar_day VARCHAR,
            rule_id VARCHAR,
            persona VARCHAR,
            action VARCHAR,
            status VARCHAR DEFAULT 'active',
            row_ids JSON,
            details JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS rule_memory (
            dataset_key VARCHAR,
            rule_id VARCHAR,
            remembered BOOLEAN DEFAULT TRUE,
            actor VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expired_at TIMESTAMP,
            PRIMARY KEY (dataset_key, rule_id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS rule_pending_patches (
            id VARCHAR PRIMARY KEY,
            dataset_key VARCHAR,
            calendar_day VARCHAR,
            rule_id VARCHAR,
            before_expr VARCHAR,
            after_expr VARCHAR,
            status VARCHAR DEFAULT 'pending',
            proposed_by VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    for col in ("source_ingestion_run_id", "calendar_day", "approved_by", "approved_at"):
        try:
            db.execute(f"ALTER TABLE quality_rules ADD COLUMN IF NOT EXISTS {col} VARCHAR")
        except Exception:
            pass
    for col in ("calendar_day", "dataset_key", "primary_rule_id", "entity_id"):
        try:
            db.execute(f"ALTER TABLE incidents ADD COLUMN IF NOT EXISTS {col} VARCHAR")
        except Exception:
            pass
    try:
        db.execute("ALTER TABLE rule_memory ALTER COLUMN remembered SET DEFAULT TRUE")
    except Exception:
        pass


def persist_decision(
    db,
    *,
    dataset_key: str,
    calendar_day: Optional[str],
    rule_id: str,
    persona: str,
    action: str,
    row_ids: Optional[list] = None,
    details: Optional[dict] = None,
) -> str:
    ensure_th_flow_tables(db)
    did = f"dec_{uuid.uuid4().hex[:16]}"
    db.execute(
        """
        INSERT INTO hitl_decisions
            (id, dataset_key, calendar_day, rule_id, persona, action, status, row_ids, details)
        VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
        """,
        [
            did,
            dataset_key or "",
            calendar_day or "",
            rule_id,
            persona or "Steward",
            action,
            json.dumps(row_ids or []),
            json.dumps(details or {}),
        ],
    )
    if action in ("accept", "approve", "reject", "warehouse_execute") and (dataset_key or "") and rule_id:
        auto_remember_on_hitl(db, dataset_key, rule_id, persona or "Steward")
    return did


def stamp_rule_run_context(db, rule_id: str, calendar_day: Optional[str], dataset_key: Optional[str] = None) -> None:
    ensure_th_flow_tables(db)
    day = calendar_day or ""
    sets = ["source_ingestion_run_id = ?", "calendar_day = ?"]
    params: list[Any] = [day, day]
    if dataset_key:
        sets.append("dataset_key = COALESCE(dataset_key, ?)")
        params.append(dataset_key)
    params.append(rule_id)
    db.execute(f"UPDATE quality_rules SET {', '.join(sets)} WHERE id = ?", params)


def day_scoped_count(db, dataset_key: str, calendar_day: Optional[str], day_idx: Optional[int] = None) -> dict:
    """COUNT(*) for bound table+day. Never SELECT * the warehouse."""
    from src.services.dataset_engine import SANDBOX_SAMPLE_CAP, canonical_main_table

    ensure_th_flow_tables(db)
    table = canonical_main_table(dataset_key)
    day = resolve_calendar_day(calendar_day, day_idx)
    idx = calendar_day_to_day_idx(day) if day else day_idx
    sources = [f"main.{table}", f"raw.{table}"]
    total = 0
    used = ""
    for src in sources:
        try:
            if idx is None and not day:
                row = db.execute(f"SELECT COUNT(*) FROM {src}")
            else:
                row = db.execute(
                    f"SELECT COUNT(*) FROM {src} WHERE assigned_day_index = ? OR day_idx = ? "
                    f"OR CAST(source_ingestion_run_id AS VARCHAR) = ?",
                    [idx, idx, day or ""],
                )
            total = int(row[0][0]) if row else 0
            used = src
            if total > 0:
                break
        except Exception:
            continue
    preview: list[dict] = []
    if used:
        cap = min(8, SANDBOX_SAMPLE_CAP)
        sql = f"SELECT * FROM {used}"
        params = None
        if idx is not None or day:
            sql += " WHERE assigned_day_index = ? OR day_idx = ? OR CAST(source_ingestion_run_id AS VARCHAR) = ?"
            params = [idx, idx, day or ""]
        sql += f" LIMIT {cap}"
        try:
            from src.services.dataset_engine import _dicts_from_sql
            preview = _dicts_from_sql(db, sql, params)[:cap]
        except Exception:
            preview = []
    return {
        "dataset_key": dataset_key,
        "table": table,
        "calendar_day": day,
        "day_idx": idx,
        "run_id": day,
        "count": total,
        "sample_cap": SANDBOX_SAMPLE_CAP,
        "preview": preview[:8],
        "source": used,
    }


def _ensure_sandbox_preview_meta(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS sandbox_preview_meta (
            snapshot_id VARCHAR PRIMARY KEY,
            dataset_key VARCHAR,
            calendar_day VARCHAR,
            scoped_rows INTEGER,
            clean_rows INTEGER,
            quarantine_rows INTEGER,
            per_rule_counts VARCHAR,
            sample_cap INTEGER,
            counts_kind VARCHAR DEFAULT 'preview'
        )
        """
    )


def save_sandbox_preview_meta(
    db,
    *,
    snapshot_id: str,
    dataset_key: str,
    calendar_day: Optional[str],
    scoped_rows: int,
    clean_rows: int,
    quarantine_rows: int,
    per_rule_counts: Optional[dict] = None,
    sample_cap: int = 50,
    counts_kind: str = "preview",
) -> None:
    _ensure_sandbox_preview_meta(db)
    try:
        db.execute("DELETE FROM sandbox_preview_meta WHERE dataset_key = ?", [dataset_key or ""])
    except Exception:
        pass
    db.execute(
        """
        INSERT INTO sandbox_preview_meta
            (snapshot_id, dataset_key, calendar_day, scoped_rows, clean_rows, quarantine_rows,
             per_rule_counts, sample_cap, counts_kind)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            snapshot_id,
            dataset_key or "",
            calendar_day or "",
            int(scoped_rows or 0),
            int(clean_rows or 0),
            int(quarantine_rows or 0),
            json.dumps(per_rule_counts or {}),
            int(sample_cap or 50),
            counts_kind,
        ],
    )


def load_sandbox_preview_meta(db, snapshot_id: str) -> Optional[dict]:
    _ensure_sandbox_preview_meta(db)
    snap = (snapshot_id or "").strip()
    if not snap:
        return None
    try:
        rows = db.execute(
            "SELECT dataset_key, calendar_day, scoped_rows, clean_rows, quarantine_rows, "
            "per_rule_counts, sample_cap, counts_kind FROM sandbox_preview_meta WHERE snapshot_id = ?",
            [snap],
        )
    except Exception:
        return None
    if not rows:
        return None
    r = rows[0]
    per = r[5]
    if isinstance(per, str):
        try:
            per = json.loads(per)
        except Exception:
            per = {}
    return {
        "dataset_key": r[0],
        "calendar_day": r[1],
        "scoped_rows": int(r[2] or 0),
        "clean_rows": int(r[3] or 0),
        "quarantine_rows": int(r[4] or 0),
        "per_rule_counts": per if isinstance(per, dict) else {},
        "sample_cap": int(r[6] or 50),
        "counts_kind": r[7] or "preview",
        "warehouse_clean_rows": int(r[3] or 0) if (r[7] or "") == "warehouse" else 0,
        "warehouse_quarantine_rows": int(r[4] or 0) if (r[7] or "") == "warehouse" else 0,
    }


def preview_split_counts(
    db,
    dataset_key: str,
    rules: list,
    calendar_day: Optional[str] = None,
    day_idx: Optional[int] = None,
) -> dict:
    """SQL COUNT over table+day. Q = fail ≥1 rule; clean = remaining that pass all.

    Never SELECT * the warehouse. Sample LIMIT is not used for headlines.
    """
    from src.services.dataset_engine import _sql_safe_expr, canonical_main_table

    ensure_th_flow_tables(db)
    table = canonical_main_table(dataset_key)
    day = resolve_calendar_day(calendar_day, day_idx)
    idx = calendar_day_to_day_idx(day) if day else day_idx
    sources = [f"main.{table}", f"raw.{table}"]
    scoped = 0
    used = ""
    params: list[Any] = []
    where = ""
    if idx is not None or day:
        where = (
            " WHERE (assigned_day_index = ? OR day_idx = ? "
            "OR CAST(source_ingestion_run_id AS VARCHAR) = ?)"
        )
        params = [idx, idx, day or ""]
    for src in sources:
        try:
            row = db.execute(f"SELECT COUNT(*) FROM {src}{where}", params or None)
            scoped = int(row[0][0]) if row else 0
            used = src
            if scoped > 0:
                break
        except Exception:
            continue
    active = [
        r for r in (rules or [])
        if str(r.get("decision") or r.get("status") or "").lower()
        in ("approved", "edit", "edited", "proposed", "pending", "preview", "draft", "queued")
    ]
    sql_exprs: list[tuple[str, str]] = []
    for r in active:
        expr = _sql_safe_expr(
            str(r.get("custom_expression") or r.get("expression") or r.get("rule_expression") or "")
        )
        if not expr:
            continue
        rid = str(r.get("rule_id") or r.get("id") or "R1")
        sql_exprs.append((rid, expr))
    sep = " AND " if where else " WHERE "
    if used:
        sql_exprs = [(rid, e) for rid, e in sql_exprs if _expr_runnable(db, used, where, sep, e, params)]
    clean = scoped
    quarantine = 0
    per_rule: dict[str, int] = {rid: 0 for rid, _ in sql_exprs}
    if used and sql_exprs:
        pass_all = pass_all_sql(sql_exprs)
        try:
            crow = db.execute(f"SELECT COUNT(*) FROM {used}{where}{sep}({pass_all})", params or None)
            clean = int(crow[0][0]) if crow else 0
        except Exception:
            clean = scoped
        quarantine = max(0, scoped - clean)
        primary = exclusive_primary_rule_sql(sql_exprs)
        try:
            qrows = db.execute(
                f"SELECT {primary} AS primary_rule, COUNT(*) FROM {used}{where}{sep}NOT ({pass_all}) "
                f"GROUP BY 1",
                params or None,
            )
            for qr in qrows or []:
                rid = str(qr[0] or "")
                if rid:
                    per_rule[rid] = int(qr[1] or 0)
        except Exception:
            pass
    elif used:
        per_rule = {}
    return {
        "dataset_key": dataset_key,
        "table": table,
        "source": used,
        "calendar_day": day,
        "day_idx": idx,
        "scoped_rows": scoped,
        "clean_rows": clean,
        "quarantine_rows": quarantine,
        "per_rule_counts": per_rule,
        "counts_kind": "preview",
        "warehouse_clean_rows": 0,
        "warehouse_quarantine_rows": 0,
        "execute": "off",
    }


def commit_warehouse_split(
    db,
    dataset_key: str,
    rules: list,
    calendar_day: Optional[str] = None,
    day_idx: Optional[int] = None,
) -> dict:
    """Steward Execute: write clean.* + main.quarantine for table+day. Not a 3000-row sample."""
    from src.api.quarantine_api import _ensure_main_quarantine_table
    from src.services.dataset_engine import _sql_safe_expr, canonical_main_table

    approved = [
        r for r in (rules or [])
        if str(r.get("decision") or r.get("status") or "").lower() in ("approved", "edit", "edited")
    ]
    counts = preview_split_counts(db, dataset_key, approved, calendar_day, day_idx)
    used = counts.get("source") or ""
    table = counts.get("table") or canonical_main_table(dataset_key)
    day = counts.get("calendar_day")
    idx = counts.get("day_idx")
    snap = f"execute:{dataset_key}:{day or 'all'}"
    if not used or not approved:
        out = {**counts, "counts_kind": "warehouse", "committed": False, "snapshot_id": snap,
               "warehouse_clean_rows": 0, "warehouse_quarantine_rows": 0, "execute": "on"}
        return out
    where = ""
    params: list[Any] = []
    if idx is not None or day:
        where = (
            " WHERE (assigned_day_index = ? OR day_idx = ? "
            "OR CAST(source_ingestion_run_id AS VARCHAR) = ?)"
        )
        params = [idx, idx, day or ""]
    sep = " AND " if where else " WHERE "
    sql_exprs: list[tuple[str, str]] = []
    for r in approved:
        expr = _sql_safe_expr(
            str(r.get("custom_expression") or r.get("expression") or r.get("rule_expression") or "")
        )
        if expr and _expr_runnable(db, used, where, sep, expr, params):
            sql_exprs.append((str(r.get("rule_id") or r.get("id") or "R1"), expr))
    pass_all = pass_all_sql(sql_exprs)
    primary_sql = exclusive_primary_rule_sql(sql_exprs)
    _ensure_main_quarantine_table(db)
    try:
        db.execute("CREATE SCHEMA IF NOT EXISTS clean")
    except Exception:
        pass
    try:
        db.execute(f"CREATE TABLE IF NOT EXISTS clean.{table} AS SELECT * FROM {used} LIMIT 0")
    except Exception:
        pass
    try:
        db.execute(f"DELETE FROM clean.{table}{where}", params or None)
    except Exception:
        try:
            db.execute(f"DELETE FROM clean.{table}")
        except Exception:
            pass
    try:
        db.execute(
            "DELETE FROM main.quarantine WHERE source_table = ? AND rule_version_id = 'execute'",
            [dataset_key],
        )
    except Exception:
        pass
    try:
        db.execute(
            f"INSERT INTO clean.{table} BY NAME SELECT * FROM {used}{where}{sep}({pass_all})",
            params or None,
        )
    except Exception:
        try:
            db.execute(
                f"INSERT INTO clean.{table} SELECT * FROM {used}{where}{sep}({pass_all})",
                params or None,
            )
        except Exception:
            pass
    q_params = [snap, dataset_key] + list(params)
    try:
        db.execute(
            f"INSERT INTO main.quarantine "
            f"(id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id, reason, original_data) "
            f"SELECT 'wq-' || CAST(row_number() OVER () AS VARCHAR), ?, ?, "
            f"row_number() OVER (), {primary_sql}, 'execute', 'FAILED_PRIMARY_RULE', "
            f"to_json(src) FROM {used} src{where}{sep}NOT ({pass_all})",
            q_params,
        )
    except Exception:
        try:
            db.execute(
                f"INSERT INTO main.quarantine "
                f"(id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id, reason, original_data) "
                f"SELECT 'wq-' || CAST(row_number() OVER () AS VARCHAR), ?, ?, "
                f"row_number() OVER (), {primary_sql}, 'execute', 'FAILED_PRIMARY_RULE', "
                f"'{{}}' FROM {used} src{where}{sep}NOT ({pass_all})",
                q_params,
            )
        except Exception:
            pass
    save_sandbox_preview_meta(
        db,
        snapshot_id=snap,
        dataset_key=dataset_key,
        calendar_day=day,
        scoped_rows=int(counts.get("scoped_rows") or 0),
        clean_rows=int(counts.get("clean_rows") or 0),
        quarantine_rows=int(counts.get("quarantine_rows") or 0),
        per_rule_counts=counts.get("per_rule_counts") or {},
        sample_cap=0,
        counts_kind="warehouse",
    )
    return {
        **counts,
        "counts_kind": "warehouse",
        "committed": True,
        "snapshot_id": snap,
        "run_id": snap,
        "warehouse_clean_rows": int(counts.get("clean_rows") or 0),
        "warehouse_quarantine_rows": int(counts.get("quarantine_rows") or 0),
        "execute": "on",
        "promoted": True,
    }


def remember_rule(db, dataset_key: str, rule_id: str, actor: str, remember: bool = True) -> dict:
    ensure_th_flow_tables(db)
    existing = db.execute(
        "SELECT remembered FROM rule_memory WHERE dataset_key = ? AND rule_id = ?",
        [dataset_key, rule_id],
    )
    if existing:
        db.execute(
            "UPDATE rule_memory SET remembered = ?, actor = ?, expired_at = NULL, created_at = CURRENT_TIMESTAMP "
            "WHERE dataset_key = ? AND rule_id = ?",
            [remember, actor, dataset_key, rule_id],
        )
    else:
        db.execute(
            "INSERT INTO rule_memory (dataset_key, rule_id, remembered, actor) VALUES (?, ?, ?, ?)",
            [dataset_key, rule_id, remember, actor],
        )
    return {"dataset_key": dataset_key, "rule_id": rule_id, "remembered": remember, "actor": actor}


def expire_memory(db, dataset_key: str, rule_id: str, actor: str) -> dict:
    """Change-mind: expire memory ONLY. Does not undo today's decision."""
    ensure_th_flow_tables(db)
    existing = db.execute(
        "SELECT 1 FROM rule_memory WHERE dataset_key = ? AND rule_id = ?",
        [dataset_key, rule_id],
    )
    if existing:
        db.execute(
            "UPDATE rule_memory SET remembered = FALSE, expired_at = CURRENT_TIMESTAMP, actor = ? "
            "WHERE dataset_key = ? AND rule_id = ?",
            [actor, dataset_key, rule_id],
        )
    else:
        db.execute(
            "INSERT INTO rule_memory (dataset_key, rule_id, remembered, actor, expired_at) "
            "VALUES (?, ?, FALSE, ?, CURRENT_TIMESTAMP)",
            [dataset_key, rule_id, actor],
        )
    return {"dataset_key": dataset_key, "rule_id": rule_id, "remembered": False, "expired": True, "actor": actor}


def memory_is_on(db, dataset_key: str, rule_id: str) -> bool:
    """Default ON: missing row is remembered. Opt-out is remembered=FALSE or expired_at set."""
    ensure_th_flow_tables(db)
    rows = db.execute(
        "SELECT remembered, expired_at FROM rule_memory WHERE dataset_key = ? AND rule_id = ?",
        [dataset_key, rule_id],
    )
    if not rows:
        return True
    remembered, expired_at = rows[0][0], rows[0][1]
    if expired_at is not None:
        return False
    return bool(remembered)


def auto_remember_on_hitl(db, dataset_key: str, rule_id: str, actor: str) -> None:
    if not dataset_key or not rule_id:
        return
    if not memory_is_on(db, dataset_key, rule_id):
        return
    remember_rule(db, dataset_key, rule_id, actor, True)


def last_reusable_hitl(db, dataset_key: str, rule_id: str) -> Optional[dict]:
    rows = db.execute(
        """
        SELECT action, calendar_day FROM hitl_decisions
        WHERE dataset_key = ? AND rule_id = ?
          AND action IN ('accept', 'approve', 'reject')
          AND COALESCE(status, 'active') = 'active'
        ORDER BY created_at DESC LIMIT 1
        """,
        [dataset_key, rule_id],
    )
    if not rows:
        return None
    return {"action": rows[0][0], "calendar_day": str(rows[0][1] or "")}


def _replay_remembered_warehouse(db, dataset_key: str, day: str) -> list[dict]:
    """7B: Remember ON replays last Execute warehouse (clean+quarantine) on a later day."""
    rows = db.execute(
        """
        SELECT rule_id, calendar_day FROM hitl_decisions
        WHERE dataset_key = ? AND action = 'warehouse_execute'
          AND COALESCE(status, 'active') = 'active'
        ORDER BY created_at DESC
        """,
        [dataset_key],
    ) or []
    seen: set[str] = set()
    to_replay: list[str] = []
    from_day = ""
    for rid, last_day in rows:
        rid = str(rid or "")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        if not memory_is_on(db, dataset_key, rid):
            continue
        last_day_s = str(last_day or "")
        if last_day_s and last_day_s == day:
            continue
        already = db.execute(
            """
            SELECT 1 FROM hitl_decisions
            WHERE dataset_key = ? AND rule_id = ? AND calendar_day = ?
              AND action = 'warehouse_execute' AND COALESCE(status, 'active') = 'active'
            LIMIT 1
            """,
            [dataset_key, rid, day],
        )
        if already:
            continue
        to_replay.append(rid)
        from_day = from_day or last_day_s
    if not to_replay:
        return []
    qmarks = ",".join(["?"] * len(to_replay))
    try:
        qrows = db.execute(
            f"SELECT id, rule_expression FROM quality_rules WHERE id IN ({qmarks})",
            to_replay,
        ) or []
    except Exception:
        qrows = []
    rules = [
        {
            "rule_id": r[0],
            "id": r[0],
            "decision": "approved",
            "status": "approved",
            "expression": r[1],
            "rule_expression": r[1],
        }
        for r in qrows
        if r and r[0] and r[1]
    ]
    if not rules:
        return []
    out = commit_warehouse_split(db, dataset_key, rules, day, None)
    persist_decision(
        db,
        dataset_key=dataset_key,
        calendar_day=day,
        rule_id=to_replay[0],
        persona="Steward",
        action="warehouse_execute",
        details={
            "inherited": True,
            "from_day": from_day,
            "counts_kind": "warehouse",
            "warehouse_clean_rows": out.get("warehouse_clean_rows"),
            "warehouse_quarantine_rows": out.get("warehouse_quarantine_rows"),
            "rule_ids": to_replay,
        },
    )
    return [{
        "rule_id": to_replay[0],
        "status": "warehouse",
        "from_day": from_day,
        "warehouse_clean_rows": out.get("warehouse_clean_rows"),
        "warehouse_quarantine_rows": out.get("warehouse_quarantine_rows"),
    }]


def apply_inherited_hitl(db, dataset_key: str, calendar_day: Optional[str] = None) -> list[dict]:
    """Reuse last HITL action next day unless Steward opted out. Execute replay is warehouse (7B)."""
    ensure_th_flow_tables(db)
    if not dataset_key:
        return []
    day = calendar_day or ""
    proposed = db.execute(
        """
        SELECT id FROM quality_rules
        WHERE dataset_key = ?
          AND LOWER(TRIM(CAST(status AS VARCHAR))) IN ('proposed', 'pending', 'draft', 'queued')
        """,
        [dataset_key],
    ) or []
    applied: list[dict] = []
    for row in proposed:
        rid = row[0]
        if not memory_is_on(db, dataset_key, rid):
            continue
        last = last_reusable_hitl(db, dataset_key, rid)
        if not last:
            continue
        last_day = last["calendar_day"]
        if last_day and day and last_day == day:
            continue
        new_status = "rejected" if last["action"] == "reject" else "approved"
        db.execute("UPDATE quality_rules SET status = ? WHERE id = ?", [new_status, rid])
        persist_decision(
            db,
            dataset_key=dataset_key,
            calendar_day=day or None,
            rule_id=rid,
            persona="Steward",
            action="reject" if new_status == "rejected" else "accept",
            details={"inherited": True, "from_day": last_day, "from_action": last["action"]},
        )
        applied.append({"rule_id": rid, "status": new_status, "from_day": last_day})
    if day:
        applied.extend(_replay_remembered_warehouse(db, dataset_key, day))
    return applied


def memory_payload(db, dataset_key: str) -> dict:
    ensure_th_flow_tables(db)
    rows = db.execute(
        "SELECT dataset_key, rule_id, remembered, actor, created_at, expired_at "
        "FROM rule_memory WHERE dataset_key = ?",
        [dataset_key],
    ) or []
    memories: list[dict] = []
    opted_out: list[dict] = []
    for r in rows:
        rec = {
            "dataset_key": r[0],
            "rule_id": r[1],
            "remembered": bool(r[2]) and r[5] is None,
            "actor": r[3],
            "created_at": str(r[4]) if r[4] else None,
            "expired_at": str(r[5]) if r[5] else None,
        }
        (memories if rec["remembered"] else opted_out).append(rec)
    return {"dataset_key": dataset_key, "default_on": True, "memories": memories, "opted_out": opted_out}


def inherited_memories(db, dataset_key: str) -> list[dict]:
    return memory_payload(db, dataset_key)["memories"]


def last_clean_decision(db, dataset_key: str, calendar_day: Optional[str], rule_id: Optional[str] = None):
    ensure_th_flow_tables(db)
    base = (
        "SELECT id, dataset_key, calendar_day, rule_id, persona, action, row_ids, details "
        "FROM hitl_decisions WHERE dataset_key = ? AND status = 'active' "
    )
    params: list[Any] = [dataset_key]
    if calendar_day:
        base += "AND calendar_day = ? "
        params.append(calendar_day)
    wh = db.execute(base + "AND action = 'warehouse_execute' ORDER BY created_at DESC LIMIT 1", params)
    if wh:
        return wh[0]
    sql = base + "AND action IN ('accept', 'approve', 'sandbox_clean') "
    if rule_id:
        sql += "AND rule_id = ? "
        params = list(params) + [rule_id]
    sql += "ORDER BY created_at DESC LIMIT 1"
    rows = db.execute(sql, params)
    return rows[0] if rows else None


def _rollback_warehouse_clean(db, ds: str, day: Optional[str], rid: str) -> int:
    from src.services.dataset_engine import canonical_main_table

    table = canonical_main_table(ds)
    idx = calendar_day_to_day_idx(day) if day else None
    where = ""
    params: list[Any] = []
    if idx is not None or day:
        where = (
            " WHERE (assigned_day_index = ? OR day_idx = ? "
            "OR CAST(source_ingestion_run_id AS VARCHAR) = ?)"
        )
        params = [idx, idx, day or ""]
    snap = f"rollback:{ds}:{uuid.uuid4().hex[:10]}"
    moved = 0
    try:
        crow = db.execute(f"SELECT COUNT(*) FROM clean.{table}{where}", params or None)
        moved = int(crow[0][0]) if crow else 0
    except Exception:
        moved = 0
    if moved:
        try:
            db.execute(
                f"INSERT INTO main.quarantine "
                f"(id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id, reason, original_data, status, user_action) "
                f"SELECT 'rb-' || CAST(row_number() OVER () AS VARCHAR), ?, ?, "
                f"row_number() OVER (), ?, 'rollback', 'ROLLBACK_WAREHOUSE_CLEAN', to_json(src), 'QUARANTINED', 'NONE' "
                f"FROM clean.{table} src{where}",
                [snap, ds, rid or "warehouse"] + list(params),
            )
        except Exception:
            pass
        try:
            db.execute(f"DELETE FROM clean.{table}{where}", params or None)
        except Exception:
            pass
    return moved


def rollback_last_clean(db, dataset_key: str, calendar_day: Optional[str], actor: str, rule_id: Optional[str] = None) -> dict:
    """Move THOSE rows back to quarantine; mark decision superseded."""
    from src.api.quarantine_api import _ensure_main_quarantine_table
    from src.services.audit import AuditService

    ensure_th_flow_tables(db)
    _ensure_main_quarantine_table(db)
    dec = last_clean_decision(db, dataset_key, calendar_day, rule_id)
    if not dec:
        return {"status": "empty", "moved": 0, "detail": "No active clean decision to roll back"}
    dec_id, ds, day, rid, persona, action, row_ids_raw, details_raw = dec[:8]
    try:
        details = json.loads(details_raw) if isinstance(details_raw, str) else (details_raw or {})
    except Exception:
        details = {}
    if not isinstance(details, dict):
        details = {}
    if action == "warehouse_execute" or details.get("counts_kind") == "warehouse":
        moved = _rollback_warehouse_clean(db, ds, day, rid)
        db.execute("UPDATE hitl_decisions SET status = 'superseded' WHERE id = ?", [dec_id])
        persist_decision(
            db,
            dataset_key=ds,
            calendar_day=day,
            rule_id=rid,
            persona=actor,
            action="rollback",
            row_ids=[],
            details={"supersedes": dec_id, "moved": moved, "counts_kind": "warehouse"},
        )
        AuditService.log(
            "ROLLBACK_CLEAN",
            actor,
            "clean",
            dec_id,
            {"dataset_key": ds, "calendar_day": day, "rule_id": rid, "moved": moved, "kind": "warehouse"},
        )
        return {
            "status": "superseded",
            "decision_id": dec_id,
            "moved": moved,
            "dataset_key": ds,
            "calendar_day": day,
            "rule_id": rid,
            "persona": persona,
            "prior_action": action,
        }
    try:
        row_ids = json.loads(row_ids_raw) if isinstance(row_ids_raw, str) else (row_ids_raw or [])
    except Exception:
        row_ids = []
    if not isinstance(row_ids, list):
        row_ids = []
    moved = 0
    snap = f"rollback:{ds}:{uuid.uuid4().hex[:10]}"
    for rid_row in row_ids:
        qid = f"rb_{uuid.uuid4().hex[:12]}"
        try:
            try:
                row_n = int(rid_row)
            except (TypeError, ValueError):
                row_n = abs(hash(str(rid_row))) % 2_000_000_000
            db.execute(
                "INSERT INTO main.quarantine "
                "(id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id, reason, original_data, status, user_action) "
                "VALUES (?, ?, ?, ?, ?, 'rollback', ?, ?, 'QUARANTINED', 'NONE')",
                [
                    qid,
                    snap,
                    ds,
                    row_n,
                    rid,
                    "ROLLBACK_CLEAN_DECISION",
                    json.dumps({"source_row_id": rid_row, "rolled_back_from": dec_id}),
                ],
            )
            moved += 1
        except Exception:
            continue
    db.execute("UPDATE hitl_decisions SET status = 'superseded' WHERE id = ?", [dec_id])
    persist_decision(
        db,
        dataset_key=ds,
        calendar_day=day,
        rule_id=rid,
        persona=actor,
        action="rollback",
        row_ids=row_ids,
        details={"supersedes": dec_id, "moved": moved},
    )
    AuditService.log(
        "ROLLBACK_CLEAN",
        actor,
        "quarantine",
        dec_id,
        {"dataset_key": ds, "calendar_day": day, "rule_id": rid, "moved": moved},
    )
    return {
        "status": "superseded",
        "decision_id": dec_id,
        "moved": moved,
        "dataset_key": ds,
        "calendar_day": day,
        "rule_id": rid,
        "persona": persona,
        "prior_action": action,
    }


def _story_kind(entity: str) -> str:
    blob = str(entity or "").lower()
    return "station" if any(k in blob for k in ("stn", "cs-", "vg-", "charger", "station")) else "vehicle"


def _row_bit(n=None, row_ids=None) -> str:
    ids = [str(x) for x in (row_ids or []) if x not in (None, "")]
    sample = ", ".join(ids[:3])
    if n is not None and sample:
        return f"{n} dòng (vd. {sample})"
    if n is not None:
        return f"{n} dòng"
    if sample:
        return f"dòng {sample}"
    return "dòng vi phạm"


def _story_record(ds, day, entity, rule_id, n=None, reason=None, sev="HIGH", status="OPEN", inc_id=None, row_ids=None) -> dict:
    kind = _story_kind(entity)
    rid = rule_id or "cluster"
    src = ds or ""
    cday = day or ""
    noun = "Trạm" if kind == "station" else "Xe"
    rows = _row_bit(n, row_ids)
    because = reason or f"vì {rows} gắn luật {rid}"
    suspected = f"{noun} {entity} nghi {rid}"
    recommend = f"→ kiểm tra luật {rid} và cách ly ngày {cday}" if cday else f"→ kiểm tra luật {rid} và cách ly"
    return {
        "incident_id": inc_id or f"INC-{src}-{cday}-{entity}-{rid}",
        "dataset_key": src,
        "calendar_day": cday,
        "entity_id": entity,
        "entity_kind": kind,
        "primary_rule_id": rid,
        "severity": sev,
        "status": status,
        "row_ids": [str(x) for x in (row_ids or [])[:5] if x not in (None, "")],
        "copy": {
            "suspected": suspected,
            "because": because,
            "recommend": recommend,
            "sentence": f"{suspected} {because} {recommend}",
        },
        "rule_href": f"/workspace?dataset_key={src}&day={cday}&tab=tab-rules&rule_id={rid}",
        "quarantine_href": f"/workspace?dataset_key={src}&day={cday}&tab=tab-split&rule_id={rid}&entity_id={entity}",
    }


def incident_stories(db, dataset_key: Optional[str], calendar_day: Optional[str], day_idx: Optional[int] = None) -> list[dict]:
    """One incident = (dataset_key, calendar_day, entity_id, primary rule). Exclusive, not a signal dump."""
    ensure_th_flow_tables(db)
    day = resolve_calendar_day(calendar_day, day_idx)
    stories: list[dict] = []
    seen: set[tuple] = set()

    def _add(story: dict) -> None:
        key = (
            str(story.get("dataset_key") or ""),
            str(story.get("calendar_day") or ""),
            str(story.get("entity_id") or ""),
            str(story.get("primary_rule_id") or ""),
        )
        if not key[2] or key in seen:
            return
        seen.add(key)
        stories.append(story)

    entity_sql = (
        "COALESCE("
        "NULLIF(json_extract_string(original_data, '$.vehicle_vin'), ''), "
        "NULLIF(json_extract_string(original_data, '$.vin'), ''), "
        "NULLIF(json_extract_string(original_data, '$.station_id'), ''), "
        "NULLIF(json_extract_string(original_data, '$.charger_id'), ''), "
        "CAST(source_row_id AS VARCHAR))"
    )
    qsql = (
        f"SELECT COALESCE(NULLIF(rule_id, ''), 'cluster'), source_table, {entity_sql}, COUNT(*), "
        "list(CAST(source_row_id AS VARCHAR)) "
        "FROM main.quarantine "
    )
    qparams: list[Any] = []
    clauses: list[str] = []
    if dataset_key:
        clauses.append("(source_table = ? OR CAST(source_table AS VARCHAR) LIKE ?)")
        qparams.extend([dataset_key, f"%{dataset_key}%"])
    if day:
        idx = calendar_day_to_day_idx(day)
        clauses.append(
            "(TRY_CAST(json_extract_string(original_data, '$.assigned_day_index') AS INTEGER) = ? "
            "OR TRY_CAST(json_extract_string(original_data, '$.day_idx') AS INTEGER) = ? "
            "OR CAST(json_extract_string(original_data, '$.source_ingestion_run_id') AS VARCHAR) = ? "
            "OR CAST(snapshot_id AS VARCHAR) LIKE ?)"
        )
        qparams.extend([idx, idx, day, f"%:{day}"])
    if clauses:
        qsql += "WHERE " + " AND ".join(clauses) + " "
    qsql += "GROUP BY 1, 2, 3 ORDER BY COUNT(*) DESC LIMIT 80"
    try:
        qrows = db.execute(qsql, qparams) if qparams else db.execute(qsql)
    except Exception:
        try:
            qsql_plain = qsql.replace("list(CAST(source_row_id AS VARCHAR))", "NULL")
            qrows = db.execute(qsql_plain, qparams) if qparams else db.execute(qsql_plain)
        except Exception:
            qrows = []
    for qr in qrows or []:
        rid, src, entity, n = qr[:4]
        raw_ids = qr[4] if len(qr) > 4 else None
        if isinstance(raw_ids, str):
            row_ids = [x.strip() for x in raw_ids.strip("[]").split(",") if x.strip()]
        elif isinstance(raw_ids, (list, tuple)):
            row_ids = list(raw_ids)
        else:
            row_ids = []
        if not entity:
            continue
        _add(_story_record(
            src or dataset_key, day, str(entity), str(rid or "cluster"),
            n=int(n or 0), row_ids=row_ids,
        ))

    try:
        rows = db.execute(
            "SELECT incident_id, entity_ids, admission_reason, severity, status, "
            "COALESCE(dataset_key, ''), COALESCE(calendar_day, ''), COALESCE(primary_rule_id, ''), COALESCE(entity_id, '') "
            "FROM incidents ORDER BY created_at DESC LIMIT 80"
        )
    except Exception:
        try:
            rows = db.execute(
                "SELECT incident_id, entity_ids, admission_reason, severity, status "
                "FROM incidents ORDER BY created_at DESC LIMIT 80"
            )
            rows = [list(r) + ["", "", "", ""] for r in (rows or [])]
        except Exception:
            rows = []
    for r in rows or []:
        inc_id, entity_ids, reason, sev, status, ds, cday, rule_id, entity = r[:9]
        if dataset_key and ds and ds != dataset_key and dataset_key not in str(ds):
            continue
        if day and cday and cday != day:
            continue
        ents = entity_ids
        if isinstance(ents, str):
            try:
                ents = json.loads(ents)
            except Exception:
                ents = [ents]
        entity = entity or (ents[0] if isinstance(ents, list) and ents else "")
        if not entity:
            continue
        rid = str(rule_id or "cluster")
        because = f"vì dòng fail {rid} — {reason or 'vi phạm chất lượng'}"
        _add(_story_record(
            ds or dataset_key, cday or day, str(entity), rid,
            reason=because, sev=sev or "HIGH", status=status or "OPEN", inc_id=inc_id,
        ))
    return stories


def _causal_empty_state(dataset_key, calendar_day, needle: str, stories: list) -> str:
    """Honest miss: do not pick a different entity's story (t086 EV_REC_* ≠ VF8 VIN)."""
    ds = dataset_key or ""
    day = calendar_day or ""
    others = []
    for s in (stories or [])[:6]:
        ent = str(s.get("entity_id") or "").strip()
        rid = str(s.get("primary_rule_id") or "cluster").strip()
        if ent:
            others.append(f"{ent}/{rid}")
    other_bit = f" Ngày này có: {', '.join(others)}." if others else " Ngày này chưa có sự cố."
    href = f"/workspace?dataset_key={ds}&day={day}&tab=tab-rules"
    label = needle or "(không có VIN)"
    return f"Không khớp sự cố cho {label} ({ds}, {day}).{other_bit}\nLuật: {href}"


def causal_reply_for_ask(db, dataset_key, calendar_day, needle: str) -> str:
    """Human sentence for a why/quarantine ask. Empty-state if needle misses."""
    stories = incident_stories(db, dataset_key, calendar_day)
    n = (needle or "").lower()
    picked = None
    for s in stories or []:
        ent = str(s.get("entity_id") or "").lower()
        sent = str((s.get("copy") or {}).get("sentence") or "").lower()
        if n and (n in ent or n in sent):
            picked = s
            break
    if picked is None and stories:
        picked = stories[0] if not n else None
    if not picked:
        return _causal_empty_state(dataset_key, calendar_day, needle, stories)
    copy = picked.get("copy") or {}
    sentence = copy.get("sentence") or f"{copy.get('suspected', '')} {copy.get('because', '')} {copy.get('recommend', '')}".strip()
    rule_h = picked.get("rule_href") or ""
    q_h = picked.get("quarantine_href") or ""
    bits = [sentence]
    if rule_h:
        bits.append(f"Luật: {rule_h}")
    if q_h:
        bits.append(f"Cách ly: {q_h}")
    return "\n".join(bits)
