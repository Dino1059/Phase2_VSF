"""Accuracy eval for VietnameseNLPService against real ground-truth labels in
data/vingroup/xanh_sm_customer_feedback_dirty.csv (extracted_location,
extracted_component, severity_level columns).

Usage:
    python eval/eval_vietnamese_nlp.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.teencode.vietnamese_nlp import VietnameseNLPService

FEEDBACK_CSV = PROJECT_ROOT / "data" / "vingroup" / "xanh_sm_customer_feedback_dirty.csv"

# Ground-truth Vietnamese component label -> our internal Aspect.component name.
COMPONENT_LABEL_MAP = {
    "Trạm sạc V-GREEN": "charger",
    "Pin xe VinFast": "battery",
    "Xe VinFast VF5": "vehicle",
    "Ứng dụng di động": "app",
    "Dịch vụ tài xế": "driver",
    "Giá cước": "pricing",
}

# Ground truth uses a 3-tier business severity (CRITICAL/WARNING/INFO); we use a
# 4-tier technical fault severity (critical/high/medium/low). The two taxonomies
# aren't 1:1, so each ground-truth tier accepts the adjacent pair of our tiers
# that plausibly represents it, rather than forcing a false exact mapping.
SEVERITY_ACCEPTABLE = {
    "CRITICAL": {"critical", "high"},
    "WARNING": {"medium", "high"},
    "INFO": {"low", "medium"},
}


def _location_hit(predicted_location: str | None, ground_truth_location: str) -> bool:
    """A predicted location counts as a hit if it's a case-insensitive substring
    match either direction against the ground-truth location string."""
    if not predicted_location or not ground_truth_location:
        return False
    pred = predicted_location.strip().lower()
    truth = ground_truth_location.strip().lower()
    return pred in truth or truth in pred


def evaluate() -> dict:
    nlp = VietnameseNLPService()
    with open(FEEDBACK_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    component_hits = 0
    location_hits = 0
    location_gradeable = 0  # rows where ground-truth location actually appears in the text
    severity_hits = 0
    per_component_totals: dict[str, int] = {}
    per_component_hits: dict[str, int] = {}

    for row in rows:
        text = row["raw_comment_text"]
        result = nlp.analyze(text)
        predicted_components = {a.component for a in result.aspects}
        predicted_locations = {a.location for a in result.aspects if a.location}
        predicted_severities = {a.severity for a in result.aspects}

        expected_component = COMPONENT_LABEL_MAP.get(row["extracted_component"])
        expected_location = row["extracted_location"]
        expected_severity = row["severity_level"]

        per_component_totals[row["extracted_component"]] = per_component_totals.get(row["extracted_component"], 0) + 1

        if expected_component and expected_component in predicted_components:
            component_hits += 1
            per_component_hits[row["extracted_component"]] = per_component_hits.get(row["extracted_component"], 0) + 1

        if expected_location.lower() in text.lower():
            location_gradeable += 1
            if any(_location_hit(loc, expected_location) for loc in predicted_locations):
                location_hits += 1

        acceptable = SEVERITY_ACCEPTABLE.get(expected_severity, set())
        if predicted_severities & acceptable:
            severity_hits += 1

    return {
        "total_rows": total,
        "component_accuracy": component_hits / total,
        "location_accuracy_when_text_grounded": (location_hits / location_gradeable) if location_gradeable else None,
        "location_gradeable_rows": location_gradeable,
        "severity_tier_accuracy": severity_hits / total,
        "component_breakdown": {
            label: {"hits": per_component_hits.get(label, 0), "total": count}
            for label, count in per_component_totals.items()
        },
    }


def print_report(metrics: dict) -> None:
    print("=" * 72)
    print("Vietnamese NLP Aspect Extraction — Accuracy vs. Ground Truth")
    print(f"  Dataset: {FEEDBACK_CSV.relative_to(PROJECT_ROOT)}")
    print("=" * 72)
    print(f"Rows evaluated:                 {metrics['total_rows']}")
    print(f"Component accuracy:             {metrics['component_accuracy']:.1%}")
    if metrics["location_accuracy_when_text_grounded"] is not None:
        print(
            f"Location accuracy (text-grounded rows only, {metrics['location_gradeable_rows']}/{metrics['total_rows']}): "
            f"{metrics['location_accuracy_when_text_grounded']:.1%}"
        )
    else:
        print("Location accuracy: n/a (no text-grounded rows)")
    print(f"Severity tier accuracy:         {metrics['severity_tier_accuracy']:.1%}")
    print("-" * 72)
    print("By ground-truth component:")
    for label, stats in metrics["component_breakdown"].items():
        rate = stats["hits"] / stats["total"] if stats["total"] else 0.0
        print(f"  {label:<20} {stats['hits']:>3}/{stats['total']:<3} ({rate:.1%})")
    print("=" * 72)


if __name__ == "__main__":
    print_report(evaluate())
