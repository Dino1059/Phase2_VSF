from typing import List, Literal, Optional, Any
from pydantic import BaseModel, Field
import uuid

CauseClassification = Literal[
    "REAL_WORLD_EVENT",      # 1. Sự kiện thực tế
    "SYSTEM_DATA_LOGIC",     # 2. Logic hệ thống & Data Pipeline
    "HARDWARE_SENSOR_FAULT", # 3. Phần cứng & Cảm biến
    "UNKNOWN"                # Thiếu evidence
]
HypothesisStatus = Literal["PROPOSED", "CONFIRMED", "REJECTED"]

class Hypothesis(BaseModel):
    hypothesis_id: str = Field(default_factory=lambda: f"hyp-{uuid.uuid4().hex[:8]}")
    incident_id: str
    classification: CauseClassification = "UNKNOWN"

    # Target Context
    target_entity_id: Optional[str] = None
    target_sub_component: Optional[str] = None
    target_component: Optional[str] = None
    target_metric: Optional[str] = None

    # Identified Issue & Reasoning
    claim: str
    technical_summary: Optional[str] = None
    failure_mechanism: Optional[str] = None
    anomalous_value_observed: Optional[Any] = None
    supporting_evidence: List[str] = Field(default_factory=list)
    contradicting_evidence: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    status: HypothesisStatus = "PROPOSED"


