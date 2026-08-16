#!/usr/bin/env bg
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🌱 [DataTrust OS] Seeding raw NYC taxi & ride-hailing trip dataset..."

if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_CMD="$PROJECT_ROOT/.venv/bin/python"
else
    PYTHON_CMD="python3"
fi

$PYTHON_CMD -c "from src.services.dataset_engine import seed_dataset; count = seed_dataset(); print(f'✅ Seeded {count} records into data/raw_taxi_trips.csv and data/datatrust.db')"
