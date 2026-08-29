import asyncio
import hashlib
import json
import uuid
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from src.db.connection import get_db
from src.services.audit import AuditService
from src.utils.table_utils import normalize_table_name

pipeline_router = APIRouter(prefix="/pipeline", tags=["Pipeline"])
PROJECT_ID = "proj-vingroup-pilot"


def _pipeline_table_name(table_name: str) -> str:
    return normalize_table_name(table_name)


def _json_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _read_telemetry(table_name: str, project_id: str) -> dict:
    from src.orchestrator.orchestrator import _load_table_as_dataframe

    config = {
        "ev_telemetry": ("timestamp", "battery_soc"),
        "charging_sessions": ("start_time", "station_temp_c"),
        "trips": ("pickup_datetime", "fare_amount"),
        "nlp_feedback": ("scenario_date", "sentiment"),
    }
    normalized = _pipeline_table_name(table_name)
    timestamp_col, metric_col = config.get(normalized, (None, None))
    if not timestamp_col or not metric_col:
        return {"table": normalized, "metric": None, "series": [], "anomalies": []}

    try:
        df = _load_table_as_dataframe(normalized, project_id=project_id)
        if timestamp_col not in df.columns or metric_col not in df.columns:
            return {"table": normalized, "metric": metric_col, "series": [], "anomalies": []}
        series = []
        for row in df[[timestamp_col, metric_col]].dropna().head(500).itertuples(index=False):
            try:
                series.append({"timestamp": _json_value(row[0]), "value": float(row[1])})
            except (TypeError, ValueError):
                continue
        return {"table": normalized, "metric": metric_col, "series": series, "anomalies": []}
    except Exception:
        return {"table": normalized, "metric": metric_col, "series": [], "anomalies": []}


def _build_pipeline_result(run_id: str, table_name: str, orchestration_result) -> dict:
    stages = orchestration_result.stages
    anomaly_stage = next((s for s in stages if s.get("stage") == "anomaly_detection"), {})
    incidents = anomaly_stage.get("incidents", [])
    nodes = []
    edges = []
    signals = []
    for incident in incidents:
        incident_id = incident.get("id") or incident.get("incident_id")
        if not incident_id:
            continue
        incident_node = {"id": incident_id, "type": "incident", "label": incident_id, "severity": incident.get("severity")}
        nodes.append(incident_node)
        supporting_layers = incident.get("supporting_layers") or ["unknown"]
        layer_label = "+".join(supporting_layers)
        for signal_id in incident.get("signal_ids", []):
            signals.append({"signal_id": signal_id, "layers": supporting_layers, "incident_id": incident_id})
        layer_id = f"{incident_id}:{layer_label}"
        if incident.get("signal_ids"):
            nodes.append({"id": layer_id, "type": "signal", "label": f"{layer_label} signals ({len(incident['signal_ids'])})"})
            edges.append({"source": layer_id, "target": incident_id, "relation": "admitted_into"})
        hypothesis = incident.get("hypothesis") or {}
        if hypothesis.get("id"):
            nodes.append({"id": hypothesis["id"], "type": "hypothesis", "label": hypothesis.get("classification", "Hypothesis"), "confidence": hypothesis.get("confidence")})
            edges.append({"source": incident_id, "target": hypothesis["id"], "relation": "explained_by"})
        recommendation = incident.get("recommendation") or {}
        if recommendation.get("id"):
            nodes.append({"id": recommendation["id"], "type": "recommendation", "label": recommendation.get("type", "Recommendation")})
            if hypothesis.get("id"):
                edges.append({"source": hypothesis["id"], "target": recommendation["id"], "relation": "routes_to"})

    telemetry = _read_telemetry(table_name, PROJECT_ID)
    db = get_db()
    quarantine = db.execute(
        "SELECT id, source_table, source_row_id, rule_id, reason, quarantined_at, lineage_hash "
        "FROM quarantine ORDER BY quarantined_at DESC LIMIT 200"
    )
    quarantine_rows = [
        {"id": r[0], "source_table": r[1], "source_row_id": r[2], "rule_id": r[3], "reason": r[4], "quarantined_at": _json_value(r[5]), "lineage_hash": r[6]}
        for r in quarantine
    ]
    manifest_payload = {
        "run_id": run_id,
        "project_id": PROJECT_ID,
        "dataset_key": table_name,
        "status": orchestration_result.status,
        "stages": stages,
        "incident_count": len(incidents),
        "quarantine_count": len(quarantine_rows),
    }
    manifest_hash = hashlib.sha256(json.dumps(manifest_payload, sort_keys=True, default=str).encode()).hexdigest()
    return {
        "run_id": run_id,
        "project_id": PROJECT_ID,
        "dataset_key": table_name,
        "status": orchestration_result.status,
        "stages": stages,
        "signals": signals,
        "rca": {"nodes": nodes, "edges": edges, "incidents": incidents},
        "telemetry": telemetry,
        "split": {
            "clean_rows": None,
            "quarantine_rows": len(quarantine_rows),
            "clean": [],
            "quarantine": quarantine_rows,
        },
        "manifest": {"hash": manifest_hash, "algorithm": "SHA-256", "status": orchestration_result.status},
    }


