from fastapi import APIRouter
from src.db.connection import get_db

quarantine_router = APIRouter(prefix="/quarantine", tags=["Quarantine"])


@quarantine_router.get("/")
async def list_quarantine(limit: int = 50):
    db = get_db()
    rows = db.execute(f"SELECT id, source_table, source_row_id, rule_id, reason, quarantined_at, lineage_hash FROM quarantine ORDER BY quarantined_at DESC LIMIT {limit}")
    return {"quarantine": [
        {"id": r[0], "source_table": r[1], "source_row_id": r[2], "rule_id": r[3], "reason": r[4], "quarantined_at": str(r[5]) if r[5] else None, "lineage_hash": r[6]}
        for r in rows
    ]}


@quarantine_router.get("/count")
async def quarantine_count():
    db = get_db()
    result = db.execute("SELECT source_table, COUNT(*) FROM quarantine GROUP BY source_table")
    return {"counts": {r[0]: r[1] for r in result} if result else {}}
