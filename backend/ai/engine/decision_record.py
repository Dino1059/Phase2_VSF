"""
DataTrust OS: Decision Record Builder
Implements SOX-404 Audit & Enterprise Data Governance compliant decision records.
Tracks:
- Action selected by Agent
- Grounds / claims made
- Evidence references (lineage hashes, row keys, policy clauses)
- Confidence score and calculation method
- Justification for continuing or terminating reasoning loop
"""

import hashlib
import uuid
from typing import Dict, Any, List, Optional

from backend.database.models import DecisionRecordModel


class DecisionRecordBuilder:
    """Helper to construct audit-verifiable decision records for agent actions."""

    @staticmethod
    def build_decision(
        selected_action: str,
        claim: str,
        evidence_refs: Optional[List[str]] = None,
        source_queries: Optional[List[str]] = None,
        confidence: float = 0.95,
        confidence_method: str = "heuristic_grounding",
        contradicting_evidence_refs: Optional[List[str]] = None,
        alternative_considered: Optional[str] = None,
        stop_continue_reason: str = "Mục tiêu bước suy luận đã hoàn thành."
    ) -> DecisionRecordModel:
        """Constructs an audit-ready DecisionRecordModel."""
        evidence_refs = evidence_refs or []
        source_queries = source_queries or []
        
        # Calculate SHA-256 hashes of queries executed to ensure reproducibility
        query_hashes = [
            hashlib.sha256(q.encode("utf-8")).hexdigest()[:16]
            for q in source_queries if q
        ]

        return DecisionRecordModel(
            decision_id=f"DEC-{uuid.uuid4().hex[:8]}",
            selected_action=selected_action,
            claim=claim,
            evidence_refs=evidence_refs,
            contradicting_evidence_refs=contradicting_evidence_refs or [],
            source_query_hashes=query_hashes,
            confidence_method=confidence_method,
            confidence=min(max(confidence, 0.0), 1.0),
            alternative_considered=alternative_considered,
            stop_continue_reason=stop_continue_reason
        )
