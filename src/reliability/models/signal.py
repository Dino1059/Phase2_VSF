from datetime import datetime, timezone
from typing import Any, List, Optional
from pydantic import BaseModel, Field
import uuid

ProvenanceType = str  # "REAL_OPERATIONAL" | "PUBLIC_PROXY" | "SEMI_SYNTHETIC" | "SYNTHETIC"
LayerType = str       # "L1" | "L2" | "L3" | "L4"


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
    # Stable rule provenance.  These fields are optional for compatibility with
    # detectors that have not yet moved to versioned reliability configuration.
    rule_id: Optional[str] = None
    rule_version: Optional[str] = None
    threshold: Optional[Any] = None
    observed_value: Optional[Any] = None
    evidence_refs: List[str] = Field(default_factory=list)
    provenance: ProvenanceType = "SEMI_SYNTHETIC"
    source_table: Optional[str] = None
    violation_direction: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
