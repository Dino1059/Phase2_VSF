from datetime import datetime, timezone
import json
import os
import threading
import uuid
from typing import Any, Dict, List, Optional

from src.models.schemas import AuditRecord, DecisionObject


class AuditStore:
    """Append-only audit store logger for state transitions, decisions, and execution events."""

    def __init__(self, log_filepath: Optional[str] = None):
        self._lock = threading.Lock()
        self._records: List[AuditRecord] = []
        self._log_filepath = log_filepath

        if self._log_filepath:
            os.makedirs(os.path.dirname(self._log_filepath), exist_ok=True)

    def _append(self, record: AuditRecord) -> AuditRecord:
        with self._lock:
            self._records.append(record)
            if self._log_filepath:
                try:
                    with open(self._log_filepath, "a", encoding="utf-8") as f:
                        f.write(json.dumps(record.model_dump()) + "\n")
                except Exception:
                    pass  # Non-blocking file append error
        return record

    def log_transition(
        self,
        run_id: str,
        state_from: str,
        state_to: str,
        actor: str = "system",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditRecord:
        record = AuditRecord(
            audit_id=f"audit_{uuid.uuid4().hex[:10]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            state_from=state_from,
            state_to=state_to,
            event_type="STATE_TRANSITION",
            actor=actor,
            details=details or {},
        )
        return self._append(record)

    def log_decision(
        self,
        run_id: str,
        decision: Any,
        actor: str = "agent",
    ) -> AuditRecord:
        if isinstance(decision, DecisionObject):
            dec_dict = decision.model_dump()
            state_to = decision.next_action
        elif isinstance(decision, dict):
            dec_dict = decision
            state_to = decision.get("next_action", "unknown")
        else:
            dec_dict = {"raw": str(decision)}
            state_to = "unknown"

        record = AuditRecord(
            audit_id=f"audit_{uuid.uuid4().hex[:10]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            state_from="DECISION_MAKING",
            state_to=state_to,
            event_type="AGENT_DECISION",
            actor=actor,
            details=dec_dict,
        )
        return self._append(record)

    def log_event(
        self,
        run_id: str,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
        actor: str = "system",
    ) -> AuditRecord:
        record = AuditRecord(
            audit_id=f"audit_{uuid.uuid4().hex[:10]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            state_from="",
            state_to="",
            event_type=event_type,
            actor=actor,
            details=details or {},
        )
        return self._append(record)

    def get_run_history(self, run_id: str) -> List[AuditRecord]:
        with self._lock:
            return [r for r in self._records if r.run_id == run_id]

    def get_all_events(self) -> List[AuditRecord]:
        with self._lock:
            return list(self._records)

    def clear_in_memory(self) -> None:
        with self._lock:
            self._records.clear()


# Global audit store instance
audit_store = AuditStore()
