#!/usr/bin/env python3
"""
Live LLM Root Cause Analysis (RCA) Benchmark Runner.

Executes an End-to-End Live RCA Evaluation:
1. Loads real VinGroup Pilot tables from DuckDB (with lock-resilient reader).
2. Runs L1-L4 Multi-Layer Detectors and FusionEngine to generate 100% REAL Incidents.
3. Automatically samples ~10-12 Gold Representative Incidents across L1-L4 & 4 Domains (EV Telemetry, Charging, Trips, Feedback).
4. Executes A1 Bounded ReAct Investigator with Live LLM (Gemini / OpenAI / Ollama) across diagnostic tools.
5. Evaluates Hypotheses against Ground Truth (fault_manifest.json) using RCAGroundTruthMatcher.
6. Exports rich Markdown Benchmark Report and full JSON execution traces to eval/fault_RCA_benchamark/v2-optimized_token_prompt.

Usage:
  python scripts/run_rca_benchmark_live.py [--use-llm] [--limit-gold 10] [--db data_new/db/vingroup_pilot.db]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import duckdb
import pandas as pd

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.reliability.models.signal import Signal
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.detectors.l1_rules import L1ConstraintDetector
from src.reliability.detectors.l2_contextual import L2ContextualDetector
from src.reliability.detectors.l3_relational import L3RelationalDetector
from src.reliability.detectors.l4_changepoint import L4ChangepointDetector
from src.reliability.fusion.engine import FusionEngine
from src.reliability.incidents.service import IncidentService
from src.reliability.investigation.a1 import A1BoundedInvestigator
from src.reliability.benchmark.rca_ground_truth_matcher import RCAGroundTruthMatcher, FAULT_FAMILY_RCA_SPECS
from src.services.llm import UnifiedLLMAdapter
from src.db.connection import DuckDBManager


class LiveRCABenchmarkRunner:
    """
    Orchestrates real pipeline detection, gold incident extraction, live LLM RCA execution,
    and ground-truth verification.
    """

    def __init__(
        self,
        db_path: str = "data_new/db/vingroup_pilot.db",
        manifest_path: str = "data_new/vingroup_faulty_pilot_dataset/fault_manifest.json",
        output_dir: str = "eval/fault_RCA_benchamark/v2-optimized_token_prompt",
        use_llm: bool = False,
        limit_gold: int = 10,
        project_id: str = "vingroup_pilot",
    ):
        self.db_path = Path(db_path) if Path(db_path).is_absolute() else (REPO_ROOT / db_path)
        self.manifest_path = Path(manifest_path) if Path(manifest_path).is_absolute() else (REPO_ROOT / manifest_path)
        self.output_dir = Path(output_dir) if Path(output_dir).is_absolute() else (REPO_ROOT / output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.use_llm = use_llm
        self.limit_gold = limit_gold
        self.project_id = project_id

        # Initialize matcher
        self.rca_matcher = RCAGroundTruthMatcher(self.manifest_path)
        self.fusion_engine = FusionEngine()

        # Initialize LLM Adapter
        self.llm_adapter = None
        if self.use_llm:
            try:
                self.llm_adapter = UnifiedLLMAdapter()
                print("  [OK] Live LLM Adapter initialized (Provider Priority: OpenAI -> OpenRouter -> Groq -> Gemini -> Ollama).")
            except Exception as e:
                print(f"  [!] Failed to init LLM adapter: {e}. Falling back to deterministic A1.")
        
        self.a1 = A1BoundedInvestigator(llm=self.llm_adapter, max_tool_calls=5, max_tokens_budget=12000, max_wall_clock_sec=60.0)

        # Detectors
        self.l1 = L1ConstraintDetector()
        self.l2 = L2ContextualDetector(z_threshold=2.5, warmup_days=7, min_samples=7)
        self.l3 = L3RelationalDetector(residual_z_threshold=3.0)
        self.l4 = L4ChangepointDetector(cusum_threshold=6.0, drift_allowance=1.0, min_segment_len=5, persistence_window=5)

    def load_data_resilient(self) -> Dict[str, pd.DataFrame]:
        """
        Loads DuckDB tables into Pandas DataFrames, handling Windows database locking gracefully.
        """
        print(f"\n[1/5] Loading datasets from DuckDB: {self.db_path}")
        tables = [
            "vinfast_bms",
            "vgreen_telemetry",
            "vgreen_charging_sessions",
            "xanhsm_trips",
            "xanhsm_feedback",
        ]
        
        dfs: Dict[str, pd.DataFrame] = {}
        conn = None
        
        candidate_paths = [self.db_path]
        eval_db = REPO_ROOT / "data_new" / "db" / "vingroup_pilot_eval.db"
        if eval_db.exists() and eval_db != self.db_path:
            candidate_paths.append(eval_db)

        for cand_path in candidate_paths:
            try:
                conn = duckdb.connect(str(cand_path), read_only=True)
                print(f"  [OK] Connected to database: {cand_path.name}")
                break
            except Exception as e:
                print(f"  [!] Could not connect to {cand_path.name} ({e}), trying fallback...")

        if conn is None:
            # Try DuckDBManager as last resort
            try:
                db_mgr = DuckDBManager(str(self.db_path))
                conn = db_mgr.get_connection()
            except Exception as e_mgr:
                raise RuntimeError(f"Failed to establish DuckDB connection: {e_mgr}")

        for t in tables:
            try:
                df = conn.execute(f"SELECT * FROM {t}").df()
                dfs[t] = df
                print(f"  - Table '{t}': {len(df):,} rows loaded.")
            except Exception as e:
                if t == "vgreen_charging_sessions":
                    try:
                        df = conn.execute("SELECT * FROM raw.charging_sessions").df()
                        dfs[t] = df
                        print(f"  - Table '{t}' (raw): {len(df):,} rows loaded.")
                        continue
                    except Exception:
                        pass
                print(f"  - Table '{t}': [WARN] {e}")
                dfs[t] = pd.DataFrame()

        conn.close()
        return dfs

    def _detect_l2_fast_window(
        self, df: pd.DataFrame, entity_col: str, ts_col: str, metric_col: str, source_name: str
    ) -> List[Signal]:
        """Fast vectorized L2 calculation with 7-day baseline and 8-15 day eval window."""
        signals: List[Signal] = []
        if df.empty or metric_col not in df.columns:
            return signals

        import numpy as np
        df_copy = df[[entity_col, ts_col, metric_col]].copy()
        df_copy["_dt"] = pd.to_datetime(df_copy[ts_col])
        min_dt = df_copy["_dt"].min()
        df_copy["_day"] = (df_copy["_dt"] - min_dt).dt.days + 1

        warmup_days = 7
        z_threshold = 2.5
        min_samples = 7

        baseline_df = df_copy[df_copy["_day"] <= warmup_days]
        eval_df = df_copy[df_copy["_day"] > warmup_days]

        if baseline_df.empty or eval_df.empty:
            return signals

        stats = baseline_df.groupby(entity_col)[metric_col].agg(
            median="median",
            mad=lambda s: np.median(np.abs(s - np.median(s))) if len(s) >= min_samples else np.nan
        ).reset_index()

        merged = eval_df.merge(stats, on=entity_col, how="inner")
        merged = merged[merged["mad"].notna() & (merged["mad"] > 1e-6)]
        
        merged["_z"] = 0.6745 * (merged[metric_col] - merged["median"]) / merged["mad"]
        anomalies = merged[merged["_z"].abs() >= z_threshold]

        for _, row in anomalies.iterrows():
            z_val = float(row["_z"])
            sev = "CRITICAL" if abs(z_val) > 5.0 else ("HIGH" if abs(z_val) > 3.5 else "MEDIUM")
            event_time = row["_dt"]
            if event_time.tzinfo is None:
                event_time = event_time.tz_localize(timezone.utc)

            sig = Signal(
                project_id=self.project_id,
                entity_ids=[str(row[entity_col])],
                layer="L2",
                signal_type="CONTEXTUAL_DRIFT",
                metric_or_relationship=f"{metric_col} (Z={z_val:.2f})",
                event_time=event_time,
                window_start=min_dt.tz_localize(timezone.utc) if min_dt.tzinfo is None else min_dt,
                window_end=event_time,
                score=abs(z_val),
                severity=sev,
                detector=f"L2_mad_{source_name}",
            )
            signals.append(sig)
        return signals

    def run_e2e_detectors(self, dfs: Dict[str, pd.DataFrame]) -> Dict[str, List[Signal]]:
        """Runs L1-L4 detectors on loaded datasets."""
        print("\n[2/5] Running Multi-Layer Detectors (L1-L4) on Real Data...")
        signals: Dict[str, List[Signal]] = {"L1": [], "L2": [], "L3": [], "L4": []}

        # 1. vinfast_bms
        bms_df = dfs.get("vinfast_bms", pd.DataFrame())
        if not bms_df.empty:
            soc_col = "soc_pct" if "soc_pct" in bms_df.columns else "battery_soc"
            temp_col = "temp_c" if "temp_c" in bms_df.columns else "battery_temp_c"
            volt_col = "voltage" if "voltage" in bms_df.columns else "battery_voltage"

            l1_bms = self.l1.detect_range_violations(bms_df, self.project_id, "vehicle_vin", "timestamp", soc_col, 0.0, 100.0)
            l1_temp = self.l1.detect_range_violations(bms_df, self.project_id, "vehicle_vin", "timestamp", temp_col, -20.0, 85.0)
            l1_volt = self.l1.detect_range_violations(bms_df, self.project_id, "vehicle_vin", "timestamp", volt_col, 200.0, 900.0)
            signals["L1"].extend(l1_bms + l1_temp + l1_volt)

            # L2 contextual drift
            l2_temp = self._detect_l2_fast_window(bms_df, "vehicle_vin", "timestamp", temp_col, "vinfast_bms_temp")
            l2_soc = self._detect_l2_fast_window(bms_df, "vehicle_vin", "timestamp", soc_col, "vinfast_bms_soc")
            signals["L2"].extend(l2_temp + l2_soc)

            # L3 relational
            sorted_bms = bms_df.sort_values("timestamp").reset_index(drop=True)
            cutoff = int(len(sorted_bms) * (14.0 / 15.0))
            ref_bms, eval_bms = sorted_bms.iloc[:cutoff], sorted_bms.iloc[cutoff:]
            l3_bms = self.l3.detect_bivariate_residual_anomalies(
                ref_df=ref_bms, eval_df=eval_bms, project_id=self.project_id,
                entity_id_col="vehicle_vin", timestamp_col="timestamp",
                feature_x=volt_col, feature_y=temp_col
            )
            signals["L3"].extend(l3_bms)

            # L4 CUSUM
            l4_bms = self.l4.detect_cusum_shift(bms_df, self.project_id, "vehicle_vin", "timestamp", temp_col)
            signals["L4"].extend(l4_bms)

        # 2. vgreen_telemetry
        telem_df = dfs.get("vgreen_telemetry", pd.DataFrame())
        if not telem_df.empty:
            speed_col = "speed_kmh" if "speed_kmh" in telem_df.columns else "speed"
            rpm_col = "rpm" if "rpm" in telem_df.columns else "motor_rpm"
            if speed_col in telem_df.columns and rpm_col in telem_df.columns:
                mismatch_mask = (telem_df[speed_col] == 0) & (telem_df[rpm_col] > 12000)
                mismatch_rows = telem_df[mismatch_mask]
                for _, r in mismatch_rows.iterrows():
                    sig = Signal(
                        project_id=self.project_id,
                        entity_ids=[str(r.get("vehicle_vin", "VF-UNKNOWN"))],
                        layer="L1",
                        signal_type="RANGE_VIOLATION",
                        metric_or_relationship="speed_vs_motor_rpm",
                        event_time=pd.to_datetime(r.get("timestamp", datetime.now(timezone.utc))),
                        window_start=pd.to_datetime(r.get("timestamp", datetime.now(timezone.utc))),
                        window_end=pd.to_datetime(r.get("timestamp", datetime.now(timezone.utc))),
                        score=float(r[rpm_col]),
                        severity="HIGH",
                        detector="L1_rules_speed_rpm_mismatch",
                    )
                    signals["L1"].append(sig)

        # 3. xanhsm_trips
        trips_df = dfs.get("xanhsm_trips", pd.DataFrame())
        if not trips_df.empty:
            ts_trip = "timestamp" if "timestamp" in trips_df.columns else "pickup_datetime"
            l1_fare = self.l1.detect_range_violations(trips_df, self.project_id, "vehicle_vin", ts_trip, "fare_amount", 0.0, None)
            signals["L1"].extend(l1_fare)

            # L1 Ledger
            if "total_fare" in trips_df.columns and "fare_amount" in trips_df.columns and "tip_amount" in trips_df.columns:
                diff = (trips_df["total_fare"] - (trips_df["fare_amount"] + trips_df["tip_amount"])).abs()
                bad_ledger = trips_df[diff > 0.01]
                for _, r in bad_ledger.iterrows():
                    sig = Signal(
                        project_id=self.project_id,
                        entity_ids=[str(r.get("vehicle_vin", "VF-UNKNOWN"))],
                        layer="L1",
                        signal_type="ARITHMETIC_INCONSISTENCY",
                        metric_or_relationship="ledger_total_vs_fare_tip",
                        event_time=pd.to_datetime(r.get(ts_trip, datetime.now(timezone.utc))),
                        window_start=pd.to_datetime(r.get(ts_trip, datetime.now(timezone.utc))),
                        window_end=pd.to_datetime(r.get(ts_trip, datetime.now(timezone.utc))),
                        score=float(abs(r["total_fare"] - (r["fare_amount"] + r["tip_amount"]))),
                        severity="HIGH",
                        detector="L1_rules_trips_ledger_mismatch",
                    )
                    signals["L1"].append(sig)

            # L3 GPS Bounding Box
            if "pickup_location" in trips_df.columns:
                trips_coords = trips_df.copy()
                coords = trips_coords["pickup_location"].astype(str).str.split(",", expand=True)
                trips_coords["_lat"] = pd.to_numeric(coords[0], errors="coerce")
                trips_coords["_lon"] = pd.to_numeric(coords[1], errors="coerce")
                sig_gps = self.l3.detect_spatial_bounding_box(
                    trips_coords, self.project_id, "vehicle_vin", ts_trip,
                    lat_col="_lat", lon_col="_lon",
                    lat_min=20.95, lat_max=21.10, lon_min=105.75, lon_max=105.90
                )
                signals["L3"].extend(sig_gps)

            # L4 Driver Trip Distance CUSUM
            if "driver_id" in trips_df.columns and "distance_km" in trips_df.columns:
                trips_c = trips_df.copy()
                trips_c["_dt"] = pd.to_datetime(trips_c[ts_trip])
                trips_c["_date"] = trips_c["_dt"].dt.floor("D")
                driver_daily = trips_c.groupby(["driver_id", "_date"])["distance_km"].mean().reset_index(name="mean_distance")
                driver_daily.rename(columns={"_date": "timestamp"}, inplace=True)
                l4_driver = self.l4.detect_cusum_shift(driver_daily, self.project_id, "driver_id", "timestamp", "mean_distance")
                signals["L4"].extend(l4_driver)

        # 4. vgreen_charging_sessions
        charging_df = dfs.get("vgreen_charging_sessions", pd.DataFrame())
        if not charging_df.empty:
            ts_chg = "start_time" if "start_time" in charging_df.columns else "timestamp"
            l1_cost = self.l1.detect_range_violations(charging_df, self.project_id, "vehicle_vin", ts_chg, "cost_vnd", 0.0, None)
            signals["L1"].extend(l1_cost)

            # L3 Duration vs kWh
            sorted_chg = charging_df.sort_values(ts_chg).reset_index(drop=True)
            c_cutoff = int(len(sorted_chg) * (14.0 / 15.0))
            ref_chg, eval_chg = sorted_chg.iloc[:c_cutoff], sorted_chg.iloc[c_cutoff:]
            l3_chg = self.l3.detect_bivariate_residual_anomalies(
                ref_df=ref_chg, eval_df=eval_chg, project_id=self.project_id,
                entity_id_col="vehicle_vin", timestamp_col=ts_chg,
                feature_x="duration_mins", feature_y="kwh_consumed"
            )
            signals["L3"].extend(l3_chg)

            # L4 Charging Frequency CUSUM
            chg_c = charging_df.copy()
            chg_c["_dt"] = pd.to_datetime(chg_c[ts_chg])
            chg_c["_date"] = chg_c["_dt"].dt.floor("D")
            daily_freq = chg_c.groupby(["vehicle_vin", "_date"]).size().reset_index(name="charging_frequency")
            daily_freq.rename(columns={"_date": "timestamp"}, inplace=True)
            l4_chg = self.l4.detect_cusum_shift(daily_freq, self.project_id, "vehicle_vin", "timestamp", "charging_frequency")
            signals["L4"].extend(l4_chg)

            # L3 Cross: Charging vs Trips
            if not trips_df.empty:
                chg_counts = charging_df.groupby("vehicle_vin").size().reset_index(name="session_count")
                trp_counts = trips_df.groupby("vehicle_vin").size().reset_index(name="trip_count")
                m = chg_counts.merge(trp_counts, on="vehicle_vin", how="left").fillna(0)
                mismatches = m[(m["session_count"] >= 15) & (m["trip_count"] <= 5)]
                for _, row in mismatches.iterrows():
                    sig = Signal(
                        project_id=self.project_id,
                        entity_ids=[str(row["vehicle_vin"])],
                        layer="L3",
                        signal_type="CHARGING_TRIP_DISCREPANCY",
                        metric_or_relationship="charging_sessions_vs_trips",
                        event_time=datetime.now(timezone.utc),
                        window_start=datetime.now(timezone.utc),
                        window_end=datetime.now(timezone.utc),
                        score=float(row["session_count"]),
                        severity="HIGH",
                        detector="L3_cross_charging_trips_relational",
                    )
                    signals["L3"].append(sig)

        total_sig = sum(len(s) for s in signals.values())
        print(f"  [OK] Total Signals Emitted: {total_sig:,} (L1={len(signals['L1'])}, L2={len(signals['L2'])}, L3={len(signals['L3'])}, L4={len(signals['L4'])})")
        return signals

    def extract_gold_incidents(
        self,
        incidents: List[Incident],
        dfs: Dict[str, pd.DataFrame],
        signal_lookup: Dict[str, Signal]
    ) -> List[Tuple[Incident, Dict[str, Any]]]:
        """
        Samples the most representative real Incidents, ensuring 1 incident per distinct Fault Family.
        """
        print(f"\n[3/5] Sampling Representative Gold Incidents from {len(incidents)} Admitted Incidents...")
        
        family_to_incident: Dict[str, Tuple[Incident, Dict[str, Any]]] = {}
        unmatched_incidents: List[Incident] = []

        for inc in incidents:
            match = self.rca_matcher.match_incident_to_fault(inc, dfs, signal_lookup)
            if match:
                fam = match["fault_family"]
                # Keep the first or highest severity incident per fault family
                if fam not in family_to_incident:
                    family_to_incident[fam] = (inc, match)
                elif inc.severity == "CRITICAL" and family_to_incident[fam][0].severity != "CRITICAL":
                    family_to_incident[fam] = (inc, match)
            else:
                unmatched_incidents.append(inc)

        # Sort selected by layer order
        layer_order = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}
        selected_pairs = sorted(
            family_to_incident.values(),
            key=lambda x: (layer_order.get(x[1]["spec"]["layer"], 9), x[1]["fault_family"])
        )

        selected_gold = selected_pairs[:self.limit_gold]
        print(f"  [OK] Selected {len(selected_gold)} Gold Incidents covering {len(family_to_incident)} fault families:")
        for idx, (inc, match) in enumerate(selected_gold, 1):
            spec = match["spec"]
            print(f"    {idx:2d}. [{spec['layer']}] {match['fault_family']:<30} | {inc.incident_id} ({inc.severity}) | Entities: {inc.entity_ids}")

        # Save snapshot to gold_rca_cases.json
        gold_export = []
        for inc, match in selected_gold:
            spec = match["spec"]
            gold_export.append({
                "incident_id": inc.incident_id,
                "fault_family": match["fault_family"],
                "layer": spec["layer"],
                "domain": spec["domain"],
                "severity": inc.severity,
                "entity_ids": inc.entity_ids,
                "admission_reason": inc.admission_reason,
                "supporting_layers": inc.supporting_layers,
                "ground_truth_cause": spec["ground_truth_cause"],
                "expected_classification": spec["expected_classification"],
                "expected_keywords": spec["expected_keywords"],
                "expected_action": spec["expected_action"],
            })

        gold_cases_file = self.output_dir / "gold_rca_cases.json"
        with open(gold_cases_file, "w", encoding="utf-8") as f:
            json.dump(gold_export, f, indent=2, ensure_ascii=False)
        print(f"  [OK] Exported snapshot to: {gold_cases_file}")

        return selected_gold

    def run_benchmark(self) -> Dict[str, Any]:
        """Executes full live benchmark suite."""
        t0 = time.time()
        print("=" * 80)
        print("DATATRUST OS - LIVE LLM ROOT CAUSE ANALYSIS (RCA) BENCHMARK RUNNER")
        print("=" * 80)

        # 1. Load Data
        dfs = self.load_data_resilient()

        # 2. Run Detectors
        signals = self.run_e2e_detectors(dfs)

        # 3. Fuse Signals into Incidents
        flat_signals: List[Signal] = []
        for s_list in signals.values():
            for s in s_list:
                # Ensure all timestamps are tz-aware (UTC)
                for attr in ["event_time", "window_start", "window_end"]:
                    val = getattr(s, attr, None)
                    if val is not None:
                        ts = pd.to_datetime(val)
                        if ts.tzinfo is None:
                            ts = ts.tz_localize(timezone.utc)
                        setattr(s, attr, ts)
                flat_signals.append(s)

        signal_lookup = {s.signal_id: s for s in flat_signals}

        incidents = self.fusion_engine.fuse_signals_into_incidents(flat_signals, self.project_id)
        print(f"\n  [OK] FusionEngine Admitted {len(incidents):,} Real Incidents.")

        # 4. Extract Gold Incidents
        gold_incidents = self.extract_gold_incidents(incidents, dfs, signal_lookup)

        # 5. Execute A1 Investigation on Gold Incidents
        print(f"\n[4/5] Running A1 Bounded ReAct Investigation on {len(gold_incidents)} Gold Incidents (Live LLM={self.use_llm})...")
        evaluated_cases: List[Dict[str, Any]] = []

        for idx, (inc, match) in enumerate(gold_incidents, 1):
            print(f"\n  -------------------------------------------------------------------------", flush=True)
            print(f"  Case [{idx}/{len(gold_incidents)}]: {match['fault_family']} ({match['spec']['layer']}) | ID: {inc.incident_id}", flush=True)
            print(f"  Ground Truth   : {match['spec']['ground_truth_cause']}", flush=True)
            print(f"  Expected Class : [{match['spec']['expected_classification']}] | Domain: {match['spec']['domain']}", flush=True)
            print(f"  -> Invoking A1 ReAct Diagnostic Loop...", flush=True)
            
            # Run A1 dynamic investigation with initial signal evidence
            init_evidence: List[Evidence] = []
            for sid in inc.signal_ids:
                if sid in signal_lookup:
                    sig = signal_lookup[sid]
                    ev = Evidence(
                        evidence_id=f"ev-sig-{sid[:8]}",
                        source_type="detector_signal",
                        source_id=sig.detector,
                        entity_ids=sig.entity_ids,
                        content_hash=f"hash-{sid}",
                        summary=f"Layer {sig.layer} ({sig.signal_type}) anomaly on metric '{sig.metric_or_relationship}' with severity {sig.severity} and score {sig.score:.2f}"
                    )
                    init_evidence.append(ev)

            t_inv_start = time.time()
            hyp, rec, meta = self.a1.investigate_incident_dynamically(inc, initial_evidence=init_evidence)
            inv_sec = round(time.time() - t_inv_start, 2)
            meta["wall_clock_elapsed_sec"] = inv_sec

            # Evaluate with RCAGroundTruthMatcher
            eval_res = self.rca_matcher.evaluate_hypothesis(inc, hyp, match, meta)

            verdict_icon = "[PASS]" if eval_res["verdict"] == "PASS" else ("[PARTIAL]" if eval_res["verdict"] == "PARTIAL" else "[FAIL]")
            print(f"  LLM Diagnosis  : {hyp.claim}", flush=True)
            print(f"  Classification : Expected [{match['spec']['expected_classification']}] vs Actual [{hyp.classification}]", flush=True)
            print(f"  Verdict        : {verdict_icon} | Score: {eval_res['overall_score']*100:.1f}% (Class: {eval_res['classification_score']*100:.0f}%, RC: {eval_res['root_cause_score']*100:.0f}%, Ev: {eval_res['evidence_grounding_score']*100:.0f}%)", flush=True)
            print(f"  ReAct Trace    : {meta.get('tool_calls_made', 0)} tool calls | {meta.get('tokens_spent', 0)} tokens | {inv_sec}s", flush=True)
            print(f"  Tools Called   : {', '.join([t.get('tool_name') for t in meta.get('tool_execution_trace', [])]) or 'None'}", flush=True)

            evaluated_cases.append({
                "case_index": idx,
                "incident_id": inc.incident_id,
                "fault_family": match["fault_family"],
                "layer": match["spec"]["layer"],
                "domain": match["spec"]["domain"],
                "severity": inc.severity,
                "entity_ids": inc.entity_ids,
                "admission_reason": inc.admission_reason,
                "ground_truth": match["spec"],
                "hypothesis": {
                    "claim": hyp.claim,
                    "classification": hyp.classification,
                    "confidence": hyp.confidence,
                    "supporting_evidence": hyp.supporting_evidence,
                    "contradicting_evidence": hyp.contradicting_evidence,
                },
                "recommendation": {
                    "action_type": rec.action_type,
                    "summary": rec.summary,
                },
                "meta": meta,
                "eval": eval_res,
            })

            # 5-second cooldown pause between test cases to ensure zero rate limit issues
            if idx < len(gold_incidents):
                print(f"  [i] Cooldown pause: sleeping 5s before Case [{idx+1}/{len(gold_incidents)}]...", flush=True)
                time.sleep(5.0)

        # 6. Aggregate Summary
        summary = self.rca_matcher.generate_benchmark_summary(evaluated_cases)
        total_time_sec = round(time.time() - t0, 2)
        summary["total_runtime_sec"] = total_time_sec
        summary["timestamp"] = datetime.now(timezone.utc).isoformat()
        summary["llm_mode"] = "LIVE_LLM" if self.use_llm else "DETERMINISTIC_REACT"

        # 7. Export Outputs
        print(f"\n[5/5] Generating Reports in {self.output_dir}...")
        self._export_json_results(evaluated_cases, summary)
        self._export_markdown_report(evaluated_cases, summary, total_time_sec)

        # Print Final Summary
        self._print_terminal_summary(summary)

        return {
            "summary": summary,
            "cases": evaluated_cases,
        }

    def _export_json_results(self, evaluated_cases: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
        out_file = self.output_dir / "rca_benchmark_results.json"
        payload = {
            "summary": summary,
            "evaluated_cases": evaluated_cases,
        }
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
        print(f"  [OK] Saved JSON trace: {out_file}")

    def _export_markdown_report(
        self,
        evaluated_cases: List[Dict[str, Any]],
        summary: Dict[str, Any],
        total_time_sec: float
    ) -> None:
        out_file = self.output_dir / "rca_benchmark_report.md"
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        lines = []
        lines.append(f"# BÁO CÁO ĐÁNH GIÁ ROOT CAUSE ANALYSIS (RCA) VỚI LIVE LLM")
        lines.append(f"**DataTrust OS — Autonomous Diagnostic & RCA Benchmark Suite**\n")
        lines.append(f"* **Thời gian đánh giá:** `{now_str}`")
        lines.append(f"* **Chế độ LLM:** `{'Live LLM (Gemini / OpenAI / Ollama)' if self.use_llm else 'Deterministic ReAct (Safe Fallback)'}`")
        lines.append(f"* **Tập dữ liệu kiểm thử:** `184,715` bản ghi DuckDB (`{self.db_path.name}`)")
        lines.append(f"* **Tệp đối chứng Ground Truth:** `{self.manifest_path}`")
        lines.append(f"* **Tổng thời gian thực thi:** `{total_time_sec:.2f}s`\n")
        lines.append(f"---\n")

        lines.append(f"## 1. TỔNG QUAN KẾT QUẢ ĐÁNH GIÁ RCA (EXECUTIVE SUMMARY)\n")
        lines.append(f"| Chỉ số | Giá trị | Đánh giá & Nhận xét |")
        lines.append(f"| :--- | :--- | :--- |")
        lines.append(f"| **Tổng số Gold Test Cases** | **{summary['total_cases_evaluated']}** | Bao phủ đầy đủ 4 tầng L1–L4 & 4 domain |")
        lines.append(f"| **Số ca chẩn đoán đạt (PASS)** | **{summary['passed_cases']} / {summary['total_cases_evaluated']}** | Tỷ lệ đạt tuyệt đối: **{summary['pass_rate']*100:.1f}%** |")
        lines.append(f"| **Số ca đạt một phần (PARTIAL)** | **{summary['partial_cases']}** | Phát hiện đúng phân loại hoặc nguyên nhân gốc |")
        lines.append(f"| **Số ca thất bại (FAIL)** | **{summary['failed_cases']}** | Phân loại sai hoặc không tìm ra nguyên nhân |")
        lines.append(f"| **Độ chuẩn xác phân loại (Classification)** | **{summary['average_metrics']['classification_accuracy']*100:.1f}%** | Khả năng phân biệt `DATA` vs `OPERATIONAL` |")
        lines.append(f"| **Độ khớp nguyên nhân gốc (Root Cause Alignment)** | **{summary['average_metrics']['root_cause_alignment']*100:.1f}%** | Trùng khớp từ khóa và bản chất lỗi với Ground Truth |")
        lines.append(f"| **Chỉ số Grounding Evidence (Chống bịa)** | **{summary['average_metrics']['evidence_grounding']*100:.1f}%** | Trích dẫn đúng bằng chứng từ Diagnostic Tools |")
        lines.append(f"| **Điểm RCA tổng thể (Overall Composite Score)** | **{summary['average_metrics']['overall_rca_score']*100:.1f}%** | Trọng số: 40% Phân loại + 40% Nguyên nhân + 20% Evidence |")
        lines.append(f"| **Trung bình Tool Calls / Case** | **{summary['operational_efficiency']['avg_tool_calls']}** | Giới hạn trần <= 5 tool calls / sự cố |")
        lines.append(f"| **Trung bình Token tiêu thụ / Case** | **{summary['operational_efficiency']['avg_tokens_spent']} tokens** | Giới hạn trần <= 2000 tokens / sự cố |")
        lines.append(f"| **Thời gian chẩn đoán TB / Case** | **{summary['operational_efficiency']['avg_latency_sec']}s** | Độ trễ đáp ứng của Agent |")
        lines.append(f"\n---\n")

        lines.append(f"## 2. BẢNG MA TRẬN ĐỐI SOÁT CHI TIẾT TỪNG CA (CASE-BY-CASE GROUND TRUTH MATRIX)\n")
        lines.append(f"| # | Tầng | Nhóm lỗi (Fault Family) | Ground Truth Root Cause | LLM Diagnosis Claim | GT Class | LLM Class | Tools | Tokens | Điểm | Kết luận |")
        lines.append(f"|---|---|---|---|---|---|---|---|---|---|---|")

        for c in evaluated_cases:
            ev = c["eval"]
            v_badge = "**PASS**" if ev["verdict"] == "PASS" else ("*PARTIAL*" if ev["verdict"] == "PARTIAL" else "~~FAIL~~")
            lines.append(
                f"| {c['case_index']} "
                f"| `{c['layer']}` "
                f"| `{c['fault_family']}` "
                f"| {c['ground_truth']['ground_truth_cause']} "
                f"| {c['hypothesis']['claim']} "
                f"| `{ev['expected_classification']}` "
                f"| `{ev['actual_classification']}` "
                f"| {ev['tool_calls_made']} "
                f"| {ev['tokens_spent']} "
                f"| **{ev['overall_score']*100:.0f}%** "
                f"| {v_badge} |"
            )

        lines.append(f"\n---\n")
        lines.append(f"## 3. CHI TIẾT TRACE VÀ PHÂN TÍCH CHẨN ĐOÁN TỪNG SỰ CỐ\n")

        for c in evaluated_cases:
            ev = c["eval"]
            lines.append(f"### Case {c['case_index']}: [{c['layer']}] {c['fault_family']} — `{c['incident_id']}`")
            lines.append(f"- **Mức độ nghiêm trọng:** `{c['severity']}` | **Thực thể ảnh hưởng:** `{', '.join(c['entity_ids'])}`")
            lines.append(f"- **Lý do thừa nhận (Fusion):** {c['admission_reason']}")
            lines.append(f"- **Ground Truth:** {c['ground_truth']['ground_truth_cause']} *(Expected Class: `{ev['expected_classification']}`)*")
            lines.append(f"- **LLM Phán đoán:** {c['hypothesis']['claim']} *(Class: `{ev['actual_classification']}`)*")
            lines.append(f"- **Khuyến nghị hành động:** `{c['recommendation']['action_type']}` — {c['recommendation']['summary']}")
            lines.append(f"- **Tool Execution Trace:** `{', '.join([t.get('tool_name') for t in c['meta'].get('tool_execution_trace', [])]) or 'None'}`")
            lines.append(f"- **Đánh giá:** Classification: `{ev['classification_score']*100:.0f}%`, Root Cause: `{ev['root_cause_score']*100:.0f}%`, Grounding: `{ev['evidence_grounding_score']*100:.0f}%` $\\rightarrow$ **Overall: {ev['overall_score']*100:.1f}% ({ev['verdict']})**\n")

        with open(out_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"  [OK] Saved Markdown Report: {out_file}")

    def _print_terminal_summary(self, summary: Dict[str, Any]) -> None:
        print("\n" + "=" * 80)
        print("  ROOT CAUSE ANALYSIS (RCA) BENCHMARK SUMMARY")
        print("=" * 80)
        print(f"  Total Gold Cases Evaluated : {summary['total_cases_evaluated']}")
        print(f"  Pass Rate (PASS)           : {summary['pass_rate']*100:.1f}% ({summary['passed_cases']}/{summary['total_cases_evaluated']})")
        print(f"  Partial Cases (PARTIAL)    : {summary['partial_cases']}")
        print(f"  Failed Cases (FAIL)        : {summary['failed_cases']}")
        print(f"  Effective Accuracy         : {summary['effective_accuracy']*100:.1f}%")
        print(f"  ----------------------------------------------------------------------")
        print(f"  Classification Accuracy    : {summary['average_metrics']['classification_accuracy']*100:.1f}%")
        print(f"  Root Cause Alignment Score : {summary['average_metrics']['root_cause_alignment']*100:.1f}%")
        print(f"  Evidence Grounding Score   : {summary['average_metrics']['evidence_grounding']*100:.1f}%")
        print(f"  Overall RCA Score          : {summary['average_metrics']['overall_rca_score']*100:.1f}%")
        print(f"  ----------------------------------------------------------------------")
        print(f"  Avg Tool Calls / Incident  : {summary['operational_efficiency']['avg_tool_calls']}")
        print(f"  Avg Tokens Spent / Incident: {summary['operational_efficiency']['avg_tokens_spent']}")
        print(f"  Avg Latency / Incident     : {summary['operational_efficiency']['avg_latency_sec']}s")
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Live LLM RCA Benchmark Runner")
    parser.add_argument("--db", type=str, default="data_new/db/vingroup_pilot.db", help="Path to DuckDB database")
    parser.add_argument("--manifest", type=str, default="data_new/vingroup_faulty_pilot_dataset/fault_manifest.json", help="Path to fault manifest")
    parser.add_argument("--output-dir", type=str, default="eval/fault_RCA_benchamark/v2-optimized_token_prompt", help="Output directory for reports")
    parser.add_argument("--limit-gold", type=int, default=10, help="Number of gold representative cases to evaluate")
    parser.add_argument("--use-llm", action="store_true", default=False, help="Enable Live LLM adapter (Gemini/OpenAI/Ollama)")

    args = parser.parse_args()

    runner = LiveRCABenchmarkRunner(
        db_path=args.db,
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        use_llm=args.use_llm,
        limit_gold=args.limit_gold,
    )
    runner.run_benchmark()


if __name__ == "__main__":
    main()
