"""VinGroup Sprint 2 (P0): Vietnamese NLP aspect extraction + V-GREEN hardware
cross-validation, tested against the real xanh_sm_customer_feedback_dirty and
vgreen_charging_stations_dirty datasets."""
import csv
import json
import os

import pytest

from src.teencode.vietnamese_nlp import VietnameseNLPService

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "vingroup")
FEEDBACK_CSV = os.path.join(DATA_DIR, "xanh_sm_customer_feedback_dirty.csv")
STATIONS_CSV = os.path.join(DATA_DIR, "vgreen_charging_stations_dirty.csv")
TEENCODE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "data", "teencode_dict.json"
)

pytestmark = pytest.mark.skipif(
    not (os.path.exists(FEEDBACK_CSV) and os.path.exists(STATIONS_CSV)),
    reason="VinGroup real datasets not present",
)


@pytest.fixture
def nlp():
    return VietnameseNLPService()


@pytest.fixture
def feedback_rows():
    with open(FEEDBACK_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def station_logs():
    with open(STATIONS_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_vietnamese_nlp_aspect_extraction_and_cross_validation(nlp, feedback_rows, station_logs):
    # AC1: Teen-code dictionary handles 50+ common slang terms.
    with open(TEENCODE_PATH, encoding="utf-8") as f:
        teencode = json.load(f)
    assert len(teencode) >= 50

    charger_rows = [r for r in feedback_rows if r["extracted_component"] == "Trạm sạc V-GREEN"]
    assert charger_rows, "expected charger-related feedback rows in xanh_sm_customer_feedback_dirty"

    confirmed_faults = 0
    for row in charger_rows:
        result = nlp.analyze(row["raw_comment_text"])

        # AC2: extract 3 fields accurately - Location, Component, Severity.
        charger_aspects = [a for a in result.aspects if a.component == "charger"]
        assert charger_aspects, f"no charger aspect extracted from: {row['raw_comment_text']!r}"
        assert any(a.location for a in charger_aspects), "location not extracted"
        assert all(a.severity in ("critical", "high", "medium", "low") for a in charger_aspects)

        # AC3: cross-validate against V-GREEN hardware logs; flag fault when
        # station_temp_c crosses the 85.5C thermal threshold.
        cross_val = nlp.cross_validate_with_station_logs(result, station_logs)
        assert cross_val.matched, f"feedback location did not resolve to a known station: {row['extracted_location']!r}"
        assert cross_val.station_id is not None
        if cross_val.confirmed_hardware_fault:
            confirmed_faults += 1
            assert cross_val.max_station_temp_c >= VietnameseNLPService.STATION_TEMP_THRESHOLD_C
            assert cross_val.evidence
            assert all(e["status"] == "THERMAL_FAULT" for e in cross_val.evidence)

    assert confirmed_faults > 0, "expected at least one charger complaint to cross-validate against a real thermal fault"


def test_cross_validation_no_false_match_for_non_charger_complaint(nlp, station_logs):
    result = nlp.analyze("pin xe VF8 chai nhanh quá, sạc mãi không đầy")
    cross_val = nlp.cross_validate_with_station_logs(result, station_logs)
    assert cross_val.matched is False
    assert cross_val.confirmed_hardware_fault is False


def test_cross_validation_below_threshold_is_not_confirmed(nlp):
    result = nlp.analyze("trạm sạc Landmark 81 hơi chậm")
    normal_logs = [
        {"station_id": "VG_STA_LANDMARK81", "station_temp_c": "40.0", "status": "COMPLETED"},
    ]
    cross_val = nlp.cross_validate_with_station_logs(result, normal_logs)
    assert cross_val.matched is True
    assert cross_val.threshold_exceeded is False
    assert cross_val.confirmed_hardware_fault is False


def test_eval_accuracy_gate_against_ground_truth():
    """Regression gate: field-extraction accuracy vs. the real ground-truth
    labels (extracted_component/extracted_location/severity_level) must not
    silently regress. See eval/eval_vietnamese_nlp.py for the full report."""
    from eval.eval_vietnamese_nlp import evaluate

    metrics = evaluate()
    assert metrics["component_accuracy"] >= 0.9
    assert metrics["severity_tier_accuracy"] >= 0.9
    assert metrics["location_accuracy_when_text_grounded"] is None or metrics["location_accuracy_when_text_grounded"] >= 0.9
