import asyncio
import hashlib
import json
import uuid
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.agents.baselines import A1Agent, C0Baseline, C1Baseline
from src.api.middleware import check_user_role
from src.api.routes import audit_store, state_machine
from src.api.state_machine import WorkflowState
from src.models.schemas import ProposeRulesRequest, ProposeRulesResponse, RuleSchema
from src.services.audit import AuditService
from src.utils.table_utils import CANONICAL_DATA_TABLES, normalize_table_name


router = APIRouter(prefix="/rules", tags=["rules"], dependencies=[Depends(check_user_role)])


DATASET_METADATA: Dict[str, Dict[str, Any]] = {
    "ev_telemetry": {
        "key": "ev_telemetry",
        "name": "VinFast EV Telemetry",
        "table": "ev_telemetry",
        "category": "ev",
        "icon": "Car",
        "color": "#0284c7",
    },
    "charging_sessions": {
        "key": "charging_sessions",
        "name": "V-GREEN Charging",
        "table": "charging_sessions",
        "category": "vgreen",
        "icon": "BatteryCharging",
        "color": "#10b981",
    },
    "trips": {
        "key": "trips",
        "name": "Xanh SM Trips",
        "table": "trips",
        "category": "xanhsm",
        "icon": "CarTaxiFront",
        "color": "#06b6d4",
    },
    "nlp_feedback": {
        "key": "nlp_feedback",
        "name": "Customer Feedback NLP",
        "table": "nlp_feedback",
        "category": "nlp",
        "icon": "MessageSquare",
        "color": "#8b5cf6",
    },
}


DEFAULT_MULTIDATASET_RULES = [
    ("RULE_EV_SOC_001", "Battery SOC within physical range", "range", "battery_soc BETWEEN 0.0 AND 100.0", "ev_telemetry", "battery_soc", 0.99),
    ("RULE_EV_VOLTAGE_002", "Battery voltage within operating range", "range", "battery_voltage BETWEEN 200.0 AND 950.0", "ev_telemetry", "battery_voltage", 0.98),
    ("RULE_EV_TEMP_003", "Battery temperature within safe range", "range", "battery_temp_c BETWEEN -20.0 AND 65.0", "ev_telemetry", "battery_temp_c", 0.95),
    ("RULE_CHARGING_TEMP_001", "Station temperature within safe range", "range", "station_temp_c BETWEEN -10.0 AND 85.0", "charging_sessions", "station_temp_c", 0.97),
    ("RULE_CHARGING_ENERGY_002", "Consumed energy is non-negative", "range", "kwh_consumed >= 0.0", "charging_sessions", "kwh_consumed", 0.96),
    ("RULE_CHARGING_DURATION_003", "Charging duration is positive", "range", "duration_mins > 0.0", "charging_sessions", "duration_mins", 0.95),
    ("RULE_TRIPS_FARE_001", "Trip fare is non-negative", "range", "fare_amount >= 0.0", "trips", "fare_amount", 0.99),
    ("RULE_TRIPS_DISTANCE_002", "Trip distance is positive", "range", "trip_distance_km > 0.0", "trips", "trip_distance_km", 0.96),
    ("RULE_TRIPS_TOTAL_003", "Trip total fare is non-negative", "range", "total_fare >= 0.0", "trips", "total_fare", 0.95),
    ("RULE_FEEDBACK_TEXT_001", "Feedback sentence is present", "not_null", "sentence IS NOT NULL", "nlp_feedback", "sentence", 0.97),
    ("RULE_FEEDBACK_SENTIMENT_002", "Feedback sentiment is in label range", "range", "sentiment BETWEEN 0 AND 2", "nlp_feedback", "sentiment", 0.95),
]


def _rule_dict(seed: tuple) -> Dict[str, Any]:
    rid, name, rtype, expr, table, col, conf = seed
    return {
        "id": rid,
        "rule_name": name,
        "rule_type": rtype,
        "rule_expression": expr,
        "confidence": conf,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": table,
        "dataset_key": table,
        "target_table": table,
        "target_column": col,
    }


def infer_dataset_for_rule(rule_id: str, rule_name: str, rule_expr: str, snapshot_id: Optional[str] = None) -> Dict[str, Any]:
    if snapshot_id:
        try:
            table = normalize_table_name(snapshot_id)
            meta = DATASET_METADATA[table]
            return {"dataset_key": meta["key"], "dataset_name": meta["name"], "target_table": meta["table"], "category": meta["category"], "icon": meta["icon"], "color": meta["color"]}
        except (KeyError, ValueError):
            pass

    combined = f"{rule_id} {rule_name} {rule_expr}".lower()
    if any(k in combined for k in ("soc", "battery_", "vehicle_vin", "ev_")):
        table = "ev_telemetry"
    elif any(k in combined for k in ("station_", "kwh_", "duration_mins", "charging")):
        table = "charging_sessions"
    elif any(k in combined for k in ("trip_", "fare", "driver_id", "pickup_")):
        table = "trips"
    elif any(k in combined for k in ("sentence", "sentiment", "topic", "feedback")):
        table = "nlp_feedback"
    else:
        table = "ev_telemetry"
    meta = DATASET_METADATA[table]
    return {"dataset_key": meta["key"], "dataset_name": meta["name"], "target_table": meta["table"], "category": meta["category"], "icon": meta["icon"], "color": meta["color"]}


