from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.models.hypothesis import Hypothesis
from src.reliability.governance.recommendations import RecommendationRouter, Recommendation


class C1FixedInvestigator:
    """
    C1 Baseline Investigator.
    Fixed evidence retrieval and deterministic hypothesis generation workflow.
    """

    def __init__(self, router: Optional[RecommendationRouter] = None):
        self.router = router or RecommendationRouter()

    def investigate_incident(
        self, incident: Incident, available_evidence: List[Evidence]
    ) -> Tuple[Hypothesis, Recommendation]:
        """
        Executes C1 fixed workflow for an incident.
        """
        # Match evidence by entity_ids
        relevant_ev = [
            e for e in available_evidence if any(eid in e.entity_ids for eid in incident.entity_ids)
        ]

        if not relevant_ev:
            hyp = Hypothesis(
                incident_id=incident.incident_id,
                claim=f"No relevant evidence found for entities {incident.entity_ids}",
                classification="UNKNOWN",
                missing_evidence=["entity_telemetry", "history_logs"],
                confidence=0.0,
                status="PROPOSED"
            )
            rec = self.router.route_hypothesis(incident.incident_id, hyp)
            return hyp, rec

        # Evaluate evidence keywords for classification
        combined_summary = " ".join([e.summary for e in relevant_ev]).lower()

        if any(w in combined_summary for w in ["soc", "battery", "temp", "thermal", "degradation", "voltage"]):
            classification = "OPERATIONAL"
            claim = f"Operational asset defect detected in entity {incident.entity_ids[0]}: {relevant_ev[0].summary}"
        elif any(w in combined_summary for w in ["fare", "negative", "null", "schema", "type", "arithmetic"]):
            classification = "DATA"
            claim = f"Data contract / pipeline defect detected in entity {incident.entity_ids[0]}: {relevant_ev[0].summary}"
        else:
            classification = "UNKNOWN"
            claim = f"Ambiguous cause for incident {incident.incident_id}"

        hyp = Hypothesis(
            incident_id=incident.incident_id,
            claim=claim,
            classification=classification,
            supporting_evidence=[e.evidence_id for e in relevant_ev],
            confidence=0.85 if classification != "UNKNOWN" else 0.3,
            status="PROPOSED"
        )

        rec = self.router.route_hypothesis(incident.incident_id, hyp)
        return hyp, rec
