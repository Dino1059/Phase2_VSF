from __future__ import annotations
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from src.tools.base import BaseTool, ToolResult
from src.services.dataset_engine import load_dataset, profile_rows, generate_rules_for_baseline, execute_compiled_rules
from src.config import get_settings
from src.api.state_machine import WorkflowState
from src.utils.table_utils import canonical_pipeline_table, pipeline_target_tables


def _resolve_table_target(dataset_key: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Decompose `dataset_key` into (file_path, table_name_or_None, base_dataset_key).

    Supports both legacy single-table datasets and the multi-table notation
    `uploaded_demo::charging_sessions`. The base key is what is registered in the
    dataset registry; the optional table name selects a specific user table inside
    a DuckDB file.

    Returns:
        file_path: absolute (or cwd-relative) path to the underlying file.
        table_name: canonical table when the key names one, else None for warehouse-wide.
        base_key: registry key (without the `::table` suffix).
    """
    base_key = dataset_key
    table_name: Optional[str] = None
    if "::" in dataset_key:
        base_key, table_name = dataset_key.rsplit("::", 1)

    settings = get_settings()
    file_path = settings.get_dataset_path(base_key)
    if table_name:
        table_name = canonical_pipeline_table(table_name) or table_name
    else:
        singles = pipeline_target_tables(base_key)
        table_name = singles[0] if len(singles) == 1 else None
    return file_path, table_name, base_key


def _pipeline_tables(dataset_key: str, file_path: Optional[str], table_name: Optional[str], base_key: Optional[str]) -> List[str]:
    listed = _list_user_tables(file_path) if file_path and os.path.exists(file_path) else []
    tables = pipeline_target_tables(dataset_key, listed=listed)
    if tables:
        return tables
    if table_name:
        return [table_name]
    return [base_key] if base_key else ["ev_telemetry"]


def _list_user_tables(file_path: str) -> List[str]:
    """Return user tables for the supplied file (empty list for non-DuckDB)."""
    try:
        from src.tools.datasource import StructuredSource
        return StructuredSource(file_path).list_tables()
    except Exception:
        return []




def namespace_rule_id(dataset_key: str, rule_id: str) -> str:
    """Scope a rule id to its dataset so HITL cards do not collide across uploads."""
    key = (dataset_key or "").strip()
    rid = (rule_id or "").strip() or "rule"
    if key and not rid.startswith(f"{key}__"):
        return f"{key}__{rid}"
    return rid


def persist_hitl_proposals(dataset_key: str, proposals: list, db=None) -> list:
    """Write HITL rows /hitl/queue reads: namespaced id, dataset_key, status proposed."""
    from src.db.connection import get_db

    key = (dataset_key or "").strip()
    if db is None:
        db = get_db()
    written = []
    for p in proposals or []:
        raw_id = str(p.get("id") or p.get("rule_id") or "").strip() or "rule"
        rid = namespace_rule_id(key, raw_id)
        name = p.get("rule_name") or f"{p.get('column', 'column')} {p.get('type') or p.get('rule_type') or 'rule'}"
        rtype = p.get("type") or p.get("rule_type") or "range_check"
        expr = p.get("expression") or p.get("rule_expression") or "val != null"
        remed_act = p.get("remediation_action") or "NO_OP"
        remed_sql = p.get("remediation_sql_expr") or ""
        target_tbl = p.get("target_table") or key
        prob_disc = p.get("problem_discovered") or ""
        why_prop = p.get("why_proposed") or ""
        qual_imp = p.get("quality_impact") or ""
        try:
            conf = float(p.get("confidence", 0.95) or 0.95)
        except (TypeError, ValueError):
            conf = 0.95
        row = {**p, "id": rid, "rule_id": rid, "status": "proposed", "dataset_key": key}
        existing = []
        try:
            existing = db.execute("SELECT id, status FROM quality_rules WHERE id = ?", [rid])
        except Exception:
            existing = []
        if existing:
            try:
                db.execute(
                    "UPDATE quality_rules SET dataset_key = ?, target_table = ?, rule_name = ?, rule_type = ?, "
                    "rule_expression = ?, remediation_action = ?, remediation_sql_expr = ?, confidence = ?, "
                    "problem_discovered = ?, why_proposed = ?, quality_impact = ?, "
                    "status = CASE "
                    "WHEN lower(trim(cast(status AS VARCHAR))) IN ('approved', 'edited', 'rejected') "
                    "THEN status ELSE 'proposed' END, "
                    "proposed_by = COALESCE(proposed_by, 'dq_proposer') WHERE id = ?",
                    [key or None, target_tbl, name, rtype, expr, remed_act, remed_sql, conf, prob_disc, why_prop, qual_imp, rid],
                )
            except Exception:
                try:
                    db.execute(
                        "UPDATE quality_rules SET rule_name = ?, rule_type = ?, rule_expression = ?, "
                        "remediation_action = ?, remediation_sql_expr = ?, confidence = ?, status = 'proposed' WHERE id = ?",
                        [name, rtype, expr, remed_act, remed_sql, conf, rid],
                    )
                except Exception:
                    pass
        else:
            try:
                db.execute(
                    """INSERT INTO quality_rules (id, dataset_key, target_table, rule_name, rule_type, rule_expression, remediation_action, remediation_sql_expr, confidence, problem_discovered, why_proposed, quality_impact, status, proposed_by, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed', 'dq_proposer', CURRENT_TIMESTAMP)""",
                    [rid, key or None, target_tbl, name, rtype, expr, remed_act, remed_sql, conf, prob_disc, why_prop, qual_imp],
                )
            except Exception:
                try:
                    db.execute(
                        """INSERT INTO quality_rules (id, dataset_key, rule_name, rule_type, rule_expression, confidence, status, proposed_by, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, 'proposed', 'dq_proposer', CURRENT_TIMESTAMP)""",
                        [rid, key or None, name, rtype, expr, conf],
                    )
                except Exception:
                    pass
        written.append(row)
    return written


def approved_rules_for_clean(db, dataset_key: Optional[str] = None, rule_ids: Optional[list] = None) -> list:
    """Load HITL-approved rules. Never synthesize. Empty list means sandbox cannot invent."""
    sql = (
        "SELECT id, rule_name, rule_type, rule_expression, status FROM quality_rules "
        "WHERE lower(trim(cast(status AS VARCHAR))) IN ('approved', 'edited')"
    )
    params: list = []
    if rule_ids:
        placeholders = ",".join(["?"] * len(rule_ids))
        sql += f" AND id IN ({placeholders})"
        params.extend(list(rule_ids))
    if dataset_key:
        like = f"{dataset_key}__%"
        sql += " AND (dataset_key = ? OR id LIKE ?)"
        params.extend([dataset_key, like])
    try:
        rows = db.execute(sql, params) if params else db.execute(sql)
    except Exception:
        try:
            rows = db.execute(
                "SELECT id, rule_name, rule_type, rule_expression, status FROM quality_rules "
                "WHERE status IN ('approved', 'edited')"
            )
        except Exception:
            rows = []
    out = []
    for row in rows or []:
        status = str(row[4] or "").strip().lower()
        decision = "edit" if status == "edited" else "approved"
        out.append({
            "rule_id": row[0],
            "id": row[0],
            "name": row[1],
            "rule_name": row[1],
            "rule_type": row[2],
            "expression": row[3],
            "rule_expression": row[3],
            "decision": decision,
        })
    return out


def persist_sandbox_split(
    dataset_key: str,
    rows: list,
    exec_res: dict,
    rules: list,
    db=None,
    snapshot_id: str | None = None,
    preview_counts: dict | None = None,
    calendar_day: str | None = None,
) -> dict:
    """Persist example quarantine rows only. Headline counts come from preview_counts (SQL).

    Does not invent rows. Does not persist SANDBOX_SAMPLE_CAP as warehouse.
    snapshot_id tags THIS sandbox run so Split never shows leftover 50k/100 as this run.
    """
    from src.db.connection import get_db
    from src.services.dataset_engine import PREVIEW_ROW_CAP, safe_eval_rule

    if db is None:
        db = get_db()
    import uuid as _uuid
    key = (dataset_key or "").strip() or "dataset"
    snap = (snapshot_id or "").strip() or f"sandbox:{key}:{_uuid.uuid4().hex[:12]}"
    active = [r for r in (rules or []) if str(r.get("decision") or "").lower() in ("approved", "edit", "edited")]
    q_items = []
    indices = exec_res.get("quarantine_indices") or []
    for idx in indices:
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(rows):
            continue
        row = rows[idx]
        violated = []
        reasons = []
        for r in active:
            expr = r.get("custom_expression") or r.get("expression") or r.get("rule_expression")
            if expr is None:
                continue
            try:
                passed = safe_eval_rule(expr, row)
            except Exception:
                passed = False
            if not passed:
                rid = str(r.get("rule_id") or r.get("id") or "R1")
                violated.append(rid)
                reasons.append(f"Violated {r.get('name') or r.get('rule_name') or rid}: {expr}")
        data = row if isinstance(row, dict) else {}
        display_id = str(
            data.get("trip_id")
            or data.get("vin")
            or data.get("vehicle_vin")
            or data.get("record_id")
            or data.get("id")
            or (idx + 1)
        )
        q_items.append({
            "id": f"q-{key}-{idx + 1}",
            "source_table": key,
            "source_row_id": display_id,
            "rule_id": violated[0] if violated else "R1",
            "reason": reasons[0] if reasons else "OUT_OF_BOUNDS",
            "lineage_hash": (exec_res.get("manifest_hash") or "")[:16] or None,
            **{k: data[k] for k in data if k not in ("id",)},
        })

    import json as _json
    from src.api.quarantine_api import _ensure_main_quarantine_table
    _ensure_main_quarantine_table(db)
    try:
        db.execute(
            "DELETE FROM main.quarantine WHERE source_table = ? AND (rule_version_id = 'sandbox' OR CAST(snapshot_id AS VARCHAR) LIKE ?)",
            [key, f"sandbox:{key}:%"],
        )
    except Exception:
        try:
            db.execute("DELETE FROM main.quarantine WHERE source_table = ?", [key])
        except Exception:
            pass
    for i, item in enumerate(q_items[:PREVIEW_ROW_CAP]):
        row_n = i + 1
        qid = str(item.get("id") or f"q-{_uuid.uuid4().hex[:12]}")
        orig = {k: item[k] for k in item if k not in ("id", "source_table", "source_row_id", "rule_id", "reason", "lineage_hash")}
        try:
            db.execute(
                "INSERT INTO main.quarantine (id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id, "
                "reason, original_data, lineage_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (id) DO NOTHING",
                [
                    qid,
                    snap,
                    key,
                    row_n,
                    item["rule_id"],
                    "sandbox",
                    item["reason"],
                    _json.dumps(orig, default=str),
                    item.get("lineage_hash"),
                ],
            )
        except Exception:
            try:
                db.execute(
                    "INSERT INTO main.quarantine (id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id, "
                    "reason, original_data, lineage_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        qid, snap, key, row_n, item["rule_id"], "sandbox",
                        item["reason"], _json.dumps(orig, default=str), item.get("lineage_hash"),
                    ],
                )
            except Exception:
                pass

    clean_rows = exec_res.get("clean_db") or []
    counts = preview_counts or {}
    per_rule = counts.get("per_rule_counts") or exec_res.get("quarantine_breakdown_by_rule") or {}
    c_count = int(counts.get("clean_rows") if counts.get("clean_rows") is not None else (exec_res.get("clean_count") or len(clean_rows) or 0))
    q_count = int(counts.get("quarantine_rows") if counts.get("quarantine_rows") is not None else (exec_res.get("quarantine_count") or len(q_items) or 0))
    scoped = int(counts.get("scoped_rows") or (c_count + q_count) or 0)
    try:
        from src.services.th_hitl_flow import save_sandbox_preview_meta
        save_sandbox_preview_meta(
            db,
            snapshot_id=snap,
            dataset_key=key,
            calendar_day=calendar_day or counts.get("calendar_day"),
            scoped_rows=scoped,
            clean_rows=c_count,
            quarantine_rows=q_count,
            per_rule_counts={str(k): int(v) for k, v in (per_rule or {}).items()},
            sample_cap=PREVIEW_ROW_CAP,
        )
    except Exception:
        pass
    cell_diffs = []
    for item in q_items[:10]:
        orig = {k: item[k] for k in item if k not in ("id", "source_table", "source_row_id", "rule_id", "reason", "lineage_hash")}
        reason = str(item.get("reason") or "")
        field = next((k for k in orig if k and k in reason), None) or (next(iter(orig), None) if orig else None)
        if not field:
            continue
        cell_diffs.append({
            "row_id": str(item.get("source_row_id")),
            "field": str(field),
            "source_table": item.get("source_table"),
            "rule_id": item.get("rule_id"),
            "before_value": orig.get(field),
            "after_value": None,
            "reason": reason,
        })
    return {
        "dataset_key": key,
        "sandbox": True,
        "snapshot_id": snap,
        "run_id": snap,
        "this_run": True,
        "clean": clean_rows[:PREVIEW_ROW_CAP],
        "quarantine": q_items[:PREVIEW_ROW_CAP],
        "clean_rows": c_count,
        "quarantine_rows": q_count,
        "scoped_rows": scoped,
        "counts_kind": "preview",
        "warehouse_clean_rows": 0,
        "warehouse_quarantine_rows": 0,
        "manifest_hash": exec_res.get("manifest_hash") or "",
        "sampled_rows": min(len(rows), PREVIEW_ROW_CAP),
        "cell_diffs": cell_diffs,
        "per_rule_counts": {str(k): int(v) for k, v in per_rule.items()},
        "tables": [key],
        "execute": "off",
        "promoted": False,
    }


