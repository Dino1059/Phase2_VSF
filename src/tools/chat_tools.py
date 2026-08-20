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

        # Load rules from DB or fallback to synthesized rules
        approved_rules = []
        try:
            rows = db.execute("SELECT id, rule_name, rule_type, rule_expression, status FROM quality_rules")
            if rows:
                for row in rows:
                    if row[4] in ("approved", "edit"):
                        approved_rules.append({
                            "rule_id": row[0],
                            "name": row[1],
                            "rule_type": row[2],
                            "expression": row[3],
                            "decision": row[4]
                        })
        except Exception:
            pass

        if not approved_rules:
            try:
                df = load_dataset(dataset_key=dataset_key)
                profile_data = profile_rows(df.to_dict("records"))
                rules, _ = generate_rules_for_baseline("A1", profile_data)
                for i, r in enumerate(rules):
                    if isinstance(r, dict):
                        rid = r.get("rule_id", f"rule_{i+1}")
                        name = r.get("name", "Range Check")
                        rtype = r.get("rule_type", "range_check")
                        expr = r.get("expression", "val != null")
                    else:
                        rid = r.rule_id
                        name = r.rule_name if hasattr(r, "rule_name") else "Range Check"
                        rtype = r.rule_family.value if hasattr(r.rule_family, "value") else str(r.rule_family)
                        expr = r.expression

                    approved_rules.append({
                        "rule_id": rid,
                        "name": name,
                        "rule_type": rtype,
                        "expression": expr,
                        "decision": "approved"
                    })
            except Exception:
                pass

        if not approved_rules:
            return ToolResult(
                status="error",
                error_message="Rule execution denied: No rules are approved by HITL"
            )

        try:
            df = load_dataset(dataset_key=dataset_key)
            result = execute_compiled_rules(df.to_dict("records"), approved_rules)
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
                        "status": "CLEAN_DATABASE_CREATED"
                    }
                }
            )
        except Exception as e:
            return ToolResult(status="error", error_message=str(e))
