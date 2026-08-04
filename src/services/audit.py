import hashlib
import json
import uuid
from datetime import datetime

from src.db.connection import get_db
from src.api.audit_store import AuditStore, audit_store


class AuditService:
    """Enhanced audit trail with SHA-256 hash-chained immutable audit ledger."""

    @staticmethod
    def _get_canonical_details(details: dict | str | None) -> str:
        if details is None:
            return json.dumps({}, sort_keys=True)
        if isinstance(details, dict):
            return json.dumps(details, sort_keys=True)
        if isinstance(details, str):
            try:
                parsed = json.loads(details)
                if isinstance(parsed, (dict, list)):
                    return json.dumps(parsed, sort_keys=True)
            except Exception:
                pass
            return details
        try:
            return json.dumps(details, sort_keys=True)
        except Exception:
            return str(details)

    @staticmethod
    def compute_event_hash(
        previous_event_hash: str,
        action: str,
        actor: str,
        target_table: str,
        target_id: str,
        canonical_details: str,
        timestamp: str,
    ) -> str:
        payload = f"{previous_event_hash}:{action}:{actor}:{target_table}:{target_id}:{canonical_details}:{timestamp}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def log(
        action: str,
        actor: str,
        target_table: str = "",
        target_id: str = "",
        details: dict | str | None = None,
        timestamp: str | datetime | None = None,
    ) -> str:
        db = get_db()
        audit_id = str(uuid.uuid4())[:8]

        target_table = target_table or ""
        target_id = target_id or ""
        action = action or ""
        actor = actor or ""

        canonical_details = AuditService._get_canonical_details(details)

        if timestamp is None:
            timestamp_str = datetime.now().isoformat()
        elif isinstance(timestamp, datetime):
            timestamp_str = timestamp.isoformat()
        else:
            timestamp_str = str(timestamp)

        # Retrieve previous_event_hash from latest row in audit_log
        rows = db.execute(
            "SELECT event_hash FROM audit_log ORDER BY rowid DESC LIMIT 1"
        )
        if rows and rows[0][0]:
            previous_event_hash = rows[0][0]
        else:
            previous_event_hash = "0" * 64

        event_hash = AuditService.compute_event_hash(
            previous_event_hash=previous_event_hash,
            action=action,
            actor=actor,
            target_table=target_table,
            target_id=target_id,
            canonical_details=canonical_details,
            timestamp=timestamp_str,
        )

        db.execute(
            "INSERT INTO audit_log (id, action, actor, target_table, target_id, details, timestamp, previous_event_hash, event_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                audit_id,
                action,
                actor,
                target_table,
                target_id,
                canonical_details,
                timestamp_str,
                previous_event_hash,
                event_hash,
            ],
        )
        return audit_id

    @staticmethod
    def verify_chain_integrity(limit: int = 1000) -> tuple[bool, list[str]]:
        db = get_db()
        rows = db.execute(
            "SELECT id, action, actor, target_table, target_id, details, timestamp, previous_event_hash, event_hash "
            "FROM audit_log ORDER BY rowid ASC LIMIT ?",
            [limit],
        )
        if not rows:
            return (True, [])

        tamper_details = []
        expected_prev_hash = "0" * 64

        for row in rows:
            r_id, action, actor, target_table, target_id, details, ts, prev_hash, stored_event_hash = row

            action = action or ""
            actor = actor or ""
            target_table = target_table or ""
            target_id = target_id or ""
            prev_hash = prev_hash or ""
            stored_event_hash = stored_event_hash or ""

            if prev_hash != expected_prev_hash:
                tamper_details.append(
                    f"Row {r_id}: previous_event_hash mismatch. Expected '{expected_prev_hash}', got '{prev_hash}'"
                )

            canonical_details = AuditService._get_canonical_details(details)

            if isinstance(ts, datetime):
                ts_str = ts.isoformat()
            else:
                ts_str = str(ts or "")

            calculated_hash = AuditService.compute_event_hash(
                previous_event_hash=prev_hash,
                action=action,
                actor=actor,
                target_table=target_table,
                target_id=target_id,
                canonical_details=canonical_details,
                timestamp=ts_str,
            )

            if stored_event_hash != calculated_hash:
                tamper_details.append(
                    f"Row {r_id}: event_hash mismatch. Expected '{calculated_hash}', got '{stored_event_hash}'"
                )

            expected_prev_hash = stored_event_hash

        if tamper_details:
            return (False, tamper_details)
        return (True, [])

    @staticmethod
    def compute_state_hash(rule_id: str, expression: str, status: str) -> str:
        payload = f"{rule_id}:{expression}:{status}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    @staticmethod
    def get_history(limit: int = 50) -> list[dict]:
        db = get_db()
        rows = db.execute(
            f"SELECT id, action, actor, target_table, target_id, details, timestamp, previous_event_hash, event_hash "
            f"FROM audit_log ORDER BY rowid DESC LIMIT {limit}"
        )
        return [
            {
                "id": r[0],
                "action": r[1],
                "actor": r[2],
                "target_table": r[3],
                "target_id": r[4],
                "details": r[5],
                "timestamp": str(r[6]) if r[6] else None,
                "previous_event_hash": r[7],
                "event_hash": r[8],
            }
            for r in rows
        ]