PREVIEW_SAMPLE_CAP = 100


def rules_for_preview(db, dataset_key: Optional[str] = None, rule_ids: Optional[list] = None, query: Optional[str] = None) -> list:
    """Load proposed/approved HITL rules for a no-write sandbox preview. Never invents rules."""
    sql = (
        "SELECT id, rule_name, rule_type, rule_expression, status FROM quality_rules "
        "WHERE lower(trim(cast(status AS VARCHAR))) NOT IN ('rejected')"
    )
    params: list = []
    if rule_ids:
        placeholders = ",".join(["?"] * len(rule_ids))
        sql += f" AND id IN ({placeholders})"
        params.extend(list(rule_ids))
    if dataset_key:
        like = f"{dataset_key}__%"
        sql += " AND (dataset_key = ? OR id LIKE ?)"
        params.extend([dataset_key, like])
    q = (query or "").strip().lower()
    if q:
        like_q = f"%{q}%"
        sql += " AND (lower(cast(id AS VARCHAR)) LIKE ? OR lower(cast(rule_name AS VARCHAR)) LIKE ? OR lower(cast(rule_expression AS VARCHAR)) LIKE ?)"
        params.extend([like_q, like_q, like_q])
    try:
        rows = db.execute(sql, params) if params else db.execute(sql)
    except Exception:
        rows = []
    out = []
    for row in rows or []:
        status = str(row[4] or "proposed").strip().lower()
        decision = "edit" if status in ("edited", "edit") else ("approved" if status == "approved" else "preview")
        out.append({
            "rule_id": row[0],
            "id": row[0],
            "name": row[1],
            "rule_name": row[1],
            "rule_type": row[2],
            "expression": row[3],
            "rule_expression": row[3],
            "status": status,
            "decision": decision,
        })
    return out


