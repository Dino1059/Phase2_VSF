from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from src.tools.base import BaseTool, ToolResult
from src.services.dataset_engine import load_dataset, profile_rows, generate_rules_for_baseline, execute_compiled_rules
from src.config import get_settings
from src.api.state_machine import WorkflowState




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
                    "UPDATE quality_rules SET dataset_key = ?, rule_name = ?, rule_type = ?, "
                    "rule_expression = ?, confidence = ?, status = CASE "
                    "WHEN lower(trim(cast(status AS VARCHAR))) IN ('approved', 'edited', 'rejected') "
                    "THEN status ELSE 'proposed' END, "
                    "proposed_by = COALESCE(proposed_by, 'dq_proposer') WHERE id = ?",
                    [key or None, name, rtype, expr, conf, rid],
                )
            except Exception:
                try:
                    db.execute(
                        "UPDATE quality_rules SET rule_name = ?, rule_type = ?, rule_expression = ?, "
                        "confidence = ?, status = 'proposed' WHERE id = ?",
                        [name, rtype, expr, conf, rid],
                    )
                except Exception:
                    pass
        else:
            try:
                db.execute(
                    """INSERT INTO quality_rules (id, dataset_key, rule_name, rule_type, rule_expression, confidence, status, proposed_by, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, 'proposed', 'dq_proposer', CURRENT_TIMESTAMP)""",
                    [rid, key or None, name, rtype, expr, conf],
                )
            except Exception:
                try:
                    db.execute(
                        """INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status, proposed_by, created_at)
                           VALUES (?, ?, ?, ?, ?, 'proposed', 'dq_proposer', CURRENT_TIMESTAMP)""",
                        [rid, name, rtype, expr, conf],
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
        sql += " AND (dataset_key = ? OR id LIKE ? OR dataset_key IS NULL)"
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


def persist_sandbox_split(dataset_key: str, rows: list, exec_res: dict, rules: list, db=None) -> dict:
    """Persist REAL quarantine rows into DuckDB and return the Split-tab payload.

    Does not invent rows. Counts come from execute_compiled_rules. Empty partitions stay empty.
    """
    from src.db.connection import get_db
    from src.services.dataset_engine import safe_eval_rule

    if db is None:
        db = get_db()
    key = (dataset_key or "").strip() or "dataset"
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
    import uuid as _uuid
    for i, item in enumerate(q_items):
        row_n = i + 1
        qid = str(item.get("id") or f"q-{_uuid.uuid4().hex[:12]}")
        orig = {k: item[k] for k in item if k not in ("id", "source_table", "source_row_id", "rule_id", "reason", "lineage_hash")}
        try:
            db.execute(
                "INSERT INTO quarantine (id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id, "
                "reason, original_data, lineage_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (snapshot_id, rule_version_id, source_row_id) DO NOTHING",
                [
                    qid,
                    key,
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
                    "INSERT INTO quarantine (id, source_table, source_row_id, rule_id, reason, lineage_hash) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [qid, key, row_n, item["rule_id"], item["reason"], item.get("lineage_hash")],
                )
            except Exception:
                pass

    clean_rows = exec_res.get("clean_db") or []
    return {
        "dataset_key": key,
        "sandbox": True,
        "clean": clean_rows[:50],
        "quarantine": q_items[:100],
        "clean_rows": int(exec_res.get("clean_count") or len(clean_rows) or 0),
        "quarantine_rows": int(exec_res.get("quarantine_count") or len(q_items) or 0),
        "manifest_hash": exec_res.get("manifest_hash") or "",
    }


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
    dataset_key: str = Field(default="vietnam_trips_dirty", description="Target dataset key to scan and profile")


class ProfileDatasetTool(BaseTool):
    name = "profile_dataset"
    description = "Scans a dataset, computes null rates, column data types, distinct counts, and health score."
    input_schema = ProfileDatasetInput
    target_workflow_state = WorkflowState.PROFILED

    def execute(self, input_data: dict) -> ToolResult:
        dataset_key = input_data.get("dataset_key", "vietnam_trips_dirty")
        try:
            df = load_dataset(dataset_key=dataset_key)
            profile_data = profile_rows(df.to_dict("records"))
            return ToolResult(
                status="success",
                output_data={
                    "dataset_key": dataset_key,
                    "total_rows": len(df),
                    "columns_count": len(df.columns),
                    "health_score": profile_data.get("data_health_score"),
                    "warehouse_soc_below_zero": profile_data.get("warehouse_soc_below_zero", 0),
                    "warehouse_open_incidents": profile_data.get("warehouse_open_incidents", 0),
                    "profile": profile_data
                }
            )
        except Exception as e:
            return ToolResult(status="error", error_message=str(e))


class ProposeQualityRulesInput(BaseModel):
    dataset_key: str = Field(default="vietnam_trips_dirty", description="Target dataset key to analyze for rule proposal")


class ProposeQualityRulesTool(BaseTool):
    name = "propose_quality_rules"
    description = "Generates data quality rules and constraints for Human-In-The-Loop review."
    input_schema = ProposeQualityRulesInput
    target_workflow_state = WorkflowState.RULES_PROPOSED

    def execute(self, input_data: dict) -> ToolResult:
        dataset_key = input_data.get("dataset_key", "vietnam_trips_dirty")
        try:
            df = load_dataset(dataset_key=dataset_key)
            profile_data = profile_rows(df.to_dict("records"))
            rules, _ = generate_rules_for_baseline("A1", profile_data)
            
            proposals = []
            for i, r in enumerate(rules):
                if isinstance(r, dict):
                    rf = r.get("rule_type") or r.get("rule_family") or "range_check"
                    col = r.get("column") or "dataset"
                    expr = r.get("expression") or "val != null"
                    desc = r.get("description") or f"Enforce {rf} constraint on {col}"
                    sev = str(r.get("severity", "warning")).lower()
                    rid = r.get("rule_id") or f"prop_{i+1}"
                else:
                    rf = r.rule_family.value if hasattr(r.rule_family, "value") else str(r.rule_family)
                    col = r.column or "dataset"
                    expr = r.expression
                    desc = f"Enforce {rf} constraint on {r.column or 'dataset'}"
                    sev = r.severity.value.lower() if hasattr(r.severity, "value") else str(r.severity).lower()
                    rid = r.rule_id
                
                if sev not in ["critical", "warning", "info"]:
                    sev = "warning"
                rid = namespace_rule_id(dataset_key, rid)
                proposals.append({
                    "id": rid,
                    "type": rf,
                    "column": col,
                    "expression": expr,
                    "description": desc,
                    "severity": sev,
                    "status": "proposed"
                })
            
            # Persist proposals into DuckDB quality_rules table for HITL review
            try:
                persist_hitl_proposals(dataset_key, proposals)
            except Exception as dbe:
                print(f"[WARN] Could not persist quality_rules to DuckDB: {dbe}")

            return ToolResult(
                status="success",
                output_data={"dataset_key": dataset_key, "proposals": proposals, "count": len(proposals)}
            )
        except Exception as e:
            return ToolResult(status="error", error_message=str(e))



class CleanDatabaseInput(BaseModel):
    dataset_key: str = Field(default="vietnam_trips_dirty", description="Target dataset key to execute approved rules on")


class CleanDatabaseTool(BaseTool):
    name = "clean_database"
    description = "Applies approved quality constraints, partitions corrupted rows into quarantine, and creates clean database."
    input_schema = CleanDatabaseInput
    target_workflow_state = WorkflowState.COMPLETED

    def execute(self, input_data: dict) -> ToolResult:
        dataset_key = input_data.get("dataset_key", "vietnam_trips_dirty")
        from src.db.connection import get_db
        db = get_db()

        approved_rules = approved_rules_for_clean(db, dataset_key)
        if not approved_rules:
            return ToolResult(
                status="error",
                error_message="Rule execution denied: No rules are approved by HITL"
            )

        try:
            df = load_dataset(dataset_key=dataset_key)
            rows = df.to_dict("records")
            result = execute_compiled_rules(rows, approved_rules)
            split = persist_sandbox_split(dataset_key, rows, result, approved_rules, db=db)
            return ToolResult(
                status="success",
                output_data={
                    "dataset_key": dataset_key,
                    "execution_result": {
                        "total_processed": result.get("total_processed", len(df)),
                        "clean_count": result.get("clean_count", 0),
                        "quarantine_count": result.get("quarantine_count", 0),
                        "quarantine_rate_pct": result.get("quarantine_rate_pct", 0.0),
                        "manifest_hash": result.get("manifest_hash", ""),
                        "status": "CLEAN_DATABASE_CREATED",
                    },
                    "split": split,
                }
            )
        except Exception as e:
            return ToolResult(status="error", error_message=str(e))
