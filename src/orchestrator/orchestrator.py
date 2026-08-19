from __future__ import annotations
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from src.services.llm import GemmaLLMAdapter
from src.agents.profiler_agent import ProfilerAgent
from src.agents.anomaly_agent import AnomalyAgent
from src.agents.diagnosis_agent import DiagnosisAgent
from src.agents.rule_proposer_agent import RuleProposerAgent
from src.agents.executor_agent import ExecutorAgent
from src.db.connection import get_db


# Official VinGroup Pilot DB (with injected faults)
VINGROUP_PILOT_DB = "data_new/db/vingroup_pilot.db"

# Mapping DuckDB table -> (entity_id_col, timestamp_col, metric_col, range_min, range_max)
# Conservative defaults for stage-2 wiring; tuned per table.
_TABLE_SIGNAL_CONFIG = {
    "vinfast_ev_telemetry": {
        "entity_id_col": "vehicle_vin",
        "timestamp_col": "timestamp",
        "metric_col": "battery_soc",
        "relational_x": "battery_voltage",
        "relational_y": "battery_current",
        "l1_min": 0.0,
        "l1_max": 100.0,
        "l1_required_cols": ["battery_voltage", "battery_current", "battery_temp_c"],
    },
    "vinfast_bms": {
        "entity_id_col": "vehicle_vin",
        "timestamp_col": "timestamp",
        "metric_col": "temp_c",
        "relational_x": "voltage",
        "relational_y": "charging_rate_kw",
        "l1_min": -20.0,
        "l1_max": 100.0,
        "l1_required_cols": ["voltage", "temp_c"],
    },
    "vgreen_charging_sessions": {
        "entity_id_col": "station_id",
        "timestamp_col": "start_time",
        "metric_col": "station_temp_c",
        "relational_x": "power_kw",
        "relational_y": "kwh_consumed",
        "l1_min": -20.0,
        "l1_max": 80.0,
        "l1_required_cols": ["kwh_consumed", "power_kw"],
    },
    "xanh_sm_trips": {
        "entity_id_col": "vehicle_vin",
        "timestamp_col": "pickup_datetime",
        "metric_col": "fare_amount",
        "relational_x": "trip_distance_km",  # EDA 2026-08-14: renamed trip_miles -> trip_distance_km
        "relational_y": "fare_amount",
        "l1_min": 0.0,
        "l1_max": None,
        "l1_required_cols": ["fare_amount", "trip_distance_km"],
    },
}


def _load_table_as_dataframe(table_name: str, project_id: str, db_path: Optional[str] = None) -> pd.DataFrame:
    """
    Load a DuckDB table into a pandas DataFrame for L1-L4 detectors.

    Source DB defaults to `data/vingroup_pilot_faulty.duckdb` (Vingroup faulty pilot dataset).
    When the configured runtime DB does not contain the table, falls back to the Vingroup
    pilot DB so the full L1-L4 + Fusion + A1 pipeline can run end-to-end.
    """
    import duckdb

    candidates = []
    if db_path:
        candidates.append(db_path)
    try:
        active_db = get_db().db_path
        if active_db and active_db not in candidates:
            candidates.append(active_db)
    except Exception:
        pass
    candidates.append(VINGROUP_PILOT_DB)
    candidates.append("data/datatrust_v4.duckdb")

    last_exc: Optional[Exception] = None
    for candidate in candidates:
        if not os.path.isabs(candidate):
            candidate = os.path.join(os.getcwd(), candidate)
        if not os.path.exists(candidate):
            continue
        try:
            db_mgr = get_db()
            is_same = os.path.abspath(candidate) == os.path.abspath(str(db_mgr.db_path))
            if is_same:
                conn = db_mgr._get_master_conn()
                df = conn.execute(f'SELECT * FROM "{table_name}" LIMIT 5000').df()
                if not df.empty:
                    return df
            else:
                try:
                    conn = duckdb.connect(candidate, read_only=True)
                except Exception:
                    conn = duckdb.connect(candidate)
                try:
                    df = conn.execute(f'SELECT * FROM "{table_name}" LIMIT 5000').df()
                    if not df.empty:
                        return df
                finally:
                    conn.close()
        except Exception as exc:
            last_exc = exc
            continue

    if last_exc is not None:
        raise last_exc
    return pd.DataFrame()


