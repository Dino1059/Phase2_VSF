from typing import List, Optional, Tuple, Dict, Any
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.models.hypothesis import Hypothesis
from src.reliability.governance.recommendations import RecommendationRouter, Recommendation


class R0DeterministicInvestigator:
    """
    R0 Deterministic Investigator.
    Resolves known incidents via fixed rule lookups, diagnostic mappings, and baseline checks.
    Zero LLM involvement. Fast SLA (<10ms).
    """

    def __init__(self, router: Optional[RecommendationRouter] = None):
        self.router = router or RecommendationRouter()

    def investigate_incident(
        self, incident: Incident, initial_evidence: List[Evidence]
    ) -> Tuple[Optional[Hypothesis], Optional[Recommendation]]:
        """
        Attempts to resolve incident deterministically.
        Returns (Hypothesis, Recommendation) if a known pattern matches, else (None, None).
        """
        # Rule 1: Known L1 Range Violation on Battery SOC
        for sig_id in incident.signal_ids:
            if "RANGE_VIOLATION" in sig_id or "battery_soc" in incident.admission_reason:
                hyp = Hypothesis(
                    incident_id=incident.incident_id,
                    claim=f"Deterministic R0 identified out-of-range sensor value for {incident.entity_ids[0]}.",
                    classification="DATA",
                    supporting_evidence=[e.evidence_id for e in initial_evidence],
                    confidence=1.0,
                    status="CONFIRMED"
                )
                rec = self.router.route_hypothesis(incident.incident_id, hyp)
                return hyp, rec

        # Rule 2: Critical L1 NULL violation
        if "NULL_VIOLATION" in incident.admission_reason:
            hyp = Hypothesis(
                incident_id=incident.incident_id,
                claim=f"Deterministic R0 confirmed missing mandatory attribute in {incident.entity_ids[0]}.",
                classification="DATA",
                supporting_evidence=[e.evidence_id for e in initial_evidence],
                confidence=1.0,
                status="CONFIRMED"
            )
            rec = self.router.route_hypothesis(incident.incident_id, hyp)
            return hyp, rec

        # Fallback: Cannot resolve deterministically -> escalate to C1/A1
        return None, None
