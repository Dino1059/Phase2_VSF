from typing import List, Optional, Tuple
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.models.hypothesis import Hypothesis
from src.reliability.governance.recommendations import RecommendationRouter, Recommendation


class C0DeterministicBaseline:
    """
    C0 Deterministic Baseline Investigator.
    
    Benchmark-only investigator. Resolves known incidents via fixed rule lookups,
    diagnostic mappings, and baseline checks. Zero LLM involvement. Fast SLA (<10ms).
    
    This is the baseline for benchmark comparison against C1 and A1 investigators.
    Used exclusively in offline benchmark harness — NOT in production pipeline.
    
    Design V2: C0 exists solely for benchmark comparison; A1 runs in production.
    """

    def __init__(self, router: Optional[RecommendationRouter] = None):
        self.router = router or RecommendationRouter()

    def investigate_incident(
        self, incident: Incident, initial_evidence: List[Evidence]
    ) -> Tuple[Optional[Hypothesis], Optional[Recommendation]]:
        """
        Attempts to resolve incident deterministically using known patterns.
        Returns (Hypothesis, Recommendation) if a known pattern matches, else (None, None).
        """
        # Rule 1: Known L1 Range Violation on Battery SOC
        for sig_id in incident.signal_ids:
            if "RANGE_VIOLATION" in sig_id or "battery_soc" in incident.admission_reason:
                entity_id = incident.entity_ids[0] if incident.entity_ids else "unknown_entity"
                hyp = Hypothesis(
                    incident_id=incident.incident_id,
                    claim=f"Deterministic C0 identified out-of-range sensor value for {entity_id}.",
                    classification="SYSTEM_DATA_LOGIC",
                    target_entity_id=entity_id,
                    supporting_evidence=[e.evidence_id for e in initial_evidence],
                    confidence=1.0,
                    status="CONFIRMED"
                )
                rec = self.router.route_hypothesis(incident.incident_id, hyp)
                return hyp, rec

        # Rule 2: Critical L1 NULL violation
        if "NULL_VIOLATION" in incident.admission_reason:
            entity_id = incident.entity_ids[0] if incident.entity_ids else "unknown_entity"
            hyp = Hypothesis(
                incident_id=incident.incident_id,
                claim=f"Deterministic C0 confirmed missing mandatory attribute in {entity_id}.",
                classification="SYSTEM_DATA_LOGIC",
                target_entity_id=entity_id,
                supporting_evidence=[e.evidence_id for e in initial_evidence],
                confidence=1.0,
                status="CONFIRMED"
            )
            rec = self.router.route_hypothesis(incident.incident_id, hyp)
            return hyp, rec

        # Fallback: Cannot resolve deterministically -> escalate to C1/A1
        return None, None
