from datetime import datetime, timezone
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid

IncidentStatus = Literal["OPEN", "INVESTIGATING", "RESOLVED", "CLOSED", "DISMISSED"]

class Incident(BaseModel):
    incident_id: str = Field(default_factory=lambda: f"inc-{uuid.uuid4().hex[:8]}")
    project_id: str
    status: IncidentStatus = "OPEN"
    entity_ids: List[str]
    signal_ids: List[str]
    admission_reason: str
    supporting_layers: List[str] = Field(default_factory=list)
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    time_window: Dict[str, datetime] = Field(default_factory=dict)
    confirmed_facts: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    correlation_key: Optional[str] = None
    occurrence_count: int = 1
    representative_signal_ids: List[str] = Field(default_factory=list)
    owner: Optional[str] = None
    feedback_type: Optional[str] = None
    feedback_reason: Optional[str] = None
    feedback_by: Optional[str] = None
    feedback_at: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
