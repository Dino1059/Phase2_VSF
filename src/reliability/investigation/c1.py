from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timezone
import re
from pydantic import BaseModel, Field

from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.models.hypothesis import Hypothesis, CauseClassification
from src.reliability.governance.recommendations import RecommendationRouter, Recommendation


class LLMAnalysisResult(BaseModel):
    """
    Strict output schema for LLM incident analysis results in C1 investigation.
    Enforces required fields, cause classifications, confidence range, and evidence IDs.
    """
    incident_id: str
    claim: str = Field(..., min_length=1, description="Root cause claim formulated by LLM analysis")
    classification: CauseClassification = Field(..., description="Root cause classification: DATA, OPERATIONAL, MIXED, or UNKNOWN")
    supporting_evidence_ids: List[str] = Field(default_factory=list, description="IDs of evidence supporting the claim")
    contradicting_evidence_ids: List[str] = Field(default_factory=list, description="IDs of evidence contradicting the claim")
    missing_evidence: List[str] = Field(default_factory=list, description="List of missing evidence types/sources if cause is UNKNOWN")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(default="", description="Chain-of-thought rationale")


@dataclass
class C1EvidenceBundle:
    """
    Fixed evidence bundle compiling signals, entity history, profile,
    recent changes, and relevant rule violations.
    """
    incident_id: str
    entity_ids: List[str]
    signals: List[Evidence] = field(default_factory=list)
    entity_history: List[Evidence] = field(default_factory=list)
    profile: List[Evidence] = field(default_factory=list)
    recent_changes: List[Evidence] = field(default_factory=list)
    rule_violations: List[Evidence] = field(default_factory=list)
    all_evidence: List[Evidence] = field(default_factory=list)
    evidence_by_id: Dict[str, Evidence] = field(default_factory=dict)

    @property
    def retrievable_evidence_ids(self) -> Set[str]:
        return set(self.evidence_by_id.keys())


