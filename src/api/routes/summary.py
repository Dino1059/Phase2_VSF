from fastapi import APIRouter
from typing import Dict, Any
from src.db.connection import get_db

summary_router = APIRouter(prefix="/summary", tags=["summary"])


@summary_router.get("", response_model=Dict[str, Any])
@summary_router.get("/", response_model=Dict[str, Any])
def get_summary():
    """
    Retrieve overall system telemetry & governance summary.
    """
    db = get_db()
    total_data_records = 0
    quarantined_count = 0
    for table in ["xanhsm_feedback", "vgreen_telemetry", "vinfast_bms", "xanhsm_trips"]:
        try:
            res = db.execute(f"SELECT COUNT(*) FROM {table}")
            total_data_records += res[0][0] if res else 0
        except Exception:
            pass

    try:
        q_res = db.execute("SELECT COUNT(*) FROM quarantine")
        quarantined_count = q_res[0][0] if q_res else 0
    except Exception:
        pass

    clean_records = max(0, total_data_records - quarantined_count)
    pass_validation_rate = (
        round((1 - quarantined_count / max(total_data_records, 1)) * 100, 1)
        if total_data_records > 0
        else 100.0
    )

    return {
        "projects_count": 1,
        "active_project_id": "proj-vingroup-pilot",
        "provenance": "SEMI_SYNTHETIC",
        "total_data_records": total_data_records,
        "clean_records": clean_records,
        "quarantined_records": quarantined_count,
        "pass_validation_rate": f"{pass_validation_rate}%",
        "system_status": "OPERATIONAL"
    }