def run_sandbox_preview(
    dataset_key: str,
    rule_ids: Optional[list] = None,
    query: Optional[str] = None,
    calendar_day: Optional[str] = None,
    day_idx: Optional[int] = None,
    sample_size: Optional[int] = None,
    db=None,
) -> dict:
    """Day COUNT + sample split. Never persist quarantine/clean. Warehouse stays 0."""
    from src.db.connection import get_db
    from src.services.dataset_engine import load_sandbox_rows, execute_compiled_rules, PREVIEW_ROW_CAP
    from src.services.th_hitl_flow import day_scoped_count, preview_split_counts, resolve_calendar_day

    if db is None:
        db = get_db()
    key = (dataset_key or "").strip() or "ev_telemetry"
    rules = rules_for_preview(db, key, rule_ids=rule_ids, query=query)
    scored = [{**r, "decision": "approved"} for r in rules]
    cap = max(1, min(int(sample_size or PREVIEW_SAMPLE_CAP), PREVIEW_SAMPLE_CAP))
    day = resolve_calendar_day(calendar_day, day_idx)
    count_payload = day_scoped_count(db, key, day, day_idx)
    counts = preview_split_counts(db, key, scored, calendar_day, day_idx) if scored else {}
    sample_q: list = []
    sample_c = 0
    sample_n = 0
    note: str | None = None
    per_rule = counts.get("per_rule_counts") or {}
    if scored:
        try:
            rows = load_sandbox_rows(
                key, scored, cap, db=db, calendar_day=day, day_idx=day_idx,
            )
            exec_res = execute_compiled_rules(rows, scored)
            sample_n = len(rows)
            sample_c = int(exec_res.get("clean_count") or 0)
            sample_q = list(exec_res.get("sample_quarantined") or [])[:8]
            if not per_rule:
                per_rule = exec_res.get("quarantine_breakdown_by_rule") or {}
        except Exception as exc:
            note = f"Sample eval skipped: {exc}"
        else:
            note = None
    else:
        note = "No matching HITL rule. Preview did not write."
    q_count = int(counts.get("quarantine_rows") if counts.get("quarantine_rows") is not None else len(sample_q))
    c_count = int(counts.get("clean_rows") if counts.get("clean_rows") is not None else sample_c)
    cell_diffs = []
    for item in sample_q[:8]:
        data = item.get("data") if isinstance(item, dict) else {}
        data = data if isinstance(data, dict) else {}
        reasons = item.get("reasons") or []
        reason = reasons[0] if reasons else ""
        field = next((k for k in data if k and k in str(reason)), None) or (next(iter(data), None) if data else None)
        if not field:
            continue
        cell_diffs.append({
            "row_id": str(item.get("trip_id") or item.get("row_id") or data.get("vehicle_vin") or ""),
            "field": str(field),
            "rule_id": (item.get("violated_rule_ids") or [""])[0],
            "before_value": data.get(field),
            "after_value": None,
            "reason": reason,
        })
    return {
        "preview": True,
        "write": False,
        "sandbox": True,
        "execute": "off",
        "promoted": False,
        "dataset_key": key,
        "query": query or "",
        "rules": rules,
        "day_count": count_payload,
        "sampled_rows": sample_n or min(8, len(count_payload.get("preview") or [])),
        "sample_cap": cap,
        "clean_rows": c_count,
        "quarantine_rows": q_count,
        "warehouse_clean_rows": 0,
        "warehouse_quarantine_rows": 0,
        "counts_kind": "preview",
        "per_rule_counts": {str(k): int(v) for k, v in (per_rule or {}).items()},
        "quarantine": sample_q,
        "cell_diffs": cell_diffs,
        "tables": [key],
        "calendar_day": day,
        "note": note,
    }


