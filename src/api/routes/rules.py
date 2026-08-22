import datetime
import hashlib
import json
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
import pandas as pd
from pydantic import BaseModel

from src.agents.baselines import A1Agent, C0Baseline, C1Baseline
from src.api.middleware import check_user_role
from src.api.routes import audit_store, state_machine
from src.api.state_machine import WorkflowState
from src.models.schemas import ProposeRulesRequest, ProposeRulesResponse, RuleSchema
from src.services.audit import AuditService


router = APIRouter(prefix="/rules", tags=["rules"], dependencies=[Depends(check_user_role)])


DATASET_METADATA = {
    "vinfast_ev_telemetry": {
        "key": "vinfast_ev_telemetry",
        "name": "VinFast EV Battery Telemetry",
        "table": "vinfast_bms",
        "category": "ev",
        "icon": "Car",
        "color": "#0284c7",
    },
    "vgreen_charging_stations": {
        "key": "vgreen_charging_stations",
        "name": "VGreen Fast-Charging Stations",
        "table": "vgreen_telemetry",
        "category": "vgreen",
        "icon": "BatteryCharging",
        "color": "#10b981",
    },
    "xanh_sm_trips": {
        "key": "xanh_sm_trips",
        "name": "Xanh SM Ride-Hailing Trips",
        "table": "xanhsm_trips",
        "category": "xanhsm",
        "icon": "CarTaxiFront",
        "color": "#06b6d4",
    },
    "xanh_sm_customer_feedback": {
        "key": "xanh_sm_customer_feedback",
        "name": "Xanh SM Customer Feedback & NLP",
        "table": "xanhsm_feedback",
        "category": "nlp",
        "icon": "MessageSquare",
        "color": "#8b5cf6",
    },
    "vietnam_trips": {
        "key": "vietnam_trips",
        "name": "Vietnam Synthetic Trips Benchmark",
        "table": "raw_taxi_trips",
        "category": "benchmark",
        "icon": "Database",
        "color": "#f59e0b",
    },
}

