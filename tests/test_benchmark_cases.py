"""Unit tests for Phase 2 Benchmark Test Cases and Harness loading."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from eval.benchmark import BenchmarkHarness
from eval.fault_injector import FaultInjector

CASES_JSON_PATH = Path(__file__).parent.parent / "eval" / "test_cases" / "cases.json"


def test_cases_json_file_exists_and_valid():
    assert CASES_JSON_PATH.exists(), f"Cases JSON file missing at {CASES_JSON_PATH}"
    with open(CASES_JSON_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    assert isinstance(cases, list)
    assert len(cases) >= 40, f"Expected >= 40 test cases, found {len(cases)}"


def test_cases_cover_all_fault_families():
    with open(CASES_JSON_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    families = {c["fault_family"] for c in cases}
    expected_families = set(FaultInjector.FAULT_FAMILIES)

    missing = expected_families - families
    assert not missing, f"Missing fault families in cases.json: {missing}"
    assert len(families) == 9, "Expected 9 fault families"


def test_cases_schema_and_difficulty():
    required_fields = {
        "case_id", "name", "fault_family", "target_table",
        "target_column", "ground_truth_fault_id", "description",
        "difficulty", "seed"
    }
    with open(CASES_JSON_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    valid_difficulties = {"easy", "medium", "hard"}
    for case in cases:
        missing_fields = required_fields - set(case.keys())
        assert not missing_fields, f"Case {case.get('case_id')} missing fields: {missing_fields}"
        assert case["difficulty"] in valid_difficulties, f"Invalid difficulty: {case['difficulty']}"


def test_cases_fault_family_counts():
    with open(CASES_JSON_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    family_counts: dict[str, int] = {}
    for c in cases:
        ff = c["fault_family"]
        family_counts[ff] = family_counts.get(ff, 0) + 1

    expected_min_counts = {
        "type_error": 5,
        "range_error": 5,
        "referential_error": 4,
        "temporal_error": 4,
        "geographic_error": 4,
        "financial_error": 4,
        "business_error": 4,
        "privacy_error": 5,
        "distribution_shift": 5,
    }

    for ff, min_cnt in expected_min_counts.items():
        cnt = family_counts.get(ff, 0)
        assert cnt >= min_cnt, f"Expected >={min_cnt} cases for family '{ff}', got {cnt}"


def test_benchmark_harness_loads_and_runs_all_cases():
    harness = BenchmarkHarness(cases_path=CASES_JSON_PATH)
    assert len(harness.test_cases) >= 40
    assert len(harness.injector.injected) >= 40

    results = harness.run_all()

    assert "C0" in results
    assert "C1" in results
    assert "A1" in results

    c0 = results["C0"]
    c1 = results["C1"]
    a1 = results["A1"]

    assert c0.faults_total >= 40
    assert c1.faults_total >= 40
    assert a1.faults_total >= 40

    # A1 achieves 100% recall over all 40 ground truth faults
    assert a1.faults_detected == a1.faults_total
    assert a1.recall == 1.0
    assert a1.precision >= 0.80

    # C0 detects type_error and range_error
    assert c0.faults_detected < a1.faults_detected
    assert c0.recall < a1.recall

    # C1 detects type, range, referential, financial
    assert c1.faults_detected > c0.faults_detected
    assert c1.faults_detected < a1.faults_detected
