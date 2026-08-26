from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from src.reliability.models.hypothesis import Hypothesis, CauseClassification
import uuid

RecommendationPriority = Literal["P0_CRITICAL", "P1_HIGH", "P2_MEDIUM", "P3_LOW"]


class ActionRecommendation(BaseModel):
    recommendation_id: str = Field(default_factory=lambda: f"rec-{uuid.uuid4().hex[:8]}")
    incident_id: str
    cause_type: CauseClassification = "UNKNOWN"
    priority: RecommendationPriority = "P2_MEDIUM"

    # 1. Target Entity (Đối tượng nào)
    target_entity_id: str
    target_sub_component: Optional[str] = None

    # 2. Identified Issue (Vấn đề gì)
    identified_issue: str

    # 3. Recommended Action (Nên làm gì ngắn gọn)
    recommended_action: str
    assigned_team: str
    requires_hitl_approval: bool = True

    # Backward compatibility properties
    @property
    def action_type(self) -> str:
        if self.cause_type == "REAL_WORLD_EVENT":
            return "OPS_REDIRECT_DISPATCH"
        elif self.cause_type == "SYSTEM_DATA_LOGIC":
            return "PREVENTIVE_DQ_RULE_PROPOSAL"
        elif self.cause_type == "HARDWARE_SENSOR_FAULT":
            return "HARDWARE_MAINTENANCE_INSPECTION"
        return "ABSTENTION"

    @property
    def summary(self) -> str:
        return f"[{self.assigned_team}] {self.identified_issue} -> {self.recommended_action}"

    @property
    def details(self) -> Dict[str, Any]:
        return {
            "target_entity_id": self.target_entity_id,
            "target_sub_component": self.target_sub_component,
            "identified_issue": self.identified_issue,
            "recommended_action": self.recommended_action,
            "assigned_team": self.assigned_team,
            "priority": self.priority,
        }


# Alias for backward compatibility
Recommendation = ActionRecommendation


class RecommendationRouter:
    """
    Routes investigation outcomes conditionally based on cause classification taxonomy.
    Produces entity-targeted actionable recommendations:
    - REAL_WORLD_EVENT -> Ops_Dispatch_Team (P1_HIGH, auto-dispatch/reroute)
    - SYSTEM_DATA_LOGIC -> Data_Engineering_Team (P2_MEDIUM, DQ rule update, HITL approval)
    - HARDWARE_SENSOR_FAULT -> Hardware_Maintenance_Team (P0_CRITICAL, sensor/cable repair, HITL approval)
    - UNKNOWN -> Tier2_Support_Team (P3_LOW, evidence collection)
    """

    def route_hypothesis(self, incident_id: str, hypothesis: Hypothesis) -> ActionRecommendation:
        target_entity = hypothesis.target_entity_id or "unknown_entity"
        sub_component = hypothesis.target_sub_component or hypothesis.target_metric or hypothesis.target_component
        issue = hypothesis.claim or "Unclassified telemetry anomaly detected."

        if hypothesis.classification == "REAL_WORLD_EVENT":
            action = f"Alert operational dispatch team to inspect operational environment or re-route active assets away from {target_entity}."
            return ActionRecommendation(
                incident_id=incident_id,
                cause_type="REAL_WORLD_EVENT",
                priority="P1_HIGH",
                target_entity_id=target_entity,
                target_sub_component=sub_component,
                identified_issue=issue,
                recommended_action=action,
                assigned_team="Ops_Dispatch_Team",
                requires_hitl_approval=False,
            )
        elif hypothesis.classification == "SYSTEM_DATA_LOGIC":
            action = f"Request Data Engineering team to add/adjust Data Quality Rule and boundary constraints for metric '{sub_component or 'telemetry'}' on entity {target_entity}."
            return ActionRecommendation(
                incident_id=incident_id,
                cause_type="SYSTEM_DATA_LOGIC",
                priority="P2_MEDIUM",
                target_entity_id=target_entity,
                target_sub_component=sub_component,
                identified_issue=issue,
                recommended_action=action,
                assigned_team="Data_Engineering_Team",
                requires_hitl_approval=True,
            )
        elif hypothesis.classification == "HARDWARE_SENSOR_FAULT":
            action = f"Request Hardware Maintenance team to inspect physical connections, CAN-bus wiring, and calibrate sensors for {target_entity}."
            return ActionRecommendation(
                incident_id=incident_id,
                cause_type="HARDWARE_SENSOR_FAULT",
                priority="P0_CRITICAL",
                target_entity_id=target_entity,
                target_sub_component=sub_component,
                identified_issue=issue,
                recommended_action=action,
                assigned_team="Hardware_Maintenance_Team",
                requires_hitl_approval=True,
            )
        else:
            return ActionRecommendation(
                incident_id=incident_id,
                cause_type="UNKNOWN",
                priority="P3_LOW",
                target_entity_id=target_entity,
                target_sub_component=sub_component,
                identified_issue="Insufficient empirical evidence to determine root cause.",
                recommended_action="Escalate to Tier 2 support team to collect additional telemetry diagnostic logs and baseline metrics.",
                assigned_team="Tier2_Support_Team",
                requires_hitl_approval=False,
            )


