from fastapi import APIRouter
from src.db.connection import get_db

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@dashboard_router.get("/stats")
async def get_stats():
    db = get_db()
    stats = {}
    for table in ["raw_snapshots", "xanhsm_feedback", "vgreen_telemetry", "vinfast_bms", "xanhsm_trips", "quality_rules", "quarantine", "audit_log", "agent_traces"]:
        try:
            count = db.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = count[0][0] if count else 0
        except Exception:
            stats[table] = 0
    
    # Quality metrics
    rules = db.execute("SELECT status, COUNT(*) FROM quality_rules GROUP BY status")
    rule_stats = {r[0]: r[1] for r in rules} if rules else {}
    quarantine_count = stats.get("quarantine", 0)
    total_records = sum(stats.get(t, 0) for t in ["xanhsm_feedback", "vgreen_telemetry", "vinfast_bms", "xanhsm_trips"])
    quality_score = round((1 - quarantine_count / max(total_records, 1)) * 100, 1)

    return {
        "tables": stats,
        "quality_score": quality_score,
        "rule_stats": rule_stats,
        "total_data_records": total_records,
        "quarantined": quarantine_count
    }


@dashboard_router.get("/activity")
async def get_activity(limit: int = 20):
    db = get_db()
    rows = db.execute(f"SELECT id, action, actor, target_table, details, timestamp FROM audit_log ORDER BY timestamp DESC LIMIT {limit}")
    return {"activity": [
        {"id": r[0], "action": r[1], "actor": r[2], "target_table": r[3], "details": r[4], "timestamp": str(r[5]) if r[5] else None}
        for r in rows
    ]}
