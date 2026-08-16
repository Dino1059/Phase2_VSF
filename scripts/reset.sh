#!/bin/bash
set -e
echo "🔄 Resetting DataTrust OS v4..."

# Remove database
rm -f data/datatrust_v4.duckdb

# Reinitialize
cd "$(dirname "$0")/.."
uv run python -c "
from src.db.connection import get_db
db = get_db()
db.init_schema()
print('✅ Database reset and schema initialized')
"

echo "✅ Reset complete"