DEFAULT_MULTIDATASET_RULES = [
    # 🚗 VinFast BMS
    {
        "id": "RULE_BMS_SOC_001",
        "rule_name": "Pin SOC Trong Ngưỡng Hóa Học",
        "rule_type": "range",
        "rule_expression": "battery_soc BETWEEN 0.0 AND 100.0",
        "confidence": 0.99,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": "vinfast_ev_telemetry",
        "target_table": "vinfast_bms",
        "target_column": "battery_soc",
        "layer": "L1 Bất Biến",
        "severity": "CRITICAL",
        "description": "Bảo đảm dung lượng pin (SOC) luôn nằm trong khoảng [0.0%, 100.0%].",
    },
    {
        "id": "RULE_BMS_VOLTAGE_002",
        "rule_name": "Trần Điện Áp Khối Pin Cao Áp",
        "rule_type": "range",
        "rule_expression": "battery_voltage BETWEEN 200.0 AND 950.0",
        "confidence": 0.98,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": "vinfast_ev_telemetry",
        "target_table": "vinfast_bms",
        "target_column": "battery_voltage",
        "layer": "L1 Bất Biến",
        "severity": "CRITICAL",
        "description": "Điện áp khối pin phải nằm trong dải vận hành định mức 200V - 950V DC.",
    },
    {
        "id": "RULE_BMS_CELL_TEMP_003",
        "rule_name": "Nhiệt Độ Cell Pin Tối Đa An Toàn",
        "rule_type": "range",
        "rule_expression": "cell_temp_max BETWEEN -20.0 AND 65.0",
        "confidence": 0.95,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": "vinfast_ev_telemetry",
        "target_table": "vinfast_bms",
        "target_column": "cell_temp_max",
        "layer": "L2 Trôi Dạt",
        "severity": "HIGH",
        "description": "Nhiệt độ cell pin tối đa không được vượt quá ngưỡng an toàn nhiệt 65°C.",
    },
    {
        "id": "RULE_BMS_FAULT_CODE_004",
        "rule_name": "Mã Trạng Thái Lỗi BMS Bắt Buộc",
        "rule_type": "not_null",
        "rule_expression": "bms_fault_code IS NOT NULL",
        "confidence": 0.94,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": "vinfast_ev_telemetry",
        "target_table": "vinfast_bms",
        "target_column": "bms_fault_code",
        "layer": "L1 Hợp Đồng",
        "severity": "MEDIUM",
        "description": "Bản ghi telemetry BMS bắt buộc phải có trường mã lỗi (kể cả 'NORMAL').",
    },

    # ⚡ VGreen Telemetry
    {
        "id": "RULE_VGREEN_TEMP_001",
        "rule_name": "Nhiệt Độ Trạm Sạc VGreen",
        "rule_type": "range",
        "rule_expression": "temperature_celsius BETWEEN -10.0 AND 85.0",
        "confidence": 0.97,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": "vgreen_charging_stations",
        "target_table": "vgreen_telemetry",
        "target_column": "temperature_celsius",
        "layer": "L1 Bất Biến",
        "severity": "CRITICAL",
        "description": "Nhiệt độ trạm sạc nhanh DC VGreen phải duy trì trong khoảng an toàn [-10°C, 85°C].",
    },
    {
        "id": "RULE_VGREEN_VOLTAGE_002",
        "rule_name": "Điện Áp Cấp Nguồn Trụ Sạc",
        "rule_type": "range",
        "rule_expression": "voltage BETWEEN 180.0 AND 1000.0",
        "confidence": 0.96,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": "vgreen_charging_stations",
        "target_table": "vgreen_telemetry",
        "target_column": "voltage",
        "layer": "L1 Bất Biến",
        "severity": "CRITICAL",
        "description": "Điện áp cấp nguồn DC trụ sạc phải nằm trong khoảng chuẩn 180V đến 1000V.",
    },
    {
        "id": "RULE_VGREEN_CURRENT_003",
        "rule_name": "Dòng Nạp DC Công Suất Cao",
        "rule_type": "range",
        "rule_expression": "current_amps BETWEEN 0.0 AND 500.0",
        "confidence": 0.95,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": "vgreen_charging_stations",
        "target_table": "vgreen_telemetry",
        "target_column": "current_amps",
        "layer": "L1 Bất Biến",
        "severity": "HIGH",
        "description": "Dòng nạp trạm sạc không được âm và không vượt trần kỹ thuật 500A.",
    },
    {
        "id": "RULE_VGREEN_DUTY_CYCLE_004",
        "rule_name": "Hệ Số Tải Hoạt Động Trạm",
        "rule_type": "range",
        "rule_expression": "duty_cycle BETWEEN 0.0 AND 1.0",
        "confidence": 0.93,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": "vgreen_charging_stations",
        "target_table": "vgreen_telemetry",
        "target_column": "duty_cycle",
        "layer": "L3 Tương Quan",
        "severity": "MEDIUM",
        "description": "Hệ số tải duty cycle của trạm sạc luôn thuộc đoạn tỷ lệ [0.0, 1.0].",
    },

    # 🚕 Xanh SM Trips
    {
        "id": "RULE_XANHSM_FARE_001",
        "rule_name": "Cước Phí Chuyến Đi Không Âm",
        "rule_type": "range",
        "rule_expression": "fare_vnd >= 0",
        "confidence": 0.99,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": "xanh_sm_trips",
        "target_table": "xanhsm_trips",
        "target_column": "fare_vnd",
        "layer": "L1 Sổ Cái",
        "severity": "CRITICAL",
        "description": "Cước phí dịch vụ taxi Xanh SM không được âm (fare_vnd >= 0).",
    },
    {
        "id": "RULE_XANHSM_DISTANCE_002",
        "rule_name": "Quãng Đường Di Chuyển Hợp Lệ",
        "rule_type": "range",
        "rule_expression": "distance_km > 0",
        "confidence": 0.96,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": "xanh_sm_trips",
        "target_table": "xanhsm_trips",
        "target_column": "distance_km",
        "layer": "L1 Vật Lý",
        "severity": "HIGH",
        "description": "Quãng đường chuyến đi hoàn tất phải là số dương hợp lệ.",
    },
    {
        "id": "RULE_XANHSM_DURATION_003",
        "rule_name": "Thời Lượng Chuyến Đi Dương",
        "rule_type": "range",
        "rule_expression": "duration_minutes > 0",
        "confidence": 0.95,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": "xanh_sm_trips",
        "target_table": "xanhsm_trips",
        "target_column": "duration_minutes",
        "layer": "L1 Bất Biến",
        "severity": "MEDIUM",
        "description": "Thời lượng chuyến đi taxi phải lớn hơn 0 phút.",
    },
    {
        "id": "RULE_XANHSM_RATING_004",
        "rule_name": "Đánh Giá Sao Chuyến Đi Chuẩn",
        "rule_type": "range",
        "rule_expression": "rating BETWEEN 1.0 AND 5.0",
        "confidence": 0.94,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": "xanh_sm_trips",
        "target_table": "xanhsm_trips",
        "target_column": "rating",
        "layer": "L1 Bất Biến",
        "severity": "LOW",
        "description": "Điểm số hài lòng của khách hàng trên ứng dụng Xanh SM nằm trong dải [1.0, 5.0].",
    },

    # 💬 Xanh SM Customer Feedback
    {
        "id": "RULE_FEEDBACK_TEXT_001",
        "rule_name": "Nội Dung Đánh Giá Không Trống",
        "rule_type": "not_null",
        "rule_expression": "review_text IS NOT NULL",
        "confidence": 0.97,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": "xanh_sm_customer_feedback",
        "target_table": "xanhsm_feedback",
        "target_column": "review_text",
        "layer": "L1 Hợp Đồng",
        "severity": "HIGH",
        "description": "Mọi bản ghi phản hồi khách hàng phải chứa văn bản review hợp lệ.",
    },
    {
        "id": "RULE_FEEDBACK_RATING_002",
        "rule_name": "Thang Điểm Khách Hàng 1-5 Sao",
        "rule_type": "range",
        "rule_expression": "rating BETWEEN 1.0 AND 5.0",
        "confidence": 0.95,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": "xanh_sm_customer_feedback",
        "target_table": "xanhsm_feedback",
        "target_column": "rating",
        "layer": "L1 Bất Biến",
        "severity": "MEDIUM",
        "description": "Thang điểm phản hồi khách hàng theo chuẩn quốc tế từ 1.0 đến 5.0 sao.",
    },

    # 🚕 Vietnam Trips Synthetic Benchmark
    {
        "id": "RULE_TAXI_FARE_001",
        "rule_name": "Cước Phí Taxi NYC/VN Không Âm",
        "rule_type": "range",
        "rule_expression": "fare_amount >= 0",
        "confidence": 0.99,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": "vietnam_trips",
        "target_table": "raw_taxi_trips",
        "target_column": "fare_amount",
        "layer": "L1 Sổ Cái",
        "severity": "CRITICAL",
        "description": "Giá trị cước chuyến xe fare_amount không được mang giá trị âm.",
    },
    {
        "id": "RULE_TAXI_PASSENGER_002",
        "rule_name": "Số Lượng Hành Khách Hợp Chuẩn",
        "rule_type": "range",
        "rule_expression": "passenger_count BETWEEN 1 AND 7",
        "confidence": 0.96,
        "status": "approved",
        "proposed_by": "a1_profiler",
        "snapshot_id": "vietnam_trips",
        "target_table": "raw_taxi_trips",
        "target_column": "passenger_count",
        "layer": "L1 Vật Lý",
        "severity": "HIGH",
        "description": "Số lượng hành khách trên mỗi chuyến xe nằm trong giới hạn ghế ngồi 1 đến 7.",
    },
]


