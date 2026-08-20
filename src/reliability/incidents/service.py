import json
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
    return json.dumps(serialized)


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
                       confirmed_facts, evidence_refs, owner, created_at, updated_at
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
                    updated_at=row[13]
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
                rec = Recommendation(
                    recommendation_id=row[0],
                    incident_id=row[1],
                    cause_type=row[2],
                    action_type=row[3],
                    summary=row[4],
                    details=details,
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
                        confirmed_facts, evidence_refs, owner, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    ]
                )
            except Exception:
                pass
        return incident

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
        if project_id:
            return [inc for inc in self._incidents.values() if inc.project_id == project_id]
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