class SandboxPreviewInput(BaseModel):
    dataset_key: str = Field(default="ev_telemetry", description="Workspace dataset_key")
    query: Optional[str] = Field(default=None, description="Rule name/id/expression fragment from edit-rule")
    rule_ids: Optional[List[str]] = None
    calendar_day: Optional[str] = None
    day_idx: Optional[int] = None


class SandboxPreviewTool(BaseTool):
    name = "sandbox_preview"
    description = (
        "HITL sandbox preview only: day COUNT(*) + sample split. No write. "
        "Does not list datasets, profile, or search Algolia. Does not approve or execute."
    )
    input_schema = SandboxPreviewInput

    def execute(self, input_data: dict) -> ToolResult:
        payload = run_sandbox_preview(
            dataset_key=input_data.get("dataset_key") or "ev_telemetry",
            rule_ids=input_data.get("rule_ids"),
            query=input_data.get("query"),
            calendar_day=input_data.get("calendar_day"),
            day_idx=input_data.get("day_idx"),
        )
        return ToolResult(status="success", output_data=payload)


class ListDatasetsInput(BaseModel):
    pass


class ListDatasetsTool(BaseTool):
    name = "list_datasets"
    description = "Lists all available registered datasets in DataTrust OS repository."
    input_schema = ListDatasetsInput

    def execute(self, input_data: dict) -> ToolResult:
        settings = get_settings()
        ds_list = settings.list_available_datasets()
        return ToolResult(
            status="success",
            output_data={"datasets": ds_list, "count": len(ds_list)}
        )


class ProfileDatasetInput(BaseModel):
    dataset_key: str = Field(default="vinfast_ev_telemetry_dirty", description="Target dataset key to scan and profile")


class ProfileDatasetTool(BaseTool):
    name = "profile_dataset"
    description = "Stage 1: Scans dataset schema, computes null rates, column types, distinct counts, and health score across all tables."
    input_schema = ProfileDatasetInput
    target_workflow_state = WorkflowState.PROFILED

    def execute(self, input_data: dict) -> ToolResult:
        dataset_key = input_data.get("dataset_key", "vinfast_ev_telemetry_dirty")
        try:
            file_path, table_name, base_key = _resolve_table_target(dataset_key)
            user_tables = _list_user_tables(file_path) if file_path and os.path.exists(file_path) else []

            tables_profile: Dict[str, Any] = {}
            total_rows = 0

            if user_tables and not table_name:
                from src.services.dataset_engine import PROFILE_SAMPLE_CAP
                sample = min(int(input_data.get("sample_size") or PROFILE_SAMPLE_CAP), PROFILE_SAMPLE_CAP)
                for tbl in user_tables:
                    try:
                        df = load_dataset(dataset_key=f"{base_key}::{tbl}", sample_size=sample)
                        prof = profile_rows(df)
                        tables_profile[tbl] = {
                            "total_rows": len(df),
                            "columns_count": len(df.columns),
                            "health_score": prof.get("data_health_score", 100.0),
                            "profile": prof,
                        }
                        total_rows += len(df)
                    except Exception as inner:
                        tables_profile[tbl] = {"error": str(inner)}
            else:
                from src.services.dataset_engine import PROFILE_SAMPLE_CAP
                sample = min(int(input_data.get("sample_size") or PROFILE_SAMPLE_CAP), PROFILE_SAMPLE_CAP)
                df = load_dataset(dataset_key=dataset_key, sample_size=sample)
                prof = profile_rows(df)
                key_name = table_name or base_key
                tables_profile[key_name] = {
                    "total_rows": len(df),
                    "columns_count": len(df.columns),
                    "health_score": prof.get("data_health_score", 100.0),
                    "profile": prof,
                }
                total_rows = len(df)

            health_values: List[float] = []
            for v in tables_profile.values():
                if isinstance(v, dict) and "health_score" in v:
                    health_values.append(float(v["health_score"]))
            aggregate_health = round(min(health_values), 1) if health_values else 100.0

            return ToolResult(
                status="success",
                output_data={
                    "dataset_key": dataset_key,
                    "total_rows": total_rows,
                    "columns_count": sum(
                        (v.get("columns_count", 0) if isinstance(v, dict) else 0) for v in tables_profile.values()
                    ),
                    "health_score": aggregate_health,
                    "profile": {"tables": tables_profile},
                    "tables_profiled": list(tables_profile.keys()),
                    "is_multi_table": len(tables_profile) > 1,
                },
            )
        except Exception as e:
            return ToolResult(status="error", error_message=str(e))


