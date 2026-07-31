#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_CMD="$PROJECT_ROOT/.venv/bin/python"
else
    PYTHON_CMD="python3"
fi

echo "=========================================================="
echo "🚀 [DataTrust OS] End-to-End Automated System Demonstration"
echo "=========================================================="

$PYTHON_CMD - << 'EOF'
import sys
import json
from fastapi.testclient import TestClient
from src.main import app

with TestClient(app) as client:
    print("\n--- 1. Testing Health Endpoint ---")
    resp = client.get("/health")
    assert resp.status_code == 200, resp.text
    print(f"✅ Health Status: {resp.json()}")

    sample_data = [
        {"trip_id": 1, "driver_pay": 10.0, "trip_miles": 5.0, "PULocationID": 10, "DOLocationID": 15},
        {"trip_id": 2, "driver_pay": None, "trip_miles": 10.0, "PULocationID": 20, "DOLocationID": 25},
        {"trip_id": 2, "driver_pay": 15.0, "trip_miles": 10.0, "PULocationID": 20, "DOLocationID": 25},
        {"trip_id": 4, "driver_pay": -5.0, "trip_miles": 999.0, "PULocationID": 30, "DOLocationID": 35},
        {"trip_id": 5, "driver_pay": 100.0, "trip_miles": 0.0, "PULocationID": 40, "DOLocationID": 40},
    ]

    print("\n--- 2. Profiling Dataset ---")
    resp = client.post("/api/profile", json={"data": sample_data})
    assert resp.status_code == 200, resp.text
    prof = resp.json()
    print(f"✅ Row Count: {prof['row_count']} | Column Count: {prof['column_count']} | Duplicates: {prof['duplicate_count']}")

    print("\n--- 3. Running Rule Proposal (Baseline A1 - DataTrust OS AI) ---")
    resp = client.post("/api/rules/propose", json={"data": sample_data, "variant": "A1"})
    assert resp.status_code == 200, resp.text
    prop = resp.json()
    print(f"✅ Variant: {prop['variant']} | Proposed Rules Count: {len(prop['rules'])}")
    for r in prop['rules']:
        print(f"  • [{r['rule_id']}] {r['rule_type']} on {r['target_column']} -> {r['action']}")

    print("\n--- 4. Executing Approved Rule Transformations ---")
    exec_payload = {"data": sample_data, "rules": prop['rules']}
    resp = client.post("/api/transform/execute", json=exec_payload)
    assert resp.status_code == 200, resp.text
    exec_res = resp.json()
    print(f"✅ Initial Rows: {exec_res['initial_rows']} | Clean Rows: {exec_res['clean_rows']} | Quarantine Rows: {exec_res['quarantine_rows']}")
    print(f"✅ Execution Time: {exec_res['execution_time_sec']}s")

    print("\n--- 5. Resetting Environment (<60s SLA) ---")
    resp = client.post("/api/reset")
    assert resp.status_code == 200, resp.text
    reset_res = resp.json()
    print(f"✅ Reset Status: {reset_res['status']} in {reset_res['reset_time_sec']}s")

print("\n=========================================================="
      "\n🎉 DataTrust OS Automated Demo Completed Cleanly & Successfully!"
      "\n==========================================================")
EOF


