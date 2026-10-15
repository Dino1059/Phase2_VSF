"""
DataTrust OS: Lane A L2 Drift & L4 Changepoint Calibration Test Suite
Verifies:
- 6/6 Entity-level drift faults (L2):
  - F10_SOC_Degradation_Drift: VF8VNF_0001, 0030, 0050 (3 VINs)
  - F11_BatteryTemp_Drift: VF8VNF_0036, 0028, 0010 (3 VINs)
- 3/3 Aggregate scenarios (L4 & L3 cross-table):
  - F13_ChargingTrip_Mismatch: 5 VINs (VF8VNF_0059, 0044, 0027, 0019, 0016)
  - F15_ChargingFrequency_Shift: 5 VINs (VF8VNF_0035, 0024, 0011, 0033, 0031)
  - F16_FareDistribution_Regime: 5 drivers (DRV_XANH_0046, 0021, 0037, 0023, 0056)
"""

from pathlib import Path
import pandas as pd
import pytest

from src.detectors.detector_suite import L1toL4DetectorSuite
from tests.benchmarks.test_fault_manifest_oracle import FaultManifestOracle

ROOT = Path(__file__).parents[1]
DATA_DIR = ROOT / "data" / "vingroup_pii_faulty_testset_3zone"


@pytest.fixture(scope="module")
def oracle():
    return FaultManifestOracle()


@pytest.fixture(scope="module")
def suite():
    return L1toL4DetectorSuite()


def test_l2_entity_drift_f10_and_f11(oracle, suite):
    """Verifies F10 (3 VINs) and F11 (3 VINs) entity drift detections against oracle."""
    df_telem = pd.read_csv(DATA_DIR / "synthetic_ev_telemetry_ved_ref.csv")

    f10_vins = suite.detect_f10_soc_drift_vins(df_telem)
    f11_vins = suite.detect_f11_temp_drift_vins(df_telem)

    detected_drift = {
        "F10_SOC_Degradation_Drift": f10_vins,
        "F11_BatteryTemp_Drift": f11_vins,
    }

    matched, target = oracle.match_entity_drift(detected_drift)
    assert target == 6, f"Expected 6 entity drift targets, got {target}"
    assert matched == 6, f"Expected 6/6 entity drift matched, got {matched}/6"

    # Exact sets verification
    assert f10_vins == {"VF8VNF_0001", "VF8VNF_0030", "VF8VNF_0050"}
    assert f11_vins == {"VF8VNF_0036", "VF8VNF_0028", "VF8VNF_0010"}


def test_l4_and_l3_all_aggregate_scenarios(oracle, suite):
    """Verifies all 3 aggregate scenarios (F13, F15, F16) against oracle."""
    df_charging = pd.read_csv(DATA_DIR / "acn_charging_mapped.csv")
    df_trips = pd.read_csv(DATA_DIR / "ride_hailing_xanh_sm_trips.csv")

    batch_id = "batch_20261015_aggregate_run"
    context = {
        "trips_daily_counts": df_trips.groupby(["vehicle_vin", "assigned_day_index"]).size().to_dict(),
        "trips_batch_id": batch_id,
        "charging_batch_id": batch_id,
    }

    f13_vins = suite.detect_f13_aggregate_vins(df_charging, context)
    f15_vins = suite.detect_f15_charging_frequency_shift_vins(df_charging)
    f16_drivers = suite.detect_f16_trip_distance_regime_drivers(df_trips)

    detected_scenarios = {
        "F13_ChargingTrip_Mismatch": f13_vins,
        "F15_ChargingFrequency_Shift": f15_vins,
        "F16_FareDistribution_Regime": f16_drivers,
    }

    matched, target = oracle.match_aggregate_scenarios(detected_scenarios)
    assert target == 3, f"Expected 3 aggregate scenarios, got {target}"
    assert matched == 3, f"Expected 3/3 aggregate scenarios matched, got {matched}/3"

    assert f13_vins == {"VF8VNF_0059", "VF8VNF_0044", "VF8VNF_0027", "VF8VNF_0019", "VF8VNF_0016"}
    assert f15_vins == {"VF8VNF_0035", "VF8VNF_0024", "VF8VNF_0011", "VF8VNF_0033", "VF8VNF_0031"}
    assert {"DRV_XANH_0046", "DRV_XANH_0021", "DRV_XANH_0037", "DRV_XANH_0023", "DRV_XANH_0056"}.issubset(f16_drivers)