class DetectAnomaliesInput(BaseModel):
    dataset_key: str = Field(default="vinfast_ev_telemetry_dirty", description="Target dataset key to scan for L1-L4 anomalies")


class DetectAnomaliesTool(BaseTool):
    name = "detect_anomalies"
    description = "Stage 2: Executes multi-layer anomaly detection (L1 Range/Boundary, L2 Temporal & Contextual Drift, L3 Relational Invariants, L4 Semantic Correlation) across all tables in the dataset, producing structured anomaly findings and incidents for RCA."
    input_schema = DetectAnomaliesInput
    target_workflow_state = WorkflowState.ANOMALY_DETECTED

    def execute(self, input_data: dict) -> ToolResult:
        dataset_key = input_data.get("dataset_key", "vinfast_ev_telemetry_dirty")
        try:
            from src.orchestrator.orchestrator import _detect_l1_l4_signals, _detect_cross_table_signals
            from src.reliability.investigation.reliability_orchestrator import ReliabilityOrchestrator
            from src.reliability.incidents.service import IncidentService

            file_path, table_name, base_key = _resolve_table_target(dataset_key)
            target_tables = _pipeline_tables(dataset_key, file_path, table_name, base_key)

            all_incidents: List[Dict[str, Any]] = []
            signals_summary = {"L1": 0, "L2": 0, "L3": 0, "L4": 0}
            per_table_findings = []
            per_table_signals_for_cross: Dict[str, list] = {}

            project_id = "proj-vingroup-pilot"
            orchestrator = ReliabilityOrchestrator()
            incident_service = IncidentService()

            for tbl in target_tables:
                effective_key = f"{base_key}::{tbl}" if tbl and tbl != base_key else base_key
                try:
                    df = load_dataset(dataset_key=effective_key)
                except Exception:
                    continue

                raw_sigs = _detect_l1_l4_signals(tbl or base_key, df, project_id)
                for k in ("L1", "L2", "L3", "L4"):
                    signals_summary[k] += len(raw_sigs.get(k, []))

                all_sigs_for_tbl = []
                for sig_list in raw_sigs.values():
                    all_sigs_for_tbl.extend(sig_list)
                per_table_signals_for_cross[tbl or base_key] = all_sigs_for_tbl

                try:
                    results = orchestrator.run_pipeline(raw_sigs, project_id=project_id)
                except Exception:
                    results = []

                table_incidents = []
                for res in results:
                    inc_id = res.incident.incident_id
                    existing_meta = incident_service.get_incident_meta(inc_id) or {}
                    existing_meta["source_table"] = tbl or base_key
                    existing_meta["dataset_key"] = dataset_key
                    incident_service.set_incident_meta(inc_id, existing_meta)

                    inc_dict = {
                        "incident_id": inc_id,
                        "severity": res.incident.severity,
                        "status": res.incident.status,
                        "supporting_layers": res.incident.supporting_layers,
                        "admission_reason": res.incident.admission_reason,
                        "entity_ids": res.incident.entity_ids,
                        "signal_ids": res.incident.signal_ids,
                        "hypothesis_id": res.hypothesis.hypothesis_id if res.hypothesis else None,
                        "hypothesis_claim": res.hypothesis.claim if res.hypothesis else "",
                        "classification": res.hypothesis.classification if res.hypothesis else "DATA",
                        "confidence": res.hypothesis.confidence if res.hypothesis else 0.88,
                        "supporting_evidence": res.hypothesis.supporting_evidence if res.hypothesis else [],
                        "recommendation_id": res.recommendation.recommendation_id if res.recommendation else None,
                        "recommendation_type": getattr(res.recommendation, "recommendation_type", getattr(res.recommendation, "cause_type", "DATA")),
                        "action_type": res.recommendation.action_type if res.recommendation else "QUARANTINE_DATA",
                        "recommendation_summary": getattr(res.recommendation, "summary", ""),
                        "source_table": tbl or base_key,
                        "dataset_key": dataset_key,
                    }
                    table_incidents.append(inc_dict)

                all_incidents.extend(table_incidents)
                per_table_findings.append({
                    "table_name": tbl or base_key,
                    "rows_analyzed": len(df),
                    "signals": {k: len(v) for k, v in raw_sigs.items()},
                    "incident_count": len(table_incidents),
                    "incidents": table_incidents,
                })

            if len(per_table_signals_for_cross) > 1:
                cross_signals = _detect_cross_table_signals(
                    per_table_signals_for_cross, project_id=project_id, dataset_key=dataset_key
                )
                if cross_signals:
                    signals_summary["L3"] += len(cross_signals)
                    try:
                        cross_results = orchestrator.run_pipeline({"L3": cross_signals, "L1": [], "L2": [], "L4": []}, project_id=project_id)
                    except Exception:
                        cross_results = []

                    for res in cross_results:
                        inc_id = res.incident.incident_id
                        source_tbl_str = "+".join(per_table_signals_for_cross.keys())
                        existing_meta = incident_service.get_incident_meta(inc_id) or {}
                        existing_meta["source_table"] = source_tbl_str
                        existing_meta["dataset_key"] = dataset_key
                        existing_meta["cross_table"] = True
                        incident_service.set_incident_meta(inc_id, existing_meta)

                        cross_inc_dict = {
                            "incident_id": inc_id,
                            "severity": res.incident.severity,
                            "status": res.incident.status,
                            "supporting_layers": res.incident.supporting_layers,
                            "admission_reason": res.incident.admission_reason,
                            "entity_ids": res.incident.entity_ids,
                            "signal_ids": res.incident.signal_ids,
                            "hypothesis_id": res.hypothesis.hypothesis_id if res.hypothesis else None,
                            "hypothesis_claim": res.hypothesis.claim if res.hypothesis else "",
                            "classification": res.hypothesis.classification if res.hypothesis else "DATA",
                            "confidence": res.hypothesis.confidence if res.hypothesis else 0.88,
                            "supporting_evidence": res.hypothesis.supporting_evidence if res.hypothesis else [],
                            "recommendation_id": res.recommendation.recommendation_id if res.recommendation else None,
                            "recommendation_type": getattr(res.recommendation, "recommendation_type", getattr(res.recommendation, "cause_type", "DATA")),
                            "action_type": res.recommendation.action_type if res.recommendation else "QUARANTINE_DATA",
                            "recommendation_summary": getattr(res.recommendation, "summary", ""),
                            "source_table": source_tbl_str,
                            "dataset_key": dataset_key,
                            "cross_table": True,
                        }
                        all_incidents.append(cross_inc_dict)

            layers_triggered = [k for k, v in signals_summary.items() if v > 0] or ["L1"]
            total_signals = sum(signals_summary.values())

            return ToolResult(
                status="success",
                output_data={
                    "dataset_key": dataset_key,
                    "tables_checked": target_tables,
                    "total_signals": total_signals,
                    "signals_summary": signals_summary,
                    "incident_count": len(all_incidents),
                    "incidents": all_incidents,
                    "layers_triggered": layers_triggered,
                    "per_table": per_table_findings,
                    "summary": f"Detected {total_signals} telemetry signals across layers {layers_triggered} and identified {len(all_incidents)} admitted incidents across {len(target_tables)} table(s)."
                }
            )
        except Exception as e:
            return ToolResult(status="error", error_message=str(e))


