"""
Benchmark runner for anomaly detector evaluation.
Loads cases from cases.json, runs C0/C1/A1, outputs to eval/benchmarks/.
"""
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.reliability.benchmark.harness import BenchmarkHarness
from src.reliability.benchmark.models import BenchmarkCase, GroundTruthLabel
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.services.llm import UnifiedLLMAdapter
from typing import Literal


# Config
CASES_PATH = Path("eval/test_cases/cases.json")
OUTPUT_DIR = Path("eval/benchmarks")
CACHE_PATH = Path("eval/benchmarks/.cache/case_results_cache.json")
FAULTY_DATA_DIR = Path("data_new/vingroup_faulty_pilot_dataset")

# Dataset column mappings
DATASET_COLUMNS = {
    "synthetic_ev_telemetry_ved_ref": ["battery_soc", "battery_voltage", "battery_temp_c", "motor_rpm", "speed_kmh", "vehicle_vin"],
    "acn_charging_mapped": ["cost_vnd", "duration_mins", "kwh_consumed", "power_kw", "vehicle_vin"],
    "ride_hailing_xanh_sm_trips": ["fare_amount", "total_fare", "tip_amount", "trip_distance_km", "pickup_latitude", "pickup_longitude", "driver_id"],
}


def load_raw_data(dataset_name: str) -> dict:
    """Load actual data for a dataset."""
    csv_path = FAULTY_DATA_DIR / f"{dataset_name}.csv"
    if not csv_path.exists():
        return {}
    
    import pandas as pd
    df = pd.read_csv(csv_path)
    return df.to_dict(orient="records")


def build_incident(case: dict, row_data: dict = None) -> Incident:
    """Build an Incident from a case definition."""
    entity_id = row_data.get("vehicle_vin", case.get("dataset", "")) if row_data else case.get("dataset", "")
    
    return Incident(
        incident_id=case["case_id"],
        project_id="benchmark",
        entity_ids=[entity_id] if entity_id else ["UNKNOWN"],
        signal_ids=[case.get("signal_type", "UNKNOWN")],
        admission_reason=f"Ground truth: {case.get('fault_family', 'UNKNOWN')} - {case.get('case_name', '')}",
    )


def build_evidence(case: dict, row_data: dict = None) -> list[Evidence]:
    """Build evidence list from case and row data."""
    if row_data is None:
        return []
    
    dataset = case.get("dataset", "")
    
    # Build evidence from row data
    evidence_list = []
    for col, val in row_data.items():
        if val is not None:
            evidence_list.append(Evidence(
                evidence_id=f"{case['case_id']}_ev_{col}",
                source_id=dataset,
                source_type="csv_row",
                entity_ids=[str(val)],
                content_hash=f"hash_{col}_{val}",
                summary=f"Column {col} = {val}",
            ))
    
    return evidence_list


def load_cases() -> list[BenchmarkCase]:
    """Load cases from cases.json."""
    with open(CASES_PATH, encoding="utf-8") as f:
        raw_cases = json.load(f)
    
    # Load raw data for each dataset
    datasets = {}
    for case in raw_cases:
        ds = case.get("dataset", "")
        if ds and ds not in datasets:
            datasets[ds] = load_raw_data(ds)
    
    benchmark_cases = []
    for raw_case in raw_cases:
        # Get row data if available
        ds = raw_case.get("dataset", "")
        idx = raw_case.get("original_index")
        row_data = None
        if ds in datasets and idx is not None and idx < len(datasets[ds]):
            row_data = datasets[ds][idx]
        
        # Build ground truth
        gt_data = raw_case.get("ground_truth", {})
        gt = GroundTruthLabel(
            correct_classification=gt_data.get("correct_classification", "DATA"),
            correct_claim_keywords=gt_data.get("correct_claim_keywords", []),
            is_false_positive=gt_data.get("is_false_positive", False),
            notes=gt_data.get("notes"),
        )
        
        # Build case
        bc = BenchmarkCase(
            case_id=raw_case["case_id"],
            case_name=raw_case.get("case_name", ""),
            description=raw_case.get("case_name", ""),
            incident=build_incident(raw_case, row_data),
            evidence=build_evidence(raw_case, row_data),
            ground_truth=gt,
            category=raw_case.get("category", "L1_RULE"),
            difficulty=raw_case.get("difficulty", "MEDIUM"),
            expected_investigator=raw_case.get("expected_investigator", "A1"),
        )
        benchmark_cases.append(bc)
    
    return benchmark_cases


