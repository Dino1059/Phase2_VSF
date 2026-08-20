from fastapi import APIRouter
from src.db.connection import get_db

quarantine_router = APIRouter(prefix="/quarantine", tags=["Quarantine"])


def _this_run_quarantine_count(db) -> int:
    """Sandbox this-run rows only — leftover warehouse 50k is not this run."""
    try:
        q = db.execute(
            "SELECT COUNT(*) FROM quarantine "
            "WHERE CAST(snapshot_id AS VARCHAR) LIKE 'sandbox:%' OR rule_version_id = 'sandbox'"
        )
        return int(q[0][0]) if q else 0
    except Exception:
        return 0


@quarantine_router.get("/")
async def list_quarantine(limit: int = 50):
    db = get_db()
    try:
        rows = db.execute(
            f"SELECT id, source_table, source_row_id, rule_id, reason, quarantined_at, "
            f"lineage_hash, snapshot_id, rule_version_id FROM quarantine "
            f"ORDER BY quarantined_at DESC LIMIT {limit}"
        )
        return {"quarantine": [
            {
                "id": r[0],
                "source_table": r[1],
                "source_row_id": r[2],
                "rule_id": r[3],
                "reason": r[4],
                "quarantined_at": str(r[5]) if r[5] else None,
                "lineage_hash": r[6],
                "snapshot_id": r[7],
                "rule_version_id": r[8],
                "this_run": str(r[7] or "").startswith("sandbox:") or str(r[8] or "") == "sandbox",
            }
            for r in (rows or [])
        ], "this_run": _this_run_quarantine_count(db)}
    except Exception:
        rows = db.execute(
            f"SELECT id, source_table, source_row_id, rule_id, reason, quarantined_at, lineage_hash "
            f"FROM quarantine ORDER BY quarantined_at DESC LIMIT {limit}"
        )
        return {"quarantine": [
            {"id": r[0], "source_table": r[1], "source_row_id": r[2], "rule_id": r[3], "reason": r[4], "quarantined_at": str(r[5]) if r[5] else None, "lineage_hash": r[6]}
            for r in (rows or [])
        ], "this_run": 0}


@quarantine_router.get("/count")
async def quarantine_count():
    db = get_db()
    result = db.execute("SELECT source_table, COUNT(*) FROM quarantine GROUP BY source_table")
    this_run = _this_run_quarantine_count(db)
    return {"counts": {r[0]: r[1] for r in result} if result else {}, "this_run": this_run}
