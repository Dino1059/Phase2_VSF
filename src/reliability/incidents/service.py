from typing import List, Dict, Optional
from datetime import datetime, timezone
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.models.hypothesis import Hypothesis


class IncidentService:
    """
    Manages persistence and retrieval of Incidents, Evidence, and Hypotheses.
    """

    def __init__(self):
        self._incidents: Dict[str, Incident] = {}
        self._evidence: Dict[str, Evidence] = {}
        self._hypotheses: Dict[str, Hypothesis] = {}

    def save_incident(self, incident: Incident) -> Incident:
        self._incidents[incident.incident_id] = incident
        return incident

    def create_incident(
        self, project_id: str, entity_ids: List[str], signal_ids: List[str], admission_reason: str, severity: str = "HIGH"
    ) -> Incident:
        inc = Incident(
            project_id=project_id,
            entity_ids=entity_ids,
            signal_ids=signal_ids,
            admission_reason=admission_reason,
            severity=severity
        )
        return self.save_incident(inc)

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        return self._incidents.get(incident_id)

    def get_evidence_for_incident(self, incident_id: str) -> List[Evidence]:
        return list(self._evidence.values())

    def list_incidents(self, project_id: Optional[str] = None) -> List[Incident]:
        if project_id:
            return [inc for inc in self._incidents.values() if inc.project_id == project_id]
        return list(self._incidents.values())

    def update_incident_status(self, incident_id: str, status: str) -> Optional[Incident]:
        inc = self._incidents.get(incident_id)
        if inc:
            inc.status = status
            inc.updated_at = datetime.now(timezone.utc)
        return inc

    def add_evidence(self, evidence: Evidence) -> Evidence:
        self._evidence[evidence.evidence_id] = evidence
        return evidence

    def get_evidence(self, evidence_id: str) -> Optional[Evidence]:
        return self._evidence.get(evidence_id)

    def add_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        self._hypotheses[hypothesis.hypothesis_id] = hypothesis
        return hypothesis

    def list_hypotheses_for_incident(self, incident_id: str) -> List[Hypothesis]:
        return [h for h in self._hypotheses.values() if h.incident_id == incident_id]
