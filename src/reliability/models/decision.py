import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class Decision(BaseModel):
    decision_id: str = Field(default_factory=lambda: f"dec-{uuid.uuid4().hex[:8]}")
    incident_id: str
    hypothesis_id: Optional[str] = None
    recommendation_id: Optional[str] = None
    action: str
    actor: str = "SYSTEM"
    rationale: Optional[str] = ""
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