def infer_layer(rule_expr: str, rule_name: str) -> str:
    combined = f"{rule_expr} {rule_name}".lower()
    if any(k in combined for k in ("temp", "lat", "lon", "gps", "drift")):
        return "L2 Drift"
    if any(k in combined for k in ("correlation", "relational", "duration_mins")):
        return "L3 Relation"
    if any(k in combined for k in ("shift", "change_point", "cusum")):
        return "L4 Change Point"
    if any(k in combined for k in ("fare", "cost", "vnd", "ledger")):
        return "L1 Ledger"
    return "L1 Invariant"


def infer_column(rule_expr: str) -> str:
    import re
    m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)", rule_expr.strip())
    return m.group(1) if m else "target_field"


def ensure_default_rules_seeded(db):
    try:
        rows = db.execute("SELECT COUNT(*) FROM quality_rules")
        if rows and int(rows[0][0]) > 0:
            return
        for seed in DEFAULT_MULTIDATASET_RULES:
            r = _rule_dict(seed)
            db.execute(
                """INSERT INTO quality_rules
                   (id, snapshot_id, dataset_key, rule_name, rule_type, rule_expression, confidence, status, proposed_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                [r["id"], r["snapshot_id"], r["dataset_key"], r["rule_name"], r["rule_type"], r["rule_expression"], r["confidence"], r["status"], r["proposed_by"]],
            )
    except Exception as e:
        print(f"[WARN] Error checking/seeding default rules: {e}")


def quarantine_violating_data_for_rule(rule_id: str, db=None) -> Dict[str, Any]:
    if db is None:
        from src.db.connection import get_db
        db = get_db()

    conn = db.get_connection()
    rules = db.execute(
        "SELECT id, rule_name, rule_type, rule_expression, status, COALESCE(dataset_key, snapshot_id) FROM quality_rules WHERE id = ?",
        [rule_id],
    )
    if not rules:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")

    r_id, r_name, _r_type, r_expr, r_status, r_snap = rules[0]
    if (r_status or "").lower() != "approved":
        raise HTTPException(status_code=400, detail=f"Rule '{rule_id}' must be approved before execution.")

    ds_info = infer_dataset_for_rule(r_id, r_name or r_id, r_expr or "", r_snap)
    dataset_key = ds_info["dataset_key"]
    target_table = normalize_table_name(ds_info["target_table"])

    from src.services.dataset_engine import SANDBOX_SAMPLE_CAP, load_dataset, safe_eval_rule
    sample_cap = int(SANDBOX_SAMPLE_CAP)
    try:
        df = load_dataset(dataset_key=dataset_key, sample_size=sample_cap)
    except Exception:
        try:
            df = conn.execute(f"SELECT * FROM main.{target_table} LIMIT {sample_cap}").df()
        except Exception:
            df = pd.DataFrame()

    quarantine_records = []
    for idx, row in enumerate(df.to_dict("records") if not df.empty else []):
        if safe_eval_rule(r_expr or "", row):
            continue
        raw_row_id = row.get("id") or row.get("record_id") or row.get("trip_id") or row.get("session_id") or row.get("feedback_id") or (idx + 1)
        try:
            source_row_id = int(raw_row_id)
        except (ValueError, TypeError):
            source_row_id = idx + 1
        version = f"{r_id}_v1"
        lineage_hash = hashlib.sha256(f"{dataset_key}:{version}:{source_row_id}".encode("utf-8")).hexdigest()[:16]
        quarantine_records.append((
            str(uuid.uuid4())[:8],
            dataset_key,
            target_table,
            source_row_id,
            r_id,
            version,
            f"Rule {r_name or r_id} failed: {r_expr}",
            json.dumps(row, default=str),
            lineage_hash,
        ))

    if quarantine_records:
        conn.executemany(
            """
            INSERT INTO main.quarantine
                (id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id, reason, original_data, lineage_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (snapshot_id, rule_version_id, source_row_id) DO NOTHING
            """,
            quarantine_records,
        )

    try:
        AuditService.log(
            action="APPROVE_AND_QUARANTINE_RULE",
            actor="steward",
            target_table=target_table,
            target_id=r_id,
            details={"dataset_key": dataset_key, "total_checked": len(df), "quarantined_count": len(quarantine_records)},
            db=db,
        )
    except Exception:
        pass

    return {
        "status": "approved",
        "rule_id": r_id,
        "rule_name": r_name,
        "dataset_key": dataset_key,
        "target_table": target_table,
        "total_checked": len(df),
        "quarantined_count": len(quarantine_records),
        "message": f"Rule '{r_name}' approved. Quarantined {len(quarantine_records)} records without altering main truth.",
    }


class CreateRuleRequest(BaseModel):
    rule_type: str
    target_column: str
    action: str = "quarantine"
    parameters: Optional[Dict[str, Any]] = None
    severity: str = "warning"
    description: Optional[str] = None
    dataset_key: Optional[str] = "ev_telemetry"


@router.get("", response_model=List[Dict[str, Any]], summary="List all quality rules with multidataset metadata")
@router.get("/", response_model=List[Dict[str, Any]], summary="List all quality rules with multidataset metadata")
async def list_rules(dataset_key: Optional[str] = Query(None), status: Optional[str] = Query(None)):
    from src.db.connection import get_db

    db = get_db()
    ensure_default_rules_seeded(db)
    try:
        rows = db.execute(
            """SELECT id, rule_type, rule_name, status, rule_expression, confidence, proposed_by, approved_by, created_at, approved_at,
                      COALESCE(dataset_key, snapshot_id)
               FROM quality_rules ORDER BY created_at DESC"""
        )
        q_counts_raw = db.execute("SELECT rule_id, COUNT(*) FROM main.quarantine GROUP BY rule_id")
        q_map = {row[0]: row[1] for row in q_counts_raw} if q_counts_raw else {}
    except Exception as e:
        print(f"[ERROR] list_rules failed: {e}")
        return []

    results = []
    for r in rows:
        r_id, r_type, r_name, r_status, r_expr = r[0], r[1] or "range", r[2] or r[0], r[3] or "proposed", r[4] or ""
        r_conf = float(r[5]) if r[5] is not None else 0.95
        ds_meta = infer_dataset_for_rule(r_id, r_name, r_expr, r[10])
        if dataset_key and dataset_key != "all" and ds_meta["dataset_key"] != normalize_table_name(dataset_key):
            continue
        if status and status != "all" and r_status.lower() != status.lower():
            continue
        proposed_by_val = r[6] or "system"
        results.append({
            "id": r_id,
            "rule_id": r_id,
            "rule_type": r_type,
            "rule_name": r_name,
            "status": r_status,
            "rule_expression": r_expr,
            "description": r_expr,
            "confidence": r_conf,
            "proposed_by": proposed_by_val,
            "incident_id": proposed_by_val.split("rca:", 1)[1] if proposed_by_val.startswith("rca:") else None,
            "approved_by": r[7],
            "created_at": str(r[8]) if r[8] else None,
            "approved_at": str(r[9]) if r[9] else None,
            "dataset_key": ds_meta["dataset_key"],
            "dataset_name": ds_meta["dataset_name"],
            "target_table": ds_meta["target_table"],
            "dataset_category": ds_meta["category"],
            "dataset_icon": ds_meta["icon"],
            "dataset_color": ds_meta["color"],
            "layer": infer_layer(r_expr, r_name),
            "target_column": infer_column(r_expr),
            "severity": "CRITICAL" if r_conf > 0.97 else ("HIGH" if r_conf > 0.9 else "MEDIUM"),
            "quarantined_count": q_map.get(r_id, 0),
        })
    return results


@router.post("/propose", response_model=ProposeRulesResponse)
async def propose_rules_endpoint(request: ProposeRulesRequest) -> ProposeRulesResponse:
    try:
        df = pd.DataFrame(request.data) if request.data else pd.DataFrame([{"fare_amount": 15.0}])
        variant = request.variant.upper()
        if variant == "C0":
            result = C0Baseline().run(df)
        elif variant == "C1":
            result = C1Baseline().run(df)
        else:
            import inspect
            res = A1Agent().run(df)
            result = await res if inspect.isawaitable(res) else res

        rules_out = []
        for r in result.rules_proposed:
            data = r if isinstance(r, dict) else r.__dict__
            rules_out.append(RuleSchema(
                rule_id=data.get("rule_id") or data.get("id") or f"rule_{uuid.uuid4().hex[:6]}",
                rule_type=data.get("rule_type", "range"),
                target_column=data.get("target_column") or data.get("column") or data.get("field"),
                action=data.get("action", "quarantine"),
                parameters=data.get("parameters") or data.get("params") or {},
                severity=data.get("severity", "warning"),
                description=data.get("description") or data.get("rationale") or data.get("rule_name") or "",
            ))

        state_machine.proposed_rules_count = len(rules_out)
        if state_machine.current_state == WorkflowState.PROFILED:
            state_machine.transition_to(WorkflowState.RULES_PROPOSED)
        audit_store.record_event("rule_proposal", {"variant": variant, "rules_count": len(rules_out)})
        return ProposeRulesResponse(variant=variant, rules=rules_out, reasoning=f"Generated {len(rules_out)} rules using variant {variant}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
@router.post("/")
async def create_rule(request: CreateRuleRequest):
    from src.db.connection import get_db

    try:
        dataset_key = normalize_table_name(request.dataset_key or "ev_telemetry")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db = get_db()
    rule_id = f"RULE_{request.rule_type.upper()}_{uuid.uuid4().hex[:6].upper()}"
    rule_name = f"{request.rule_type}_{request.target_column}"
    expr = request.description or f"{request.target_column} IS NOT NULL"
    try:
        db.execute(
            """INSERT INTO quality_rules
               (id, snapshot_id, dataset_key, rule_name, rule_type, rule_expression, confidence, status, proposed_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 0.95, 'pending', 'user_custom', CURRENT_TIMESTAMP)""",
            [rule_id, dataset_key, dataset_key, rule_name, request.rule_type, expr],
        )
        return {"status": "created", "rule_id": rule_id, "dataset_key": dataset_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{rule_id}/approve")
async def approve_rule_endpoint(rule_id: str):
    from src.db.connection import get_db

    db = get_db()
    try:
        db.execute("UPDATE quality_rules SET status = 'approved', approved_by = 'human_steward', approved_at = CURRENT_TIMESTAMP WHERE id = ?", [rule_id])
        return quarantine_violating_data_for_rule(rule_id, db=db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{rule_id}/reject")
async def reject_rule_endpoint(rule_id: str):
    from src.db.connection import get_db

    db = get_db()
    try:
        db.execute("UPDATE quality_rules SET status = 'rejected' WHERE id = ?", [rule_id])
        AuditService.log(action="REJECT_RULE", actor="steward", target_table="quality_rules", target_id=rule_id, details={"status": "rejected"}, db=db)
        return {"status": "rejected", "rule_id": rule_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-approve")
async def batch_approve_rules(payload: Dict[str, Any]):
    rule_ids = [str(rid) for rid in (payload.get("rule_ids") or []) if rid]
    if not rule_ids:
        raise HTTPException(status_code=400, detail="No rule_ids provided.")

    def _mark_approved() -> List[str]:
        from src.db.connection import get_db
        db = get_db()
        placeholders = ",".join(["?"] * len(rule_ids))
        updated = db.execute(
            f"""UPDATE quality_rules
                SET status = 'approved',
                    approved_by = 'human_steward',
                    approved_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
                  AND lower(status) IN ('proposed','pending','draft','queued')
                RETURNING id""",
            list(rule_ids),
        )
        return [row[0] for row in (updated or [])]

    marked_ids = await asyncio.to_thread(_mark_approved)
    return {
        "status": "success",
        "processed_count": len(marked_ids),
        "total_quarantined": 0,
        "execute": "off",
        "results": [{"rule_id": rid, "status": "approved"} for rid in marked_ids],
    }


@router.post("/seed-defaults")
async def seed_defaults_endpoint():
    from src.db.connection import get_db
    db = get_db()
    inserted = 0
    for seed in DEFAULT_MULTIDATASET_RULES:
        r = _rule_dict(seed)
        if db.execute("SELECT id FROM quality_rules WHERE id = ?", [r["id"]]):
            continue
        db.execute(
            """INSERT INTO quality_rules
               (id, snapshot_id, dataset_key, rule_name, rule_type, rule_expression, confidence, status, proposed_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            [r["id"], r["snapshot_id"], r["dataset_key"], r["rule_name"], r["rule_type"], r["rule_expression"], r["confidence"], r["status"], r["proposed_by"]],
        )
        inserted += 1
    return {"status": "seeded", "count": inserted}


@router.get("/{rule_id}")
async def get_rule(rule_id: str):
    from src.db.connection import get_db

    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, rule_type, rule_name, status, rule_expression, confidence, COALESCE(dataset_key, snapshot_id) FROM quality_rules WHERE id = ?",
            [rule_id],
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")
        r = rows[0]
        ds_meta = infer_dataset_for_rule(r[0], r[2] or r[0], r[4] or "", r[6])
        return {
            "id": r[0],
            "rule_id": r[0],
            "rule_type": r[1],
            "rule_name": r[2],
            "status": r[3],
            "rule_expression": r[4],
            "confidence": r[5],
            "dataset_key": ds_meta["dataset_key"],
            "dataset_name": ds_meta["dataset_name"],
            "target_table": ds_meta["target_table"],
            "layer": infer_layer(r[4] or "", r[2] or ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str):
    from src.db.connection import get_db

    try:
        get_db().execute("DELETE FROM quality_rules WHERE id = ?", [rule_id])
        return {"status": "deleted", "rule_id": rule_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

