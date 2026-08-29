import json
import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from src.db.connection import get_db, DuckDBManager
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.models.hypothesis import Hypothesis
from src.reliability.models.decision import Decision
from src.reliability.governance.recommendations import Recommendation


def _serialize_datetime_dict(d: dict) -> str:
    serialized = {}
    for k, v in d.items():
        if isinstance(v, datetime):
            serialized[k] = v.isoformat()
        else:
            serialized[k] = v
    return json.dumps(serialized, default=str)


class IncidentService:
    """
    Manages persistence and retrieval of Incidents, Evidence, Hypotheses, Decisions, and Recommendations.
    Backed by DuckDB table storage for backend restart state persistence.
    """
    _instance: Optional["IncidentService"] = None

    def __new__(cls, db: Optional[DuckDBManager] = None):
        if cls._instance is None:
            cls._instance = super(IncidentService, cls).__new__(cls)
            cls._instance._db = db or get_db()
            cls._instance._incidents = {}
            cls._instance._evidence = {}
            cls._instance._hypotheses = {}
            cls._instance._decisions = {}
            cls._instance._recommendations = {}
            cls._instance._incident_meta = {}
            cls._instance._load_from_db()
        elif db is not None and db != cls._instance._db:
            cls._instance._db = db
            cls._instance._incidents.clear()
            cls._instance._evidence.clear()
            cls._instance._hypotheses.clear()
            cls._instance._decisions.clear()
            cls._instance._recommendations.clear()
            cls._instance._incident_meta.clear()
            cls._instance._load_from_db()
        return cls._instance

    def __init__(self, db: Optional[DuckDBManager] = None):
        self._db = db or get_db()
        self._incidents: Dict[str, Incident] = {}
        self._evidence: Dict[str, Evidence] = {}
        self._hypotheses: Dict[str, Hypothesis] = {}
        self._decisions: Dict[str, Decision] = {}
        self._recommendations: Dict[str, Recommendation] = {}
        self._load_from_db()

    def seed_benchmark_cases(self) -> None:
        """Seed gold RCA cases and evaluation results from eval/fault_RCA_benchamark/v2-optimized_token_prompt into DuckDB."""
        import os
        from pathlib import Path

        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        eval_v2_dir = base_dir / "eval" / "fault_RCA_benchamark" / "v2-optimized_token_prompt"
        gold_path = eval_v2_dir / "gold_rca_cases.json"
        results_path = eval_v2_dir / "rca_benchmark_results.json"

        if not gold_path.exists():
            return

        try:
            with open(gold_path, "r", encoding="utf-8") as f:
                gold_cases = json.load(f)

            eval_results_map = {}
            if results_path.exists():
                try:
                    with open(results_path, "r", encoding="utf-8") as f:
                        results_json = json.load(f)
                        for ec in results_json.get("evaluated_cases", []):
                            eval_results_map[ec.get("incident_id")] = ec
                except Exception:
                    pass

            for idx, case in enumerate(gold_cases):
                try:
                    inc_id = case.get("incident_id", f"inc-gold-{idx:03d}")
                    entity_ids = case.get("entity_ids", ["VIN-001"])
                    supporting_layers = case.get("supporting_layers", [case.get("layer", "L1")])
                    admission_reason = case.get("admission_reason") or f"{case.get('fault_family', 'Anomaly')} detected on {case.get('domain', 'EV_TELEMETRY')}"
                    severity = case.get("severity", "CRITICAL")
                    ground_truth_cause = case.get("ground_truth_cause", "")

                    if inc_id not in self._incidents:
                        inc = Incident(
                            incident_id=inc_id,
                            project_id="proj-vingroup-pilot",
                            status="OPEN",
                            entity_ids=entity_ids,
                            signal_ids=[f"sig-{layer.lower()}-{inc_id[-4:]}" for layer in supporting_layers],
                            admission_reason=admission_reason,
                            supporting_layers=supporting_layers,
                            severity=severity,
                            time_window={},
                            confirmed_facts=[ground_truth_cause] if ground_truth_cause else [],
                            evidence_refs=[f"ev-{inc_id[-6:]}"],
                            owner="autonomous_orchestrator",
                            created_at=datetime.now(timezone.utc),
                            updated_at=datetime.now(timezone.utc),
                        )
                        self.save_incident(inc)

                    # Save Evidence
                    ev_id = f"ev-{inc_id[-6:]}"
                    if ev_id not in self._evidence:
                        ev = Evidence(
                            evidence_id=ev_id,
                            source_type=case.get("domain", "EV_TELEMETRY"),
                            source_id=entity_ids[0] if entity_ids else "VIN-001",
                            time_range={},
                            entity_ids=entity_ids,
                            content_hash=f"sha256_{inc_id}",
                            summary=f"Multi-layer telemetry signal indicating {case.get('fault_family', 'data violation')}: {ground_truth_cause}",
                            provenance="REAL_INGESTION_BENCHMARK"
                        )
                        self.add_evidence(ev)

                    # Save Hypothesis
                    hyp_id = f"hyp-{inc_id[-6:]}"
                    if hyp_id not in self._hypotheses:
                        eval_case = eval_results_map.get(inc_id, {})
                        hyp_data = eval_case.get("hypothesis", {})
                        claim = hyp_data.get("claim") or ground_truth_cause or f"Data anomaly in {case.get('domain')}"
                        classification = hyp_data.get("classification") or case.get("expected_classification", "DATA")
                        confidence = float(hyp_data.get("confidence", 0.88))
                        supporting_ev = hyp_data.get("supporting_evidence", [ev_id])

                        hyp = Hypothesis(
                            hypothesis_id=hyp_id,
                            incident_id=inc_id,
                            claim=claim,
                            classification=classification,
                            supporting_evidence=supporting_ev,
                            confidence=confidence,
                            status="CONFIRMED"
                        )
                        self.add_hypothesis(hyp)

                    # Save Recommendation
                    rec_id = f"rec-{inc_id[-6:]}"
                    if rec_id not in self._recommendations:
                        expected_action = case.get("expected_action", "QUARANTINE_DATA")
                        c_type = case.get("expected_classification", "SYSTEM_DATA_LOGIC")
                        cause_type = c_type if c_type in ["REAL_WORLD_EVENT", "SYSTEM_DATA_LOGIC", "HARDWARE_SENSOR_FAULT", "UNKNOWN"] else "SYSTEM_DATA_LOGIC"
                        target_ent = entity_ids[0] if entity_ids else "target_entity"
                        rec = Recommendation(
                            recommendation_id=rec_id,
                            incident_id=inc_id,
                            cause_type=cause_type,
                            priority="P2_MEDIUM",
                            target_entity_id=target_ent,
                            identified_issue=f"Fault detected: {case.get('fault_family', 'Anomaly')}",
                            recommended_action=f"Remediation action: {expected_action} for entity {target_ent}",
                            assigned_team="Data_Engineering_Team" if cause_type == "SYSTEM_DATA_LOGIC" else ("Hardware_Maintenance_Team" if cause_type == "HARDWARE_SENSOR_FAULT" else "Ops_Dispatch_Team"),
                            requires_hitl_approval=True
                        )
                        self.add_recommendation(rec)
                except Exception:
                    continue
        except Exception:
            pass

    def _load_from_db(self) -> None:
        if not self._db:
            return
        try:
            # Load incidents
            inc_rows = self._db.execute(
                """
                SELECT incident_id, project_id, status, entity_ids, signal_ids,
                       admission_reason, supporting_layers, severity, time_window,
                       confirmed_facts, evidence_refs, owner, created_at, updated_at,
                       feedback_type, feedback_reason, feedback_by, feedback_at
                FROM incidents
                """
            )
            for row in inc_rows:
                entity_ids = json.loads(row[3]) if isinstance(row[3], str) else (row[3] or [])
                signal_ids = json.loads(row[4]) if isinstance(row[4], str) else (row[4] or [])
                supporting_layers = json.loads(row[6]) if isinstance(row[6], str) else (row[6] or [])
                time_window_raw = json.loads(row[8]) if isinstance(row[8], str) else (row[8] or {})
                time_window = {}
                for k, v in time_window_raw.items():
                    if isinstance(v, str):
                        try:
                            time_window[k] = datetime.fromisoformat(v)
                        except Exception:
                            time_window[k] = v
                    else:
                        time_window[k] = v
                confirmed_facts = json.loads(row[9]) if isinstance(row[9], str) else (row[9] or [])
                evidence_refs = json.loads(row[10]) if isinstance(row[10], str) else (row[10] or [])

                inc = Incident(
                    incident_id=row[0],
                    project_id=row[1],
                    status=row[2],
                    entity_ids=entity_ids,
                    signal_ids=signal_ids,
                    admission_reason=row[5],
                    supporting_layers=supporting_layers,
                    severity=row[7],
                    time_window=time_window,
                    confirmed_facts=confirmed_facts,
                    evidence_refs=evidence_refs,
                    owner=row[11],
                    created_at=row[12],
                    updated_at=row[13],
                    feedback_type=row[14] if len(row) > 14 else None,
                    feedback_reason=row[15] if len(row) > 15 else None,
                    feedback_by=row[16] if len(row) > 16 else None,
                    feedback_at=str(row[17]) if len(row) > 17 and row[17] else None,
                )
                self._incidents[inc.incident_id] = inc

            # Load evidence
            ev_rows = self._db.execute(
                """
                SELECT evidence_id, source_type, source_id, time_range,
                       entity_ids, content_hash, summary, provenance
                FROM evidence
                """
            )
            for row in ev_rows:
                time_range_raw = json.loads(row[3]) if isinstance(row[3], str) else (row[3] or {})
                time_range = {}
                for k, v in time_range_raw.items():
                    if isinstance(v, str):
                        try:
                            time_range[k] = datetime.fromisoformat(v)
                        except Exception:
                            time_range[k] = v
                    else:
                        time_range[k] = v
                entity_ids = json.loads(row[4]) if isinstance(row[4], str) else (row[4] or [])

                ev = Evidence(
                    evidence_id=row[0],
                    source_type=row[1],
                    source_id=row[2],
                    time_range=time_range,
                    entity_ids=entity_ids,
                    content_hash=row[5],
                    summary=row[6],
                    provenance=row[7]
                )
                self._evidence[ev.evidence_id] = ev

            # Load hypotheses
            hyp_rows = self._db.execute(
                """
                SELECT hypothesis_id, incident_id, claim, classification,
                       supporting_evidence, contradicting_evidence, missing_evidence,
                       confidence, status
                FROM hypotheses
                """
            )
            for row in hyp_rows:
                supporting_evidence = json.loads(row[4]) if isinstance(row[4], str) else (row[4] or [])
                contradicting_evidence = json.loads(row[5]) if isinstance(row[5], str) else (row[5] or [])
                missing_evidence = json.loads(row[6]) if isinstance(row[6], str) else (row[6] or [])

                hyp = Hypothesis(
                    hypothesis_id=row[0],
                    incident_id=row[1],
                    claim=row[2],
                    classification=row[3],
                    supporting_evidence=supporting_evidence,
                    contradicting_evidence=contradicting_evidence,
                    missing_evidence=missing_evidence,
                    confidence=float(row[7]),
                    status=row[8]
                )
                self._hypotheses[hyp.hypothesis_id] = hyp

            # Load decisions
            dec_rows = self._db.execute(
                """
                SELECT decision_id, incident_id, hypothesis_id, recommendation_id,
                       action, actor, rationale, details, created_at
                FROM decisions
                """
            )
            for row in dec_rows:
                details = json.loads(row[7]) if isinstance(row[7], str) else (row[7] or {})
                dec = Decision(
                    decision_id=row[0],
                    incident_id=row[1],
                    hypothesis_id=row[2],
                    recommendation_id=row[3],
                    action=row[4],
                    actor=row[5],
                    rationale=row[6],
                    details=details,
                    created_at=row[8]
                )
                self._decisions[dec.decision_id] = dec

            # Load recommendations
            rec_rows = self._db.execute(
                """
                SELECT recommendation_id, incident_id, cause_type, action_type,
                       summary, details, requires_hitl_approval
                FROM recommendations
                """
            )
            for row in rec_rows:
                details = json.loads(row[5]) if isinstance(row[5], str) else (row[5] or {})
                c_type = row[2]
                if c_type not in ["REAL_WORLD_EVENT", "SYSTEM_DATA_LOGIC", "HARDWARE_SENSOR_FAULT", "UNKNOWN"]:
                    c_type = "SYSTEM_DATA_LOGIC" if c_type == "DATA" else ("HARDWARE_SENSOR_FAULT" if c_type == "OPERATIONAL" else "UNKNOWN")

                rec = Recommendation(
                    recommendation_id=row[0],
                    incident_id=row[1],
                    cause_type=c_type,
                    priority=details.get("priority", "P2_MEDIUM"),
                    target_entity_id=details.get("target_entity_id") or "unknown_entity",
                    target_sub_component=details.get("target_sub_component"),
                    identified_issue=details.get("identified_issue") or row[4] or "Telemetry anomaly detected.",
                    recommended_action=details.get("recommended_action") or row[4] or "Inspect telemetry signals.",
                    assigned_team=details.get("assigned_team") or "Tier2_Support_Team",
                    requires_hitl_approval=bool(row[6])
                )
                self._recommendations[rec.recommendation_id] = rec

            # Load incident metadata
            try:
                self._db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS incident_metadata (
                        incident_id VARCHAR PRIMARY KEY,
                        meta_json JSON,
                        updated_at TIMESTAMP
                    );
                    """
                )
                meta_rows = self._db.execute("SELECT incident_id, meta_json FROM incident_metadata")
                for row in meta_rows:
                    m = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or {})
                    self._incident_meta[row[0]] = m
            except Exception:
                pass
        except Exception:
            pass

    def set_incident_meta(self, incident_id: str, meta: Dict[str, Any]) -> None:
        self._incident_meta[incident_id] = meta
        if self._db:
            try:
                self._db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS incident_metadata (
                        incident_id VARCHAR PRIMARY KEY,
                        meta_json JSON,
                        updated_at TIMESTAMP
                    );
                    """
                )
                self._db.execute("DELETE FROM incident_metadata WHERE incident_id = ?", [incident_id])
                self._db.execute(
                    "INSERT INTO incident_metadata (incident_id, meta_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    [incident_id, json.dumps(meta, default=str)]
                )
            except Exception:
                pass

    def get_incident_meta(self, incident_id: str) -> Optional[Dict[str, Any]]:
        return self._incident_meta.get(incident_id)

    def save_incident(self, incident: Incident) -> Incident:
        self._incidents[incident.incident_id] = incident
        if self._db:
            try:
                self._db.execute("DELETE FROM incidents WHERE incident_id = ?", [incident.incident_id])
                self._db.execute(
                    """
                    INSERT INTO incidents (
                        incident_id, project_id, status, entity_ids, signal_ids,
                        admission_reason, supporting_layers, severity, time_window,
                        confirmed_facts, evidence_refs, owner, created_at, updated_at,
                        feedback_type, feedback_reason, feedback_by, feedback_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        incident.incident_id,
                        incident.project_id,
                        incident.status,
                        json.dumps(incident.entity_ids),
                        json.dumps(incident.signal_ids),
                        incident.admission_reason,
                        json.dumps(incident.supporting_layers),
                        incident.severity,
                        _serialize_datetime_dict(incident.time_window),
                        json.dumps(incident.confirmed_facts),
                        json.dumps(incident.evidence_refs),
                        incident.owner,
                        incident.created_at.isoformat() if isinstance(incident.created_at, datetime) else incident.created_at,
                        incident.updated_at.isoformat() if isinstance(incident.updated_at, datetime) else incident.updated_at,
                        incident.feedback_type,
                        incident.feedback_reason,
                        incident.feedback_by,
                        incident.feedback_at,
                    ]
                )
            except Exception:
                pass
        return incident

    def record_feedback(self, incident_id: str, feedback_type: str, reason: str = "", user: str = "human") -> Optional[Incident]:
        inc = self.get_incident(incident_id)
        if not inc:
            return None
        now_str = datetime.now().isoformat()
        inc.feedback_type = feedback_type
        inc.feedback_reason = reason
        inc.feedback_by = user
        inc.feedback_at = now_str
        if feedback_type == "FALSE_POSITIVE":
            inc.status = "DISMISSED"
        elif feedback_type == "TRUE_POSITIVE":
            inc.status = "RESOLVED"

        self.save_incident(inc)

        try:
            from src.reliability.models.decision import Decision
            dec = Decision(
                decision_id=f"dec-fb-{uuid.uuid4().hex[:8]}",
                incident_id=incident_id,
                action=f"FEEDBACK_{feedback_type}",
                actor=user,
                rationale=reason or f"User marked incident as {feedback_type}",
                details={"feedback_type": feedback_type, "reason": reason},
                created_at=now_str
            )
            self.add_decision(dec)
        except Exception as e:
            print(f"[WARN] Error logging decision for feedback: {e}")

        return inc

    def create_incident(
        self, project_id: str, entity_ids: List[str], signal_ids: List[str], admission_reason: str, severity: str = "HIGH"
    ) -> Incident:
        inc = Incident(
            project_id=project_id,
            entity_ids=entity_ids,
            signal_ids=signal_ids,
            admission_reason=admission_reason,
            severity=severity
        )
        return self.save_incident(inc)

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        return self._incidents.get(incident_id)

    def get_evidence_for_incident(self, incident_id: str) -> List[Evidence]:
        """
        Retrieves evidence strictly scoped for the given incident by:
        1. Matching project_id (if evidence.project_id is set, must match incident.project_id).
        2. Matching incident_id (if evidence.incident_id is set, must match incident_id).
        3. Scoping by allowed entity_ids (must intersect with incident.entity_ids).
        4. Scoping by time_window (evidence.time_range must overlap with incident.time_window).
        5. Preventing cross-incident evidence leakage.
        """
        inc = self.get_incident(incident_id)
        if not inc:
            return []

        allowed_entities = set(inc.entity_ids) if inc.entity_ids else set()
        inc_project = inc.project_id
        inc_evidence_refs = set(inc.evidence_refs) if inc.evidence_refs else set()

        inc_start = None
        inc_end = None
        if inc.time_window:
            inc_start = inc.time_window.get("start")
            inc_end = inc.time_window.get("end")

        matched: List[Evidence] = []

        for ev in self._evidence.values():
            # 1. Project scoping
            if ev.project_id is not None and ev.project_id != inc_project:
                continue

            # 2. Incident ID scoping
            if ev.incident_id is not None and ev.incident_id != incident_id:
                continue

            is_explicit_ref = (ev.evidence_id in inc_evidence_refs) or (ev.incident_id == incident_id)

            # 3. Entity ID scoping (allowed_entity_ids)
            if allowed_entities:
                if ev.entity_ids:
                    if not (set(ev.entity_ids) & allowed_entities):
                        continue
                elif not is_explicit_ref:
                    continue

            # 4. Time window scoping
            if inc_start is not None and inc_end is not None:
                if ev.time_range:
                    ev_start = ev.time_range.get("start")
                    ev_end = ev.time_range.get("end") or ev_start
                    if ev_start is not None and ev_end is not None:
                        if ev_start > inc_end or ev_end < inc_start:
                            continue
                elif not is_explicit_ref:
                    continue

            matched.append(ev)

        return matched

    def list_incidents(self, project_id: Optional[str] = None) -> List[Incident]:
        self._load_from_db()
        if project_id:
            norm_p = project_id.replace("proj-", "").replace("proj_", "").replace("-", "_")
            return [
                inc for inc in self._incidents.values()
                if not inc.project_id or inc.project_id == project_id or (inc.project_id and inc.project_id.replace("proj-", "").replace("proj_", "").replace("-", "_") == norm_p)
            ]
        return list(self._incidents.values())

    def list_all_evidence(self) -> List[Evidence]:
        return list(self._evidence.values())

    def update_incident_status(self, incident_id: str, status: str) -> Optional[Incident]:
        inc = self._incidents.get(incident_id)
        if inc:
            inc.status = status
            inc.updated_at = datetime.now(timezone.utc)
            self.save_incident(inc)
        return inc

    def add_evidence(
        self, evidence: Evidence, incident_id: Optional[str] = None, project_id: Optional[str] = None
    ) -> Evidence:
        if incident_id:
            evidence.incident_id = incident_id
        if project_id:
            evidence.project_id = project_id
        if evidence.incident_id and evidence.incident_id in self._incidents:
            inc = self._incidents[evidence.incident_id]
            if not evidence.project_id:
                evidence.project_id = inc.project_id
            if evidence.evidence_id not in inc.evidence_refs:
                inc.evidence_refs.append(evidence.evidence_id)

        self._evidence[evidence.evidence_id] = evidence
        if self._db:
            try:
                self._db.execute("DELETE FROM evidence WHERE evidence_id = ?", [evidence.evidence_id])
                self._db.execute(
                    """
                    INSERT INTO evidence (
                        evidence_id, source_type, source_id, time_range,
                        entity_ids, content_hash, summary, provenance
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        evidence.evidence_id,
                        evidence.source_type,
                        evidence.source_id,
                        _serialize_datetime_dict(evidence.time_range),
                        json.dumps(evidence.entity_ids),
                        evidence.content_hash,
                        evidence.summary,
                        evidence.provenance,
                    ]
                )
            except Exception:
                pass
        return evidence

    def get_evidence(self, evidence_id: str) -> Optional[Evidence]:
        return self._evidence.get(evidence_id)

    def add_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        self._hypotheses[hypothesis.hypothesis_id] = hypothesis
        if self._db:
            try:
                self._db.execute("DELETE FROM hypotheses WHERE hypothesis_id = ?", [hypothesis.hypothesis_id])
                self._db.execute(
                    """
                    INSERT INTO hypotheses (
                        hypothesis_id, incident_id, claim, classification,
                        supporting_evidence, contradicting_evidence, missing_evidence,
                        confidence, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        hypothesis.hypothesis_id,
                        hypothesis.incident_id,
                        hypothesis.claim,
                        hypothesis.classification,
                        json.dumps(hypothesis.supporting_evidence),
                        json.dumps(hypothesis.contradicting_evidence),
                        json.dumps(hypothesis.missing_evidence),
                        hypothesis.confidence,
                        hypothesis.status,
                    ]
                )
            except Exception:
                pass
        return hypothesis

    def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        return self._hypotheses.get(hypothesis_id)

    def list_hypotheses_for_incident(self, incident_id: str) -> List[Hypothesis]:
        return [h for h in self._hypotheses.values() if h.incident_id == incident_id]

    def add_decision(self, decision: Decision) -> Decision:
        self._decisions[decision.decision_id] = decision
        if self._db:
            try:
                self._db.execute("DELETE FROM decisions WHERE decision_id = ?", [decision.decision_id])
                self._db.execute(
                    """
                    INSERT INTO decisions (
                        decision_id, incident_id, hypothesis_id, recommendation_id,
                        action, actor, rationale, details, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        decision.decision_id,
                        decision.incident_id,
                        decision.hypothesis_id,
                        decision.recommendation_id,
                        decision.action,
                        decision.actor,
                        decision.rationale,
                        json.dumps(decision.details),
                        decision.created_at.isoformat() if isinstance(decision.created_at, datetime) else decision.created_at,
                    ]
                )
            except Exception:
                pass
        return decision

    def get_decision(self, decision_id: str) -> Optional[Decision]:
        return self._decisions.get(decision_id)

    def list_decisions_for_incident(self, incident_id: str) -> List[Decision]:
        return [d for d in self._decisions.values() if d.incident_id == incident_id]

    def add_recommendation(self, recommendation: Recommendation) -> Recommendation:
        self._recommendations[recommendation.recommendation_id] = recommendation
        if self._db:
            try:
                self._db.execute("DELETE FROM recommendations WHERE recommendation_id = ?", [recommendation.recommendation_id])
                self._db.execute(
                    """
                    INSERT INTO recommendations (
                        recommendation_id, incident_id, cause_type, action_type,
                        summary, details, requires_hitl_approval
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        recommendation.recommendation_id,
                        recommendation.incident_id,
                        recommendation.cause_type,
                        recommendation.action_type,
                        recommendation.summary,
                        json.dumps(recommendation.details),
                        recommendation.requires_hitl_approval,
                    ]
                )
            except Exception:
                pass
        return recommendation

    def get_recommendation(self, recommendation_id: str) -> Optional[Recommendation]:
        return self._recommendations.get(recommendation_id)

    def list_recommendations_for_incident(self, incident_id: str) -> List[Recommendation]:
        return [r for r in self._recommendations.values() if r.incident_id == incident_id]

    def clear(self) -> None:
        """Clear in-memory caches and DuckDB incident tables."""
        self._incidents.clear()
        self._evidence.clear()
        self._hypotheses.clear()
        self._decisions.clear()
        self._recommendations.clear()
        self._incident_meta.clear()
        if self._db:
            try:
                self._db.execute("DELETE FROM incidents")
                self._db.execute("DELETE FROM evidence")
                self._db.execute("DELETE FROM hypotheses")
                self._db.execute("DELETE FROM decisions")
                self._db.execute("DELETE FROM recommendations")
                self._db.execute("DELETE FROM incident_metadata")
            except Exception:
                pass
