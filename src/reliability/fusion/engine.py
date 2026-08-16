from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from src.reliability.models.signal import Signal
from src.reliability.models.incident import Incident
from src.reliability.fusion.policy import AdmissionPolicy


class FusionEngine:
    """
    Groups multi-layer signals (L1-L4) strictly by entity_id, project_id, and time_window,
    deduplicates signals, and applies AdmissionPolicy to form persistent Incidents.
    """

    def __init__(
        self,
        policy: Optional[AdmissionPolicy] = None,
        time_window_gap_seconds: float = 1800.0,
    ):
        self.policy = policy or AdmissionPolicy()
        self.time_window_gap_seconds = time_window_gap_seconds

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

    def fuse_signals_into_incidents(
        self, signals: List[Signal], project_id: str
    ) -> List[Incident]:
        """
        Group signals strictly by entity_id, project_id, and time_window into Incidents
        with explicit admission_reason and supporting_layers.
        """
        if not signals:
            return []

        # Filter by project_id and deduplicate signals by signal_id
        project_signals: List[Signal] = []
        seen_ids = set()
        for sig in signals:
            # If signal project_id is empty, assign target project_id
            effective_project_id = sig.project_id or project_id
            if effective_project_id == project_id:
                if sig.signal_id not in seen_ids:
                    seen_ids.add(sig.signal_id)
                    project_signals.append(sig)

        if not project_signals:
            return []

        # Build adjacency graph for connected components based on entity_id, project_id, and time_window
        n = len(project_signals)
        adj = [[] for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                if self._signals_are_connected(project_signals[i], project_signals[j]):
                    adj[i].append(j)
                    adj[j].append(i)

        # Find connected components (clusters)
        visited = [False] * n
        clusters: List[List[Signal]] = []

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
                clusters.append(cluster)

        # Sort clusters by min window_start for deterministic ordering
        clusters.sort(key=lambda cl: min(s.window_start for s in cl))

        incidents: List[Incident] = []

        for sig_list in clusters:
            is_admitted, reason = self.policy.evaluate_admission(sig_list)
            if is_admitted:
                start_time = min(s.window_start for s in sig_list)
                end_time = max(s.window_end for s in sig_list)

                # Determine overall severity
                severities = {s.severity for s in sig_list}
                if "CRITICAL" in severities:
                    overall_sev = "CRITICAL"
                elif "HIGH" in severities:
                    overall_sev = "HIGH"
                elif "MEDIUM" in severities:
                    overall_sev = "MEDIUM"
                else:
                    overall_sev = "LOW"

                all_evidence = []
                for s in sig_list:
                    all_evidence.extend(s.evidence_refs)

                cluster_entities = sorted(list({e for s in sig_list for e in s.entity_ids}))
                supporting_layers = sorted(list({s.layer for s in sig_list}))

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
                    evidence_refs=sorted(list(set(all_evidence)))
                )
                incidents.append(inc)

        return incidents