class ProposeQualityRulesInput(BaseModel):
    dataset_key: str = Field(default="vinfast_ev_telemetry_dirty", description="Target dataset key to analyze for rule proposal")
    anomaly_findings: Optional[Dict[str, Any]] = Field(default=None, description="Optional structured anomaly findings from Stage 2")
    profile_summary: Optional[Dict[str, Any]] = Field(default=None, description="Optional Stage 1 profile summary for typed rule context")


class ProposeQualityRulesTool(BaseTool):
    name = "propose_quality_rules"
    description = "Stage 3: Synthesizes targeted data quality rules grounded in BOTH Stage 1 Profile Summary AND Stage 2 L1-L4 Anomaly Findings for Human-In-The-Loop review."
    input_schema = ProposeQualityRulesInput
    target_workflow_state = WorkflowState.RULES_PROPOSED

    def execute(self, input_data: dict) -> ToolResult:
        dataset_key = input_data.get("dataset_key", "vinfast_ev_telemetry_dirty")
        anomaly_findings = input_data.get("anomaly_findings") if isinstance(input_data.get("anomaly_findings"), dict) else {}

        try:
            file_path, table_name, base_key = _resolve_table_target(dataset_key)
            target_tables = _pipeline_tables(dataset_key, file_path, table_name, base_key)

            proposals: List[Dict[str, Any]] = []
            from src.services.dataset_engine import PROFILE_SAMPLE_CAP
            from src.tools.rule_proposer import RuleProposerTool

            for tbl in target_tables:
                canon = canonical_pipeline_table(tbl) or tbl or "ev_telemetry"
                effective_key = f"{base_key}::{canon}" if canon else base_key
                try:
                    extra = RuleProposerTool().execute({
                        "target_table": canon,
                        "profile_summary": input_data.get("profile_summary") or {},
                        "anomaly_findings": anomaly_findings,
                    })
                    for r in extra.get("proposed_rules") or extra.get("proposals") or []:
                        if not isinstance(r, dict):
                            continue
                        expr = r.get("rule_expression") or r.get("expression")
                        if not expr:
                            continue
                        proposals.append({
                            "id": r.get("rule_name") or f"{canon}_rule",
                            "type": r.get("rule_type", "range"),
                            "column": str(expr).split()[0] if expr else canon,
                            "expression": expr,
                            "description": r.get("problem_discovered") or r.get("rule_name") or "canonical policy rule",
                            "severity": "warning",
                            "status": "pending",
                            "table_name": canon,
                            "dataset_key": dataset_key,
                            "source": "rule_proposer",
                            "rule_name": r.get("rule_name"),
                            "rule_expression": expr,
                            "remediation_action": r.get("remediation_action"),
                            "remediation_sql_expr": r.get("remediation_sql_expr"),
                            "confidence": r.get("confidence", 0.95),
                            "problem_discovered": r.get("problem_discovered"),
                            "why_proposed": r.get("why_proposed"),
                            "quality_impact": r.get("quality_impact"),
                        })
                except Exception:
                    pass
                try:
                    sample = min(int(input_data.get("sample_size") or PROFILE_SAMPLE_CAP), PROFILE_SAMPLE_CAP)
                    df = load_dataset(dataset_key=effective_key, sample_size=sample)
                    profile_data = profile_rows(df)
                    rules, _ = generate_rules_for_baseline("A1", profile_data)
                except Exception:
                    rules = []

                for i, r in enumerate(rules):
                    if isinstance(r, dict):
                        rf = r.get("rule_type") or r.get("rule_family") or "range_check"
                        col = r.get("column") or "dataset"
                        expr = r.get("expression") or "val != null"
                        desc = r.get("description") or f"Enforce {rf} constraint on {col}"
                        sev = str(r.get("severity", r.get("risk_level", "warning"))).lower()
                        rid = r.get("rule_id") or f"prop_{tbl or base_key}_{i+1}"
                    else:
                        rf = r.rule_family.value if hasattr(r.rule_family, "value") else str(r.rule_family)
                        col = r.column or "dataset"
                        expr = r.expression
                        desc = f"Enforce {rf} constraint on {r.column or 'dataset'}"
                        sev = r.severity.value.lower() if hasattr(r.severity, "value") else str(r.severity).lower()
                        rid = r.rule_id

                    if sev not in ["critical", "warning", "info", "high", "medium", "low"]:
                        sev = "warning"
                    sev_norm = {"high": "critical", "medium": "warning", "low": "info"}.get(sev, sev)

                    proposals.append({
                        "id": rid,
                        "type": rf,
                        "column": col,
                        "expression": expr,
                        "description": desc,
                        "severity": sev_norm,
                        "status": "pending",
                        "table_name": canon,
                        "dataset_key": dataset_key,
                        "source": "baseline_profiler",
                    })

                # Synthesize rules directly targeting L1-L4 anomaly findings
                if anomaly_findings:
                    incidents = anomaly_findings.get("incidents", [])
                    for idx, inc in enumerate(incidents):
                        inc_tbl = inc.get("source_table") or tbl
                        if tbl and inc_tbl and inc_tbl != tbl:
                            continue
                        layers = inc.get("supporting_layers", [])
                        inc_id = inc.get("incident_id", f"inc_{idx+1}")
                        claim = (inc.get("hypothesis_claim", "") or inc.get("admission_reason", "") or "").lower()
                        entity_str = str(inc.get("entity_ids", [])).lower()
                        reason_str = str(inc.get("admission_reason", "")).lower()
                        text_corpus = f"{claim} {reason_str} {entity_str}"

                        rule_id = f"rule_anom_{inc_tbl or base_key}_{idx+1}"
                        severity = "critical" if inc.get("severity") in ("CRITICAL", "HIGH") else "warning"

                        # Precision heuristic mapping matching fault_manifest.json L1-L4 fault patterns
                        if "soc" in text_corpus or "battery_soc" in text_corpus:
                            rule_type = "range_boundary_check"
                            rule_col = "battery_soc"
                            rule_expr = "battery_soc >= 0 AND battery_soc <= 100"
                            rule_desc = f"L1/L2 Battery SOC boundary constraint for {inc_id}"
                        elif "voltage" in text_corpus or "overvoltage" in text_corpus:
                            rule_type = "range_boundary_check"
                            rule_col = "battery_voltage"
                            rule_expr = "battery_voltage >= 0 AND battery_voltage <= 1000"
                            rule_desc = f"L1 Voltage surge constraint for {inc_id}"
                        elif "fare_amount" in text_corpus or "negative fare" in text_corpus or "fare" in text_corpus:
                            rule_type = "range_boundary_check"
                            rule_col = "fare_amount"
                            rule_expr = "fare_amount >= 0"
                            rule_desc = f"L1 Fare amount non-negative constraint for {inc_id}"
                        elif "ledger" in text_corpus or "total_fare" in text_corpus or "mismatch" in text_corpus:
                            rule_type = "relational_invariant"
                            rule_col = "total_fare"
                            rule_expr = "ABS(total_fare - (fare_amount + COALESCE(tip_amount, 0))) < 0.01"
                            rule_desc = f"L1 Accounting ledger sum invariant for {inc_id}"
                        elif "cost" in text_corpus or "cost_vnd" in text_corpus:
                            rule_type = "range_boundary_check"
                            rule_col = "cost_vnd"
                            rule_expr = "cost_vnd >= 0"
                            rule_desc = f"L1 Charging cost non-negative constraint for {inc_id}"
                        elif "temp" in text_corpus or "thermal" in text_corpus:
                            rule_type = "contextual_drift_limit"
                            rule_col = "battery_temp_c"
                            rule_expr = "battery_temp_c BETWEEN -20 AND 65"
                            rule_desc = f"L2 Thermal degradation drift bound for {inc_id}"
                        elif "rpm" in text_corpus or "speed" in text_corpus:
                            rule_type = "relational_invariant"
                            rule_col = "motor_rpm"
                            rule_expr = "NOT (speed = 0 AND motor_rpm > 1000)"
                            rule_desc = f"L3 Speed vs Motor RPM sync invariant for {inc_id}"
                        elif "duration" in text_corpus or "energy" in text_corpus or "kwh" in text_corpus:
                            rule_type = "relational_invariant"
                            rule_col = "duration_mins"
                            rule_expr = "NOT (duration_mins > 180 AND energy_kwh < 5.0)"
                            rule_desc = f"L3 Charging duration vs energy invariant for {inc_id}"
                        elif "frequency" in text_corpus or "cusum" in text_corpus or "shift" in text_corpus:
                            rule_type = "semantic_enum_check"
                            rule_col = "charging_frequency"
                            rule_expr = "charging_frequency <= 3"
                            rule_desc = f"L4 Fleet charging frequency regime bound for {inc_id}"
                        else:
                            if "L1" in layers:
                                rule_expr = "battery_voltage >= 0 AND battery_voltage <= 1000" if "voltage" in text_corpus else "val IS NOT NULL"
                                rule_type = "range_boundary_check"
                                rule_col = "telemetry"
                                rule_desc = f"L1 Range constraint to resolve {inc_id}"
                            elif "L2" in layers:
                                rule_expr = "ABS(rate_of_change) < 3.5"
                                rule_type = "contextual_drift_limit"
                                rule_col = "telemetry"
                                rule_desc = f"L2 Temporal Drift bound to resolve {inc_id}"
                            elif "L3" in layers:
                                rule_expr = "voltage * current <= max_power_kw * 1000"
                                rule_type = "relational_invariant"
                                rule_col = "telemetry"
                                rule_desc = f"L3 Physical invariant check for {inc_id}"
                            else:
                                rule_expr = "status IN ('active', 'charging', 'idle')"
                                rule_type = "semantic_enum_check"
                                rule_col = "status"
                                rule_desc = f"L4 Semantic constraint for {inc_id}"

                        proposals.append({
                            "id": rule_id,
                            "type": rule_type,
                            "column": rule_col,
                            "expression": rule_expr,
                            "description": rule_desc,
                            "severity": severity,
                            "status": "pending",
                            "table_name": inc_tbl or tbl,
                            "dataset_key": effective_key,
                            "source": "anomaly_detector_l1_l4",
                        })

            # Deduplicate proposals before persisting to DuckDB quality_rules table for HITL review
            unique_proposals = []
            seen_signatures = set()
            for p in proposals:
                sig_key = (p.get("table_name"), p.get("column"), p.get("type"), p.get("expression"))
                if sig_key not in seen_signatures:
                    seen_signatures.add(sig_key)
                    unique_proposals.append(p)
            proposals = unique_proposals

            try:
                persisted = persist_hitl_proposals(dataset_key, proposals)
                if persisted:
                    proposals = persisted
            except Exception as dbe:
                print(f"[WARN] Could not persist quality_rules to DuckDB: {dbe}")

            return ToolResult(
                status="success",
                output_data={
                    "dataset_key": dataset_key,
                    "proposals": proposals,
                    "count": len(proposals),
                    "tables_covered": target_tables,
                    "grounded_in_anomalies": bool(anomaly_findings),
                }
            )
        except Exception as e:
            return ToolResult(status="error", error_message=str(e))