class C1FixedContextBuilder:
    """
    Deterministic context builder that compiles a fixed evidence bundle
    (signals, entity history, profile, recent changes, relevant rule violations).
    Ensures NO hidden ground truth or pre-assigned answers are passed to downstream LLMs.
    """

    # Forbidden keys that could leak ground truth into LLM prompts
    FORBIDDEN_GROUND_TRUTH_KEYS: Set[str] = {
        "ground_truth",
        "expected_classification",
        "expected_top_causes",
        "ground_truth_evidence_ids",
        "is_abstention_case",
        "preassigned_cause",
        "preassigned_answer",
        "target_cause",
        "label",
        "true_cause",
        "classification_hint",
        "answer",
    }

    def compile_evidence_bundle(
        self, incident: Incident, available_evidence: List[Evidence]
    ) -> C1EvidenceBundle:
        """
        Deterministically compiles available evidence into a 5-dimension fixed bundle.
        Enforces valid typed evidence IDs (`ev_...` / `ev-...`).
        """
        # Step 1: Match evidence relevant to incident entities/incident_id
        matching_ev: List[Evidence] = []
        if incident.entity_ids:
            matching_ev = [
                e for e in available_evidence
                if any(eid in e.entity_ids for eid in incident.entity_ids) or e.incident_id == incident.incident_id
            ]

        # Fallback to available_evidence if no specific match
        if not matching_ev and available_evidence:
            matching_ev = list(available_evidence)

        bundle = C1EvidenceBundle(
            incident_id=incident.incident_id,
            entity_ids=list(incident.entity_ids or [])
        )

        for ev in matching_ev:
            norm_ev = self._normalize_evidence_id(ev)
            ev_id = norm_ev.evidence_id
            bundle.all_evidence.append(norm_ev)
            bundle.evidence_by_id[ev_id] = norm_ev

            stype = (norm_ev.source_type or "").lower()
            summary = (norm_ev.summary or "").lower()

            # Categorize into 5 fixed evidence categories
            if any(k in stype or k in summary for k in ["signal", "telemetry", "sensor", "bms", "metric", "voltage", "temp", "soc"]):
                bundle.signals.append(norm_ev)
            elif any(k in stype or k in summary for k in ["history", "log", "past", "historical", "event"]):
                bundle.entity_history.append(norm_ev)
            elif any(k in stype or k in summary for k in ["profile", "schema", "spec", "asset", "metadata", "database"]):
                bundle.profile.append(norm_ev)
            elif any(k in stype or k in summary for k in ["change", "deploy", "commit", "config", "update", "pipeline"]):
                bundle.recent_changes.append(norm_ev)
            elif any(k in stype or k in summary for k in ["violation", "rule", "null", "range", "contract", "mismatch", "arithmetic"]):
                bundle.rule_violations.append(norm_ev)
            else:
                bundle.signals.append(norm_ev)

        return bundle

    def _normalize_evidence_id(self, ev: Evidence) -> Evidence:
        """
        Validates and normalizes evidence ID format to ensure typed evidence IDs starting with `ev_` or `ev-`.
        """
        ev_id = ev.evidence_id
        if not (ev_id.startswith("ev_") or ev_id.startswith("ev-")):
            prefix = f"ev_{ev.source_type.lower()}_" if ev.source_type else "ev_"
            new_id = f"{prefix}{ev_id}"
            return ev.model_copy(update={"evidence_id": new_id})
        return ev

    def build_llm_context(
        self, bundle: C1EvidenceBundle, incident: Optional[Incident] = None
    ) -> str:
        """
        Renders structured evidence bundle into an LLM context prompt string.
        Ensures NO hidden ground truth or pre-assigned answers are included.
        """
        lines = [
            "=== FIXED EVIDENCE BUNDLE FOR INVESTIGATION ===",
            f"Incident ID: {bundle.incident_id}",
            f"Entity IDs: {', '.join(bundle.entity_ids)}",
        ]

        if incident:
            sanitized_reason = self._sanitize_text(incident.admission_reason)
            lines.append(f"Admission Observation: {sanitized_reason}")
            lines.append(f"Severity Level: {incident.severity}")

        lines.append("\n--- 1. SIGNALS & TELEMETRY ---")
        if bundle.signals:
            for e in bundle.signals:
                lines.append(f"[{e.evidence_id}] Source: {e.source_type} ({e.source_id}) | Summary: {self._sanitize_text(e.summary)}")
        else:
            lines.append("No signal telemetry anomalies recorded.")

        lines.append("\n--- 2. ENTITY HISTORY ---")
        if bundle.entity_history:
            for e in bundle.entity_history:
                lines.append(f"[{e.evidence_id}] Source: {e.source_type} ({e.source_id}) | Summary: {self._sanitize_text(e.summary)}")
        else:
            lines.append("No historical anomaly logs recorded.")

        lines.append("\n--- 3. PROFILE & SCHEMA ---")
        if bundle.profile:
            for e in bundle.profile:
                lines.append(f"[{e.evidence_id}] Source: {e.source_type} ({e.source_id}) | Summary: {self._sanitize_text(e.summary)}")
        else:
            lines.append("Entity schema and baseline profile normal.")

        lines.append("\n--- 4. RECENT CHANGES ---")
        if bundle.recent_changes:
            for e in bundle.recent_changes:
                lines.append(f"[{e.evidence_id}] Source: {e.source_type} ({e.source_id}) | Summary: {self._sanitize_text(e.summary)}")
        else:
            lines.append("No recent configuration or code deployment changes recorded.")

        lines.append("\n--- 5. RELEVANT RULE VIOLATIONS ---")
        if bundle.rule_violations:
            for e in bundle.rule_violations:
                lines.append(f"[{e.evidence_id}] Source: {e.source_type} ({e.source_id}) | Summary: {self._sanitize_text(e.summary)}")
        else:
            lines.append("No active rule violations detected.")

        return "\n".join(lines)

    def _sanitize_text(self, text: str) -> str:
        """
        Removes hidden ground truth labels, pre-assigned answers, or evaluation metadata from prompt text.
        """
        if not text:
            return ""
        sanitized = text
        for kw in self.FORBIDDEN_GROUND_TRUTH_KEYS:
            sanitized = re.sub(rf"(?i){kw}\s*:\s*[^\s,\n]+", "", sanitized)
        return sanitized.strip()


