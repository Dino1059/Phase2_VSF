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
    List open incidents in project enriched with domain fault family and root causes.
    """
    incidents = service.list_incidents(project_id)
    if not incidents:
        service.seed_benchmark_cases()
        incidents = service.list_incidents(project_id)

    # Load gold benchmark metadata and evaluation results
    import json
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    eval_dir = base_dir / "eval" / "fault_RCA_benchamark" / "v2-optimized_token_prompt"
    gold_path = eval_dir / "gold_rca_cases.json"
    bench_path = eval_dir / "rca_benchmark_results.json"

    gold_map = {}
    if gold_path.exists():
        try:
            with open(gold_path, "r", encoding="utf-8") as f:
                for c in json.load(f):
                    gold_map[c.get("incident_id")] = c
        except Exception:
            pass

    bench_map = {}
    if bench_path.exists():
        try:
            with open(bench_path, "r", encoding="utf-8") as f:
                bdata = json.load(f)
                for ec in bdata.get("evaluated_cases", []):
                    bench_map[ec.get("incident_id")] = ec
        except Exception:
            pass

    res = []
    for inc in incidents:
        d = inc.model_dump(mode="json")
        g = gold_map.get(inc.incident_id, {})
        b = bench_map.get(inc.incident_id, {})

        if g:
            d["fault_family"] = g.get("fault_family")
            d["domain"] = g.get("domain")
            d["layer"] = g.get("layer") or (d.get("supporting_layers", ["L1"])[0] if d.get("supporting_layers") else "L1")
            d["ground_truth_cause"] = g.get("ground_truth_cause")
            d["expected_action"] = g.get("expected_action")
            d["expected_classification"] = g.get("expected_classification")
            d["target_entity"] = g.get("entity_ids", ["VIN-001"])[0] if g.get("entity_ids") else "VIN-001"

        if b:
            eval_info = b.get("evaluation", {})
            meta_info = b.get("meta", {})
            hyp_info = b.get("hypothesis", {})
            d["benchmark_score"] = round(eval_info.get("composite_score", 0.8) * 100, 1)
            d["verdict"] = eval_info.get("verdict", "PASS")
            d["tool_trace"] = meta_info.get("tool_trace", [])
            d["tokens_spent"] = meta_info.get("tokens_spent", 0)
            d["llm_claim"] = hyp_info.get("claim", "")
            d["llm_classification"] = hyp_info.get("classification", "DATA")

        res.append(d)
    return res


@router.get("/{incident_id}", response_model=Dict[str, Any])
def get_incident(incident_id: str):
    """
    Retrieve incident details by ID including hypotheses, evidence, recommendations, and benchmark metadata.
    """
    inc = service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    data = inc.model_dump(mode="json")
    ev_list = service.get_evidence_for_incident(incident_id)
    hyp_list = service.list_hypotheses_for_incident(incident_id)
    rec_list = service.list_recommendations_for_incident(incident_id)

    data["evidence"] = [e.model_dump(mode="json") for e in ev_list]
    data["hypotheses"] = [h.model_dump(mode="json") for h in hyp_list]
    data["recommendations"] = [r.model_dump(mode="json") for r in rec_list]

    # Load gold benchmark metadata and evaluation results
    import json
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    eval_dir = base_dir / "eval" / "fault_RCA_benchamark" / "v2-optimized_token_prompt"
    gold_path = eval_dir / "gold_rca_cases.json"
    bench_path = eval_dir / "rca_benchmark_results.json"

    if gold_path.exists():
        try:
            with open(gold_path, "r", encoding="utf-8") as f:
                cases = json.load(f)
            for c in cases:
                if c.get("incident_id") == incident_id:
                    data["fault_family"] = c.get("fault_family")
                    data["domain"] = c.get("domain")
                    data["layer"] = c.get("layer") or (data.get("supporting_layers", ["L1"])[0] if data.get("supporting_layers") else "L1")
                    data["ground_truth_cause"] = c.get("ground_truth_cause")
                    data["expected_action"] = c.get("expected_action")
                    data["expected_keywords"] = c.get("expected_keywords", [])
                    data["expected_classification"] = c.get("expected_classification")
                    data["target_entity"] = c.get("entity_ids", ["VIN-001"])[0] if c.get("entity_ids") else "VIN-001"
                    break
        except Exception:
            pass

    if bench_path.exists():
        try:
            with open(bench_path, "r", encoding="utf-8") as f:
                bdata = json.load(f)
            for ec in bdata.get("evaluated_cases", []):
                if ec.get("incident_id") == incident_id:
                    eval_info = ec.get("evaluation", {})
                    meta_info = ec.get("meta", {})
                    hyp_info = ec.get("hypothesis", {})
                    rec_info = ec.get("recommendation", {})
                    data["benchmark_eval"] = {
                        "case_index": ec.get("case_index"),
                        "hypothesis": hyp_info,
                        "recommendation": rec_info,
                        "meta": meta_info,
                        "evaluation": eval_info,
                        "score_pct": round(eval_info.get("composite_score", 0.8) * 100, 1),
                        "verdict": eval_info.get("verdict", "PASS"),
                        "tool_trace": meta_info.get("tool_trace", []),
                        "tokens_spent": meta_info.get("tokens_spent", 0),
                        "latency_sec": meta_info.get("latency_sec", 0),
                    }
                    break
        except Exception:
            pass

    return data


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