class CleanDatabaseInput(BaseModel):
    dataset_key: str = Field(default="vinfast_ev_telemetry_dirty", description="Target dataset key to execute approved rules on")


class CleanDatabaseTool(BaseTool):
    name = "clean_database"
    description = "Stage 4: Applies approved quality constraints, partitions corrupted rows into quarantine, and creates clean database snapshot with SHA-256 lineage manifest."
    input_schema = CleanDatabaseInput
    target_workflow_state = WorkflowState.COMPLETED

    def execute(self, input_data: dict) -> ToolResult:
        dataset_key = input_data.get("dataset_key", "vinfast_ev_telemetry_dirty")
        from src.db.connection import get_db
        db = get_db()

        try:
            file_path, table_name, base_key = _resolve_table_target(dataset_key)
            user_tables = _list_user_tables(file_path) if file_path and os.path.exists(file_path) else []
        except Exception:
            file_path, table_name, base_key, user_tables = None, None, dataset_key, []

        target_tables: List[Optional[str]] = [table_name] if table_name else (user_tables if user_tables else [None])

        approved_rules = approved_rules_for_clean(db, base_key or dataset_key)
        if not approved_rules:
            return ToolResult(
                status="error",
                error_message="Rule execution denied: No rules are approved by HITL",
                output_data={"status": "awaiting_hitl", "writes": 0},
            )

        per_table_results: List[Dict[str, Any]] = []
        total_processed = 0
        total_clean = 0
        total_quarantine = 0
        combined_manifest_hash = ""

        for tbl in target_tables:
            effective_key = f"{base_key}::{tbl}" if tbl else base_key
            try:
                df = load_dataset(dataset_key=effective_key)
                table_rules = [r for r in approved_rules if not tbl or r.get("table_name") in (None, tbl)]
                if not table_rules:
                    table_rules = approved_rules
                result = execute_compiled_rules(df.to_dict("records"), table_rules)
                per_table_results.append({
                    "table_name": tbl,
                    "total_processed": result.get("total_processed", len(df)),
                    "clean_count": result.get("clean_count", 0),
                    "quarantine_count": result.get("quarantine_count", 0),
                    "quarantine_rate_pct": result.get("quarantine_rate_pct", 0.0),
                    "manifest_hash": result.get("manifest_hash", ""),
                })
                total_processed += result.get("total_processed", len(df))
                total_clean += result.get("clean_count", 0)
                total_quarantine += result.get("quarantine_count", 0)
                combined_manifest_hash += result.get("manifest_hash", "")
            except Exception as e:
                per_table_results.append({"table_name": tbl, "error": str(e)})

        overall_quarantine_rate = round(
            (total_quarantine / total_processed * 100.0) if total_processed > 0 else 0.0, 2
        )

        return ToolResult(
            status="success",
            output_data={
                "dataset_key": dataset_key,
                "execution_result": {
                    "total_processed": total_processed,
                    "clean_count": total_clean,
                    "quarantine_count": total_quarantine,
                    "quarantine_rate_pct": overall_quarantine_rate,
                    "manifest_hash": combined_manifest_hash,
                    "status": "CLEAN_DATABASE_CREATED",
                    "per_table": per_table_results,
                },
            },
        )


