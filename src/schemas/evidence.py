from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class EvidenceTier(str, Enum):
    SIMULATED = "SIMULATED"
    PROXY = "PROXY"
    PILOT = "PILOT"
    VALIDATED = "VALIDATED"


class ConfidenceMethod(str, Enum):
    HEURISTIC_GROUNDING = "heuristic_grounding"
    BAYESIAN_EVIDENCE = "bayesian_evidence"
    STATISTICAL_MAD = "statistical_mad"
    VERIFIER_AUDIT = "verifier_audit"


@dataclass
class EvidenceItem:
    evidence_id: str = field(default_factory=lambda: f"ev-{uuid.uuid4().hex[:8]}")
    tier: EvidenceTier = EvidenceTier.PROXY
    source_query_hash: str = ""
    claim: str = ""
    table_name: Optional[str] = None
    column_name: Optional[str] = None
    metric_value: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionRecord:
    decision_id: str = field(default_factory=lambda: f"dec-{uuid.uuid4().hex[:8]}")
    claim: str = ""
    selected_action: str = ""
    evidence_refs: List[str] = field(default_factory=list)
    contradicting_evidence_refs: List[str] = field(default_factory=list)
    source_query_hashes: List[str] = field(default_factory=list)
    confidence_method: ConfidenceMethod = ConfidenceMethod.HEURISTIC_GROUNDING
    confidence_value: float = 0.95
    alternatives_considered: List[str] = field(default_factory=list)
    stop_continue_reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class EvidenceLedger:
    run_id: str
    items: List[EvidenceItem] = field(default_factory=list)
    decisions: List[DecisionRecord] = field(default_factory=list)

    def add_evidence(self, item: EvidenceItem) -> str:
        self.items.append(item)
        return item.evidence_id

    def record_decision(self, decision: DecisionRecord) -> str:
        self.decisions.append(decision)
        return decision.decision_id

    def get_supporting_evidence(self, evidence_ids: List[str]) -> List[EvidenceItem]:
        return [item for item in self.items if item.evidence_id in evidence_ids]