def check_llm():
    """Performs a 1-shot connectivity check to verify LLM provider and credentials with minimal tokens."""
    print("\n[*] Checking LLM Connectivity (dry run)...")
    adapter = UnifiedLLMAdapter()
    print(f"    - Google API Keys detected: {len(adapter._google_keys._keys)}")
    print(f"    - OpenAI Key set: {bool(adapter.openai_key and not adapter.openai_key.startswith('sk-your-'))}")
    print(f"    - OpenRouter Key set: {bool(adapter.openrouter_key)}")
    print(f"    - Ollama Available: {adapter._check_ollama()}")
    print(f"    - Selected Model: {adapter.model}")
    
    t0 = datetime.now()
    resp = adapter.chat([{"role": "user", "content": "Respond with only: PONG"}])
    elapsed_ms = (datetime.now() - t0).total_seconds() * 1000
    print(f"    [OK] Response: '{resp.content.strip()}' (Model: {resp.model_used}, Latency: {elapsed_ms:.1f}ms, Tokens: {resp.tokens_used})")


def main():
    parser = argparse.ArgumentParser(description="Anomaly Detector Benchmark Runner")
    parser.add_argument("--check-llm", action="store_true", help="Perform a 1-shot LLM connectivity check and exit")
    parser.add_argument("--no-cache", action="store_true", help="Disable case-level caching and re-run all cases")
    parser.add_argument("--clear-cache", action="store_true", help="Clear the existing case cache before running")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of cases to evaluate (e.g. --limit 1 for a quick test)")
    parser.add_argument("--no-c1", action="store_true", help="Disable C1 fixed LLM investigator")
    args = parser.parse_args()

    if args.check_llm:
        check_llm()
        return

    print("=" * 70)
    print("Anomaly Detector Benchmark Runner")
    print("=" * 70)

    if args.clear_cache and CACHE_PATH.exists():
        CACHE_PATH.unlink()
        print(f"[*] Cleared cache at: {CACHE_PATH}")

    # Load cases
    print(f"\n[*] Loading cases from: {CASES_PATH}")
    cases = load_cases()
    if args.limit:
        cases = cases[:args.limit]
        print(f"    Limited to first {len(cases)} benchmark cases")
    else:
        print(f"    Loaded {len(cases)} benchmark cases")

    # Group by category
    from collections import Counter
    by_cat = Counter(c.category for c in cases)
    for cat, count in sorted(by_cat.items()):
        print(f"    - {cat}: {count}")

    # Initialize harness
    print("\n[*] Initializing benchmark harness...")
    use_cache = not args.no_cache
    enable_c1 = not args.no_c1
    print(f"    - Investigators: C0 (Deterministic), C1 ({'Live LLM' if enable_c1 else 'Disabled'}), A1 (Dynamic Bounded)")
    print(f"    - Caching: {'ENABLED (' + str(CACHE_PATH) + ')' if use_cache else 'DISABLED'}")
    
    harness = BenchmarkHarness(
        enable_c0=True,
        enable_c1=enable_c1,
        enable_a1=True,
        max_a1_tool_calls=3,
        max_a1_tokens=1000,
        max_a1_wallclock_sec=15.0,
    )

    # Run benchmark with per-case caching
    print("\n[*] Running benchmark...")
    print("    (Using cache to resume or prevent duplicate LLM calls)")
    results = harness.run_all(cases, use_cache=use_cache, cache_path=CACHE_PATH)

    # Generate output filename
    output_path = OUTPUT_DIR / "rca_benchmark.json"

    # Save results
    print(f"\n[*] Saving results to: {output_path}")
    harness.save_results(results, str(output_path))

    # Print summary
    print("\n")
    harness.print_summary(results)

    print(f"\n[OK] Benchmark complete. Results: {output_path}")


if __name__ == "__main__":
    main()
