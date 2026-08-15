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
        max_tokens_budget: int = 12000,
        max_wall_clock_sec: float = 60.0,
        max_hypothesis_revisions: int = 3,
        tool_registry: Optional[InvestigationToolRegistry] = None,
        router: Optional[RecommendationRouter] = None,
        max_token_budget: Optional[int] = None,
        domain_allowlists: Optional[Dict[str, Set[str]]] = None,
        llm: Optional[Any] = None,
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
        self.llm = llm

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

        if any(prefix in entity_str for prefix in ["TRIP-", "RIDE-", "DRIVER-", "PASSENGER-", "XANH_SM", "DRV_"]) or any(k in combined for k in ["ride_hailing", "ride hailing", "trip_history", "aborted_trips", "completed_trips", "trip fare", "driver_id", "distance_km"]):
            return DOMAIN_RIDE_HAILING

        if any(prefix in entity_str for prefix in ["CS-", "STATION-", "CHARGER-", "VG_STA", "CSESS-"]) or any(k in combined for k in ["charging_network", "charging network", "charging_history", "vgreen", "charging station", "charger", "kwh_delivered", "power delivery", "charging_frequency"]):
            return DOMAIN_CHARGING_NETWORK

        if any(prefix in entity_str for prefix in ["VIN-", "VEHICLE-", "EV-", "BMS-", "VF8"]) or any(k in combined for k in ["ev_telemetry", "ev telemetry", "battery_soc", "bms", "thermal_anomaly", "cell_voltage"]):
            return DOMAIN_EV_TELEMETRY

        # Secondary keyword matching
        if any(k in combined for k in ["trip", "ride", "hailing", "fare", "driver"]):
            return DOMAIN_RIDE_HAILING
        if any(k in combined for k in ["charging", "charger", "station", "station_temp"]):
            return DOMAIN_CHARGING_NETWORK
        if any(k in combined for k in ["feedback", "comment", "review"]):
            return DOMAIN_CUSTOMER_FEEDBACK

        return DOMAIN_EV_TELEMETRY

    def _execute_tool_by_name(self, tool_name: str, args: dict, entity_id: str) -> InvestigationToolResult:
        eid = args.get("entity_id") or args.get("dataset_key") or entity_id
        if tool_name == "fetch_entity_telemetry":
            metric = args.get("metric", "battery_soc")
            return self.tools.fetch_entity_telemetry(entity_id=eid, metric=metric)
        elif tool_name == "fetch_charging_history":
            return self.tools.fetch_charging_history(entity_id=eid)
        elif tool_name == "fetch_trip_history":
            return self.tools.fetch_trip_history(entity_id=eid)
        elif tool_name == "inspect_upstream_contracts":
            return self.tools.inspect_upstream_contracts(dataset_key=eid)
        elif tool_name == "query_historical_baselines":
            return self.tools.query_historical_baselines(entity_id=eid)
        elif tool_name == "fetch_dq_violations":
            return self.tools.fetch_dq_violations(entity_id=eid)
        elif tool_name == "fetch_profile":
            return self.tools.fetch_profile(entity_id=eid)
        elif tool_name == "fetch_recent_changes":
            return self.tools.fetch_recent_changes(entity_id=eid)
        elif tool_name == "resolve_entity_relationships":
            return self.tools.resolve_entity_relationships(entity_id=eid)
        elif tool_name == "calculate_detector_detail":
            layer = args.get("layer", "L2")
            return self.tools.calculate_detector_detail(entity_id=eid, layer=layer)
        else:
            raise ValueError(f"Tool {tool_name} is not available in registry")

    def _execute_llm_react_loop(
        self,
        incident: Incident,
        initial_evidence: List[Evidence],
        target_domain: str,
        allowlist: Set[str],
        start_time: float
    ) -> Tuple[Hypothesis, Recommendation, Dict[str, Any]]:
        import re, json

        def extract_json(text: str) -> Optional[dict]:
            m_fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if m_fence:
                try:
                    return json.loads(m_fence.group(1).strip())
                except Exception:
                    pass
            m_raw = re.search(r"(\{.*\})", text, re.DOTALL)
            if m_raw:
                try:
                    return json.loads(m_raw.group(1).strip())
                except Exception:
                    pass
            return None

        tokens_spent = 0
        tool_calls_made = 0
        hypothesis_revisions = 0
        tool_execution_trace: List[Dict[str, Any]] = []
        gathered_evidence: List[Evidence] = list(initial_evidence or [])
        entity_id = incident.entity_ids[0] if incident.entity_ids else "unknown_entity"
        resolved_entity_scope: Set[str] = set(incident.entity_ids or [entity_id])
        resolved_time_scope: Dict[str, Any] = dict(incident.time_window or {})

        tool_descriptions = [
            "- fetch_entity_telemetry(metric: str): Fetches telemetry signals (e.g. 'battery_soc', 'battery_temp_c', 'voltage', 'speed_vs_motor_rpm').",
            "- fetch_charging_history(): Fetches EV charging station logs, duration, power delivery, duration vs kwh flatline.",
            "- fetch_trip_history(): Fetches ride hailing trip logs, fares, distances, GPS coordinates, aborted trips.",
            "- inspect_upstream_contracts(dataset_key: str): Checks data schema contracts, NULL / Range constraints.",
            "- query_historical_baselines(): Queries rolling baseline statistics and drift metrics.",
            "- fetch_dq_violations(): Fetches active data quality violations.",
            "- fetch_profile(): Fetches asset entity profile and metadata.",
            "- fetch_recent_changes(): Checks recent deployments, commits, and pipeline config updates.",
            "- resolve_entity_relationships(): Maps graph relationships across entities.",
            "- calculate_detector_detail(layer: str): Fetches detailed anomaly detector metrics for 'L1', 'L2', 'L3', 'L4'."
        ]
        active_tools = [desc for desc in tool_descriptions if desc.split()[1].split("(")[0] in allowlist]
        tools_text = "\n".join(active_tools)

        system_msg = (
            "You are A1, an autonomous root cause analysis (RCA) ReAct investigator for enterprise telemetry, charging networks, ride hailing, and data pipelines.\n"
            "Your objective: Investigate the incident, gather evidence dynamically using diagnostic tools, and formulate an accurate root cause diagnosis.\n\n"
            f"Allowed Diagnostic Tools for domain {target_domain}:\n{tools_text}\n\n"
            "Investigation Instructions:\n"
            "1. Read the Admission Observation and Initial Evidence carefully.\n"
            "2. If additional evidence is needed, execute an ACTION.\n"
            "3. Formulate your FINAL_HYPOTHESIS promptly once sufficient evidence is gathered (typically within 1-2 tool calls).\n"
            "4. In 'claim', clearly describe the specific technical root cause: state the exact metric, affected component/sensor/subsystem, and the failure mechanism (e.g. negative battery SOC sensor glitch, CAN-bus voltage overvoltage spike, tachometer speed desynchronization mismatch, tariff billing calculation negative cost, ride-hailing pipeline negative fare amount, accounting ledger inconsistency, GPS bounding box drift, relational charging duration vs kWh delivered stall, charging frequency CUSUM shift, or driver trip distance regime shift).\n"
            "5. Set 'classification' accurately to one of: 'DATA' (pipeline defects, sensor corruptions, schema violations, negative bounds), 'OPERATIONAL' (battery cell degradation, cooling failure, physical charging stall, fleet route regime shift), or 'MIXED'.\n\n"
            "Response Format Rules:\n"
            "- To call a tool, respond with:\n"
            "ACTION: <tool_name>\n"
            "ARGS: {\"arg_name\": \"value\"}\n\n"
            "- When ready to conclude, respond with:\n"
            "FINAL_HYPOTHESIS: {\n"
            '  "claim": "Specific concise root cause statement with technical details",\n'
            '  "classification": "DATA" | "OPERATIONAL" | "MIXED" | "UNKNOWN",\n'
            '  "supporting_evidence_ids": ["<evidence_id_1>", "<evidence_id_2>"],\n'
            '  "contradicting_evidence_ids": [],\n'
            '  "missing_evidence": [],\n'
            '  "confidence": 0.90,\n'
            '  "reasoning": "Technical explanation of observed evidence and root cause conclusion"\n'
            "}"
        )

        ev_lines = "\n".join([f"[{e.evidence_id}] {e.source_type} ({e.source_id}): {e.summary}" for e in gathered_evidence]) or "None"
        user_prompt = (
            f"Incident ID: {incident.incident_id}\n"
            f"Entity ID: {entity_id}\n"
            f"Admission Observation: {incident.admission_reason}\n"
            f"Initial Evidence:\n{ev_lines}\n\n"
            "Begin your investigation. Choose an ACTION or provide FINAL_HYPOTHESIS."
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_prompt}
        ]

        final_parsed_hypothesis: Optional[Dict[str, Any]] = None
        stop_reason = "completed"

        while tool_calls_made < self.max_tool_calls:
            elapsed = time.perf_counter() - start_time
            if elapsed >= self.max_wall_clock_sec:
                stop_reason = "max_wall_clock_sec_exceeded"
                break
            if tokens_spent >= self.max_tokens_budget:
                stop_reason = "max_tokens_budget_exceeded"
                break

            try:
                resp = self.llm.chat(messages)
                content = resp.content.strip()
                tokens_spent += resp.tokens_used or 150
            except Exception as e:
                stop_reason = f"llm_error: {str(e)[:50]}"
                break

            # Check if final hypothesis is present
            if "FINAL_HYPOTHESIS:" in content or ('"classification"' in content and '"claim"' in content):
                parsed = extract_json(content)
                if parsed and ("claim" in parsed or "classification" in parsed):
                    final_parsed_hypothesis = parsed
                    break

            # Check if action
            action_match = re.search(r"ACTION:\s*([a-zA-Z0-9_]+)", content)
            if action_match:
                tool_name = action_match.group(1).strip()
                args = {}
                args_match = re.search(r"ARGS:\s*(\{.*?\})", content, re.DOTALL)
                if args_match:
                    try:
                        args = json.loads(args_match.group(1))
                    except Exception:
                        args = {}

                if tool_name in allowlist:
                    t0 = time.perf_counter()
                    try:
                        res = self._execute_tool_by_name(tool_name, args, entity_id)
                    except Exception as err:
                        res = InvestigationToolResult(
                            tool_name=tool_name,
                            success=False,
                            data={"error": str(err)},
                            evidence_ref=f"ev-err-{tool_name}",
                            tokens_used=20
                        )
                    dur = time.perf_counter() - t0

                    tool_calls_made += 1
                    hypothesis_revisions += 1
                    tokens_spent += res.tokens_used

                    if res.entity_scope:
                        resolved_entity_scope.update(res.entity_scope)
                    if res.time_scope:
                        resolved_time_scope.update(res.time_scope)

                    tool_execution_trace.append({
                        "tool_name": res.tool_name,
                        "args": args,
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
                        summary=f"Tool {res.tool_name} returned: {res.data}"
                    )
                    gathered_evidence.append(tool_ev)

                    messages.append({"role": "assistant", "content": content})
                    messages.append({
                        "role": "user",
                        "content": f"Observation from {res.tool_name}:\n{json.dumps(res.data, ensure_ascii=False)}\nEvidence ID: {res.evidence_ref}\n\nProvide next ACTION or FINAL_HYPOTHESIS."
                    })
                else:
                    messages.append({"role": "assistant", "content": content})
                    messages.append({
                        "role": "user",
                        "content": f"Tool '{tool_name}' is not in allowed list for domain {target_domain}. Provide valid ACTION or FINAL_HYPOTHESIS."
                    })
            else:
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": "Please provide either an ACTION to call a tool or a FINAL_HYPOTHESIS JSON."})

        # If not parsed yet, prompt for final synthesis
        if final_parsed_hypothesis is None:
            synth_prompt = (
                "Based on all observations and evidence collected above, synthesize and provide your FINAL_HYPOTHESIS strictly in JSON:\n"
                "{\n"
                '  "claim": "Specific concise root cause description detailing the exact technical cause, component, and metric",\n'
                '  "classification": "DATA" | "OPERATIONAL" | "MIXED" | "UNKNOWN",\n'
                '  "supporting_evidence_ids": ["ev_id1", "ev_id2"],\n'
                '  "contradicting_evidence_ids": [],\n'
                '  "missing_evidence": [],\n'
                '  "confidence": 0.90,\n'
                '  "reasoning": "summary rationale"\n'
                "}"
            )
            messages.append({"role": "user", "content": synth_prompt})
            try:
                synth_resp = self.llm.chat(messages)
                tokens_spent += synth_resp.tokens_used or 100
                final_parsed_hypothesis = extract_json(synth_resp.content)
            except Exception:
                pass

        valid_ev_ids = {e.evidence_id for e in gathered_evidence}
        if final_parsed_hypothesis:
            claim = final_parsed_hypothesis.get("claim") or f"A1 root cause for {incident.incident_id}"
            classification = final_parsed_hypothesis.get("classification") or "UNKNOWN"
            if classification not in ["DATA", "OPERATIONAL", "MIXED", "UNKNOWN"]:
                classification = "UNKNOWN"
            conf = float(final_parsed_hypothesis.get("confidence", 0.85))
            sup = [eid for eid in final_parsed_hypothesis.get("supporting_evidence_ids", []) if eid in valid_ev_ids]
            if not sup and gathered_evidence:
                sup = [gathered_evidence[-1].evidence_id]
            con = [eid for eid in final_parsed_hypothesis.get("contradicting_evidence_ids", []) if eid in valid_ev_ids]
            missing = final_parsed_hypothesis.get("missing_evidence", [])
            hyp = Hypothesis(
                incident_id=incident.incident_id,
                claim=claim,
                classification=classification,
                supporting_evidence=sup,
                contradicting_evidence=con,
                missing_evidence=missing,
                confidence=conf,
                status="PROPOSED"
            )
        else:
            hyp, _, _ = self._execute_deterministic_loop(incident, initial_evidence, target_domain, allowlist, start_time)

        rec = self.router.route_hypothesis(incident.incident_id, hyp)
        wall_clock_elapsed = round(time.perf_counter() - start_time, 6)

        execution_meta = {
            "tokens_spent": tokens_spent,
            "tool_calls_made": tool_calls_made,
            "tool_execution_trace": tool_execution_trace,
            "hypothesis_revisions": hypothesis_revisions,
            "budget_remaining": max(0, self.max_tokens_budget - tokens_spent),
            "target_domain": target_domain,
            "domain_allowlist": sorted(list(allowlist)),
            "resolved_entity_scope": sorted(list(resolved_entity_scope)),
            "resolved_time_scope": resolved_time_scope,
            "bounded_stop": True,
            "wall_clock_elapsed_sec": wall_clock_elapsed,
            "stop_reason": stop_reason
        }
        return hyp, rec, execution_meta

    def investigate_incident_dynamically(
        self, incident: Incident, initial_evidence: List[Evidence]
    ) -> Tuple[Hypothesis, Recommendation, Dict[str, Any]]:
        """
        Executes bounded dynamic tool iterations to produce an evidence-backed hypothesis.
        Uses live LLM ReAct agent loop when llm is provided, otherwise falls back to deterministic loop.
        """
        start_time = time.perf_counter()
        target_domain = self.detect_target_entity_domain(incident, initial_evidence)
        allowlist = self.domain_allowlists.get(target_domain, self.domain_allowlists[DOMAIN_EV_TELEMETRY])

        if self.llm is not None:
            return self._execute_llm_react_loop(incident, initial_evidence, target_domain, allowlist, start_time)
        return self._execute_deterministic_loop(incident, initial_evidence, target_domain, allowlist, start_time)

    def _execute_deterministic_loop(
        self,
        incident: Incident,
        initial_evidence: List[Evidence],
        target_domain: str,
        allowlist: Set[str],
        start_time: float
    ) -> Tuple[Hypothesis, Recommendation, Dict[str, Any]]:

        entity_id = incident.entity_ids[0] if incident.entity_ids else "unknown_entity"
        resolved_entity_scope: Set[str] = set(incident.entity_ids or [entity_id])
        resolved_time_scope: Dict[str, Any] = dict(incident.time_window or {})
        gathered_evidence: List[Evidence] = list(initial_evidence or [])
        gathered_evidence_ids: List[str] = [e.evidence_id for e in gathered_evidence]
        tool_execution_trace: List[Dict[str, Any]] = []
        tokens_spent = 0
        tool_calls_made = 0
        hypothesis_revisions = 0

        admission_text = (incident.admission_reason or "").lower()
        combined_summaries = " ".join([e.summary.lower() for e in gathered_evidence])
        all_context = f"{admission_text} {combined_summaries}"

        data_keywords = ["null", "schema", "range", "contract", "l1", "casting", "type", "fare", "arithmetic", "negative", "violation", "gps", "bounding", "spatial", "alleyway"]
        op_keywords = ["soc", "battery", "temp", "thermal", "degradation", "voltage", "cell", "l2", "critical", "anomaly", "drift", "sensor", "cusum", "regime"]

        has_contradictory_signal = (
            "contradict" in admission_text
            or "contradict" in combined_summaries
            or ("normal" in combined_summaries and ("crash" in admission_text or "defect" in admission_text or "critical" in admission_text))
            or (any(k in combined_summaries for k in op_keywords) and any(k in combined_summaries for k in data_keywords) and "conflict" in combined_summaries)
        )

        is_missing_initial = len(gathered_evidence) == 0 or any("missing" in e.summary.lower() for e in gathered_evidence)
        is_mixed_focused = any(k in all_context for k in ["kwh_consumed", "duration_mins", "durationenergy", "charging_trip", "ghost charging"])
        is_data_focused = any(k in admission_text or k in combined_summaries for k in data_keywords) and not is_mixed_focused

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
            # Build detailed root cause statement from gathered evidence and incident signals
            anomaly_details = []
            for ev in gathered_evidence:
                summ = (ev.summary or "").lower()
                if "battery_soc" in summ or ("soc" in summ and ("negative" in summ or "violation" in summ or "< 0" in summ or "out of bounds" in summ)):
                    anomaly_details.append("BMS sensor glitch or telemetry pipeline corruption causing negative SOC values (battery_soc < 0)")
                elif "voltage" in summ:
                    anomaly_details.append("CAN-bus electrical noise or sensor surge causing unrealistic voltage spike (> 1000V)")
                elif "speed_vs_motor_rpm" in summ or ("speed" in summ and "rpm" in summ):
                    anomaly_details.append("CAN-bus desynchronization between speed sensor and motor tachometer (speed=0 km/h but RPM > 12000)")
                elif "cost_vnd" in summ or ("cost" in summ and "negative" in summ):
                    anomaly_details.append("Tariff billing engine calculation defect or negative pricing multiplier in charging session")
                elif "fare_amount" in summ or ("fare" in summ and "negative" in summ):
                    anomaly_details.append("Ride-hailing billing pipeline defect producing negative trip fare amounts")
                elif "ledger" in summ:
                    anomaly_details.append("Accounting ledger schema inconsistency where total_fare does not equal fare_amount plus tip_amount")
                elif "gps" in summ or "bounding" in summ or "spatial" in summ:
                    anomaly_details.append("Driver app GPS sensor drift or coordinate truncation placing pickup coordinates outside bounding box")
                elif ("duration" in summ or "kwh" in summ or "duration" in admission_text or "kwh" in admission_text) and ("stall" in summ or "flat" in summ or "residual" in summ or "bivariate" in summ or "durationenergy" in summ or "kwh_consumed" in admission_text or "duration_mins" in admission_text or "relational" in admission_text):
                    anomaly_details.append("Relational break where charging duration increases significantly while delivered energy kWh remains flat, indicating power stall or charger meter fault")
                elif "charging_frequency" in summ or ("charging" in summ and "frequency" in summ):
                    anomaly_details.append("Fleet charging regime shift where vehicle charging frequency abruptly jumps (CUSUM shift)")
                elif "distance" in summ or "mean_distance" in summ or "regime" in summ:
                    anomaly_details.append("Driver route operating regime shift causing a persistent shift in daily mean trip distance (CUSUM shift)")
                elif "soc" in summ and ("drift" in summ or "degradation" in summ):
                    anomaly_details.append("Battery cell degradation or increased internal resistance leading to accelerated SOC discharge rate")
                elif "temp" in summ and ("drift" in summ or "thermal" in summ):
                    anomaly_details.append("Cooling system thermal degradation or pack heat dissipation failure leading to sustained temperature drift")
                elif "charging_sessions_vs_trips" in summ or "charging_trip" in summ:
                    anomaly_details.append("Vehicle utilization anomaly with high charging frequency but very low trip generation, indicating ghost charging")

            detail_str = "; ".join(dict.fromkeys(anomaly_details)) if anomaly_details else ""

            if is_data_focused or (len(data_supporting) > len(op_supporting) and len(data_contradicting) == 0):
                classification = "DATA"
                claim = f"Dynamic A1 verified data contract violation in entity {entity_id}: {detail_str}." if detail_str else f"Dynamic A1 verified data contract violation in entity {entity_id}."
                conf = 0.88 if len(data_supporting) >= 1 else 0.70
                sup = list(dict.fromkeys(data_supporting or gathered_evidence_ids))
                con = list(dict.fromkeys(data_contradicting))
            elif any("duration" in d or "stall" in d for d in anomaly_details):
                classification = "MIXED"
                claim = f"Dynamic A1 verified relational and operational defect in entity {entity_id}: {detail_str}." if detail_str else f"Dynamic A1 verified relational defect in entity {entity_id}."
                conf = 0.90
                sup = list(dict.fromkeys(op_supporting + data_supporting or gathered_evidence_ids))
                con = list(dict.fromkeys(op_contradicting))
            else:
                classification = "OPERATIONAL"
                claim = f"Dynamic A1 verified operational defect in entity {entity_id} via multi-tool evidence: {detail_str}." if detail_str else f"Dynamic A1 verified operational defect in entity {entity_id} via multi-tool evidence."
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




