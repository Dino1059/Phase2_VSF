from typing import List, Literal, Optional
from pydantic import BaseModel, Field
import uuid

CauseClassification = Literal["DATA", "OPERATIONAL", "MIXED", "UNKNOWN"]
HypothesisStatus = Literal["PROPOSED", "CONFIRMED", "REJECTED"]

class Hypothesis(BaseModel):
    hypothesis_id: str = Field(default_factory=lambda: f"hyp-{uuid.uuid4().hex[:8]}")
    incident_id: str
    claim: str
    classification: CauseClassification = "UNKNOWN"
    supporting_evidence: List[str] = Field(default_factory=list)
    contradicting_evidence: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    status: HypothesisStatus = "PROPOSED"
