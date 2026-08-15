"""
Generate benchmark cases.json from fault_manifest.json.
Samples representative faults per family for C0/C1/A1 comparison.
"""
import json
import random
from collections import defaultdict
from pathlib import Path

# Config
MANIFEST_PATH = Path("data_new/vingroup_faulty_pilot_dataset/fault_manifest.json")
OUTPUT_PATH = Path("eval/test_cases/cases.json")
MAX_PER_FAMILY = 5  # Max cases per fault family


def load_manifest():
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_cases_from_manifest(manifest: dict) -> list[dict]:
    """Build cases from fault manifest."""
    cases = []
    faults = manifest["faults"]
    
    # Group by fault_family
    by_family = defaultdict(list)
    for f in faults:
        by_family[f["fault_family"]].append(f)
    
    # Sample and create cases
    for family, family_faults in sorted(by_family.items()):
        layer = family_faults[0].get("layer", "L1")
        dataset = family_faults[0].get("dataset", "")
        
        # Sample up to MAX_PER_FAMILY
        sampled = random.sample(
            family_faults, 
            min(MAX_PER_FAMILY, len(family_faults))
        )
        
        for i, fault in enumerate(sampled):
            case_id = f"CASE-{family}"
            if len(sampled) > 1:
                case_id += f"-{i+1}"
            
            # Determine category based on layer
            category_map = {
                "L1": "L1_RULE",
                "L2": "L2_CONTEXTUAL",
                "L3": "L3_RELATIONAL",
                "L4": "L4_CHANGEPOINT",
                "EXT_NLP": "L1_RULE",  # NLP maps to L1 for now
            }
            category = category_map.get(layer, "L1_RULE")
            
            # Difficulty based on fault complexity
            difficulty = "EASY"
            if "Mismatch" in family or "Drift" in family or "Regime" in family:
                difficulty = "MEDIUM"
            if "Frequency" in family or "Distribution" in family:
                difficulty = "HARD"
            
            # Ground truth classification based on fault family
            gt_classification = _infer_classification(family)
            
            case = {
                "case_id": case_id,
                "case_name": fault.get("description", family),
                "category": category,
                "difficulty": difficulty,
                "layer": layer,
                "fault_family": family,
                "dataset": dataset,
                "original_index": fault.get("original_index"),
                "column": fault.get("column"),
                "signal_type": fault.get("signal_type"),
                "ground_truth": {
                    "correct_classification": gt_classification,
                    "correct_claim_keywords": _extract_keywords(family, fault),
                    "is_false_positive": False,
                    "notes": fault.get("description", ""),
                },
                "expected_investigator": _expected_investigator(layer, difficulty),
            }
            cases.append(case)
    
    return cases


def _infer_classification(family: str) -> str:
    """Infer cause classification from fault family."""
    if any(x in family for x in ["SOC", "Voltage", "RPM", "Cost", "Fare", "GPS", "Duration"]):
        return "DATA"
    elif any(x in family for x in ["Drift", "Shift", "Regime", "Frequency"]):
        return "OPERATIONAL"
    elif "Mismatch" in family:
        return "MIXED"
    return "DATA"


def _extract_keywords(family: str, fault: dict) -> list[str]:
    """Extract relevant keywords for evaluation."""
    keywords = []
    
    # Extract from family name
    parts = family.replace("_", " ").split()
    keywords.extend([p.lower() for p in parts if len(p) > 2])
    
    # Extract from description
    desc = fault.get("description", "")
    if "negative" in desc.lower():
        keywords.append("negative")
    if "overvoltage" in desc.lower():
        keywords.extend(["overvoltage", "spike"])
    if "mismatch" in desc.lower():
        keywords.append("mismatch")
    if "drift" in desc.lower():
        keywords.append("drift")
    if "shift" in desc.lower():
        keywords.append("shift")
    
    return list(set(keywords))


def _expected_investigator(layer: str, difficulty: str) -> str:
    """Determine which investigator should handle this best."""
    if layer == "L1":
        return "C0"  # C0 handles L1 rules well
    elif layer in ["L2", "L3"]:
        return "A1"  # A1 handles contextual/relational
    else:  # L4
        return "A1"


def main():
    print("=" * 60)
    print("Generating benchmark cases from fault manifest")
    print("=" * 60)
    
    manifest = load_manifest()
    print(f"\nLoaded manifest: {MANIFEST_PATH}")
    print(f"Total faults: {len(manifest['faults'])}")
    
    # Build cases
    cases = build_cases_from_manifest(manifest)
    print(f"\nGenerated {len(cases)} benchmark cases")
    
    # Group by category
    by_category = defaultdict(int)
    for case in cases:
        by_category[case["category"]] += 1
    
    print("\nCases by category:")
    for cat, count in sorted(by_category.items()):
        print(f"  {cat}: {count}")
    
    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved: {OUTPUT_PATH}")


if __name__ == "__main__":
    random.seed(42)  # Reproducibility
    main()