def infer_dataset_for_rule(rule_id: str, rule_name: str, rule_expr: str, snapshot_id: Optional[str] = None) -> Dict[str, Any]:
    """Infer dataset key, display name, target table, and layer for any rule."""
    if snapshot_id and snapshot_id in DATASET_METADATA:
        meta = DATASET_METADATA[snapshot_id]
        return {
            "dataset_key": meta["key"],
            "dataset_name": meta["name"],
            "target_table": meta["table"],
            "category": meta["category"],
            "icon": meta["icon"],
            "color": meta["color"],
        }

    combined = f"{rule_id} {rule_name} {rule_expr} {snapshot_id or ''}".lower()

    if any(k in combined for k in ["soc", "battery_soc", "battery_voltage", "cell_temp", "vehicle_id", "bms", "bms_fault"]):
        meta = DATASET_METADATA["vinfast_ev_telemetry"]
        return {
            "dataset_key": meta["key"],
            "dataset_name": meta["name"],
            "target_table": meta["table"],
            "category": meta["category"],
            "icon": meta["icon"],
            "color": meta["color"],
        }
    elif any(k in combined for k in ["temperature", "voltage", "duty_cycle", "station_id", "current_amps", "vgreen", "fault_code"]):
        meta = DATASET_METADATA["vgreen_charging_stations"]
        return {
            "dataset_key": meta["key"],
            "dataset_name": meta["name"],
            "target_table": meta["table"],
            "category": meta["category"],
            "icon": meta["icon"],
            "color": meta["color"],
        }
    elif any(k in combined for k in ["distance_km", "fare_vnd", "duration_minutes", "driver_id", "trip_id", "xanhsm_trips", "pickup_location"]):
        meta = DATASET_METADATA["xanh_sm_trips"]
        return {
            "dataset_key": meta["key"],
            "dataset_name": meta["name"],
            "target_table": meta["table"],
            "category": meta["category"],
            "icon": meta["icon"],
            "color": meta["color"],
        }
    elif any(k in combined for k in ["review_text", "normalized_text", "aspects", "feedback", "xanhsm_feedback"]):
        meta = DATASET_METADATA["xanh_sm_customer_feedback"]
        return {
            "dataset_key": meta["key"],
            "dataset_name": meta["name"],
            "target_table": meta["table"],
            "category": meta["category"],
            "icon": meta["icon"],
            "color": meta["color"],
        }
    elif snapshot_id and snapshot_id.startswith("uploaded_"):
        return {
            "dataset_key": snapshot_id,
            "dataset_name": snapshot_id.replace("uploaded_", "").replace("_", " ").title(),
            "target_table": snapshot_id,
            "category": "uploaded",
            "icon": "Database",
            "color": "#a855f7",
        }
    else:
        meta = DATASET_METADATA["vietnam_trips"]
        return {
            "dataset_key": meta["key"],
            "dataset_name": meta["name"],
            "target_table": meta["table"],
            "category": meta["category"],
            "icon": meta["icon"],
            "color": meta["color"],
        }


