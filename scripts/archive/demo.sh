#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.." || exit 1

echo '=== DataTrust OS Demo — Real Data Pipeline ==='
echo ''

# Start server in background
echo '1. Starting server...'
.venv/bin/python -c "
import sys, os
sys.path.insert(0, '.')
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

# Step 1: Health check
print('\n--- Health Check ---')
r = client.get('/health')
print(f'Status: {r.status_code}')
assert r.status_code == 200

# Step 2: List datasets
print('\n--- Available Datasets ---')
r = client.get('/api/v1/datasets')
for ds in r.json()['datasets']:
    status = '✅' if ds['exists'] else '❌'
    print(f'  {status} {ds[\"key\"]:25s} {ds[\"size_mb\"]:>8.1f} MB')

# Step 3: Profile Vietnam dirty dataset (small, fast)
print('\n--- Profiling Vietnam Trips (Dirty) ---')
r = client.post('/api/v1/datasets/vietnam_trips_dirty/profile?sample_size=50000')
data = r.json()
print(f'  Rows profiled: {data[\"sample_size\"]}')
profile = data['profile']
print(f'  Columns: {profile[\"column_count\"]}')
print(f'  Null rate: {profile.get(\"overall_null_rate\", \"N/A\")}')

# Step 4: Propose rules (A1 agent)
print('\n--- Proposing Rules (A1 Agent) ---')
r = client.post('/api/v1/datasets/vietnam_trips_dirty/propose?variant=A1&sample_size=50000')
data = r.json()
print(f'  Rules generated: {data[\"rules_count\"]}')
print(f'  Generation time: {data[\"generation_time_seconds\"]}s')
for rule in data['rules'][:5]:
    print(f'    • {rule.get(\"description\", rule.get(\"rule_type\", \"rule\"))}')
if data['rules_count'] > 5:
    print(f'    ... and {data[\"rules_count\"] - 5} more')

# Step 5: Execute rules -> clean/quarantine
print('\n--- Executing Rules ---')
r = client.post('/api/v1/datasets/vietnam_trips_dirty/execute?sample_size=10000')
data = r.json()
print(f'  Input rows:      {data[\"input_rows\"]}')
print(f'  Clean rows:      {data[\"clean_rows\"]}')
print(f'  Quarantine rows: {data[\"quarantine_rows\"]}')
print(f'  Rules applied:   {data[\"rules_applied\"]}')

# Step 6: Profile NYC FHVHV (large dataset, sampled)
print('\n--- Profiling NYC FHVHV (100K sample) ---')
r = client.post('/api/v1/datasets/nyc_fhvhv/profile?sample_size=100000')
data = r.json()
print(f'  Rows profiled: {data[\"sample_size\"]}')
print(f'  Columns: {data[\"profile\"][\"column_count\"]}')

print('\n=== Demo Complete! ✅ ===')
"
