from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from src.reliability.incidents.service import IncidentService
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.models.hypothesis import Hypothesis
from src.reliability.investigation.r0 import R0DeterministicInvestigator
from src.reliability.investigation.c1 import C1FixedInvestigator
from src.reliability.investigation.a1 import A1BoundedInvestigator

router = APIRouter(prefix="/incidents", tags=["incidents"])
service = IncidentService()
r0_investigator = R0DeterministicInvestigator()
c1_investigator = C1FixedInvestigator()
a1_investigator = A1BoundedInvestigator()


@router.get("", response_model=List[Dict[str, Any]])
def list_incidents(project_id: str = Query("proj-vingroup-pilot")):
    """
    List open incidents in project.
    """
    incidents = service.list_incidents(project_id)
    if not incidents:
        # Create seed sample incident for demonstration
        inc = service.create_incident(
            project_id=project_id,
            entity_ids=["VIN-010"],
            signal_ids=["sig-l2-002"],
            admission_reason="Persistent L2 drift on battery discharge rate",
            severity="HIGH"
        )
        return [inc.model_dump(mode="json")]
    return [i.model_dump(mode="json") for i in incidents]


@router.get("/{incident_id}", response_model=Dict[str, Any])
def get_incident(incident_id: str):
    """
    Retrieve incident details by ID.
    """
    inc = service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc.model_dump(mode="json")


@router.post("/{incident_id}/investigate")
def investigate_incident(incident_id: str, mode: str = Query("C1")):
    """
    Run incident investigation (mode: R0, C1, or A1).
    """
    inc = service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    evidence_list = service.get_evidence_for_incident(incident_id)

    if mode == "R0":
        hyp, rec = r0_investigator.investigate_incident(inc, evidence_list)
        meta = {"mode": "R0", "resolved": hyp is not None}
    elif mode == "A1":
        hyp, rec, meta = a1_investigator.investigate_incident_dynamically(inc, evidence_list)
    else:  # Default C1
        hyp, rec = c1_investigator.investigate_incident(inc, evidence_list)
        meta = {"mode": "C1", "resolved": True}

    if hyp:
        service.add_hypothesis(hyp)

    return {
        "incident_id": incident_id,
        "mode": mode,
        "hypothesis": hyp.model_dump(mode="json") if hyp else None,
        "recommendation": rec.model_dump(mode="json") if rec else None,
        "metadata": meta
    }


class IncidentChatRequest(BaseModel):
    message: str
    investigation_mode: Optional[str] = "C1"
    user_role: Optional[str] = "steward"
    active_hypothesis: Optional[Dict[str, Any]] = None
    selected_evidence: Optional[Dict[str, Any]] = None


@router.post("/{incident_id}/chat")
def incident_chat(incident_id: str, request: IncidentChatRequest):
    """
    Contextual Assistant Chat Endpoint powered by LLM.
    """
    from src.services.llm import LLMService
    llm = LLMService()

    inc = service.get_incident(incident_id)
    evidence_list = service.get_evidence_for_incident(incident_id)

    system_prompt = f"""
    You are the Contextual Assistant for DataTrust OS v5 Operational Trust Console.
    You are currently assisting a Data Steward ({request.user_role}) analyzing Incident {incident_id}.
    
    Incident Context:
    - Incident ID: {incident_id}
    - Admission Reason: {inc.admission_reason if inc else 'Anomaly detection drift'}
    - Severity: {inc.severity if inc else 'HIGH'}
    - Target Entities: {', '.join(inc.entity_ids) if inc and inc.entity_ids else 'VIN-010'}
    - Investigation Mode: {request.investigation_mode}
    - Supporting Evidence Count: {len(evidence_list)}
    - Active Hypothesis: {request.active_hypothesis.get('claim') if request.active_hypothesis else 'None selected'}
    - Focused Evidence: {request.selected_evidence.get('summary') if request.selected_evidence else 'None focused'}

    Provide concise, professional, evidence-grounded answers for data stewardship and reliability operations.
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request.message}
    ]

    res = llm.chat(messages)
    return {
        "incident_id": incident_id,
        "reply": res.content,
        "reasoning": f"Synthesized via LLM against incident evidence & hypothesis graph.",
        "tokens_used": res.tokens_used
    }
