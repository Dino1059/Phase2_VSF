from fastapi import APIRouter, HTTPException
from src.db.connection import get_db

snapshots_router = APIRouter(prefix="/snapshots", tags=["Snapshots"])


@snapshots_router.get("/")
@snapshots_router.get("")
async def list_snapshots():
    db = get_db()
    conn = db.get_connection()
    try:
        cols = [
            row[0].lower()
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='raw_snapshots'"
            ).fetchall()
        ]
    except Exception:
        cols = []

    if not cols:
        return {"snapshots": []}

    source_col = "source_file" if "source_file" in cols else "source_name" if "source_name" in cols else "file_path" if "file_path" in cols else "id"
    has_prov = "provenance" in cols
    has_tag = "tag" in cols
    
    prov_expr = "provenance" if has_prov else "NULL"
    tag_expr = "tag" if has_tag else "NULL"

    rows = db.execute(
        f"SELECT id, {source_col}, sha256_hash, row_count, column_count, {prov_expr}, {tag_expr}, ingested_at FROM raw_snapshots ORDER BY ingested_at DESC"
    )
    return {"snapshots": [
        {
            "id": r[0],
            "source_file": r[1],
            "source_name": r[1],
            "sha256_hash": r[2],
            "row_count": r[3],
            "column_count": r[4],
            "provenance": r[5],
            "tag": r[6],
            "ingested_at": str(r[7]) if r[7] else None,
        }
        for r in rows
    ]}


@snapshots_router.get("/{snapshot_id}")
async def get_snapshot(snapshot_id: str):
    db = get_db()
    conn = db.get_connection()
    try:
        cols = [
            row[0].lower()
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='raw_snapshots'"
            ).fetchall()
        ]
    except Exception:
        cols = []

    source_col = "source_file" if "source_file" in cols else "source_name" if "source_name" in cols else "file_path" if "file_path" in cols else "id"
    has_prov = "provenance" in cols
    has_tag = "tag" in cols

    prov_expr = "provenance" if has_prov else "NULL"
    tag_expr = "tag" if has_tag else "NULL"

    rows = db.execute(
        f"SELECT id, {source_col}, sha256_hash, row_count, column_count, {prov_expr}, {tag_expr}, ingested_at FROM raw_snapshots WHERE id = ?",
        [snapshot_id],
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    r = rows[0]
    return {
        "id": r[0],
        "source_file": r[1],
        "source_name": r[1],
        "sha256_hash": r[2],
        "row_count": r[3],
        "column_count": r[4],
        "provenance": r[5],
        "tag": r[6],
        "ingested_at": str(r[7]) if r[7] else None,
    }
