from __future__ import annotations
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any

import pandas as pd

from src.services.llm import GemmaLLMAdapter
from src.agents.profiler_agent import ProfilerAgent
from src.agents.anomaly_agent import AnomalyAgent
from src.agents.diagnosis_agent import DiagnosisAgent
from src.agents.rule_proposer_agent import RuleProposerAgent
from src.agents.executor_agent import ExecutorAgent
from src.db.connection import get_db

logger = logging.getLogger(__name__)


def _notify(progress_callback: Optional[Callable[[str, str, dict], None]], stage: str, message: str, metadata: Optional[dict] = None):
    msg = f"⚡ [Orchestrator] [{stage}] {message}"
    print(msg, flush=True)
    logger.info(msg)
    if progress_callback:
        try:
            progress_callback(stage, message, metadata or {})
        except Exception as exc:
            logger.warning(f"progress_callback error: {exc}")


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
    "ev_telemetry": {
        "entity_id_col": "vehicle_vin",
        "timestamp_col": "timestamp",
        "metric_col": "battery_soc",
        "relational_x": "battery_voltage",
        "relational_y": "battery_current",
        "l1_min": 0.0,
        "l1_max": 100.0,
        "l1_required_cols": ["battery_voltage", "battery_current", "battery_temp_c"],
    },
    "raw.ev_telemetry": {
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
    "charging_sessions": {
        "entity_id_col": "vehicle_vin",
        "timestamp_col": "start_time",
        "metric_col": "station_temp_c",
        "relational_x": "power_kw",
        "relational_y": "kwh_consumed",
        "l1_min": -20.0,
        "l1_max": 80.0,
        "l1_required_cols": ["kwh_consumed", "power_kw"],
    },
    "raw.charging_sessions": {
        "entity_id_col": "vehicle_vin",
        "timestamp_col": "start_time",
        "metric_col": "station_temp_c",
        "relational_x": "power_kw",
        "relational_y": "kwh_consumed",
        "l1_min": -20.0,
        "l1_max": 80.0,
        "l1_required_cols": ["kwh_consumed", "power_kw"],
    },
    "acn_charging": {
        "entity_id_col": "vehicle_vin",
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
        "relational_x": "trip_distance_km",
        "relational_y": "fare_amount",
        "l1_min": 0.0,
        "l1_max": None,
        "l1_required_cols": ["fare_amount", "trip_distance_km"],
    },
    "trips": {
        "entity_id_col": "vehicle_vin",
        "timestamp_col": "pickup_datetime",
        "metric_col": "fare_amount",
        "relational_x": "trip_distance_km",
        "relational_y": "fare_amount",
        "l1_min": 0.0,
        "l1_max": None,
        "l1_required_cols": ["fare_amount", "trip_distance_km"],
    },
    "raw.trips": {
        "entity_id_col": "vehicle_vin",
        "timestamp_col": "pickup_datetime",
        "metric_col": "fare_amount",
        "relational_x": "trip_distance_km",
        "relational_y": "fare_amount",
        "l1_min": 0.0,
        "l1_max": None,
        "l1_required_cols": ["fare_amount", "trip_distance_km"],
    },
    "ride_trips": {
        "entity_id_col": "vehicle_vin",
        "timestamp_col": "pickup_datetime",
        "metric_col": "fare_amount",
        "relational_x": "trip_distance_km",
        "relational_y": "fare_amount",
        "l1_min": 0.0,
        "l1_max": None,
        "l1_required_cols": ["fare_amount", "trip_distance_km"],
    },
}


# Mapping from logical table name (used in _TABLE_SIGNAL_CONFIG / batch callers)
# to the dataset_table value stored in the landing parquet.
_PARQUET_TABLE_ALIAS: dict[str, str] = {
    "vinfast_ev_telemetry": "ev_telemetry",
    "vinfast_ev_telemetry_dirty": "ev_telemetry",
    "raw.ev_telemetry": "ev_telemetry",
    "ev_telemetry": "ev_telemetry",
    "vinfast_bms": "ev_telemetry",

    "vgreen_charging_sessions": "acn_charging",
    "vgreen_charging_stations": "acn_charging",
    "vgreen_charging_stations_dirty": "acn_charging",
    "raw.charging_sessions": "acn_charging",
    "charging_sessions": "acn_charging",
    "acn_charging": "acn_charging",

    "xanh_sm_trips": "ride_trips",
    "xanh_sm_trips_dirty": "ride_trips",
    "raw.trips": "ride_trips",
    "trips": "ride_trips",
    "ride_trips": "ride_trips",

    "xanh_sm_customer_feedback": "feedback",
    "xanh_sm_customer_feedback_dirty": "feedback",
    "raw.nlp_feedback": "feedback",
    "nlp_feedback": "feedback",
    "feedback": "feedback",
    "customer_nlp": "feedback",
}


