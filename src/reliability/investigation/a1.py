import time
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timezone
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.models.hypothesis import Hypothesis, CauseClassification
from src.reliability.investigation.tools import InvestigationToolRegistry, InvestigationToolResult
from src.reliability.governance.recommendations import RecommendationRouter, Recommendation


# Target Entity Domains
DOMAIN_EV_TELEMETRY = "EV_TELEMETRY"
DOMAIN_CHARGING_NETWORK = "CHARGING_NETWORK"
DOMAIN_RIDE_HAILING = "RIDE_HAILING"
DOMAIN_CUSTOMER_FEEDBACK = "CUSTOMER_FEEDBACK"

# Domain-scoped tool allowlists based on target entity domain
DOMAIN_TOOL_ALLOWLIST: Dict[str, Set[str]] = {
    DOMAIN_EV_TELEMETRY: {
        "fetch_entity_telemetry",
        "query_historical_baselines",
        "inspect_upstream_contracts",
        "fetch_profile",
        "fetch_dq_violations",
        "fetch_recent_changes",
        "resolve_entity_relationships",
        "calculate_detector_detail",
    },
    DOMAIN_CHARGING_NETWORK: {
        "fetch_charging_history",
        "query_historical_baselines",
        "inspect_upstream_contracts",
        "fetch_profile",
        "fetch_dq_violations",
        "fetch_recent_changes",
        "resolve_entity_relationships",
        "calculate_detector_detail",
        "fetch_entity_telemetry",
    },
    DOMAIN_RIDE_HAILING: {
        "fetch_trip_history",
        "query_historical_baselines",
        "inspect_upstream_contracts",
        "fetch_profile",
        "fetch_dq_violations",
        "fetch_recent_changes",
        "resolve_entity_relationships",
        "calculate_detector_detail",
        "fetch_entity_telemetry",
    },
    DOMAIN_CUSTOMER_FEEDBACK: {
        "fetch_dq_violations",
        "inspect_upstream_contracts",
        "fetch_profile",
        "fetch_recent_changes",
        "query_historical_baselines",
        "calculate_detector_detail",
        "resolve_entity_relationships",
    },
}


