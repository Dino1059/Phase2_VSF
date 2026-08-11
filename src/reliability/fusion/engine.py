from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from src.reliability.models.signal import Signal
from src.reliability.models.incident import Incident
from src.reliability.fusion.policy import AdmissionPolicy


class FusionEngine:
    """
    Groups multi-layer signals (L1-L4) by entity/time window, normalizes scores,
    and applies AdmissionPolicy to form persistent Incidents.
    """

    def __init__(self, policy: Optional[AdmissionPolicy] = None):
        self.policy = policy or AdmissionPolicy()

    def fuse_signals_into_incidents(
        self, signals: List[Signal], project_id: str
    ) -> List[Incident]:
        """
        Group signals by entity and construct Incidents if admission policy is met.
        """
        if not signals:
            return []

        # Group signals by entity_id
        entity_groups = defaultdict(list)
        for sig in signals:
            for entity_id in sig.entity_ids:
                entity_groups[entity_id].append(sig)

        incidents: List[Incident] = []

        for entity_id, sig_list in entity_groups.items():
            is_admitted, reason = self.policy.evaluate_admission(sig_list)
            if is_admitted:
                start_time = min(s.window_start for s in sig_list)
                end_time = max(s.window_end for s in sig_list)

                # Determine overall severity
                severities = [s.severity for s in sig_list]
                if "CRITICAL" in severities:
                    overall_sev = "CRITICAL"
                elif "HIGH" in severities:
                    overall_sev = "HIGH"
                else:
                    overall_sev = "MEDIUM"

                all_evidence = []
                for s in sig_list:
                    all_evidence.extend(s.evidence_refs)

                inc = Incident(
                    project_id=project_id,
                    status="OPEN",
                    entity_ids=[entity_id],
                    signal_ids=[s.signal_id for s in sig_list],
                    admission_reason=reason,
                    severity=overall_sev,
                    time_window={"start": start_time, "end": end_time},
                    confirmed_facts=[f"Admitted via {reason}"],
                    evidence_refs=list(set(all_evidence))
                )
                incidents.append(inc)

        return incidents