def _table_candidates(table_name: str) -> list[str]:
    aliases = {
        "vinfast_ev_telemetry_dirty": ["raw.ev_telemetry", "ev_telemetry", "vinfast_bms", "vinfast_ev_telemetry"],
        "vinfast_ev_telemetry": ["raw.ev_telemetry", "ev_telemetry", "vinfast_bms", "vinfast_ev_telemetry"],
        "vinfast_bms": ["vinfast_bms", "raw.ev_telemetry", "ev_telemetry"],
        "ev_telemetry": ["raw.ev_telemetry", "ev_telemetry", "vinfast_bms"],
        "vgreen_charging_stations_dirty": ["raw.charging_sessions", "charging_sessions", "acn_charging", "vgreen_charging_sessions"],
        "vgreen_charging_stations": ["raw.charging_sessions", "charging_sessions", "acn_charging", "vgreen_charging_sessions"],
        "vgreen_charging_sessions": ["vgreen_charging_sessions", "raw.charging_sessions", "acn_charging"],
        "acn_charging": ["raw.charging_sessions", "charging_sessions", "acn_charging"],
        "xanh_sm_trips_dirty": ["raw.trips", "trips", "ride_trips", "xanh_sm_trips"],
        "xanh_sm_trips": ["raw.trips", "trips", "ride_trips", "xanh_sm_trips"],
        "ride_trips": ["raw.trips", "trips", "ride_trips"],
        "xanh_sm_customer_feedback_dirty": ["raw.nlp_feedback", "nlp_feedback", "feedback", "xanhsm_feedback"],
        "xanh_sm_customer_feedback": ["raw.nlp_feedback", "nlp_feedback", "feedback", "xanhsm_feedback"],
        "customer_nlp": ["raw.nlp_feedback", "nlp_feedback", "feedback", "xanhsm_feedback"],
        "nlp_feedback": ["raw.nlp_feedback", "nlp_feedback", "feedback"],
    }
    cands = list(aliases.get(table_name, [table_name]))
    if table_name not in cands:
        cands.append(table_name)
    if not table_name.startswith("raw."):
        cands.append(f"raw.{table_name}")
    return cands


def _load_table_as_dataframe(
    table_name: str,
    project_id: str,
    db_path: Optional[str] = None,
    target_day_idx: int | None = None,
    window_days: int = 10,
) -> pd.DataFrame:
    import duckdb

    # --- Day-aware landing-parquet path (added in Giai đoạn 2) ---
    from src.config import get_settings
    from src.db.connection import get_db
    landing_rel = get_settings().landing_parquet_path
    try:
        root = get_db().project_root
        LANDING_PARQUET = os.path.join(root, landing_rel).replace("\\", "/") if not os.path.isabs(landing_rel) else landing_rel.replace("\\", "/")
    except Exception:
        LANDING_PARQUET = landing_rel.replace("\\", "/")

    if target_day_idx is not None and os.path.exists(LANDING_PARQUET):
        day_min = max(0, target_day_idx - window_days)
        day_max = target_day_idx
        # Try both the logical table name and its parquet alias
        pq_table_names = [
            table_name,
            _PARQUET_TABLE_ALIAS.get(table_name, table_name),
        ]
        for pq_name in dict.fromkeys(pq_table_names):  # deduplicate
            try:
                con = duckdb.connect()
                try:
                    df = con.execute(f"""
                        SELECT *
                        FROM read_parquet('{LANDING_PARQUET}')
                        WHERE day_idx >= {day_min} AND day_idx <= {day_max}
                          AND dataset_table = '{pq_name}'
                    """).df()
                    if not df.empty:
                        return df
                finally:
                    con.close()
            except Exception:
                pass

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

    tbl_names = _table_candidates(table_name)
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
                for tbl in tbl_names:
                    try:
                        df = conn.execute(f'SELECT * FROM {tbl}').df()
                        if not df.empty:
                            return df
                    except Exception:
                        pass
            else:
                try:
                    conn = duckdb.connect(candidate, read_only=True)
                except Exception:
                    conn = duckdb.connect(candidate)
                try:
                    for tbl in tbl_names:
                        try:
                            df = conn.execute(f'SELECT * FROM {tbl}').df()
                            if not df.empty:
                                return df
                        except Exception:
                            pass
                finally:
                    conn.close()
        except Exception as exc:
            last_exc = exc
            continue

    try:
        from src.services.dataset_engine import load_dataset
        df = load_dataset(dataset_key=table_name)
        if not df.empty:
            return df
    except Exception:
        pass

    if last_exc is not None:
        raise last_exc
    return pd.DataFrame()


