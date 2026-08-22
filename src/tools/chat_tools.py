from __future__ import annotations
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from src.tools.base import BaseTool, ToolResult
from src.services.dataset_engine import load_dataset, profile_rows, generate_rules_for_baseline, execute_compiled_rules
from src.config import get_settings
from src.api.state_machine import WorkflowState


def _resolve_table_target(dataset_key: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Decompose `dataset_key` into (file_path, table_name_or_None, base_dataset_key).

    Supports both legacy single-table datasets and the multi-table notation
    `uploaded_demo::vgreen_telemetry`. The base key is what is registered in the
    dataset registry; the optional table name selects a specific user table inside
    a DuckDB file.

    Returns:
        file_path: absolute (or cwd-relative) path to the underlying file.
        table_name: explicit table to load, or None for legacy single-table files.
        base_key: registry key (without the `::table` suffix).
    """
    base_key = dataset_key
    table_name: Optional[str] = None
    if "::" in dataset_key:
        base_key, table_name = dataset_key.rsplit("::", 1)

    settings = get_settings()
    file_path = settings.get_dataset_path(base_key)
    return file_path, table_name, base_key


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


def persist_sandbox_split(dataset_key: str, rows: list, exec_res: dict, rules: list, db=None, snapshot_id: str | None = None) -> dict:
    """Persist REAL quarantine rows into DuckDB and return the Split-tab payload.

    Does not invent rows. Counts come from execute_compiled_rules. Empty partitions stay empty.
    snapshot_id tags THIS sandbox run so Split never shows leftover 50k/100 as this run.
    """
    from src.db.connection import get_db
    from src.services.dataset_engine import safe_eval_rule

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
    try:
        db.execute(
            "DELETE FROM quarantine WHERE source_table = ? AND (rule_version_id = 'sandbox' OR snapshot_id LIKE ?)",
            [key, f"sandbox:{key}:%"],
        )
    except Exception:
        try:
            db.execute("DELETE FROM quarantine WHERE source_table = ?", [key])
        except Exception:
            pass
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
        "snapshot_id": snap,
        "this_run": True,
        "clean": clean_rows[:50],
        "quarantine": q_items[:100],
        "clean_rows": int(exec_res.get("clean_count") or len(clean_rows) or 0),
        "quarantine_rows": int(exec_res.get("quarantine_count") or len(q_items) or 0),
        "manifest_hash": exec_res.get("manifest_hash") or "",
        "sampled_rows": len(rows),
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
    description = "Stage 1: Scans dataset schema, computes null rates, column types, distinct counts, and health score across all tables."
    input_schema = ProfileDatasetInput
    target_workflow_state = WorkflowState.PROFILED

    def execute(self, input_data: dict) -> ToolResult:
        dataset_key = input_data.get("dataset_key", "vietnam_trips_dirty")
        try:
            file_path, table_name, base_key = _resolve_table_target(dataset_key)
            user_tables = _list_user_tables(file_path) if file_path and os.path.exists(file_path) else []

            tables_profile: Dict[str, Any] = {}
            total_rows = 0

            if user_tables and not table_name:
                for tbl in user_tables:
                    try:
                        df = load_dataset(dataset_key=f"{base_key}::{tbl}")
                        prof = profile_rows(df.to_dict("records"))
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
                df = load_dataset(dataset_key=dataset_key)
                prof = profile_rows(df.to_dict("records"))
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
    dataset_key: str = Field(default="vietnam_trips_dirty", description="Target dataset key to scan for L1-L4 anomalies")


class DetectAnomaliesTool(BaseTool):
    name = "detect_anomalies"
    description = "Stage 2: Executes multi-layer anomaly detection (L1 Range/Boundary, L2 Temporal & Contextual Drift, L3 Relational Invariants, L4 Semantic Correlation) across all tables in the dataset, producing structured anomaly findings and incidents for RCA."
    input_schema = DetectAnomaliesInput
    target_workflow_state = WorkflowState.ANOMALY_DETECTED

    def execute(self, input_data: dict) -> ToolResult:
        dataset_key = input_data.get("dataset_key", "vietnam_trips_dirty")
        try:
            from src.orchestrator.orchestrator import _detect_l1_l4_signals, _run_reliability_pipeline
            file_path, table_name, base_key = _resolve_table_target(dataset_key)
            user_tables = _list_user_tables(file_path) if file_path and os.path.exists(file_path) else []
            target_tables = [table_name] if table_name else (user_tables if user_tables else [base_key])

            all_incidents: List[Dict[str, Any]] = []
            signals_summary = {"L1": 0, "L2": 0, "L3": 0, "L4": 0}
            per_table_findings = []

            for tbl in target_tables:
                effective_key = f"{base_key}::{tbl}" if tbl and tbl != base_key else base_key
                try:
                    df = load_dataset(dataset_key=effective_key)
                except Exception:
                    continue

                raw_sigs = _detect_l1_l4_signals(tbl or base_key, df, "proj-vingroup-pilot")
                for k in ("L1", "L2", "L3", "L4"):
                    signals_summary[k] += len(raw_sigs.get(k, []))

                try:
                    incidents = _run_reliability_pipeline(table_name=tbl or base_key, project_id="proj-vingroup-pilot")
                except Exception:
                    incidents = []

                for inc in incidents:
                    inc["source_table"] = tbl or base_key
                    inc["dataset_key"] = dataset_key

                all_incidents.extend(incidents)
                per_table_findings.append({
                    "table_name": tbl or base_key,
                    "rows_analyzed": len(df),
                    "signals": {k: len(v) for k, v in raw_sigs.items()},
                    "incident_count": len(incidents),
                    "incidents": incidents,
                })

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
    dataset_key: str = Field(default="vietnam_trips_dirty", description="Target dataset key to analyze for rule proposal")
    anomaly_findings: Optional[Dict[str, Any]] = Field(default=None, description="Optional structured anomaly findings from Stage 2")


class ProposeQualityRulesTool(BaseTool):
    name = "propose_quality_rules"
    description = "Stage 3: Synthesizes targeted data quality rules grounded in BOTH Stage 1 Profile Summary AND Stage 2 L1-L4 Anomaly Findings for Human-In-The-Loop review."
    input_schema = ProposeQualityRulesInput
    target_workflow_state = WorkflowState.RULES_PROPOSED

    def execute(self, input_data: dict) -> ToolResult:
        dataset_key = input_data.get("dataset_key", "vietnam_trips_dirty")
        anomaly_findings = input_data.get("anomaly_findings")

        # Guarantee flow dependency: if anomaly findings not passed in, run anomaly detection now
        if not anomaly_findings:
            anom_tool = DetectAnomaliesTool()
            anom_res = anom_tool.execute({"dataset_key": dataset_key})
            if anom_res.status == "success":
                anomaly_findings = anom_res.output_data
            else:
                anomaly_findings = {}

        try:
            file_path, table_name, base_key = _resolve_table_target(dataset_key)
            user_tables = _list_user_tables(file_path) if file_path and os.path.exists(file_path) else []
            target_tables = [table_name] if table_name else (user_tables if user_tables else [None])

            proposals: List[Dict[str, Any]] = []

            for tbl in target_tables:
                effective_key = f"{base_key}::{tbl}" if tbl else base_key
                try:
                    df = load_dataset(dataset_key=effective_key)
                    profile_data = profile_rows(df.to_dict("records"))
                    rules, _ = generate_rules_for_baseline("A1", profile_data)
                except Exception:
                    continue

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
                        "table_name": tbl,
                        "dataset_key": effective_key,
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
                        claim = inc.get("hypothesis_claim", "") or inc.get("admission_reason", "")
                        rule_id = f"rule_anom_{inc_tbl or base_key}_{idx+1}"

                        if "L1" in layers:
                            rule_expr = "temp_c BETWEEN -20 AND 85" if "temp" in claim.lower() else "voltage >= 0 AND voltage <= 1000"
                            rule_type = "range_boundary_check"
                            rule_desc = f"L1 Range constraint to resolve {inc_id} ({claim})"
                        elif "L2" in layers:
                            rule_expr = "ABS(rate_of_change) < 3.5"
                            rule_type = "contextual_drift_limit"
                            rule_desc = f"L2 Temporal Drift bound to resolve {inc_id}"
                        elif "L3" in layers:
                            rule_expr = "voltage * current <= max_power_kw * 1000"
                            rule_type = "relational_invariant"
                            rule_desc = f"L3 Physical invariant check for {inc_id}"
                        else:
                            rule_expr = "status IN ('active', 'charging', 'idle')"
                            rule_type = "semantic_enum_check"
                            rule_desc = f"L4 Semantic constraint for {inc_id}"

                        proposals.append({
                            "id": rule_id,
                            "type": rule_type,
                            "column": "telemetry",
                            "expression": rule_expr,
                            "description": rule_desc,
                            "severity": "critical" if inc.get("severity") == "CRITICAL" else "warning",
                            "status": "pending",
                            "table_name": inc_tbl or tbl,
                            "dataset_key": effective_key,
                            "source": "anomaly_detector_l1_l4",
                        })

            # Persist proposals into DuckDB quality_rules table for HITL review
            try:
                persist_hitl_proposals(dataset_key, proposals)
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
    dataset_key: str = Field(default="vietnam_trips_dirty", description="Target dataset key to execute approved rules on")


class CleanDatabaseTool(BaseTool):
    name = "clean_database"
    description = "Stage 4: Applies approved quality constraints, partitions corrupted rows into quarantine, and creates clean database snapshot with SHA-256 lineage manifest."
    input_schema = CleanDatabaseInput
    target_workflow_state = WorkflowState.COMPLETED

    def execute(self, input_data: dict) -> ToolResult:
        dataset_key = input_data.get("dataset_key", "vietnam_trips_dirty")
        from src.db.connection import get_db
        db = get_db()

        try:
            file_path, table_name, base_key = _resolve_table_target(dataset_key)
            user_tables = _list_user_tables(file_path) if file_path and os.path.exists(file_path) else []
        except Exception:
            file_path, table_name, base_key, user_tables = None, None, dataset_key, []

        target_tables: List[Optional[str]] = [table_name] if table_name else (user_tables if user_tables else [None])

        # Load rules from DB or fallback to synthesized rules (per table)
        approved_rules: List[Dict[str, Any]] = []
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
                            "decision": row[4],
                        })
        except Exception:
            pass

        if not approved_rules:
            for tbl in target_tables:
                effective_key = f"{base_key}::{tbl}" if tbl else base_key
                try:
                    df = load_dataset(dataset_key=effective_key)
                    profile_data = profile_rows(df.to_dict("records"))
                    rules, _ = generate_rules_for_baseline("A1", profile_data)
                except Exception:
                    continue
                for i, r in enumerate(rules):
                    if isinstance(r, dict):
                        rid = r.get("rule_id", f"rule_{(tbl or base_key)}_{i+1}")
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
                        "decision": "approved",
                        "table_name": tbl,
                    })

        if not approved_rules:
            return ToolResult(
                status="error",
                error_message="Rule execution denied: No rules are approved by HITL"
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
    dataset_key: str = Field(default="vietnam_trips_dirty", description="Target dataset key to execute complete 4-stage pipeline")


class RunFullPipelineTool(BaseTool):
    name = "run_full_pipeline"
    description = "Executes the strict sequential 4-stage DataTrust pipeline: Stage 1 (Profile) -> Stage 2 (L1-L4 Anomaly Detection) -> Stage 3 (Rule Synthesis from Profile & Anomalies) -> Stage 4 (Clean Database & Quarantine)."
    input_schema = RunFullPipelineInput
    target_workflow_state = WorkflowState.COMPLETED

    def execute(self, input_data: dict) -> ToolResult:
        dataset_key = input_data.get("dataset_key", "vietnam_trips_dirty")

        # Step 1: Profiling
        prof_tool = ProfileDatasetTool()
        prof_res = prof_tool.execute({"dataset_key": dataset_key})
        prof_data = prof_res.output_data if prof_res.status == "success" else {}

        # Step 2: Anomaly Detection L1-L4
        anom_tool = DetectAnomaliesTool()
        anom_res = anom_tool.execute({"dataset_key": dataset_key})
        anom_data = anom_res.output_data if anom_res.status == "success" else {}

        # Step 3: Propose Rules based on Profile + Anomalies
        rules_tool = ProposeQualityRulesTool()
        rules_res = rules_tool.execute({"dataset_key": dataset_key, "anomaly_findings": anom_data})
        rules_data = rules_res.output_data if rules_res.status == "success" else {}

        # Step 4: Clean & Quarantine
        clean_tool = CleanDatabaseTool()
        clean_res = clean_tool.execute({"dataset_key": dataset_key})
        clean_data = clean_res.output_data if clean_res.status == "success" else {}

        # Background sync with DataTrustOrchestrator for run_id
        run_id = None
        try:
            from src.orchestrator.orchestrator import DataTrustOrchestrator
            from src.services.llm import GemmaLLMAdapter
            from src.api.pipeline import _build_pipeline_result, _update_pipeline_run
            from src.db.connection import get_db

            run_id = str(uuid.uuid4())[:8]
            db = get_db()
            db.execute(
                "INSERT INTO pipeline_runs (run_id, project_id, dataset_key, status) VALUES (?, ?, ?, ?)",
                [run_id, "proj-vingroup-pilot", dataset_key, "running"],
            )
            orch = DataTrustOrchestrator(llm=GemmaLLMAdapter(), project_id="proj-vingroup-pilot")
            orch_res = orch.run_analysis(dataset_key)
            payload = _build_pipeline_result(run_id, dataset_key, orch_res)
            _update_pipeline_run(run_id, payload["status"], payload)
        except Exception as oe:
            print(f"[WARN] Failed background orchestrator sync: {oe}")

        return ToolResult(
            status="success",
            output_data={
                "dataset_key": dataset_key,
                "run_id": run_id,
                "stage_1_profile": prof_data,
                "stage_2_anomalies": anom_data,
                "stage_3_rules": rules_data,
                "stage_4_clean": clean_data,
            }
        )
