import hashlib
from typing import List, Dict, Optional
from collections import defaultdict
from src.reliability.models.signal import Signal
from src.reliability.models.incident import Incident

SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

class FaultCorrelationEngine:
    """
    Deterministic correlation engine for deduplicating and clustering signals
    by fault identity key (correlation_key).
    """

    @staticmethod
    def compute_correlation_key(signal: Signal) -> str:
        """
        Compute a deterministic key based on signal attributes defining the root fault rule:
        project_id, source_table, detector, signal_type, metric_or_relationship, violation_direction.
        """
        raw_key = (
            f"{signal.project_id}|"
            f"{signal.source_table or ''}|"
            f"{signal.detector}|"
            f"{signal.signal_type}|"
            f"{signal.metric_or_relationship}|"
            f"{signal.violation_direction or ''}"
        )
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]

    def group_signals_by_key(self, signals: List[Signal]) -> Dict[str, List[Signal]]:
        """
        Group signals strictly by correlation_key.
        """
        groups: Dict[str, List[Signal]] = defaultdict(list)
        for sig in signals:
            key = self.compute_correlation_key(sig)
            groups[key].append(sig)
        return dict(groups)

    def correlate_signals(self, signals: List[Signal], project_id: str) -> List[Incident]:
        """
        Correlate signals into incident groups based on correlation_key.
        Each correlation_key yields exactly 1 Incident with representative_signal_ids
        and occurrence_count.
        """
        if not signals:
            return []

        grouped = self.group_signals_by_key(signals)
        incidents: List[Incident] = []

        for corr_key, sig_list in grouped.items():
            start_time = min(s.window_start for s in sig_list)
            end_time = max(s.window_end for s in sig_list)

            # Determine max severity
            highest_sev = max(sig_list, key=lambda s: SEVERITY_RANK.get(s.severity, 0)).severity

            # Representative signal IDs (top 3 highest scoring signals)
            sorted_by_score = sorted(sig_list, key=lambda s: s.score, reverse=True)
            rep_ids = [s.signal_id for s in sorted_by_score[:3]]

            all_entities = sorted(list({e for s in sig_list for e in s.entity_ids}))
            all_layers = sorted(list({s.layer for s in sig_list}))
            all_evidence = sorted(list({ref for s in sig_list for ref in s.evidence_refs}))

            inc = Incident(
                project_id=project_id,
                status="OPEN",
                entity_ids=all_entities,
                signal_ids=[s.signal_id for s in sig_list],
                admission_reason=f"FaultCorrelationEngine: {len(sig_list)} signals compressed under key {corr_key}",
                supporting_layers=all_layers,
                severity=highest_sev,
                time_window={"start": start_time, "end": end_time},
                confirmed_facts=[f"Correlated {len(sig_list)} occurrences of fault key {corr_key}"],
                evidence_refs=all_evidence,
                correlation_key=corr_key,
                occurrence_count=len(sig_list),
                representative_signal_ids=rep_ids,
            )
            incidents.append(inc)

        return incidents