class RunFullPipelineInput(BaseModel):
    dataset_key: str = Field(default="vinfast_ev_telemetry_dirty", description="Target dataset key to execute complete 4-stage pipeline")


class RunFullPipelineTool(BaseTool):
    name = "run_full_pipeline"
    description = "Executes the analysis pipeline through HITL: Stage 1 (Profile) -> Stage 2 (L1-L4 Anomaly Detection) -> Stage 3 (Rule Proposal). Stops before clean; Stage 4 runs only after steward approval."
    input_schema = RunFullPipelineInput
    target_workflow_state = WorkflowState.RULES_PROPOSED

    def execute(self, input_data: dict) -> ToolResult:
        dataset_key = input_data.get("dataset_key", "vinfast_ev_telemetry_dirty")

        # Step 1: Profiling
        prof_tool = ProfileDatasetTool()
        prof_res = prof_tool.execute({"dataset_key": dataset_key})
        prof_data = prof_res.output_data if prof_res.status == "success" else {}

        # Step 2: Anomaly Detection L1-L4
        anom_tool = DetectAnomaliesTool()
        anom_res = anom_tool.execute({"dataset_key": dataset_key})
        anom_data = anom_res.output_data if anom_res.status == "success" else {}

        # Step 3: Propose Rules based on Profile + Anomalies; stop at HITL
        rules_tool = ProposeQualityRulesTool()
        rules_res = rules_tool.execute({
            "dataset_key": dataset_key,
            "profile_summary": prof_data,
            "anomaly_findings": anom_data,
        })
        rules_data = rules_res.output_data if rules_res.status == "success" else {}

        return ToolResult(
            status="success",
            output_data={
                "status": "awaiting_hitl",
                "dataset_key": dataset_key,
                "profile": prof_data,
                "anomalies": anom_data,
                "proposals": rules_data,
                "steps_executed": ["profile_dataset", "detect_anomalies", "propose_quality_rules"],
            },
        )