class A1BoundedInvestigator:
    """
    A1 Dynamic Bounded Investigator.
    Uses typed read-only tool registry, maintains dynamic competing hypotheses (supporting vs contradicting evidence),
    enforces strict operational bounds (max_tool_calls, max_wall_clock_sec, max_tokens_budget, max_hypothesis_revisions),
    supports domain-scoped tool allowlisting based on target entity domain (EV_TELEMETRY, CHARGING_NETWORK, RIDE_HAILING, CUSTOMER_FEEDBACK),
    filters domain-irrelevant tools upfront to reduce token overhead,
    supports explicit abstention for missing or contradictory evidence,
    and returns trace metadata (tokens_spent, tool_calls_made, tool_execution_trace).
    """

    def __init__(
        self,
        max_tool_calls: int = 5,
        max_tokens_budget: int = 2000,
        max_wall_clock_sec: float = 30.0,
        max_hypothesis_revisions: int = 3,
        tool_registry: Optional[InvestigationToolRegistry] = None,
        router: Optional[RecommendationRouter] = None,
        max_token_budget: Optional[int] = None,
        domain_allowlists: Optional[Dict[str, Set[str]]] = None,
    ):
        self.max_tool_calls = max_tool_calls
        if max_token_budget is not None:
            self.max_tokens_budget = max_token_budget
        else:
            self.max_tokens_budget = max_tokens_budget
        self.max_token_budget = self.max_tokens_budget  # Backward-compatibility alias
        self.max_wall_clock_sec = float(max_wall_clock_sec)
        self.max_hypothesis_revisions = max_hypothesis_revisions
        self.tools = tool_registry or InvestigationToolRegistry()
        self.router = router or RecommendationRouter()
        self.domain_allowlists = domain_allowlists or DOMAIN_TOOL_ALLOWLIST

        self.tools.verify_zero_state_mutation()

    def detect_target_entity_domain(
        self, incident: Incident, initial_evidence: List[Evidence]
    ) -> str:
        """
        Determines target entity domain based on entity IDs, admission reason, signals, and evidence.
        Returns one of: EV_TELEMETRY, CHARGING_NETWORK, RIDE_HAILING, CUSTOMER_FEEDBACK.
        """
        explicit_domain = getattr(incident, "domain", None) or getattr(incident, "entity_domain", None)
        if explicit_domain and str(explicit_domain).upper() in self.domain_allowlists:
            return str(explicit_domain).upper()

        entity_str = " ".join(incident.entity_ids or []).upper()
        admission_text = (incident.admission_reason or "").lower()
        signals_text = " ".join(incident.signal_ids or []).lower()
        evidence_text = " ".join([f"{e.source_type} {e.source_id} {e.summary}" for e in (initial_evidence or [])]).lower()
        project_text = (incident.project_id or "").lower()

        combined = f"{entity_str} {admission_text} {signals_text} {evidence_text} {project_text}"

        # Entity ID prefix / explicit keyword checks
        if any(prefix in entity_str for prefix in ["FB-", "FEEDBACK-", "REVIEW-", "COMMENT-"]) or any(k in combined for k in ["customer_feedback", "customer feedback", "user_feedback", "teencode", "nlp_aspect", "raw_comment"]):
            return DOMAIN_CUSTOMER_FEEDBACK

        if any(prefix in entity_str for prefix in ["TRIP-", "RIDE-", "DRIVER-", "PASSENGER-", "XANH_SM"]) or any(k in combined for k in ["ride_hailing", "ride hailing", "trip_history", "aborted_trips", "completed_trips", "trip fare", "driver_id"]):
            return DOMAIN_RIDE_HAILING

        if any(prefix in entity_str for prefix in ["CS-", "STATION-", "CHARGER-", "VG_STA", "CSESS-"]) or any(k in combined for k in ["charging_network", "charging network", "charging_history", "vgreen", "charging station", "charger", "kwh_delivered", "power delivery"]):
            return DOMAIN_CHARGING_NETWORK

        if any(prefix in entity_str for prefix in ["VIN-", "VEHICLE-", "EV-", "BMS-"]) or any(k in combined for k in ["ev_telemetry", "ev telemetry", "battery_soc", "bms", "thermal_anomaly", "cell_voltage"]):
            return DOMAIN_EV_TELEMETRY

        # Secondary keyword matching
        if any(k in combined for k in ["trip", "ride", "hailing", "fare"]):
            return DOMAIN_RIDE_HAILING
        if any(k in combined for k in ["charging", "charger", "station", "station_temp"]):
            return DOMAIN_CHARGING_NETWORK
        if any(k in combined for k in ["feedback", "comment", "review"]):
            return DOMAIN_CUSTOMER_FEEDBACK

        return DOMAIN_EV_TELEMETRY

    def investigate_incident_dynamically(
        self, incident: Incident, initial_evidence: List[Evidence]
    ) -> Tuple[Hypothesis, Recommendation, Dict[str, Any]]:
        """
        Executes bounded dynamic tool iterations to produce an evidence-backed hypothesis.
        Applies domain-scoped tool allowlisting based on target entity domain, excluding domain-irrelevant tools upfront.
        Maintains competing hypothesis tracking, enforces operational bounds, and supports explicit abstention.
        """
        start_time = time.perf_counter()
        tokens_spent = 0
        tool_calls_made = 0
        hypothesis_revisions = 0
        tool_execution_trace: List[Dict[str, Any]] = []

        gathered_evidence: List[Evidence] = list(initial_evidence or [])
        gathered_evidence_ids: List[str] = [e.evidence_id for e in gathered_evidence if e.evidence_id]

        entity_id = incident.entity_ids[0] if incident.entity_ids else "unknown_entity"
        resolved_entity_scope: Set[str] = set(incident.entity_ids or [entity_id])
        resolved_time_scope: Dict[str, Any] = dict(incident.time_window or {})

        admission_text = (incident.admission_reason or "").lower()
        combined_summaries = " ".join([e.summary.lower() for e in gathered_evidence])

        data_keywords = ["null", "schema", "range", "contract", "l1", "casting", "type", "fare", "arithmetic", "negative", "violation"]
        op_keywords = ["soc", "battery", "temp", "thermal", "degradation", "voltage", "cell", "l2", "critical", "anomaly", "drift", "sensor"]

        has_contradictory_signal = (
            "contradict" in admission_text
            or "contradict" in combined_summaries
            or ("normal" in combined_summaries and ("crash" in admission_text or "defect" in admission_text or "critical" in admission_text))
            or (any(k in combined_summaries for k in op_keywords) and any(k in combined_summaries for k in data_keywords) and "conflict" in combined_summaries)
        )

        is_missing_initial = len(gathered_evidence) == 0 or any("missing" in e.summary.lower() for e in gathered_evidence)
        is_data_focused = any(k in admission_text or k in combined_summaries for k in data_keywords)

        # Detect target entity domain
        target_domain = self.detect_target_entity_domain(incident, initial_evidence)
        allowlist = self.domain_allowlists.get(target_domain, self.domain_allowlists[DOMAIN_EV_TELEMETRY])

        # Define candidate tool definitions
        candidate_tool_map = {
            "fetch_entity_telemetry": (
                "fetch_entity_telemetry",
                lambda: self.tools.fetch_entity_telemetry(entity_id=entity_id, metric="battery_soc"),
                {"entity_id": entity_id, "metric": "battery_soc"}
            ),
            "fetch_charging_history": (
                "fetch_charging_history",
                lambda: self.tools.fetch_charging_history(entity_id=entity_id),
                {"entity_id": entity_id}
            ),
            "fetch_trip_history": (
                "fetch_trip_history",
                lambda: self.tools.fetch_trip_history(entity_id=entity_id),
                {"entity_id": entity_id}
            ),
            "inspect_upstream_contracts": (
                "inspect_upstream_contracts",
                lambda: self.tools.inspect_upstream_contracts(dataset_key=entity_id),
                {"dataset_key": entity_id}
            ),
            "query_historical_baselines": (
                "query_historical_baselines",
                lambda: self.tools.query_historical_baselines(entity_id=entity_id),
                {"entity_id": entity_id}
            ),
            "fetch_dq_violations": (
                "fetch_dq_violations",
                lambda: self.tools.fetch_dq_violations(entity_id=entity_id),
                {"entity_id": entity_id}
            ),
            "fetch_profile": (
                "fetch_profile",
                lambda: self.tools.fetch_profile(entity_id=entity_id),
                {"entity_id": entity_id}
            ),
            "fetch_recent_changes": (
                "fetch_recent_changes",
                lambda: self.tools.fetch_recent_changes(entity_id=entity_id),
                {"entity_id": entity_id}
            ),
            "resolve_entity_relationships": (
                "resolve_entity_relationships",
                lambda: self.tools.resolve_entity_relationships(entity_id=entity_id),
                {"entity_id": entity_id}
            ),
            "calculate_detector_detail": (
                "calculate_detector_detail",
                lambda: self.tools.calculate_detector_detail(entity_id=entity_id, layer="L2"),
                {"entity_id": entity_id, "layer": "L2"}
            ),
        }

        # Build candidate priority order based on observation focus and domain
        if is_data_focused:
            candidate_order = [
                "inspect_upstream_contracts",
                "fetch_dq_violations",
                "query_historical_baselines",
                "fetch_profile",
                "fetch_recent_changes",
                "resolve_entity_relationships",
                "calculate_detector_detail",
                "fetch_entity_telemetry",
                "fetch_charging_history",
                "fetch_trip_history",
            ]
        else:
            if target_domain == DOMAIN_CHARGING_NETWORK:
                primary_op = "fetch_charging_history"
            elif target_domain == DOMAIN_RIDE_HAILING:
                primary_op = "fetch_trip_history"
            elif target_domain == DOMAIN_CUSTOMER_FEEDBACK:
                primary_op = "fetch_dq_violations"
            else:
                primary_op = "fetch_entity_telemetry"

            candidate_order = [
                primary_op,
                "query_historical_baselines",
                "inspect_upstream_contracts",
                "fetch_profile",
                "fetch_dq_violations",
                "fetch_recent_changes",
                "resolve_entity_relationships",
                "calculate_detector_detail",
                "fetch_charging_history",
                "fetch_trip_history",
                "fetch_entity_telemetry",
            ]

        # Deduplicate while preserving priority order
        seen_tools = set()
        deduped_candidates = []
        for tname in candidate_order:
            if tname not in seen_tools and tname in candidate_tool_map:
                seen_tools.add(tname)
                deduped_candidates.append(tname)

        # Apply domain-scoped allowlist upfront, excluding domain-irrelevant tools
        tool_plan = [
            candidate_tool_map[tname]
            for tname in deduped_candidates
            if tname in allowlist
        ]

        stop_reason = "completed"

        # Dynamic tool execution loop bounded by operational limits
        for tool_name, tool_fn, tool_args in tool_plan:
            elapsed = time.perf_counter() - start_time
            if tool_calls_made >= self.max_tool_calls:
                stop_reason = "max_tool_calls_exceeded"
                break
            if tokens_spent >= self.max_tokens_budget:
                stop_reason = "max_tokens_budget_exceeded"
                break
            if elapsed >= self.max_wall_clock_sec:
                stop_reason = "max_wall_clock_sec_exceeded"
                break
            if hypothesis_revisions >= self.max_hypothesis_revisions:
                stop_reason = "max_hypothesis_revisions_exceeded"
                break

            t0 = time.perf_counter()
            res: InvestigationToolResult = tool_fn()
            dur = time.perf_counter() - t0

            tool_calls_made += 1
            tokens_spent += res.tokens_used
            gathered_evidence_ids.append(res.evidence_ref)
            hypothesis_revisions += 1

            if res.entity_scope:
                resolved_entity_scope.update(res.entity_scope)
            if res.time_scope:
                resolved_time_scope.update(res.time_scope)

            tool_execution_trace.append({
                "tool_name": res.tool_name,
                "args": tool_args,
                "success": res.success,
                "evidence_ref": res.evidence_ref,
                "tokens_used": res.tokens_used,
                "wall_clock_sec": round(dur, 6),
                "data": res.data
            })

            tool_ev = Evidence(
                evidence_id=res.evidence_ref,
                source_type="tool_output",
                source_id=res.tool_name,
                entity_ids=[entity_id],
                content_hash=f"hash-{res.evidence_ref}",
                summary=f"Tool {res.tool_name} returned data: {res.data}"
            )
            gathered_evidence.append(tool_ev)

        wall_clock_elapsed = round(time.perf_counter() - start_time, 6)

        # Competing hypothesis evaluation: support vs contradiction tracking
        op_supporting: List[str] = []
        op_contradicting: List[str] = []
        data_supporting: List[str] = []
        data_contradicting: List[str] = []
        missing_evidence: List[str] = []

        for ev in gathered_evidence:
            eid = ev.evidence_id
            summ = (ev.summary or "").lower()

            is_op_ev = (
                any(k in summ for k in op_keywords)
                or "ev-telemetry" in eid
                or "ev-baseline" in eid
                or "bms" in eid
                or "charging" in summ
                or "trip" in summ
            )
            is_data_ev = (
                any(k in summ for k in data_keywords)
                or "ev-contract" in eid
                or "range_violation" in summ
                or "null_violation" in summ
                or "ev-dq" in eid
            )

            if is_op_ev and not is_data_ev:
                op_supporting.append(eid)
                if "contract" in summ or "normal" in summ:
                    op_contradicting.append(eid)
            elif is_data_ev and not is_op_ev:
                data_supporting.append(eid)
                if "telemetry" in summ and "normal" in summ:
                    data_contradicting.append(eid)
            elif is_op_ev and is_data_ev:
                op_supporting.append(eid)
                data_supporting.append(eid)
            else:
                if is_data_focused:
                    data_supporting.append(eid)
                else:
                    op_supporting.append(eid)

        if has_contradictory_signal:
            op_contradicting.extend(gathered_evidence_ids)
            data_contradicting.extend(gathered_evidence_ids)

        if not gathered_evidence or (len(gathered_evidence) == 1 and "missing" in gathered_evidence[0].summary.lower()):
            missing_evidence.append("telemetry_logs")
            missing_evidence.append("baseline_metrics")

        # Evaluate explicit abstention criteria
        if is_missing_initial and tool_calls_made == 0:
            should_abstain = True
            abstention_reason = "Missing critical initial evidence and tool execution budget exhausted."
        elif has_contradictory_signal:
            should_abstain = True
            abstention_reason = "Contradictory evidence detected across telemetry and pipeline logs."
        elif not op_supporting and not data_supporting:
            should_abstain = True
            abstention_reason = "Lack of supporting evidence for operational or data root cause."
        else:
            should_abstain = False
            abstention_reason = ""

        if should_abstain:
            hyp = Hypothesis(
                incident_id=incident.incident_id,
                claim=f"Dynamic A1 abstained: {abstention_reason}",
                classification="UNKNOWN",
                supporting_evidence=list(dict.fromkeys(op_supporting + data_supporting)),
                contradicting_evidence=list(dict.fromkeys(op_contradicting + data_contradicting)),
                missing_evidence=missing_evidence or ["diagnostic_telemetry"],
                confidence=0.0,
                status="PROPOSED"
            )
        else:
            if is_data_focused or (len(data_supporting) > len(op_supporting) and len(data_contradicting) == 0):
                classification = "DATA"
                claim = f"Dynamic A1 verified data contract violation in entity {entity_id}."
                conf = 0.88 if len(data_supporting) >= 1 else 0.70
                sup = list(dict.fromkeys(data_supporting or gathered_evidence_ids))
                con = list(dict.fromkeys(data_contradicting))
            else:
                classification = "OPERATIONAL"
                claim = f"Dynamic A1 verified operational defect in entity {entity_id} via multi-tool evidence."
                conf = 0.92 if len(op_supporting) >= 2 else 0.85
                sup = list(dict.fromkeys(op_supporting or gathered_evidence_ids))
                con = list(dict.fromkeys(op_contradicting))

            hyp = Hypothesis(
                incident_id=incident.incident_id,
                claim=claim,
                classification=classification,
                supporting_evidence=sup,
                contradicting_evidence=con,
                missing_evidence=missing_evidence,
                confidence=conf,
                status="PROPOSED"
            )

        rec = self.router.route_hypothesis(incident.incident_id, hyp)

        execution_meta = {
            "tokens_spent": tokens_spent,
            "tool_calls_made": tool_calls_made,
            "tool_execution_trace": tool_execution_trace,
            "hypothesis_revisions": hypothesis_revisions,
            "budget_remaining": self.max_tokens_budget - tokens_spent,
            "target_domain": target_domain,
            "domain_allowlist": sorted(list(allowlist)),
            "resolved_entity_scope": sorted(list(resolved_entity_scope)),
            "resolved_time_scope": resolved_time_scope,
            "bounded_stop": True,
            "wall_clock_elapsed_sec": wall_clock_elapsed,
            "stop_reason": stop_reason
        }

        return hyp, rec, execution_meta




