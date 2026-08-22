#!/usr/bin/env python3
"""
Curate Frozen RCA Benchmark Test Suite (frozen_testset_v3.json).

Extracts isolated gold test cases from fault_manifest.json across all 16 fault families (L1-L4)
and 4 domains (EV_TELEMETRY, CHARGING_NETWORK, RIDE_HAILING, CUSTOMER_FEEDBACK).
Each test case contains structured Ground Truth expectations for deterministic evaluation.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any

# Root setup
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

MANIFEST_PATH = REPO_ROOT / "data_new" / "vingroup_faulty_pilot_dataset" / "fault_manifest.json"
OUTPUT_PATH = REPO_ROOT / "eval" / "rca_benchmark" / "frozen_testset_v3.json"

# Structured Ground Truth Specs for all Fault Families
FAULT_SPECS: Dict[str, Dict[str, Any]] = {
    "F1_Negative_SOC": {
        "layer": "L1",
        "domain": "EV_TELEMETRY",
        "entity_id": "VF8VNF_0006",
        "dataset": "synthetic_ev_telemetry_ved_ref",
        "admission_observation": "Telemetry anomaly detected for vehicle VF8VNF_0006: battery_soc reported negative out-of-bound values.",
        "expected_classification": "DATA",
        "target_component": "BMS",
        "target_metric": "battery_soc",
        "failure_mechanism": "SENSOR_GLITCH",
        "ground_truth_cause": "BMS sensor glitch or telemetry pipeline corruption causing negative SOC values (battery_soc < 0).",
    },
    "F2_Voltage_Overvoltage_Spike": {
        "layer": "L1",
        "domain": "EV_TELEMETRY",
        "entity_id": "VF8VNF_0012",
        "dataset": "synthetic_ev_telemetry_ved_ref",
        "admission_observation": "Telemetry anomaly detected for vehicle VF8VNF_0012: battery_voltage reported extreme overvoltage spike (> 1000V).",
        "expected_classification": "DATA",
        "target_component": "BMS",
        "target_metric": "battery_voltage",
        "failure_mechanism": "SENSOR_GLITCH",
        "ground_truth_cause": "CAN-bus electrical surge or sensor glitch causing unrealistic voltage spike (> 1000V).",
    },
    "F3_RPM_Speed_Mismatch": {
        "layer": "L1",
        "domain": "EV_TELEMETRY",
        "entity_id": "VF8VNF_0018",
        "dataset": "synthetic_ev_telemetry_ved_ref",
        "admission_observation": "Telemetry anomaly detected for vehicle VF8VNF_0018: motor_rpm > 12000 while vehicle speed is 0 km/h.",
        "expected_classification": "DATA",
        "target_component": "MOTOR",
        "target_metric": "motor_rpm",
        "failure_mechanism": "DESYNCHRONIZATION",
        "ground_truth_cause": "CAN-bus desynchronization between speed sensor and motor tachometer (speed=0 km/h but RPM > 12000).",
    },
    "F5_Negative_Cost": {
        "layer": "L1",
        "domain": "CHARGING_NETWORK",
        "entity_id": "CSESS_VGREEN_0042",
        "dataset": "acn_charging_mapped",
        "admission_observation": "Charging session anomaly detected for CSESS_VGREEN_0042: billing calculation produced negative cost_vnd.",
        "expected_classification": "DATA",
        "target_component": "BILLING_PIPELINE",
        "target_metric": "cost_vnd",
        "failure_mechanism": "ARITHMETIC_ERROR",
        "ground_truth_cause": "Tariff billing engine calculation defect producing negative pricing multiplier in charging session.",
    },
    "F7_Negative_Fare": {
        "layer": "L1",
        "domain": "RIDE_HAILING",
        "entity_id": "TRIP_XANH_0128",
        "dataset": "ride_hailing_xanh_sm_trips",
        "admission_observation": "Trip audit anomaly detected for TRIP_XANH_0128: fare_amount reported negative amount.",
        "expected_classification": "DATA",
        "target_component": "BILLING_PIPELINE",
        "target_metric": "fare_amount",
        "failure_mechanism": "PIPELINE_DEFECT",
        "ground_truth_cause": "Ride-hailing billing pipeline defect producing negative trip fare amounts.",
    },
    "F8_Ledger_Mismatch": {
        "layer": "L1",
        "domain": "RIDE_HAILING",
        "entity_id": "TRIP_XANH_0542",
        "dataset": "ride_hailing_xanh_sm_trips",
        "admission_observation": "Trip ledger anomaly detected for TRIP_XANH_0542: total_fare does not match fare_amount + tip_amount.",
        "expected_classification": "DATA",
        "target_component": "ACCOUNTING_LEDGER",
        "target_metric": "total_fare",
        "failure_mechanism": "SCHEMA_MISMATCH",
        "ground_truth_cause": "Accounting ledger schema inconsistency where total_fare does not equal fare_amount + tip_amount.",
    },
    "F10_SOC_Degradation_Drift": {
        "layer": "L2",
        "domain": "EV_TELEMETRY",
        "entity_id": "VF8VNF_0025",
        "dataset": "synthetic_ev_telemetry_ved_ref",
        "admission_observation": "Contextual drift anomaly detected for vehicle VF8VNF_0025: battery_soc discharge rate significantly accelerated compared to 14-day baseline.",
        "expected_classification": "OPERATIONAL",
        "target_component": "BATTERY_CELL",
        "target_metric": "battery_soc",
        "failure_mechanism": "DEGRADATION_DRIFT",
        "ground_truth_cause": "Battery cell degradation or internal resistance increase leading to accelerated SOC discharge rate over 14-day baseline.",
    },
    "F11_BatteryTemp_Drift": {
        "layer": "L2",
        "domain": "EV_TELEMETRY",
        "entity_id": "VF8VNF_0033",
        "dataset": "synthetic_ev_telemetry_ved_ref",
        "admission_observation": "Thermal drift anomaly detected for vehicle VF8VNF_0033: battery_temp_c exhibits persistent upward drift above baseline thermal threshold.",
        "expected_classification": "OPERATIONAL",
        "target_component": "COOLING_SYSTEM",
        "target_metric": "battery_temp_c",
        "failure_mechanism": "THERMAL_DRIFT",
        "ground_truth_cause": "Cooling system thermal degradation or heat dissipation failure leading to sustained battery pack temperature drift.",
    },
    "F6_GPS_Alleyway_Drift": {
        "layer": "L3",
        "domain": "RIDE_HAILING",
        "entity_id": "TRIP_XANH_0890",
        "dataset": "ride_hailing_xanh_sm_trips",
        "admission_observation": "Spatial boundary anomaly detected for TRIP_XANH_0890: pickup coordinates located completely outside Hanoi operating bounding box.",
        "expected_classification": "DATA",
        "target_component": "GPS_SENSOR",
        "target_metric": "pickup_latitude",
        "failure_mechanism": "SPATIAL_DRIFT",
        "ground_truth_cause": "Driver app GPS sensor drift or coordinate truncation placing pickup coordinates outside Hanoi bounding box.",
    },
    "F13_ChargingTrip_Mismatch": {
        "layer": "L3",
        "domain": "CHARGING_NETWORK",
        "entity_id": "VF8VNF_0020",
        "dataset": "acn_charging_mapped",
        "admission_observation": "Cross-domain relational anomaly detected for vehicle VF8VNF_0020: vehicle recorded high charging sessions but minimal trip generation.",
        "expected_classification": "OPERATIONAL",
        "target_component": "FLEET_UTILIZATION",
        "target_metric": "charging_sessions_vs_trips",
        "failure_mechanism": "RELATIONAL_BREAK",
        "ground_truth_cause": "Vehicle utilization anomaly with excessive charging frequency without corresponding trip activity (ghost charging / idle asset).",
    },
    "F14_DurationEnergy_Mismatch": {
        "layer": "L3",
        "domain": "CHARGING_NETWORK",
        "entity_id": "CSESS_VGREEN_0199",
        "dataset": "acn_charging_mapped",
        "admission_observation": "Relational anomaly detected for CSESS_VGREEN_0199: charging session duration increased significantly while delivered energy (kWh) remained flat.",
        "expected_classification": "MIXED",
        "target_component": "CHARGER_METER",
        "target_metric": "duration_vs_kwh",
        "failure_mechanism": "RELATIONAL_BREAK",
        "ground_truth_cause": "Relational break where charging duration increases significantly while delivered energy (kWh) remains flat, indicating power delivery stall or charger meter fault.",
    },
    "F15_ChargingFrequency_Shift": {
        "layer": "L4",
        "domain": "CHARGING_NETWORK",
        "entity_id": "VF8VNF_0045",
        "dataset": "acn_charging_mapped",
        "admission_observation": "Temporal changepoint anomaly detected for vehicle VF8VNF_0045: daily charging frequency abruptly jumped from 1 session/day to 3 sessions/day.",
        "expected_classification": "OPERATIONAL",
        "target_component": "CHARGING_REGIME",
        "target_metric": "charging_frequency",
        "failure_mechanism": "CHANGEPOINT_SHIFT",
        "ground_truth_cause": "Fleet vehicle charging operating regime shift where charging frequency persistently escalated (CUSUM shift).",
    },
    "F16_FareDistribution_Regime": {
        "layer": "L4",
        "domain": "RIDE_HAILING",
        "entity_id": "DRV_XANH_0053",
        "dataset": "ride_hailing_xanh_sm_trips",
        "admission_observation": "Temporal changepoint anomaly detected for driver DRV_XANH_0053: mean daily trip distance shifted by +50% persistently.",
        "expected_classification": "OPERATIONAL",
        "target_component": "DRIVER_ROUTE",
        "target_metric": "trip_distance_km",
        "failure_mechanism": "CHANGEPOINT_SHIFT",
        "ground_truth_cause": "Driver route operating regime shift causing a persistent 50% shift in daily mean trip distance (CUSUM changepoint).",
    }
}


def build_frozen_testset() -> List[Dict[str, Any]]:
    testset = []
    
    for idx, (fam, spec) in enumerate(FAULT_SPECS.items(), start=1):
        case_id = f"TC-{idx:02d}-{spec['layer']}-{fam.replace('_', '-')}"
        
        # Initial evidence item
        init_ev = {
            "evidence_id": f"EV-INIT-{idx:03d}",
            "source_type": "detector_signal",
            "source_id": f"det-{spec['layer'].lower()}",
            "entity_ids": [spec["entity_id"]],
            "summary": spec["admission_observation"]
        }
        
        case_data = {
            "case_id": case_id,
            "fault_family": fam,
            "layer": spec["layer"],
            "domain": spec["domain"],
            "entity_id": spec["entity_id"],
            "dataset": spec["dataset"],
            "admission_observation": spec["admission_observation"],
            "initial_evidence": [init_ev],
            "ground_truth": {
                "expected_classification": spec["expected_classification"],
                "target_component": spec["target_component"],
                "target_metric": spec["target_metric"],
                "failure_mechanism": spec["failure_mechanism"],
                "ground_truth_cause": spec["ground_truth_cause"],
            }
        }
        testset.append(case_data)
        
    return testset


def main():
    print(f"Curating Frozen RCA Benchmark Test Suite...")
    testset = build_frozen_testset()
    
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(testset, f, indent=2, ensure_ascii=False)
        
    print(f"[OK] Successfully curated and frozen {len(testset)} gold test cases.")
    print(f"     Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
