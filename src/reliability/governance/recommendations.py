from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from src.reliability.models.hypothesis import Hypothesis


class Recommendation(BaseModel):
    incident_id: str
    cause_type: Literal["DATA", "OPERATIONAL", "UNKNOWN"]
    action_type: str
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    requires_hitl_approval: bool = True


class RecommendationRouter:
    """
    Routes investigation outcomes conditionally based on cause classification.
    """

    def route_hypothesis(self, incident_id: str, hypothesis: Hypothesis) -> Recommendation:
        if hypothesis.classification == "DATA":
            return Recommendation(
                incident_id=incident_id,
                cause_type="DATA",
                action_type="PREVENTIVE_DQ_RULE_PROPOSAL",
                summary=f"Propose preventive DQ rule for: {hypothesis.claim}",
                details={"hypothesis_id": hypothesis.hypothesis_id, "rule_proposal": hypothesis.claim},
                requires_hitl_approval=True
            )
        elif hypothesis.classification == "OPERATIONAL":
            return Recommendation(
                incident_id=incident_id,
                cause_type="OPERATIONAL",
                action_type="MAINTENANCE_ROUTING",
                summary=f"Route operational maintenance recommendation: {hypothesis.claim}",
                details={"hypothesis_id": hypothesis.hypothesis_id, "target_team": "Maintenance_Ops"},
                requires_hitl_approval=False
            )
        else:
            return Recommendation(
                incident_id=incident_id,
                cause_type="UNKNOWN",
                action_type="ABSTAIN_AND_REQUEST_CONTEXT",
                summary="Insufficient evidence to classify root cause. Investigation abstained.",
                details={"missing_evidence": hypothesis.missing_evidence},
                requires_hitl_approval=False
            )
