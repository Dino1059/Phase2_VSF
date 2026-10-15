"""
DataTrust OS: Benchmark & Oracle Test Harness
Provides ground truth matching against fault_manifest.json (465 faults)
and lane_b_manifest.json (16 operational runs, 5 excluded archive runs).

Structure of 465 faults:
- 456 row-level: F1 (108), F2 (91), F3 (89), F5 (22), F7 (36), F8 (33), F6 (69), F14 (8)
- 6 entity-level: F10 (3), F11 (3)
- 3 aggregate: F13 (1), F15 (1), F16 (1)
Total = 456 + 6 + 3 = 465 faults.

Structure of 21 Lane B runs:
- 16 operational runs (B05, B06, B07, B11, B12, B13, B14, B15, B16, B19)
- 5 excluded archive runs (R-B08-ERR, R-B08-OK, R-B09-HOLD, R-B10-ERR, R-B10-OK) marked EXCLUDED_BY_SCOPE
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pytest

ROOT = Path(__file__).parents[2]
DATA_DIR = ROOT / "data" / "vingroup_pii_faulty_testset_3zone"
FAULT_MANIFEST_PATH = DATA_DIR / "fault_manifest.json"
LANE_B_MANIFEST_PATH = DATA_DIR / "lane_b_manifest.json"

ROW_LEVEL_FAMILIES = {
    "F1_Negative_SOC",
    "F2_Voltage_Overvoltage_Spike",
    "F3_RPM_Speed_Mismatch",
    "F5_Negative_Cost",
    "F7_Negative_Fare",
    "F8_Ledger_Mismatch",
    "F6_GPS_Alleyway_Drift",
    "F14_DurationEnergy_Mismatch",
}

ENTITY_LEVEL_FAMILIES = {
    "F10_SOC_Degradation_Drift",
    "F11_BatteryTemp_Drift",
}

AGGREGATE_FAMILIES = {
    "F13_ChargingTrip_Mismatch",
    "F15_ChargingFrequency_Shift",
    "F16_FareDistribution_Regime",
}

EXCLUDED_ARCHIVE_RUN_IDS = {
    "R-B08-ERR",
    "R-B08-OK",
    "R-B09-HOLD",
    "R-B10-ERR",
    "R-B10-OK",
}


@dataclass
class FamilyMetrics:
    family: str
    target_count: int
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0
    candidate_count: int = 0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return (self.true_positives / denom) if denom > 0 else 1.0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return (self.true_positives / denom) if denom > 0 else 1.0

    @property
    def false_positive_rate(self) -> float:
        denom = self.false_positives + self.true_negatives
        return (self.false_positives / denom) if denom > 0 else 0.0


@dataclass
class OracleBenchmarkResult:
    row_level_matches: int = 0
    row_level_target: int = 456
    entity_level_matches: int = 0
    entity_level_target: int = 6
    aggregate_matches: int = 0
    aggregate_target: int = 3
    total_manifest_faults: int = 465
    family_metrics: Dict[str, FamilyMetrics] = field(default_factory=dict)
    lane_b_operational_passed: int = 0
    lane_b_operational_target: int = 16
    lane_b_excluded_count: int = 5
    unmatched_manifest_indices: List[Tuple[str, int, str]] = field(default_factory=list)


class FaultManifestOracle:
    """
    Evaluates detector suite outputs and Lane B policy runs against ground truth manifests.
    """

    def __init__(
        self,
        fault_manifest_path: Optional[Path] = None,
        lane_b_manifest_path: Optional[Path] = None
    ):
        self.fault_manifest_path = fault_manifest_path or FAULT_MANIFEST_PATH
        self.lane_b_manifest_path = lane_b_manifest_path or LANE_B_MANIFEST_PATH
        self.fault_data = self._load_json(self.fault_manifest_path)
        self.lane_b_data = self._load_json(self.lane_b_manifest_path)
        self._classify_faults()
        self._classify_lane_b_runs()

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _classify_faults(self):
        faults = self.fault_data.get("faults", [])
        self.row_faults = [f for f in faults if f.get("fault_family") in ROW_LEVEL_FAMILIES]
        self.entity_faults = [f for f in faults if f.get("fault_family") in ENTITY_LEVEL_FAMILIES]
        self.aggregate_faults = [f for f in faults if f.get("fault_family") in AGGREGATE_FAMILIES]

        # Keyed index lookups: (dataset, original_index) -> fault
        self.row_fault_index: Dict[Tuple[str, int], Dict[str, Any]] = {
            (f["dataset"], f["original_index"]): f for f in self.row_faults
        }

    def _classify_lane_b_runs(self):
        runs = self.lane_b_data.get("runs", [])
        self.operational_runs = [r for r in runs if r["run_id"] not in EXCLUDED_ARCHIVE_RUN_IDS]
        self.excluded_runs = [r for r in runs if r["run_id"] in EXCLUDED_ARCHIVE_RUN_IDS]

    def match_row_signals(
        self,
        dataset_id: str,
        detected_indices_by_family: Dict[str, Set[int]],
        total_rows_in_dataset: int
    ) -> Dict[str, FamilyMetrics]:
        """
        Calculates precision, recall, and FPR for each row-level fault family on a dataset.
        Uses negative oracle: Candidate rows minus true manifest positives of that family.
        """
        metrics_by_family: Dict[str, FamilyMetrics] = {}
        all_candidate_indices = set(range(total_rows_in_dataset))

        # Filter row faults belonging to this dataset
        relevant_faults = [f for f in self.row_faults if f["dataset"] == dataset_id]
        families_in_ds = set(f["fault_family"] for f in relevant_faults)

        for fam in families_in_ds:
            fam_manifest_positives = set(
                f["original_index"] for f in relevant_faults if f["fault_family"] == fam
            )
            fam_detected = detected_indices_by_family.get(fam, set())

            # True Positives: in manifest AND detected
            tp_set = fam_detected & fam_manifest_positives
            # False Positives: detected BUT not in manifest for this family
            fp_set = fam_detected - fam_manifest_positives
            # False Negatives: in manifest BUT not detected
            fn_set = fam_manifest_positives - fam_detected
            # True Negatives: candidates not in manifest AND not detected
            negatives = all_candidate_indices - fam_manifest_positives
            tn_set = negatives - fam_detected

            metrics_by_family[fam] = FamilyMetrics(
                family=fam,
                target_count=len(fam_manifest_positives),
                true_positives=len(tp_set),
                false_positives=len(fp_set),
                false_negatives=len(fn_set),
                true_negatives=len(tn_set),
                candidate_count=total_rows_in_dataset,
            )

        return metrics_by_family

    def match_entity_drift(
        self,
        detected_drift_vins: Dict[str, Set[str]]
    ) -> Tuple[int, int]:
        """
        Matches L2 entity drift detections against F10 and F11 target VINs.
        detected_drift_vins: {"F10_SOC_Degradation_Drift": {vin1, ...}, "F11_BatteryTemp_Drift": {vin2, ...}}
        """
        matched = 0
        target = len(self.entity_faults)
        for ef in self.entity_faults:
            fam = ef["fault_family"]
            vin = ef["entity_id"]
            if vin in detected_drift_vins.get(fam, set()):
                matched += 1
        return matched, target

    def match_aggregate_scenarios(
        self,
        detected_scenarios: Dict[str, Set[str]]
    ) -> Tuple[int, int]:
        """
        Matches L4/L3 aggregate scenarios (F13, F15, F16) against target entity sets.
        detected_scenarios: {"F13_...": {vin1, ...}, "F15_...": {vin1, ...}, "F16_...": {driver1, ...}}
        """
        matched = 0
        target = len(self.aggregate_faults)
        for af in self.aggregate_faults:
            fam = af["fault_family"]
            target_entities = set(af.get("target_vins") or af.get("target_drivers") or [])
            detected = detected_scenarios.get(fam, set())
            if target_entities and target_entities.issubset(detected):
                matched += 1
        return matched, target

    def evaluate_lane_b_runs(
        self,
        run_verdicts: Dict[str, str]
    ) -> Tuple[int, int, Dict[str, str]]:
        """
        Evaluates run verdicts against expected_lane_b.
        Excludes 5 archive runs, marking them 'EXCLUDED_BY_SCOPE'.
        """
        passed = 0
        status_map: Dict[str, str] = {}

        # 1. Check operational runs (16)
        for r in self.operational_runs:
            run_id = r["run_id"]
            expected = r["expected_lane_b"]
            actual = run_verdicts.get(run_id)
            if actual == expected:
                passed += 1
                status_map[run_id] = "PASS"
            else:
                status_map[run_id] = f"FAIL (expected {expected}, got {actual})"

        # 2. Mark archive runs as EXCLUDED_BY_SCOPE
        for r in self.excluded_runs:
            status_map[r["run_id"]] = "EXCLUDED_BY_SCOPE"

        return passed, len(self.operational_runs), status_map


# =============================================================================
# PYTEST SUITE FOR ORACLE BENCHMARK HARNESS
# =============================================================================

def test_fault_manifest_counts_exact_breakdown():
    """Validates the exact math: 456 row-level + 6 entity + 3 aggregate = 465 total."""
    oracle = FaultManifestOracle()

    assert len(oracle.fault_data["faults"]) == 465, "Total faults must be exactly 465"
    assert len(oracle.row_faults) == 456, f"Row-level faults must be 456, got {len(oracle.row_faults)}"
    assert len(oracle.entity_faults) == 6, f"Entity-level drift faults must be 6, got {len(oracle.entity_faults)}"
    assert len(oracle.aggregate_faults) == 3, f"Aggregate scenarios must be 3, got {len(oracle.aggregate_faults)}"

    # Check individual family counts
    family_counts = {}
    for f in oracle.row_faults:
        fam = f["fault_family"]
        family_counts[fam] = family_counts.get(fam, 0) + 1

    assert family_counts["F1_Negative_SOC"] == 108
    assert family_counts["F2_Voltage_Overvoltage_Spike"] == 91
    assert family_counts["F3_RPM_Speed_Mismatch"] == 89
    assert family_counts["F5_Negative_Cost"] == 22
    assert family_counts["F7_Negative_Fare"] == 36
    assert family_counts["F8_Ledger_Mismatch"] == 33
    assert family_counts["F6_GPS_Alleyway_Drift"] == 69
    assert family_counts["F14_DurationEnergy_Mismatch"] == 8

    # Sum of row-level: 108 + 91 + 89 + 22 + 36 + 33 + 69 + 8 = 456
    assert sum(family_counts.values()) == 456


def test_lane_b_manifest_runs_breakdown():
    """Validates 16 operational runs and 5 excluded archive runs out of 21 total."""
    oracle = FaultManifestOracle()

    total_runs = len(oracle.lane_b_data["runs"])
    assert total_runs == 21, f"Expected 21 total runs in manifest, got {total_runs}"
    assert len(oracle.operational_runs) == 16, f"Expected 16 operational runs, got {len(oracle.operational_runs)}"
    assert len(oracle.excluded_runs) == 5, f"Expected 5 excluded archive runs, got {len(oracle.excluded_runs)}"

    excluded_ids = set(r["run_id"] for r in oracle.excluded_runs)
    assert excluded_ids == EXCLUDED_ARCHIVE_RUN_IDS


def test_confusion_matrix_and_metric_math():
    """Unit tests for true/false positive/negative math, precision, recall, and FPR."""
    metrics = FamilyMetrics(
        family="F1_Negative_SOC",
        target_count=100,
        true_positives=95,
        false_positives=5,
        false_negatives=5,
        true_negatives=9895,
        candidate_count=10000,
    )

    assert metrics.recall == 95 / (95 + 5)  # 0.95
    assert metrics.precision == 95 / (95 + 5)  # 0.95
    assert metrics.false_positive_rate == 5 / (5 + 9895)  # 5 / 9900 ~= 0.0005


def test_oracle_row_matching_simulation():
    """Simulates row signal matching against oracle."""
    oracle = FaultManifestOracle()

    # Create dummy detected indices that perfectly catch F5_Negative_Cost (22 rows) in acn_charging_mapped
    f5_manifest_indices = set(
        f["original_index"] for f in oracle.row_faults if f["fault_family"] == "F5_Negative_Cost"
    )
    assert len(f5_manifest_indices) == 22

    detected_map = {
        "F5_Negative_Cost": set(f5_manifest_indices),  # 100% recall
    }

    metrics = oracle.match_row_signals("acn_charging_mapped", detected_map, total_rows_in_dataset=983)
    f5_m = metrics["F5_Negative_Cost"]

    assert f5_m.true_positives == 22
    assert f5_m.false_positives == 0
    assert f5_m.false_negatives == 0
    assert f5_m.recall == 1.0
    assert f5_m.precision == 1.0
    assert f5_m.false_positive_rate == 0.0
