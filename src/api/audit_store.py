import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    event_id: str
    event_type: str  # "profile", "rule_proposal", "hitl_review", "execution", "reset"
    timestamp: float = Field(default_factory=time.time)
    details: Dict[str, Any] = Field(default_factory=dict)


class AuditStore:
    def __init__(self):
        self.records: List[AuditRecord] = []

    def record_event(self, event_type: str, details: Dict[str, Any]) -> AuditRecord:
        event_id = f"evt_{len(self.records) + 1:04d}"
        rec = AuditRecord(event_id=event_id, event_type=event_type, details=details)
        self.records.append(rec)
        return rec

    def log_event(self, run_id: str, event_type: str, details: Dict[str, Any]) -> AuditRecord:
        merged_details = {"run_id": run_id, **(details or {})}
        return self.record_event(event_type=event_type, details=merged_details)

    def log_decision(self, run_id: str, decision: Any, actor: str) -> AuditRecord:
        details = {
            "run_id": run_id,
            "actor": actor,
            "decision": decision.model_dump() if hasattr(decision, "model_dump") else str(decision)
        }
        return self.record_event(event_type="AGENT_DECISION", details=details)



    def get_records(self, event_type: Optional[str] = None) -> List[AuditRecord]:
        if event_type:
            return [r for r in self.records if r.event_type == event_type]
        return self.records

    def clear(self):
        self.records.clear()


audit_store = AuditStore()

