import hashlib
import json
import uuid
from datetime import datetime

from src.db.connection import get_db
from src.api.audit_store import AuditStore, audit_store


class AuditService:
    """Enhanced audit trail with SHA-256 state hashing."""

    @staticmethod
    def log(action: str, actor: str, target_table: str = "", target_id: str = "", details: dict | None = None) -> str:
        db = get_db()
        audit_id = str(uuid.uuid4())[:8]
        detail_str = json.dumps(details or {})[:500]
        db.execute(
            "INSERT INTO audit_log (id, action, actor, target_table, target_id, details) VALUES (?, ?, ?, ?, ?, ?)",
            [audit_id, action, actor, target_table, target_id, detail_str]
        )
        return audit_id

    @staticmethod
    def compute_state_hash(rule_id: str, expression: str, status: str) -> str:
        payload = f"{rule_id}:{expression}:{status}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    @staticmethod
    def get_history(limit: int = 50) -> list[dict]:
        db = get_db()
        rows = db.execute(f"SELECT id, action, actor, target_table, target_id, details, timestamp FROM audit_log ORDER BY timestamp DESC LIMIT {limit}")
        return [
            {"id": r[0], "action": r[1], "actor": r[2], "target_table": r[3], "target_id": r[4], "details": r[5], "timestamp": str(r[6]) if r[6] else None}
            for r in rows
        ]
