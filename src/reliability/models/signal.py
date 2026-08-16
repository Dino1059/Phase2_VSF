from datetime import datetime, timezone
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
import uuid

ProvenanceType = Literal["REAL_OPERATIONAL", "PUBLIC_PROXY", "SEMI_SYNTHETIC", "SYNTHETIC"]
LayerType = Literal["L1", "L2", "L3", "L4"]

class Signal(BaseModel):
    signal_id: str = Field(default_factory=lambda: f"sig-{uuid.uuid4().hex[:8]}")
    project_id: str
    entity_ids: List[str]
    layer: LayerType
    signal_type: str
    metric_or_relationship: str
    event_time: datetime
    window_start: datetime
    window_end: datetime
    score: float
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    detector: str
    detector_version: str = "1.0.0"
    evidence_refs: List[str] = Field(default_factory=list)
    provenance: ProvenanceType = "SEMI_SYNTHETIC"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
