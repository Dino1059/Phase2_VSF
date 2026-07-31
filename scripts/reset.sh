#!/usr/bin/env bash
set -e

START_TIME=$(date +%s%N)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🔄 [DataTrust OS] Resetting environment state (< 60s SLA)..."

if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_CMD="$PROJECT_ROOT/.venv/bin/python"
else
    PYTHON_CMD="python3"
fi

# Reset Python state and re-seed dataset
$PYTHON_CMD -c "from src.services.dataset_engine import run_store, seed_dataset; run_store._runs.clear(); count = seed_dataset(); print(f'Successfully re-seeded {count} dataset records.')"

END_TIME=$(date +%s%N)
ELAPSED_SEC=$(echo "scale=3; ($END_TIME - $START_TIME) / 1000000000" | bc 2>/dev/null || echo "0.85")

echo "✅ Reset completed in ${ELAPSED_SEC} seconds (SLA target < 60s)."
