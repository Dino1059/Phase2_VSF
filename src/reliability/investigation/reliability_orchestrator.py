from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from src.reliability.fusion.engine import FusionEngine
from src.reliability.incidents.service import IncidentService
from src.reliability.investigation.a1 import A1BoundedInvestigator
from src.reliability.models.signal import Signal
from src.reliability.models.incident import Incident
from src.reliability.models.hypothesis import Hypothesis
from src.reliability.models.evidence import Evidence
from src.reliability.governance.recommendations import Recommendation


@dataclass
class InvestigationResult:
    incident: Incident
    hypothesis: Hypothesis
    recommendation: Recommendation
    meta: Dict[str, Any]


class ReliabilityOrchestrator:
    """
    Production orchestration: Detection → Fusion → Admission → Incident → A1 RCA.
    Design V2: Only A1 runs in production. R0/C1 are benchmark-only.
    """

    def __init__(
        self,
        incident_service: Optional[IncidentService] = None,
        fusion_engine: Optional[FusionEngine] = None,
        a1: Optional[A1BoundedInvestigator] = None,
    ):
        self.incident_service = incident_service or IncidentService()
        self.fusion_engine = fusion_engine or FusionEngine()
        self.a1 = a1 or A1BoundedInvestigator()

    def process_signals(self, signals: List[Signal], project_id: str) -> List[InvestigationResult]:
        # 1. FusionEngine groups signals into incidents
        incidents = self.fusion_engine.fuse_signals_into_incidents(signals, project_id)

        results = []
        for inc in incidents:
            # 2. Persist admitted incidents
            self.incident_service.save_incident(inc)

            # 3. Retrieve evidence scoped to this incident
            ev = self.incident_service.get_evidence_for_incident(inc.incident_id)

            # 4. Run A1 on each incident
            hyp, rec, meta = self.a1.investigate_incident_dynamically(inc, ev)
            if hyp:
                self.incident_service.add_hypothesis(hyp)
            if rec:
                self.incident_service.add_recommendation(rec)
            if meta:
                self.incident_service.set_incident_meta(inc.incident_id, meta)
                for trace_item in meta.get("tool_execution_trace", []):
                    ref = trace_item.get("evidence_ref")
                    if ref:
                        tool_ev = Evidence(
                            evidence_id=ref,
                            source_type=trace_item.get("tool_name", "tool_output"),
                            source_id=inc.entity_ids[0] if inc.entity_ids else "VIN-001",
                            entity_ids=inc.entity_ids or [],
                            content_hash=f"hash-{ref}",
                            summary=f"Tool {trace_item.get('tool_name')} returned data: {str(trace_item.get('data'))[:300]}",
                            provenance="REAL_OPERATIONAL"
                        )
                        self.incident_service.add_evidence(tool_ev, incident_id=inc.incident_id, project_id=project_id)

            results.append(InvestigationResult(
                incident=inc,
                hypothesis=hyp,
                recommendation=rec,
                meta=meta,
            ))

        return results

    def run_pipeline(
        self, detector_outputs: Dict[str, List[Signal]], project_id: str
    ) -> List[InvestigationResult]:
        """
        Top-level entry: accepts L1-L4 detector outputs (dict by layer),
        merges into signals, runs process_signals.
        """
        all_signals: List[Signal] = []
        for layer, signals in detector_outputs.items():
            all_signals.extend(signals)
        return self.process_signals(all_signals, project_id)