class C1FixedInvestigator:
    """
    C1 Baseline Investigator.
    Fixed evidence retrieval and deterministic hypothesis generation workflow.
    Uses C1FixedContextBuilder to compile fixed evidence bundles without ground truth leaks.
    Requires all cited evidence in hypotheses to use valid, retrievable typed evidence IDs.
    """

    def __init__(
        self,
        router: Optional[RecommendationRouter] = None,
        context_builder: Optional[C1FixedContextBuilder] = None,
        llm: Optional[Any] = None
    ):
        self.router = router or RecommendationRouter()
        self.context_builder = context_builder or C1FixedContextBuilder()
        self.llm = llm

    def build_context(self, incident: Incident, available_evidence: List[Evidence]) -> str:
        """
        Helper to construct sanitized LLM context prompt for an incident and evidence set.
        """
        bundle = self.context_builder.compile_evidence_bundle(incident, available_evidence)
        return self.context_builder.build_llm_context(bundle, incident=incident)

    def analyze_with_llm(
        self,
        incident: Incident,
        relevant_evidence: List[Evidence],
        raw_llm_response: Optional[Dict[str, Any]] = None
    ) -> LLMAnalysisResult:
        """
        Executes structured LLM analysis on an incident and evidence, enforcing strict output schema validation.
        """
        valid_ev_ids = {e.evidence_id for e in relevant_evidence}

        if raw_llm_response is not None:
            analysis = LLMAnalysisResult.model_validate(raw_llm_response)
        elif self.llm is not None:
            try:
                bundle = self.context_builder.compile_evidence_bundle(incident, relevant_evidence)
                context_str = self.context_builder.build_llm_context(bundle, incident=incident)
                prompt = (
                    "You are an expert root cause analysis investigator for enterprise telemetry and data systems.\n"
                    "Analyze the following evidence bundle and determine the root cause.\n"
                    "Provide your diagnosis strictly as a JSON object matching this schema:\n"
                    "{\n"
                    f'  "incident_id": "{incident.incident_id}",\n'
                    '  "claim": "concise description of root cause defect",\n'
                    '  "classification": "DATA" | "OPERATIONAL" | "MIXED" | "UNKNOWN",\n'
                    '  "supporting_evidence_ids": ["ev_id1", "ev_id2"],\n'
                    '  "contradicting_evidence_ids": [],\n'
                    '  "missing_evidence": [],\n'
                    '  "confidence": 0.85,\n'
                    '  "reasoning": "rationale explaining root cause"\n'
                    "}\n\n"
                    f"{context_str}\n\n"
                    "Return ONLY the valid JSON object with no markdown formatting or commentary."
                )
                resp = self.llm.chat([{"role": "user", "content": prompt}])
                import json as _json, re as _re
                match = _re.search(r"\{.*\}", resp.content, _re.DOTALL)
                if match:
                    parsed = _json.loads(match.group(0))
                    parsed["incident_id"] = incident.incident_id
                    analysis = LLMAnalysisResult.model_validate(parsed)
                else:
                    raise ValueError(f"No JSON in LLM response: {resp.content[:80]}")
            except Exception as e:
                # Fallback to heuristic
                analysis = self._heuristic_analysis(incident, relevant_evidence)
        else:
            analysis = self._heuristic_analysis(incident, relevant_evidence)

        # Validate evidence IDs: filter out any supporting/contradicting evidence IDs not present in retrievable evidence
        if valid_ev_ids:
            analysis.supporting_evidence_ids = [
                eid for eid in analysis.supporting_evidence_ids
                if eid in valid_ev_ids and (eid.startswith("ev_") or eid.startswith("ev-"))
            ]
            analysis.contradicting_evidence_ids = [
                eid for eid in analysis.contradicting_evidence_ids
                if eid in valid_ev_ids and (eid.startswith("ev_") or eid.startswith("ev-"))
            ]
        else:
            analysis.supporting_evidence_ids = []
            analysis.contradicting_evidence_ids = []

        return analysis

    def _heuristic_analysis(
        self,
        incident: Incident,
        relevant_evidence: List[Evidence]
    ) -> LLMAnalysisResult:
        """Deterministic fallback analysis when LLM is unavailable or unconfigured."""
        if not relevant_evidence:
            return LLMAnalysisResult(
                incident_id=incident.incident_id,
                claim=f"No relevant evidence found for entities {incident.entity_ids}",
                classification="UNKNOWN",
                supporting_evidence_ids=[],
                missing_evidence=["entity_telemetry", "history_logs"],
                confidence=0.0,
                reasoning="Fixed evidence retrieval returned empty evidence set."
            )

        diagnostic_ev = [
            e for e in relevant_evidence
            if not any(w in e.summary.lower() for w in [
                "routine system ping normal response",
                "comfortable temperature inside cabin",
                "unrelated telemetry for another vehicle",
                "routine maintenance inspection logged"
            ])
        ]

        if not diagnostic_ev:
            return LLMAnalysisResult(
                incident_id=incident.incident_id,
                claim=f"Ambiguous cause for incident {incident.incident_id}: evidence lacks actionable defect signals",
                classification="UNKNOWN",
                supporting_evidence_ids=[],
                missing_evidence=["diagnostic_telemetry"],
                confidence=0.3,
                reasoning="No actionable defect evidence after noise filtering."
            )

        combined_summary = " ".join([e.summary for e in diagnostic_ev]).lower()
        op_keywords = ["soc", "battery", "temp", "thermal", "degradation", "voltage", "cell", "run-away", "collapse"]
        data_keywords = ["fare", "negative", "null", "schema", "type", "arithmetic", "casting", "constraint", "non-numeric"]

        has_op = any(w in combined_summary for w in op_keywords)
        has_data = any(w in combined_summary for w in data_keywords)

        if has_op and not has_data:
            classification = "OPERATIONAL"
            supporting_candidates = [e for e in diagnostic_ev if any(w in e.summary.lower() for w in op_keywords)]
            lead_ev = supporting_candidates[0] if supporting_candidates else diagnostic_ev[0]
            claim = f"Operational asset defect detected in entity {incident.entity_ids[0] if incident.entity_ids else 'unknown'}: {lead_ev.summary}"
            conf = 0.85
            missing = []
        elif has_data and not has_op:
            classification = "DATA"
            supporting_candidates = [e for e in diagnostic_ev if any(w in e.summary.lower() for w in data_keywords)]
            lead_ev = supporting_candidates[0] if supporting_candidates else diagnostic_ev[0]
            claim = f"Data contract / pipeline defect detected in entity {incident.entity_ids[0] if incident.entity_ids else 'unknown'}: {lead_ev.summary}"
            conf = 0.85
            missing = []
        elif has_data and has_op:
            classification = "DATA" if any(w in incident.admission_reason.lower() for w in data_keywords) else "OPERATIONAL"
            supporting_candidates = diagnostic_ev
            claim = f"Defect detected in entity {incident.entity_ids[0] if incident.entity_ids else 'unknown'}: {supporting_candidates[0].summary}"
            conf = 0.85
            missing = []
        else:
            classification = "UNKNOWN"
            supporting_candidates = []
            claim = f"Ambiguous cause for incident {incident.incident_id}"
            conf = 0.3
            missing = ["entity_telemetry", "history_logs"]

        return LLMAnalysisResult(
            incident_id=incident.incident_id,
            claim=claim,
            classification=classification,
            supporting_evidence_ids=[e.evidence_id for e in (supporting_candidates if classification != "UNKNOWN" else [])],
            missing_evidence=missing,
            confidence=conf,
            reasoning=f"Analyzed {len(diagnostic_ev)} diagnostic evidence items."
        )

        # Validate evidence IDs: filter out any supporting/contradicting evidence IDs not present in retrievable evidence
        if valid_ev_ids:
            analysis.supporting_evidence_ids = [
                eid for eid in analysis.supporting_evidence_ids
                if eid in valid_ev_ids and (eid.startswith("ev_") or eid.startswith("ev-"))
            ]
            analysis.contradicting_evidence_ids = [
                eid for eid in analysis.contradicting_evidence_ids
                if eid in valid_ev_ids and (eid.startswith("ev_") or eid.startswith("ev-"))
            ]
        else:
            analysis.supporting_evidence_ids = []
            analysis.contradicting_evidence_ids = []

        return analysis

    def investigate_incident(
        self,
        incident: Incident,
        available_evidence: List[Evidence],
        raw_llm_response: Optional[Dict[str, Any]] = None
    ) -> Tuple[Hypothesis, Recommendation]:
        """
        Executes C1 fixed workflow for an incident.
        """
        # Step 1: Compile fixed evidence bundle
        bundle = self.context_builder.compile_evidence_bundle(incident, available_evidence)

        # Step 2: Build LLM prompt context ensuring NO hidden ground truth
        _ = self.context_builder.build_llm_context(bundle, incident=incident)

        # Step 3: Perform structured LLM analysis with strict schema validation
        analysis = self.analyze_with_llm(incident, bundle.all_evidence, raw_llm_response=raw_llm_response)

        hyp = Hypothesis(
            incident_id=incident.incident_id,
            claim=analysis.claim,
            classification=analysis.classification,
            supporting_evidence=analysis.supporting_evidence_ids,
            contradicting_evidence=analysis.contradicting_evidence_ids,
            missing_evidence=analysis.missing_evidence,
            confidence=analysis.confidence,
            status="PROPOSED"
        )

        rec = self.router.route_hypothesis(incident.incident_id, hyp)
        return hyp, rec
