from fastapi import APIRouter
from src.db.connection import get_db

snapshots_router = APIRouter(prefix="/snapshots", tags=["Snapshots"])


@snapshots_router.get("/")
async def list_snapshots():
    db = get_db()
    rows = db.execute("SELECT id, source_file, sha256_hash, row_count, column_count, ingested_at FROM raw_snapshots ORDER BY ingested_at DESC")
    return {"snapshots": [
        {"id": r[0], "source_file": r[1], "sha256_hash": r[2], "row_count": r[3], "column_count": r[4], "ingested_at": str(r[5]) if r[5] else None}
        for r in rows
    ]}


@snapshots_router.get("/{snapshot_id}")
async def get_snapshot(snapshot_id: str):
    db = get_db()
    rows = db.execute("SELECT id, source_file, sha256_hash, row_count, column_count, ingested_at FROM raw_snapshots WHERE id = ?", [snapshot_id])
    if not rows:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Snapshot not found")
    r = rows[0]
    return {"id": r[0], "source_file": r[1], "sha256_hash": r[2], "row_count": r[3], "column_count": r[4], "ingested_at": str(r[5]) if r[5] else None}