def _detect_l1_l4_signals(table_name: str, df: pd.DataFrame, project_id: str) -> dict:
    """
    Run L1-L4 detectors on the provided DataFrame and return a dict of
    {layer: List[Signal]} compatible with ReliabilityOrchestrator.run_pipeline.
    Empty signal lists are returned when column configuration is missing.
    """
    from src.reliability.detectors.l1_rules import L1ConstraintDetector
    from src.reliability.detectors.l2_contextual import L2ContextualDetector
    from src.reliability.detectors.l3_relational import L3RelationalDetector
    from src.reliability.detectors.l4_changepoint import L4ChangepointDetector

    cfg = _TABLE_SIGNAL_CONFIG.get(table_name, {})
    entity_col = cfg.get("entity_id_col")
    ts_col = cfg.get("timestamp_col")
    metric_col = cfg.get("metric_col")

    if not entity_col or not ts_col or not metric_col or df.empty:
        return {"L1": [], "L2": [], "L3": [], "L4": []}

    if entity_col not in df.columns or ts_col not in df.columns or metric_col not in df.columns:
        return {"L1": [], "L2": [], "L3": [], "L4": []}

    signals: dict = {"L1": [], "L2": [], "L3": [], "L4": []}

    # L1: range + null violations
    try:
        l1 = L1ConstraintDetector()
        signals["L1"].extend(l1.detect_range_violations(
            df=df, project_id=project_id,
            entity_id_col=entity_col, timestamp_col=ts_col,
            metric_col=metric_col,
            min_val=cfg.get("l1_min"), max_val=cfg.get("l1_max"),
        ))
        signals["L1"].extend(l1.detect_null_violations(
            df=df, project_id=project_id,
            entity_id_col=entity_col, timestamp_col=ts_col,
            required_cols=cfg.get("l1_required_cols", []),
        ))
    except Exception:
        pass

    # L2: contextual drift via robust Z-score
    try:
        l2 = L2ContextualDetector(z_threshold=3.5, warmup_days=14, min_samples=14)
        signals["L2"].extend(l2.detect_entity_anomalies(
            df=df, project_id=project_id,
            entity_id_col=entity_col, timestamp_col=ts_col,
            metric_col=metric_col,
        ))
    except Exception:
        pass

    # L3: relational break using a simple temporal split (first 50% ref, last 50% eval)
    try:
        rel_x = cfg.get("relational_x")
        rel_y = cfg.get("relational_y")
        if rel_x and rel_y and rel_x in df.columns and rel_y in df.columns:
            sorted_df = df.sort_values(ts_col).reset_index(drop=True)
            cutoff = max(5, len(sorted_df) // 2)
            ref_df = sorted_df.iloc[:cutoff]
            eval_df = sorted_df.iloc[cutoff:]
            l3 = L3RelationalDetector(residual_z_threshold=3.5, comparator="linear_regression")
            signals["L3"].extend(l3.detect_bivariate_residual_anomalies(
                ref_df=ref_df, eval_df=eval_df,
                project_id=project_id,
                entity_id_col=entity_col, timestamp_col=ts_col,
                feature_x=rel_x, feature_y=rel_y,
            ))
    except Exception:
        pass

    # L4: CUSUM change-point
    try:
        l4 = L4ChangepointDetector(cusum_threshold=4.0, min_segment_len=3, persistence_window=3)
        signals["L4"].extend(l4.detect_cusum_shift(
            df=df, project_id=project_id,
            entity_id_col=entity_col, timestamp_col=ts_col,
            metric_col=metric_col,
        ))
    except Exception:
        pass

    return signals


def _run_reliability_pipeline(table_name: str, project_id: str) -> List[dict]:
    """
    End-to-end L1-L4 -> FusionEngine -> IncidentService -> A1BoundedInvestigator pipeline.
    Returns a list of investigation result dicts (one per admitted incident).
    Raises if the table cannot be loaded.
    """
    df = _load_table_as_dataframe(table_name, project_id=project_id)
    if df.empty:
        return []

    detector_outputs = _detect_l1_l4_signals(table_name, df, project_id)
    if not any(detector_outputs.values()):
        return []

    from src.reliability.investigation.reliability_orchestrator import ReliabilityOrchestrator

    orchestrator = ReliabilityOrchestrator()
    results = orchestrator.run_pipeline(detector_outputs, project_id=project_id)

    out: List[dict] = []
    for res in results:
        out.append({
            "incident_id": res.incident.incident_id,
            "severity": res.incident.severity,
            "supporting_layers": res.incident.supporting_layers,
            "admission_reason": res.incident.admission_reason,
            "entity_ids": res.incident.entity_ids,
            "signal_ids": res.incident.signal_ids,
            "hypothesis_id": res.hypothesis.hypothesis_id,
            "classification": res.hypothesis.classification,
            "confidence": res.hypothesis.confidence,
            "recommendation_id": res.recommendation.recommendation_id,
            "recommendation_type": res.recommendation.recommendation_type,
            "action_type": res.recommendation.action_type,
        })
    return out


@dataclass
class OrchestratorResult:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    stages: list[dict] = field(default_factory=list)
    proposed_rules: list[dict] = field(default_factory=list)
    pending_approval: list[dict] = field(default_factory=list)
    diagnosis: str = ""
    status: str = "pending"
    total_duration_ms: int = 0


class DataTrustOrchestrator:
    """Top-level orchestrator implementing the full pipeline:
    Profiler -> L1-L4 Detection + Fusion + A1 Investigation -> Diagnosis -> Rule Proposer -> HITL queue -> (approval) -> Executor
    """

    def __init__(self, llm: GemmaLLMAdapter, project_id: str = "default_project", source_db_path: Optional[str] = None):
        self.llm = llm
        self.project_id = project_id
        self.source_db_path = source_db_path or VINGROUP_PILOT_DB
        self.profiler = ProfilerAgent(llm)
        self.anomaly = AnomalyAgent(llm)
        self.diagnosis = DiagnosisAgent(llm)
        self.rule_proposer = RuleProposerAgent(llm)
        self.executor = ExecutorAgent(llm)

    def run_analysis(self, table_name: str, review_text: str | None = None) -> OrchestratorResult:
        """Run the full analysis pipeline on a table."""
        start = time.time()
        result = OrchestratorResult()

        # Stage 1: Profile
        profile_result = self.profiler.run(table_name)
        result.stages.append({
            "stage": "profiling",
            "agent": "profiler",
            "status": profile_result.status,
            "steps": len(profile_result.steps),
            "summary": profile_result.final_answer[:500]
        })

        # Stage 2: Anomaly Detection (Design V2: L1-L4 -> Fusion -> Incident -> A1)
        anomaly_stage = self._run_anomaly_stage(table_name)
        result.stages.append(anomaly_stage)
        anomaly_findings = anomaly_stage.get("anomaly_findings", {})

        # Stage 3: Diagnosis (if review text provided)
        if review_text:
            diag_result = self.diagnosis.run(review_text)
            result.diagnosis = diag_result.final_answer
            result.stages.append({
                "stage": "diagnosis",
                "agent": "diagnosis",
                "status": diag_result.status,
                "steps": len(diag_result.steps),
                "summary": diag_result.final_answer[:500]
            })

        # Stage 4: Rule Proposal (now receives real anomaly findings)
        rule_result = self.rule_proposer.run(
            table_name,
            profile_summary=profile_result.final_answer[:500],
            anomaly_findings=anomaly_findings
        )
        result.stages.append({
            "stage": "rule_proposal",
            "agent": "rule_proposer",
            "status": rule_result.status,
            "steps": len(rule_result.steps),
            "summary": rule_result.final_answer[:500]
        })

        # Stage 5: Queue rules for HITL approval
        # Rules are stored as 'proposed' and need human approval before execution
        result.status = "awaiting_approval"
        result.total_duration_ms = int((time.time() - start) * 1000)

        # Log orchestration
        self._log_orchestration(result)
        return result

    def _run_anomaly_stage(self, table_name: str) -> dict:
        """
        Run Design V2 anomaly pipeline: L1-L4 detectors -> Fusion -> IncidentService -> A1.
        Returns a stage dict compatible with the orchestrator's stage list, plus
        `anomaly_findings` containing real admitted incidents and A1 hypotheses.
        """
        try:
            investigations = _run_reliability_pipeline(
                table_name=table_name,
                project_id=self.project_id,
            )
        except Exception as exc:
            return {
                "stage": "anomaly_detection",
                "agent": "reliability_orchestrator",
                "status": "error",
                "error": str(exc),
                "incident_count": 0,
                "incidents": [],
                "anomaly_findings": {"incidents": []},
                "summary": f"Reliability pipeline failed: {exc}",
            }

        incidents_payload = [
            {
                "id": inv["incident_id"],
                "severity": inv["severity"],
                "supporting_layers": inv["supporting_layers"],
                "admission_reason": inv["admission_reason"],
                "entity_ids": inv["entity_ids"],
                "signal_ids": inv["signal_ids"],
                "hypothesis": {
                    "id": inv["hypothesis_id"],
                    "classification": inv["classification"],
                    "confidence": inv["confidence"],
                },
                "recommendation": {
                    "id": inv["recommendation_id"],
                    "type": inv["recommendation_type"],
                    "action_type": inv["action_type"],
                },
            }
            for inv in investigations
        ]

        if not investigations:
            status = "no_anomalies"
            summary = "No L1-L4 signals admitted by FusionEngine."
        else:
            status = "completed"
            summary = (
                f"L1-L4 detectors produced {len(investigations)} admitted incident(s); "
                f"A1 returned hypotheses + recommendations."
            )

        return {
            "stage": "anomaly_detection",
            "agent": "reliability_orchestrator",
            "status": status,
            "incident_count": len(investigations),
            "incidents": incidents_payload,
            "anomaly_findings": {"incidents": incidents_payload},
            "summary": summary,
        }

    def execute_approved_rules(self, rule_ids: list[str], dry_run: bool = True) -> list[dict]:
        """Execute approved rules after HITL approval."""
        results = []
        for rule_id in rule_ids:
            exec_result = self.executor.run(rule_id, dry_run=dry_run)
            results.append({
                "rule_id": rule_id,
                "status": exec_result.status,
                "summary": exec_result.final_answer[:500]
            })
        return results

    def _log_orchestration(self, result: OrchestratorResult):
        try:
            from src.services.audit import AuditService
            AuditService.log(
                action="ORCHESTRATION_RUN",
                actor="orchestrator",
                target_table="",
                target_id="",
                details={"stages": len(result.stages), "status": result.status}
            )
        except Exception:
            pass