def _auto_signal_config(table_name: str, df: pd.DataFrame) -> dict:
    """
    Heuristic auto-config for tables that are not in `_TABLE_SIGNAL_CONFIG`.

    Picks:
      - entity_id_col: first column whose name suggests a vehicle/station/driver id
      - timestamp_col: first parseable datetime column
      - metric_col:    first numeric column (excluding the chosen id / timestamp cols)
      - relational_x/y: first two remaining numeric columns
      - l1_min/max:    None → no hard range; rely on null checks only
    """
    if df.empty:
        return {}

    id_keywords = ("vin", "vehicle", "entity", "driver", "station", "id", "device")
    ts_keywords = ("time", "date", "ts", "timestamp", "datetime", "pickup", "start")

    cols = list(df.columns)
    entity_col = None
    for c in cols:
        cl = str(c).lower()
        if any(k in cl for k in id_keywords):
            entity_col = c
            break
    if not entity_col:
        entity_col = cols[0]

    ts_col = None
    for c in cols:
        if c == entity_col:
            continue
        cl = str(c).lower()
        if any(k in cl for k in ts_keywords):
            ts_col = c
            break
    if not ts_col:
        # Try the first non-id column and validate it can be parsed as datetime
        for c in cols:
            if c == entity_col:
                continue
            try:
                parsed = pd.to_datetime(df[c], errors="coerce")
                if parsed.notna().sum() > max(1, len(df) // 2):
                    ts_col = c
                    break
            except Exception:
                continue
    if not ts_col:
        ts_col = entity_col  # best-effort fallback

    numeric_cols = [
        c for c in cols
        if c not in (entity_col, ts_col) and pd.api.types.is_numeric_dtype(df[c])
    ]
    metric_col = numeric_cols[0] if numeric_cols else None
    rel_x = numeric_cols[1] if len(numeric_cols) > 1 else None
    rel_y = numeric_cols[2] if len(numeric_cols) > 2 else None

    return {
        "entity_id_col": entity_col,
        "timestamp_col": ts_col,
        "metric_col": metric_col,
        "relational_x": rel_x,
        "relational_y": rel_y,
        "l1_min": None,
        "l1_max": None,
        "l1_required_cols": numeric_cols[:4],
        "auto": True,
    }


def _get_all_tables_for_dataset(dataset_key: Optional[str]) -> List[str]:
    """
    Return the user tables that should be analyzed for a given dataset_key.

    If dataset_key is None or the file is not a multi-table DuckDB, fall back to
    the legacy single-table key (treated as one table).
    """
    if not dataset_key:
        return []
    try:
        from src.config import get_settings
        from src.tools.datasource import StructuredSource
        settings = get_settings()
        base_key = dataset_key.split("::", 1)[0] if "::" in dataset_key else dataset_key
        file_path = settings.get_dataset_path(base_key)
        if not file_path or not os.path.exists(file_path):
            return []
        tables = StructuredSource(file_path).list_tables()
        if tables:
            return tables
    except Exception:
        pass
    return [dataset_key]


def _detect_l1_l4_signals(
    table_name: str,
    df: pd.DataFrame,
    project_id: str,
    target_day_idx: int | None = None,
    window_days: int = 10,
    progress_callback: Optional[Callable[[str, str, dict], None]] = None,
) -> dict:
    """
    Run L1-L4 detectors on the provided DataFrame and return a dict of
    {layer: List[Signal]} compatible with ReliabilityOrchestrator.run_pipeline.
    Empty signal lists are returned when column configuration is missing.

    Tables not in `_TABLE_SIGNAL_CONFIG` get a best-effort auto-config so the
    detectors can still produce useful signals.
    """
    from src.reliability.detectors.l1_rules import L1ConstraintDetector
    from src.reliability.detectors.l2_contextual import L2ContextualDetector
    from src.reliability.detectors.l3_relational import L3RelationalDetector
    from src.reliability.detectors.l4_changepoint import L4ChangepointDetector

    cfg = _TABLE_SIGNAL_CONFIG.get(table_name) or _auto_signal_config(table_name, df)
    if not cfg:
        _notify(progress_callback, "Anomaly Detect", f"Table '{table_name}': No signal config. Skipping L1-L4.", {"table": table_name})
        return {"L1": [], "L2": [], "L3": [], "L4": []}

    entity_col = cfg.get("entity_id_col")
    ts_col = cfg.get("timestamp_col")
    metric_col = cfg.get("metric_col")

    if not entity_col or not ts_col or not metric_col or df.empty:
        _notify(progress_callback, "Anomaly Detect", f"Table '{table_name}': Required signal cols missing or df empty.", {"table": table_name})
        return {"L1": [], "L2": [], "L3": [], "L4": []}

    if entity_col not in df.columns or ts_col not in df.columns or metric_col not in df.columns:
        _notify(progress_callback, "Anomaly Detect", f"Table '{table_name}': Signal cols not present in df.", {"table": table_name})
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
    except Exception as exc:
        logger.error(f"[L1 Detector] Exception on table '{table_name}': {exc}", exc_info=True)

    # L2: contextual drift via robust Z-score
    try:
        l2 = L2ContextualDetector(z_threshold=4.5, warmup_days=10, min_samples=10)
        signals["L2"].extend(l2.detect_entity_anomalies(
            df=df, project_id=project_id,
            entity_id_col=entity_col, timestamp_col=ts_col,
            metric_col=metric_col,
        ))
    except Exception as exc:
        logger.error(f"[L2 Detector] Exception on table '{table_name}': {exc}", exc_info=True)

    # L3: relational break using a simple temporal split (first 50% ref, last 50% eval)
    try:
        rel_x = cfg.get("relational_x")
        rel_y = cfg.get("relational_y")
        if rel_x and rel_y and rel_x in df.columns and rel_y in df.columns:
            sorted_df = df.sort_values(ts_col).reset_index(drop=True)
            cutoff = max(5, len(sorted_df) // 2)
            ref_df = sorted_df.iloc[:cutoff]
            eval_df = sorted_df.iloc[cutoff:]
            l3 = L3RelationalDetector(residual_z_threshold=4.5, comparator="linear_regression")
            signals["L3"].extend(l3.detect_bivariate_residual_anomalies(
                ref_df=ref_df, eval_df=eval_df,
                project_id=project_id,
                entity_id_col=entity_col, timestamp_col=ts_col,
                feature_x=rel_x, feature_y=rel_y,
            ))
    except Exception as exc:
        logger.error(f"[L3 Detector] Exception on table '{table_name}': {exc}", exc_info=True)

    # L4: CUSUM change-point
    try:
        l4 = L4ChangepointDetector(cusum_threshold=6.0, min_segment_len=3, persistence_window=3)
        signals["L4"].extend(l4.detect_cusum_shift(
            df=df, project_id=project_id,
            entity_id_col=entity_col, timestamp_col=ts_col,
            metric_col=metric_col,
        ))
    except Exception as exc:
        logger.error(f"[L4 Detector] Exception on table '{table_name}': {exc}", exc_info=True)

    # Filter signals to target_day_idx if specified and day_idx column is available
    if target_day_idx is not None and "day_idx" in df.columns:
        day_ts_series = pd.to_datetime(df[df["day_idx"] == target_day_idx][ts_col], errors="coerce").dropna()
        day_ts_set = set(day_ts_series.astype(str))
        if day_ts_set:
            for layer_key in ("L1", "L2", "L3", "L4"):
                filtered = []
                for sig in signals[layer_key]:
                    ts_str = str(pd.to_datetime(sig.event_time))
                    if ts_str in day_ts_set or any(ts_str[:16] in t for t in day_ts_set):
                        filtered.append(sig)
                signals[layer_key] = filtered

    return signals


def _run_reliability_pipeline(
    table_name: str,
    project_id: str,
    target_day_idx: int | None = None,
    window_days: int = 10,
    progress_callback: Optional[Callable[[str, str, dict], None]] = None,
) -> List[dict]:
    """
    End-to-end L1-L4 -> FusionEngine -> IncidentService -> A1BoundedInvestigator pipeline.
    Returns a list of investigation result dicts (one per admitted incident).
    Raises if the table cannot be loaded.
    """
    _notify(progress_callback, "Data Load", f"Loading dataset for table '{table_name}' (day={target_day_idx}, window={window_days})...", {"table": table_name})
    df = _load_table_as_dataframe(
        table_name, project_id=project_id,
        target_day_idx=target_day_idx, window_days=window_days,
    )
    if df.empty:
        _notify(progress_callback, "Data Load", f"Table '{table_name}' loaded 0 rows.", {"table": table_name})
        return []

    _notify(progress_callback, "Anomaly Detect", f"Table '{table_name}': Running L1-L4 detectors on {len(df)} rows...", {"table": table_name, "rows": len(df)})
    detector_outputs = _detect_l1_l4_signals(
        table_name, df, project_id,
        target_day_idx=target_day_idx, window_days=window_days,
        progress_callback=progress_callback,
    )
    total_sigs = sum(len(s) for s in detector_outputs.values())
    l1_cnt, l2_cnt, l3_cnt, l4_cnt = len(detector_outputs["L1"]), len(detector_outputs["L2"]), len(detector_outputs["L3"]), len(detector_outputs["L4"])
    _notify(progress_callback, "Anomaly Detect", f"Table '{table_name}': Detected {total_sigs} signals (L1={l1_cnt}, L2={l2_cnt}, L3={l3_cnt}, L4={l4_cnt})", {"table": table_name, "signals": total_sigs})

    if not any(detector_outputs.values()):
        return []

    from src.reliability.investigation.reliability_orchestrator import ReliabilityOrchestrator

    _notify(progress_callback, "Incident Fusion", f"Table '{table_name}': Running FusionEngine & A1 RCA on {total_sigs} signals...", {"table": table_name})
    orchestrator = ReliabilityOrchestrator()
    results = orchestrator.run_pipeline(detector_outputs, project_id=project_id)
    _notify(progress_callback, "Incident Fusion", f"Table '{table_name}': Admitted {len(results)} incidents with A1 root cause analysis.", {"table": table_name, "incidents": len(results)})

    out: List[dict] = []
    for res in results:
        out.append({
            "incident_id": res.incident.incident_id,
            "severity": res.incident.severity,
            "status": res.incident.status,
            "supporting_layers": res.incident.supporting_layers,
            "admission_reason": res.incident.admission_reason,
            "entity_ids": res.incident.entity_ids,
            "signal_ids": res.incident.signal_ids,
            "hypothesis_id": res.hypothesis.hypothesis_id if res.hypothesis else None,
            "hypothesis_claim": res.hypothesis.claim if res.hypothesis else "",
            "classification": res.hypothesis.classification if res.hypothesis else "DATA",
            "confidence": res.hypothesis.confidence if res.hypothesis else 0.88,
            "supporting_evidence": res.hypothesis.supporting_evidence if res.hypothesis else [],
            "contradicting_evidence": res.hypothesis.contradicting_evidence if res.hypothesis else [],
            "missing_evidence": res.hypothesis.missing_evidence if res.hypothesis else [],
            "recommendation_id": res.recommendation.recommendation_id if res.recommendation else None,
            "recommendation_type": getattr(res.recommendation, "recommendation_type", getattr(res.recommendation, "cause_type", "DATA")),
            "action_type": res.recommendation.action_type if res.recommendation else "QUARANTINE_DATA",
            "recommendation_summary": getattr(res.recommendation, "summary", ""),
            "meta": res.meta or {},
            "tool_trace": [t.get("tool_name") for t in (res.meta or {}).get("tool_execution_trace", [])],
            "tokens_spent": (res.meta or {}).get("tokens_spent", 0),
        })
    return out


def _detect_cross_table_signals(
    per_table_signals: dict, project_id: str, dataset_key: str = ""
) -> List:
    """
    Given {table_name: [Signal, ...]} from multiple tables, build CROSS_TABLE
    signals when the same entity_id appears in 2+ tables within a 30-minute
    time window.

    Returns a list of synthetic Signal objects tagged with
    `layer='L3'` and a `cross_table=True` attribute (set on the Signal via
    extra evidence_refs to avoid schema changes).
    """
    if not per_table_signals or len(per_table_signals) < 2:
        return []

    from datetime import timedelta
    from collections import defaultdict
    from src.reliability.models.signal import Signal

    entity_signals: "defaultdict[str, list]" = defaultdict(list)
    for table_name, sigs in per_table_signals.items():
        for sig in sigs:
            for eid in sig.entity_ids or []:
                entity_signals[eid].append((table_name, sig))

    cross_signals: List[Signal] = []
    window = timedelta(minutes=30)

    for eid, items in entity_signals.items():
        # group by overlapping window
        items_sorted = sorted(items, key=lambda x: x[1].event_time)
        used = [False] * len(items_sorted)
        for i, (t_i, s_i) in enumerate(items_sorted):
            if used[i]:
                continue
            cluster = [(t_i, s_i)]
            used[i] = True
            for j in range(i + 1, len(items_sorted)):
                if used[j]:
                    continue
                t_j, s_j = items_sorted[j]
                # Overlap check: s_j.event_time within window of cluster start..end
                cluster_start = min(c.event_time for _, c in cluster)
                cluster_end = max(c.event_time for _, c in cluster)
                if (s_j.event_time >= cluster_start - window and
                        s_j.event_time <= cluster_end + window):
                    cluster.append((t_j, s_j))
                    used[j] = True
            tables = {t for t, _ in cluster}
            if len(tables) >= 2:
                avg_score = sum(float(c.score) for _, c in cluster) / len(cluster)
                layers = sorted({c.layer for _, c in cluster})
                ev_refs = [f"{t}:{c.detector}:{c.signal_type}" for t, c in cluster]
                cluster_start = min(c.event_time for _, c in cluster)
                cluster_end = max(c.event_time for _, c in cluster)
                cross_sig = Signal(
                    project_id=project_id,
                    entity_ids=[eid],
                    layer="L3",
                    signal_type="CROSS_TABLE_CORRELATION",
                    metric_or_relationship=f"multi_table:{','.join(sorted(tables))}",
                    event_time=cluster_start,
                    window_start=cluster_start,
                    window_end=cluster_end,
                    score=round(avg_score, 2),
                    severity="HIGH",
                    detector="L3_CrossTable_Correlation",
                    detector_version="1.0.0",
                    evidence_refs=ev_refs + [f"dataset={dataset_key}", f"layers={','.join(layers)}"],
                    provenance="REAL_OPERATIONAL",
                )
                cross_signals.append(cross_sig)

    return cross_signals


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

    def run_analysis(
        self,
        dataset_key: str,
        review_text: str | None = None,
        table_name: str | None = None,
        target_day_idx: int | None = None,
        window_days: int = 10,
        progress_callback: Optional[Callable[[str, str, dict], None]] = None,
    ) -> OrchestratorResult:
        """Run the full analysis pipeline. Supports both single-table (legacy) and multi-table DuckDB datasets."""
        start = time.time()
        result = OrchestratorResult()

        _notify(progress_callback, "Analysis Pipeline", f"Starting DataTrust analysis for dataset '{dataset_key}' (day={target_day_idx}, window={window_days})...", {"dataset": dataset_key, "day": target_day_idx})

        # Stage 1: Profile (multi-table aware when dataset_key resolves to >1 table)
        all_tables = _get_all_tables_for_dataset(dataset_key)
        if table_name:
            target_tables = [table_name]
        elif all_tables:
            target_tables = all_tables
        else:
            target_tables = [dataset_key]

        _notify(progress_callback, "Stage 1: Profiling", f"Profiling {len(target_tables)} target tables: {target_tables}", {"tables": target_tables})
        profile_result = self.profiler.run(dataset_key)
        result.stages.append({
            "stage": "profiling",
            "agent": "profiler",
            "status": profile_result.status,
            "steps": len(profile_result.steps),
            "summary": profile_result.final_answer[:500],
            "tables_profiled": target_tables,
        })
        _notify(progress_callback, "Stage 1: Profiling", f"Profiling completed in {len(profile_result.steps)} steps.", {"status": profile_result.status})

        # Stage 2: Anomaly Detection (Design V2: L1-L4 -> Fusion -> Incident -> A1)
        _notify(progress_callback, "Stage 2: Anomaly Detection", f"Running L1-L4 multi-layer reliability pipeline across {len(target_tables)} tables...", {"tables": target_tables})
        anomaly_stage = self._run_anomaly_stage(
            target_tables,
            dataset_key=dataset_key,
            target_day_idx=target_day_idx,
            window_days=window_days,
            progress_callback=progress_callback,
        )
        result.stages.append(anomaly_stage)
        anomaly_findings = anomaly_stage.get("anomaly_findings", {})
        total_incidents = anomaly_stage.get("incident_count", 0)
        _notify(progress_callback, "Stage 2: Anomaly Detection", f"Anomaly detection finished: {total_incidents} incidents evaluated across tables.", {"incidents": total_incidents})

        # Stage 3: Diagnosis (if review text provided)
        if review_text:
            _notify(progress_callback, "Stage 3: Diagnosis", "Running analyst review diagnosis...", {})
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
        _notify(progress_callback, "Stage 4: Rule Proposal", "Generating data quality rule proposals based on findings...", {})
        rule_result = self.rule_proposer.run(
            dataset_key,
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

        result.status = "awaiting_approval"
        result.total_duration_ms = int((time.time() - start) * 1000)
        _notify(progress_callback, "Analysis Complete", f"DataTrust analysis completed in {result.total_duration_ms}ms.", {"duration_ms": result.total_duration_ms})

        self._log_orchestration(result)
        return result

    def _run_anomaly_stage(
        self,
        table_names,
        dataset_key: str = "",
        target_day_idx: int | None = None,
        window_days: int = 10,
        progress_callback: Optional[Callable[[str, str, dict], None]] = None,
    ) -> dict:
        """
        Run Design V2 anomaly pipeline across every table in `table_names`.
        """
        if isinstance(table_names, str):
            table_names = [table_names]
        table_names = [t for t in (table_names or []) if t]

        all_investigations: List[dict] = []
        per_table_summary: List[dict] = []
        per_table_signals_for_cross: dict = {}

        for idx, tbl in enumerate(table_names, 1):
            _notify(progress_callback, "Table Processing", f"[{idx}/{len(table_names)}] Processing table '{tbl}'...", {"table": tbl, "idx": idx, "total": len(table_names)})
            try:
                investigations = _run_reliability_pipeline(
                    table_name=tbl,
                    project_id=self.project_id,
                    target_day_idx=target_day_idx,
                    window_days=window_days,
                    progress_callback=progress_callback,
                )
            except Exception as exc:
                logger.error(f"[AnomalyStage] Failed to process table '{tbl}': {exc}", exc_info=True)
                _notify(progress_callback, "Table Processing Error", f"Table '{tbl}' failed: {exc}", {"table": tbl, "error": str(exc)})
                per_table_summary.append({
                    "table_name": tbl,
                    "status": "error",
                    "error": str(exc),
                    "incident_count": 0,
                })
                continue

            # Collect signals from this table for cross-table correlation
            try:
                df = _load_table_as_dataframe(tbl, project_id=self.project_id)
                raw_sigs = _detect_l1_l4_signals(
                    tbl, df, self.project_id,
                    target_day_idx=target_day_idx,
                    window_days=window_days,
                )
                per_table_signals_for_cross[tbl] = (
                    raw_sigs.get("L1", []) +
                    raw_sigs.get("L2", []) +
                    raw_sigs.get("L3", []) +
                    raw_sigs.get("L4", [])
                )
            except Exception:
                per_table_signals_for_cross[tbl] = []

            # Tag investigations with their source table & dataset_key so the
            # Alert Dashboard can filter by the active dataset.
            for inv in investigations:
                inv["source_table"] = tbl
                inv["dataset_key"] = dataset_key
                # Persist dataset_key / source_table into incident metadata so
                # the GET /incidents filter can use them later.
                try:
                    from src.reliability.incidents.service import IncidentService
                    existing_meta = IncidentService().get_incident_meta(inv["incident_id"]) or {}
                    existing_meta["source_table"] = tbl
                    existing_meta["dataset_key"] = dataset_key
                    IncidentService().set_incident_meta(inv["incident_id"], existing_meta)
                except Exception:
                    pass

            all_investigations.extend(investigations)
            per_table_summary.append({
                "table_name": tbl,
                "status": "completed" if investigations else "no_anomalies",
                "incident_count": len(investigations),
            })

        # Cross-table correlation (only meaningful when 2+ tables produced signals)
        cross_investigations: List[dict] = []
        cross_signals = _detect_cross_table_signals(
            per_table_signals_for_cross,
            project_id=self.project_id,
            dataset_key=dataset_key,
        )
        if cross_signals:
            try:
                from src.reliability.investigation.reliability_orchestrator import ReliabilityOrchestrator
                cross_results = ReliabilityOrchestrator().run_pipeline(
                    {"L3": cross_signals, "L1": [], "L2": [], "L4": []},
                    project_id=self.project_id,
                )
                for res in cross_results:
                    try:
                        from src.reliability.incidents.service import IncidentService
                        existing_meta = IncidentService().get_incident_meta(res.incident.incident_id) or {}
                        existing_meta["source_table"] = "+".join(per_table_signals_for_cross.keys())
                        existing_meta["dataset_key"] = dataset_key
                        existing_meta["cross_table"] = True
                        IncidentService().set_incident_meta(res.incident.incident_id, existing_meta)
                    except Exception:
                        pass
                    cross_investigations.append({
                        "incident_id": res.incident.incident_id,
                        "severity": res.incident.severity,
                        "status": res.incident.status,
                        "supporting_layers": res.incident.supporting_layers,
                        "admission_reason": res.incident.admission_reason,
                        "entity_ids": res.incident.entity_ids,
                        "signal_ids": res.incident.signal_ids,
                        "hypothesis_id": res.hypothesis.hypothesis_id if res.hypothesis else None,
                        "hypothesis_claim": res.hypothesis.claim if res.hypothesis else "",
                        "classification": res.hypothesis.classification if res.hypothesis else "DATA",
                        "confidence": res.hypothesis.confidence if res.hypothesis else 0.88,
                        "supporting_evidence": res.hypothesis.supporting_evidence if res.hypothesis else [],
                        "contradicting_evidence": res.hypothesis.contradicting_evidence if res.hypothesis else [],
                        "missing_evidence": res.hypothesis.missing_evidence if res.hypothesis else [],
                        "recommendation_id": res.recommendation.recommendation_id if res.recommendation else None,
                        "recommendation_type": getattr(res.recommendation, "recommendation_type", getattr(res.recommendation, "cause_type", "DATA")),
                        "action_type": res.recommendation.action_type if res.recommendation else "QUARANTINE_DATA",
                        "recommendation_summary": getattr(res.recommendation, "summary", ""),
                        "meta": res.meta or {},
                        "tool_trace": [t.get("tool_name") for t in (res.meta or {}).get("tool_execution_trace", [])],
                        "tokens_spent": (res.meta or {}).get("tokens_spent", 0),
                        "source_table": "+".join(per_table_signals_for_cross.keys()),
                        "dataset_key": dataset_key,
                        "cross_table": True,
                    })
            except Exception:
                cross_investigations = []

        investigations = all_investigations + cross_investigations

        incidents_payload = [
            {
                "id": inv["incident_id"],
                "incident_id": inv["incident_id"],
                "severity": inv["severity"],
                "status": inv.get("status", "OPEN"),
                "supporting_layers": inv["supporting_layers"],
                "admission_reason": inv["admission_reason"],
                "entity_ids": inv["entity_ids"],
                "target_entity": inv["entity_ids"][0] if inv["entity_ids"] else "VIN-001",
                "signal_ids": inv["signal_ids"],
                "llm_claim": inv.get("hypothesis_claim", ""),
                "llm_classification": inv.get("classification", "DATA"),
                "confidence": inv.get("confidence", 0.88),
                "hypothesis": {
                    "id": inv["hypothesis_id"],
                    "claim": inv.get("hypothesis_claim", ""),
                    "classification": inv["classification"],
                    "confidence": inv["confidence"],
                    "supporting_evidence": inv.get("supporting_evidence", []),
                    "contradicting_evidence": inv.get("contradicting_evidence", []),
                    "missing_evidence": inv.get("missing_evidence", []),
                },
                "recommendation": {
                    "id": inv["recommendation_id"],
                    "type": inv.get("recommendation_type", "DATA"),
                    "action_type": inv["action_type"],
                    "summary": inv.get("recommendation_summary", ""),
                },
                "meta": inv.get("meta", {}),
                "tool_trace": inv.get("tool_trace", []),
                "tokens_spent": inv.get("tokens_spent", 0),
                "source_table": inv.get("source_table"),
                "dataset_key": inv.get("dataset_key"),
                "cross_table": inv.get("cross_table", False),
            }
            for inv in investigations
        ]

        if not investigations:
            status = "no_anomalies"
            summary = (
                f"No L1-L4 signals admitted by FusionEngine across "
                f"{len(table_names)} table(s)."
            )
        else:
            status = "completed"
            summary = (
                f"L1-L4 detectors produced {len(all_investigations)} intra-table "
                f"incident(s) across {len(table_names)} table(s); "
                f"{len(cross_investigations)} cross-table incident(s); "
                f"A1 returned hypotheses + recommendations."
            )

        return {
            "stage": "anomaly_detection",
            "agent": "reliability_orchestrator",
            "status": status,
            "incident_count": len(investigations),
            "incidents": incidents_payload,
            "anomaly_findings": {
                "incidents": incidents_payload,
                "total_incidents": len(incidents_payload),
                "per_table": per_table_summary,
                "cross_table_count": len(cross_investigations),
            },
            "summary": summary,
            "tables_processed": table_names,
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
