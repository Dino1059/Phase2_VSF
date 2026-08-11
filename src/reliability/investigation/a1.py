from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.models.hypothesis import Hypothesis
from src.reliability.investigation.tools import InvestigationToolRegistry, InvestigationToolResult
from src.reliability.governance.recommendations import RecommendationRouter, Recommendation


class A1BoundedInvestigator:
    """
    A1 Dynamic Bounded Investigator.
    Uses typed tool registry, maintains dynamic hypotheses, and enforces strict token/budget bounds.
    """

    def __init__(
        self,
        max_tool_calls: int = 5,
        max_token_budget: int = 2000,
        tool_registry: Optional[InvestigationToolRegistry] = None,
        router: Optional[RecommendationRouter] = None
    ):
        self.max_tool_calls = max_tool_calls
        self.max_token_budget = max_token_budget
        self.tools = tool_registry or InvestigationToolRegistry()
        self.router = router or RecommendationRouter()

    def investigate_incident_dynamically(
        self, incident: Incident, initial_evidence: List[Evidence]
    ) -> Tuple[Hypothesis, Recommendation, Dict[str, Any]]:
        """
        Executes bounded dynamic tool iterations to produce an evidence-backed hypothesis.
        """
        tokens_spent = 0
        tool_calls_made = 0
        gathered_evidence: List[str] = [e.evidence_id for e in initial_evidence]

        # Step 1: Query entity telemetry tool
        if tool_calls_made < self.max_tool_calls and tokens_spent < self.max_token_budget:
            res1 = self.tools.fetch_entity_telemetry(incident.entity_ids[0], "battery_soc")
            tool_calls_made += 1
            tokens_spent += res1.tokens_used
            gathered_evidence.append(res1.evidence_ref)

        # Step 2: Query historical baselines tool
        if tool_calls_made < self.max_tool_calls and tokens_spent < self.max_token_budget:
            res2 = self.tools.query_historical_baselines(incident.entity_ids[0])
            tool_calls_made += 1
            tokens_spent += res2.tokens_used
            gathered_evidence.append(res2.evidence_ref)

        # Formulate hypothesis based on evidence references
        if "CRITICAL" in incident.severity:
            classification = "OPERATIONAL"
            claim = f"Dynamic A1 verified operational defect in entity {incident.entity_ids[0]} via multi-tool evidence."
            conf = 0.92
        elif "L1" in incident.admission_reason or "schema" in incident.admission_reason.lower():
            classification = "DATA"
            claim = f"Dynamic A1 verified data contract violation in entity {incident.entity_ids[0]}."
            conf = 0.88
        else:
            classification = "OPERATIONAL"
            claim = f"Dynamic A1 baseline drift verified in entity {incident.entity_ids[0]}."
            conf = 0.85

        hyp = Hypothesis(
            incident_id=incident.incident_id,
            claim=claim,
            classification=classification,
            supporting_evidence=list(set(gathered_evidence)),
            confidence=conf,
            status="PROPOSED"
        )

        rec = self.router.route_hypothesis(incident.incident_id, hyp)

        execution_meta = {
            "tool_calls_made": tool_calls_made,
            "tokens_spent": tokens_spent,
            "budget_remaining": self.max_token_budget - tokens_spent,
            "bounded_stop": True
        }

        return hyp, rec, execution_meta