def _update_pipeline_run(run_id: str, status: str, result: dict | None = None, error: str | None = None) -> None:
    db = get_db()
    db.execute(
        "UPDATE pipeline_runs SET status = ?, result_json = ?, error_message = ?, completed_at = CURRENT_TIMESTAMP WHERE run_id = ?",
        [status, json.dumps(result, default=str) if result is not None else None, error, run_id],
    )


def _run_pipeline_background(run_id: str, table_name: str) -> None:
    try:
        from src.orchestrator.orchestrator import DataTrustOrchestrator
        from src.services.llm import GemmaLLMAdapter

        canonical_table = _pipeline_table_name(table_name)
        result = DataTrustOrchestrator(
            llm=GemmaLLMAdapter(),
            project_id=PROJECT_ID,
        ).run_analysis(canonical_table)
        payload = _build_pipeline_result(run_id, canonical_table, result)
        _update_pipeline_run(run_id, payload["status"], payload)
    except Exception as exc:
        _update_pipeline_run(run_id, "failed", {"run_id": run_id, "dataset_key": table_name, "status": "failed", "error": str(exc)}, str(exc))


async def _run_pipeline_async(run_id: str, table_name: str) -> None:
    await asyncio.to_thread(_run_pipeline_background, run_id, table_name)


def check_pipeline_rule_approved(rule_id: Optional[str] = None, table_name: str = "charging_sessions"):
    db = get_db()
    table_name = _pipeline_table_name(table_name)
    if rule_id:
        rules = db.execute("SELECT id, status FROM quality_rules WHERE id = ?", [rule_id])
        if not rules or rules[0][1] != "approved":
            raise HTTPException(
                status_code=403,
                detail="Rule execution denied: Rule is not approved by HITL"
            )
    else:
        unapproved = db.execute(
            "SELECT id FROM quality_rules WHERE (snapshot_id = ? OR rule_name LIKE ?) AND status != 'approved'",
            [table_name, f"%{table_name}%"]
        )
        if unapproved:
            raise HTTPException(
                status_code=403,
                detail="Rule execution denied: Rule is not approved by HITL"
            )


@pipeline_router.post("/trigger")
async def trigger_pipeline(
    background_tasks: BackgroundTasks,
    table_name: str = "charging_sessions",
    rule_id: Optional[str] = None,
):
    """Trigger the analysis pipeline on a table."""
    table_name = _pipeline_table_name(table_name)
    if rule_id:
        check_pipeline_rule_approved(rule_id, table_name)
    run_id = str(uuid.uuid4())[:8]
    db = get_db()
    db.execute(
        "INSERT INTO pipeline_runs (run_id, project_id, dataset_key, status) VALUES (?, ?, ?, ?)",
        [run_id, PROJECT_ID, table_name, "running"],
    )
    asyncio.create_task(_run_pipeline_async(run_id, table_name))
    AuditService.log("PIPELINE_TRIGGER", "user", table_name, run_id, {"table": table_name})
    return {"run_id": run_id, "status": "running", "table": table_name}


@pipeline_router.post("/execute")
async def execute_pipeline(
    rule_id: Optional[str] = None,
    table_name: str = "charging_sessions",
):
    """Execute pipeline for table/rule."""
    table_name = _pipeline_table_name(table_name)
    check_pipeline_rule_approved(rule_id, table_name)
    run_id = str(uuid.uuid4())[:8]
    return {"run_id": run_id, "status": "executed", "table": table_name}


@pipeline_router.get("/status/{run_id}")
async def get_pipeline_status(run_id: str):
    db = get_db()
    run = db.execute("SELECT status, dataset_key, error_message FROM pipeline_runs WHERE run_id = ?", [run_id])
    if run:
        return {"run_id": run_id, "status": run[0][0], "table": run[0][1], "error": run[0][2], "steps": []}
    traces = db.execute("SELECT agent_type, step_index, action, timestamp FROM agent_traces WHERE session_id = ? ORDER BY step_index", [run_id])
    if not traces:
        return {"run_id": run_id, "status": "not_found", "steps": []}
    return {
        "run_id": run_id,
        "status": "completed",
        "steps": [{"agent": t[0], "step": t[1], "action": t[2], "timestamp": str(t[3]) if t[3] else None} for t in traces]
    }


@pipeline_router.get("/result/{run_id}")
async def get_pipeline_result(run_id: str):
    db = get_db()
    rows = db.execute(
        "SELECT project_id, dataset_key, status, result_json, error_message, started_at, completed_at "
        "FROM pipeline_runs WHERE run_id = ?",
        [run_id],
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    project_id, dataset_key, status, result_json, error_message, started_at, completed_at = rows[0]
    result = json.loads(result_json) if isinstance(result_json, str) else (result_json or {})
    return {
        **result,
        "run_id": run_id,
        "project_id": project_id,
        "dataset_key": dataset_key,
        "status": status,
        "error": error_message,
        "started_at": _json_value(started_at),
        "completed_at": _json_value(completed_at),
    }
