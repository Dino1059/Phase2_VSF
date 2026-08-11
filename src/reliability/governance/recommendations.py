from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from src.reliability.models.hypothesis import Hypothesis
import uuid

RecommendationType = Literal["PREVENTIVE_DATA_CONTROL", "OPERATIONAL_RECOMMENDATION", "ABSTENTION"]


class Recommendation(BaseModel):
    recommendation_id: str = Field(default_factory=lambda: f"rec-{uuid.uuid4().hex[:8]}")
    incident_id: str
    recommendation_type: Optional[RecommendationType] = None
    cause_type: Literal["DATA", "OPERATIONAL", "UNKNOWN"]
    action_type: str = "ABSTENTION"
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    requires_hitl_approval: bool = True

    def model_post_init(self, __context: Any) -> None:
        if self.recommendation_type is None:
            if self.cause_type == "DATA":
                self.recommendation_type = "PREVENTIVE_DATA_CONTROL"
            elif self.cause_type == "OPERATIONAL":
                self.recommendation_type = "OPERATIONAL_RECOMMENDATION"
            else:
                self.recommendation_type = "ABSTENTION"


class RecommendationRouter:
    """
    Routes investigation outcomes conditionally based on cause classification.
    Produces typed recommendations:
    - PREVENTIVE_DATA_CONTROL for data/pipeline/contract causes
    - OPERATIONAL_RECOMMENDATION for asset/real-world operational causes
    - ABSTENTION for unknown/insufficient evidence
    """

    def route_hypothesis(self, incident_id: str, hypothesis: Hypothesis) -> Recommendation:
        if hypothesis.classification == "DATA":
            return Recommendation(
                incident_id=incident_id,
                recommendation_type="PREVENTIVE_DATA_CONTROL",
                cause_type="DATA",
                action_type="PREVENTIVE_DQ_RULE_PROPOSAL",
                summary=f"Propose preventive data control rule for: {hypothesis.claim}",
                details={"hypothesis_id": hypothesis.hypothesis_id, "rule_proposal": hypothesis.claim},
                requires_hitl_approval=True
            )
        elif hypothesis.classification == "OPERATIONAL":
            return Recommendation(
                incident_id=incident_id,
                recommendation_type="OPERATIONAL_RECOMMENDATION",
                cause_type="OPERATIONAL",
                action_type="MAINTENANCE_ROUTING",
                summary=f"Route operational maintenance recommendation: {hypothesis.claim}",
                details={"hypothesis_id": hypothesis.hypothesis_id, "target_team": "Maintenance_Ops"},
                requires_hitl_approval=False
            )
        else:
            return Recommendation(
                incident_id=incident_id,
                recommendation_type="ABSTENTION",
                cause_type="UNKNOWN",
                action_type="ABSTENTION",
                summary="Insufficient evidence to classify root cause. Investigation abstained.",
                details={"missing_evidence": hypothesis.missing_evidence},
                requires_hitl_approval=False
            )