def infer_layer(rule_expr: str, rule_name: str) -> str:
    """Infer detection layer L1-L4."""
    combined = f"{rule_expr} {rule_name}".lower()
    if any(k in combined for k in ["temp", "cell_temp", "lat", "lon", "gps", "drift"]):
        return "L2 Trôi Dạt"
    elif any(k in combined for k in ["duty_cycle", "rpm", "speed", "correlation", "relational"]):
        return "L3 Tương Quan"
    elif any(k in combined for k in ["pelt", "variance", "rupture", "shift", "change_point"]):
        return "L4 Đổi Điểm"
    elif any(k in combined for k in ["fare", "cost", "vnd", "ledger"]):
        return "L1 Sổ Cái"
    return "L1 Bất Biến"


def infer_column(rule_expr: str) -> str:
    """Extract candidate target column from expression."""
    import re
    m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)", rule_expr.strip())
    if m:
        return m.group(1)
    return "target_field"


def ensure_default_rules_seeded(db):
    """Seed comprehensive multidataset quality rules if table is empty."""
    try:
        rows = db.execute("SELECT COUNT(*) FROM quality_rules")
        count = rows[0][0] if rows else 0
        if count == 0:
            for r in DEFAULT_MULTIDATASET_RULES:
                db.execute(
                    """INSERT INTO quality_rules (id, snapshot_id, rule_name, rule_type, rule_expression, confidence, status, proposed_by, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    [
                        r["id"],
                        r["snapshot_id"],
                        r["rule_name"],
                        r["rule_type"],
                        r["rule_expression"],
                        r["confidence"],
                        r["status"],
                        r["proposed_by"],
                    ],
                )
    except Exception as e:
        print(f"[WARN] Error checking/seeding default rules: {e}")


def quarantine_violating_data_for_rule(rule_id: str, db=None) -> Dict[str, Any]:
    """Execute rule validation against target dataset and isolate violating records into quarantine table.
    
    CRITICAL REQUIREMENT: Raw data is preserved intact ('không sửa gì cả').
    """
    if db is None:
        from src.db.connection import get_db
        db = get_db()

    conn = db.get_connection()

    # 1. Fetch rule
    rules = db.execute(
        "SELECT id, rule_name, rule_type, rule_expression, status, snapshot_id FROM quality_rules WHERE id = ?",
        [rule_id]
    )

    if not rules:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")

    rule = rules[0]
    r_id, r_name, r_type, r_expr, r_status, r_snap = rule[0], rule[1], rule[2], rule[3], rule[4], rule[5]

    # 2. Infer dataset & table
    ds_info = infer_dataset_for_rule(r_id, r_name, r_expr, r_snap)
    dataset_key = ds_info["dataset_key"]
    target_table = ds_info["target_table"]

    # 3. Load dataset records safely
    from src.services.dataset_engine import load_dataset, safe_eval_rule
    try:
        df = load_dataset(dataset_key=dataset_key, sample_size=50_000)
    except Exception:
        try:
            # Fallback to direct DB table query
            df = conn.execute(f"SELECT * FROM {target_table} LIMIT 50000").df()
        except Exception:
            df = pd.DataFrame()

    quarantined_count = 0
    total_checked = len(df)

    if not df.empty:
        rows = df.to_dict("records")
        quarantine_records = []
        effective_snapshot = r_snap or dataset_key
        effective_version = f"{r_id}_v1"

        for idx, row in enumerate(rows):
            # Non-destructive check
            passed = safe_eval_rule(r_expr, row)
            if not passed:
                raw_row_id = row.get("id") or row.get("row_id") or (idx + 1)
                try:
                    source_row_id = int(raw_row_id)
                except (ValueError, TypeError):
                    source_row_id = idx + 1

                q_id = str(uuid.uuid4())[:8]
                lineage_str = f"{effective_snapshot}:{effective_version}:{source_row_id}"
                lineage_hash = hashlib.sha256(lineage_str.encode("utf-8")).hexdigest()[:16]
                orig_json = json.dumps(row, default=str)

                reason_text = f"Vi phạm luật {r_name} ({r_id}): {r_expr}"

                quarantine_records.append((
                    q_id,
                    effective_snapshot,
                    target_table,
                    source_row_id,
                    r_id,
                    effective_version,
                    reason_text,
                    orig_json,
                    lineage_hash,
                ))

        # Batch insert into quarantine table with conflict guard
        if quarantine_records:
            CHUNK_SIZE = 500
            for i in range(0, len(quarantine_records), CHUNK_SIZE):
                chunk = quarantine_records[i : i + CHUNK_SIZE]
                conn.executemany(
                    """
                    INSERT INTO quarantine (
                        id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id, reason, original_data, lineage_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (snapshot_id, rule_version_id, source_row_id) DO NOTHING
                    """,
                    chunk
                )
            quarantined_count = len(quarantine_records)

    # 4. Audit logging
    try:
        AuditService.log(
            action="APPROVE_AND_QUARANTINE_RULE",
            actor="steward",
            target_table=target_table,
            target_id=r_id,
            details={
                "rule_name": r_name,
                "rule_expression": r_expr,
                "dataset_key": dataset_key,
                "total_checked": total_checked,
                "quarantined_count": quarantined_count,
                "preservation_guarantee": "Source dataset untouched (non-destructive quarantine)",
            },
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
        "total_checked": total_checked,
        "quarantined_count": quarantined_count,
        "message": f"Rule '{r_name}' approved. Quarantined {quarantined_count} records into isolated quarantine zone without altering source data.",
    }


class CreateRuleRequest(BaseModel):
    rule_type: str
    target_column: str
    action: str = "quarantine"
    parameters: Optional[Dict[str, Any]] = None
    severity: str = "warning"
    description: Optional[str] = None
    dataset_key: Optional[str] = "vinfast_ev_telemetry"


@router.get("", response_model=List[Dict[str, Any]], summary="List all quality rules with multidataset metadata")
@router.get("/", response_model=List[Dict[str, Any]], summary="List all quality rules with multidataset metadata")
async def list_rules(
    dataset_key: Optional[str] = Query(None, description="Filter rules by dataset source key"),
    status: Optional[str] = Query(None, description="Filter rules by status (approved, proposed, rejected)"),
):
    """List all active and proposed quality rules across all registered datasets."""
    from src.db.connection import get_db

    db = get_db()
    ensure_default_rules_seeded(db)

    try:
        rows = db.execute(
            """SELECT id, rule_type, rule_name, status, rule_expression, confidence, proposed_by, approved_by, created_at, approved_at, snapshot_id
               FROM quality_rules ORDER BY created_at DESC"""
        )

        # Get quarantine counts per rule
        q_counts_raw = db.execute("SELECT rule_id, COUNT(*) FROM quarantine GROUP BY rule_id")
        q_map = {row[0]: row[1] for row in q_counts_raw} if q_counts_raw else {}

        results = []
        for r in rows:
            r_id = r[0]
            r_type = r[1] or "range"
            r_name = r[2] or r_id
            r_status = r[3] or "proposed"
            r_expr = r[4] or ""
            r_conf = float(r[5]) if r[5] is not None else 0.95
            r_snap = r[10]

            ds_meta = infer_dataset_for_rule(r_id, r_name, r_expr, r_snap)
            layer_label = infer_layer(r_expr, r_name)
            target_col = infer_column(r_expr)

            # Apply filters
            if dataset_key and dataset_key != "all" and ds_meta["dataset_key"] != dataset_key:
                continue
            if status and status != "all" and r_status.lower() != status.lower():
                continue

            proposed_by_val = r[6] or "system"
            incident_id_val = None
            if proposed_by_val.startswith("rca:"):
                incident_id_val = proposed_by_val.split("rca:", 1)[1]
            elif "INC-" in proposed_by_val.upper():
                incident_id_val = proposed_by_val

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
                "incident_id": incident_id_val,
                "approved_by": r[7],
                "created_at": str(r[8]) if r[8] else None,
                "approved_at": str(r[9]) if r[9] else None,
                "dataset_key": ds_meta["dataset_key"],
                "dataset_name": ds_meta["dataset_name"],
                "target_table": ds_meta["target_table"],
                "dataset_category": ds_meta["category"],
                "dataset_icon": ds_meta["icon"],
                "dataset_color": ds_meta["color"],
                "layer": layer_label,
                "target_column": target_col,
                "severity": "CRITICAL" if "CRITICAL" in r_name.upper() or r_conf > 0.97 else ("HIGH" if r_conf > 0.9 else "MEDIUM"),
                "quarantined_count": q_map.get(r_id, 0),
            })

        return results
    except Exception as e:
        print(f"[ERROR] list_rules failed: {e}")
        return []


@router.post("/propose", response_model=ProposeRulesResponse)
async def propose_rules_endpoint(request: ProposeRulesRequest) -> ProposeRulesResponse:
    try:
        df = (
            pd.DataFrame(request.data)
            if request.data
            else pd.DataFrame([{"hvfhs_license_num": "HV0003", "driver_pay": 15.0}])
        )
        variant = request.variant.upper()

        if variant == "C0":
            runner = C0Baseline()
            result = runner.run(df)
        elif variant == "C1":
            runner = C1Baseline()
            result = runner.run(df)
        else:
            runner = A1Agent()
            import inspect
            res = runner.run(df)
            result = await res if inspect.isawaitable(res) else res
        rules_out = []
        for r in result.rules_proposed:
            if hasattr(r, "rule_id"):
                rules_out.append(
                    RuleSchema(
                        rule_id=r.rule_id,
                        rule_type=r.rule_type,
                        target_column=r.target_column,
                        action=r.action,
                        parameters=r.parameters,
                        severity=r.severity,
                        description=r.description or "",
                    )
                )
            elif isinstance(r, dict):
                rules_out.append(
                    RuleSchema(
                        rule_id=r.get("rule_id") or r.get("id") or r.get("rule_name") or f"rule_{uuid.uuid4().hex[:6]}",
                        rule_type=r.get("rule_type", "range"),
                        target_column=r.get("target_column") or r.get("column") or r.get("field"),
                        action=r.get("action", "quarantine"),
                        parameters=r.get("parameters") or r.get("params") or {},
                        severity=r.get("severity", "warning"),
                        description=r.get("description") or r.get("rationale") or r.get("rule_name") or "",
                    )
                )

        state_machine.proposed_rules_count = len(rules_out)
        if state_machine.current_state == WorkflowState.PROFILED:
            state_machine.transition_to(WorkflowState.RULES_PROPOSED)

        cost = getattr(result, "cost_usd", getattr(result, "cost_tokens", 0) * 0.00001)
        audit_store.record_event(
            "rule_proposal",
            {"variant": variant, "rules_count": len(rules_out), "cost_usd": cost},
        )

        return ProposeRulesResponse(
            variant=variant,
            rules=rules_out,
            reasoning=f"Generated {len(rules_out)} rules using variant {variant}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
@router.post("/")
async def create_rule(request: CreateRuleRequest):
    from src.db.connection import get_db

    db = get_db()
    rule_id = f"RULE_{request.rule_type.upper()}_{uuid.uuid4().hex[:6].upper()}"
    rule_name = f"{request.rule_type}_{request.target_column}"
    expr = request.description or f"{request.target_column} IS NOT NULL"
    snap_id = request.dataset_key or "vinfast_ev_telemetry"

    try:
        db.execute(
            """INSERT INTO quality_rules (id, snapshot_id, rule_name, rule_type, rule_expression, confidence, status, proposed_by, created_at)
               VALUES (?, ?, ?, ?, ?, 0.95, 'pending', 'user_custom', CURRENT_TIMESTAMP)""",
            [rule_id, snap_id, rule_name, request.rule_type, expr],
        )
        return {"status": "created", "rule_id": rule_id, "dataset_key": snap_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{rule_id}/approve")
async def approve_rule_endpoint(rule_id: str):
    """Approve a rule and atomically quarantine violating records without altering raw source data."""
    from src.db.connection import get_db

    db = get_db()
    try:
        # Update rule status
        db.execute(
            "UPDATE quality_rules SET status = 'approved', approved_by = 'human_steward', approved_at = CURRENT_TIMESTAMP WHERE id = ?",
            [rule_id]
        )
        # Execute non-destructive quarantine isolation
        quarantine_res = quarantine_violating_data_for_rule(rule_id, db=db)
        return quarantine_res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{rule_id}/reject")
async def reject_rule_endpoint(rule_id: str):
    """Reject a quality rule."""
    from src.db.connection import get_db

    db = get_db()
    try:
        db.execute("UPDATE quality_rules SET status = 'rejected' WHERE id = ?", [rule_id])
        AuditService.log(
            action="REJECT_RULE",
            actor="steward",
            target_table="quality_rules",
            target_id=rule_id,
            details={"status": "rejected"},
            db=db,
        )
        return {"status": "rejected", "rule_id": rule_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-approve")
async def batch_approve_rules(payload: Dict[str, Any]):
    """Batch approve multiple rules and isolate violations to quarantine."""
    rule_ids = payload.get("rule_ids", [])
    if not rule_ids:
        raise HTTPException(status_code=400, detail="No rule_ids provided.")

    from src.db.connection import get_db
    db = get_db()

    results = []
    total_quarantined = 0

    for rid in rule_ids:
        try:
            db.execute(
                "UPDATE quality_rules SET status = 'approved', approved_by = 'human_steward', approved_at = CURRENT_TIMESTAMP WHERE id = ?",
                [rid]
            )
            res = quarantine_violating_data_for_rule(rid, db=db)
            total_quarantined += res.get("quarantined_count", 0)
            results.append(res)
        except Exception as err:
            results.append({"rule_id": rid, "status": "error", "error": str(err)})

    return {
        "status": "success",
        "processed_count": len(rule_ids),
        "total_quarantined": total_quarantined,
        "results": results,
    }


@router.post("/seed-defaults")
async def seed_defaults_endpoint():
    """Explicitly re-seed or ensure all default multi-dataset quality rules exist."""
    from src.db.connection import get_db
    db = get_db()
    for r in DEFAULT_MULTIDATASET_RULES:
        existing = db.execute("SELECT id FROM quality_rules WHERE id = ?", [r["id"]])
        if not existing:
            db.execute(
                """INSERT INTO quality_rules (id, snapshot_id, rule_name, rule_type, rule_expression, confidence, status, proposed_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                [
                    r["id"],
                    r["snapshot_id"],
                    r["rule_name"],
                    r["rule_type"],
                    r["rule_expression"],
                    r["confidence"],
                    r["status"],
                    r["proposed_by"],
                ],
            )
    return {"status": "seeded", "count": len(DEFAULT_MULTIDATASET_RULES)}


@router.get("/{rule_id}")
async def get_rule(rule_id: str):
    from src.db.connection import get_db

    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, rule_type, rule_name, status, rule_expression, confidence, snapshot_id FROM quality_rules WHERE id = ?",
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

    db = get_db()
    try:
        db.execute("DELETE FROM quality_rules WHERE id = ?", [rule_id])
        return {"status": "deleted", "rule_id": rule_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
