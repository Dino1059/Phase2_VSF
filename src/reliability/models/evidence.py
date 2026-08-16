from datetime import datetime
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid

ProvenanceType = Literal["REAL_OPERATIONAL", "PUBLIC_PROXY", "SEMI_SYNTHETIC", "SYNTHETIC"]

class Evidence(BaseModel):
    evidence_id: str = Field(default_factory=lambda: f"ev-{uuid.uuid4().hex[:8]}")
    project_id: Optional[str] = None
    incident_id: Optional[str] = None
    source_type: str
    source_id: str
    time_range: Dict[str, datetime] = Field(default_factory=dict)
    entity_ids: List[str] = Field(default_factory=list)
    content_hash: str
    summary: str
    provenance: ProvenanceType = "SEMI_SYNTHETIC"

