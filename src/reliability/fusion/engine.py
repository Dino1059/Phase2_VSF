import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from src.reliability.models.signal import Signal
from src.reliability.models.incident import Incident
from src.reliability.fusion.policy import AdmissionPolicy
from src.reliability.fusion.correlation import FaultCorrelationEngine


class FusionEngine:
    """
    Groups multi-layer signals (L1-L4) strictly by entity_id, project_id, and time_window (Tầng 1),
    evaluates AdmissionPolicy, and applies FaultCorrelationEngine (Tầng 2) to compress
    duplicate fault signatures into deterministic Incident groups.
    """

    def __init__(
        self,
        policy: Optional[AdmissionPolicy] = None,
        time_window_gap_seconds: float = 1800.0,
        use_correlation: bool = True,
    ):
        self.policy = policy or AdmissionPolicy()
        self.time_window_gap_seconds = time_window_gap_seconds
        self.use_correlation = use_correlation
        self.correlation_engine = FaultCorrelationEngine()

    def _signals_are_connected(self, s1: Signal, s2: Signal) -> bool:
        # 1. Project match
        if s1.project_id != s2.project_id:
            return False

        # 2. Shared entity match
        if not (set(s1.entity_ids) & set(s2.entity_ids)):
            return False

        # 3. Time window overlap / proximity match
        start1, end1 = s1.window_start, s1.window_end
        start2, end2 = s2.window_start, s2.window_end

        latest_start = max(start1, start2)
        earliest_end = min(end1, end2)
        if latest_start <= earliest_end:
            return True

        gap = (latest_start - earliest_end).total_seconds()
        return gap <= self.time_window_gap_seconds

    def _compute_cluster_correlation_key(self, sig_list: List[Signal]) -> str:
        distinct_keys = sorted(list({self.correlation_engine.compute_correlation_key(s) for s in sig_list}))
        if len(distinct_keys) == 1:
            return distinct_keys[0]
        raw = "|".join(distinct_keys)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def fuse_signals_into_incidents(
        self, signals: List[Signal], project_id: str
    ) -> List[Incident]:
        """
        Group signals strictly by entity_id, project_id, and time_window into raw clusters (Tầng 1),
        evaluate admission, and correlate clusters by fault key (Tầng 2).
        """
        if not signals:
            return []

        # Filter by project_id and deduplicate signals by signal_id
        project_signals: List[Signal] = []
        seen_ids = set()
        for sig in signals:
            effective_project_id = sig.project_id or project_id
            if effective_project_id == project_id:
                if sig.signal_id not in seen_ids:
                    seen_ids.add(sig.signal_id)
                    project_signals.append(sig)

        if not project_signals:
            return []

        # Tầng 1: Connected components graph based on entity_id and time_window
        n = len(project_signals)
        adj = [[] for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                if self._signals_are_connected(project_signals[i], project_signals[j]):
                    adj[i].append(j)
                    adj[j].append(i)

        visited = [False] * n
        raw_clusters: List[List[Signal]] = []

        for i in range(n):
            if not visited[i]:
                cluster = []
                queue = [i]
                visited[i] = True
                while queue:
                    curr = queue.pop(0)
                    cluster.append(project_signals[curr])
                    for neighbor in adj[curr]:
                        if not visited[neighbor]:
                            visited[neighbor] = True
                            queue.append(neighbor)
                raw_clusters.append(cluster)

        raw_clusters.sort(key=lambda cl: min(s.window_start for s in cl))

        # Admission evaluation
        admitted_clusters: List[Tuple[List[Signal], str]] = []
        for sig_list in raw_clusters:
            is_admitted, reason = self.policy.evaluate_admission(sig_list)
            if is_admitted:
                admitted_clusters.append((sig_list, reason))

        if not admitted_clusters:
            return []

        # Tầng 2: Correlation Engine grouping by correlation_key
        if self.use_correlation:
            corr_groups: Dict[str, List[Tuple[List[Signal], str]]] = defaultdict(list)
            for sig_list, reason in admitted_clusters:
                key = self._compute_cluster_correlation_key(sig_list)
                corr_groups[key].append((sig_list, reason))

            incidents: List[Incident] = []
            for corr_key, items in corr_groups.items():
                merged_signals: List[Signal] = []
                seen_sig_ids = set()
                reasons = []

                for sig_list, reason in items:
                    reasons.append(reason)
                    for s in sig_list:
                        if s.signal_id not in seen_sig_ids:
                            seen_sig_ids.add(s.signal_id)
                            merged_signals.append(s)

                start_time = min(s.window_start for s in merged_signals)
                end_time = max(s.window_end for s in merged_signals)

                severities = {s.severity for s in merged_signals}
                if "CRITICAL" in severities:
                    overall_sev = "CRITICAL"
                elif "HIGH" in severities:
                    overall_sev = "HIGH"
                elif "MEDIUM" in severities:
                    overall_sev = "MEDIUM"
                else:
                    overall_sev = "LOW"

                all_evidence = sorted(list({ref for s in merged_signals for ref in s.evidence_refs}))
                cluster_entities = sorted(list({e for s in merged_signals for e in s.entity_ids}))
                supporting_layers = sorted(list({s.layer for s in merged_signals}))
                rep_ids = [s.signal_id for s in sorted(merged_signals, key=lambda s: s.score, reverse=True)[:3]]

                if len(items) == 1:
                    adm_reason = reasons[0]
                    facts = [f"Admitted via {adm_reason}"]
                else:
                    adm_reason = f"FaultCorrelationEngine: {len(merged_signals)} signals compressed under key {corr_key}"
                    facts = [f"Correlated {len(merged_signals)} occurrences of fault key {corr_key}"]

                inc = Incident(
                    project_id=project_id,
                    status="OPEN",
                    entity_ids=cluster_entities,
                    signal_ids=[s.signal_id for s in merged_signals],
                    admission_reason=adm_reason,
                    supporting_layers=supporting_layers,
                    severity=overall_sev,
                    time_window={"start": start_time, "end": end_time},
                    confirmed_facts=facts,
                    evidence_refs=all_evidence,
                    correlation_key=corr_key,
                    occurrence_count=len(merged_signals),
                    representative_signal_ids=rep_ids,
                )
                incidents.append(inc)

            return incidents

        # Fallback if use_correlation is False
        incidents: List[Incident] = []
        for sig_list, reason in admitted_clusters:
            start_time = min(s.window_start for s in sig_list)
            end_time = max(s.window_end for s in sig_list)

            severities = {s.severity for s in sig_list}
            if "CRITICAL" in severities:
                overall_sev = "CRITICAL"
            elif "HIGH" in severities:
                overall_sev = "HIGH"
            elif "MEDIUM" in severities:
                overall_sev = "MEDIUM"
            else:
                overall_sev = "LOW"

            all_evidence = sorted(list({ref for s in sig_list for ref in s.evidence_refs}))
            cluster_entities = sorted(list({e for s in sig_list for e in s.entity_ids}))
            supporting_layers = sorted(list({s.layer for s in sig_list}))
            corr_key = self._compute_cluster_correlation_key(sig_list)
            rep_ids = [s.signal_id for s in sorted(sig_list, key=lambda s: s.score, reverse=True)[:3]]

            inc = Incident(
                project_id=project_id,
                status="OPEN",
                entity_ids=cluster_entities,
                signal_ids=[s.signal_id for s in sig_list],
                admission_reason=reason,
                supporting_layers=supporting_layers,
                severity=overall_sev,
                time_window={"start": start_time, "end": end_time},
                confirmed_facts=[f"Admitted via {reason}"],
                evidence_refs=all_evidence,
                correlation_key=corr_key,
                occurrence_count=len(sig_list),
                representative_signal_ids=rep_ids,
            )
            incidents.append(inc)

        return incidents

