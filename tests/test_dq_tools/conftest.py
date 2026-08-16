import json
import sqlite3

import pytest


@pytest.fixture
def temp_db(tmp_path):
    """A tiny, isolated SQLite DB with one table and known-good/known-bad rows."""
    db_path = tmp_path / "source.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE trips (
            trip_id TEXT PRIMARY KEY,
            fare_amount REAL,
            status TEXT,
            pickup_datetime TEXT
        )
        """
    )
    rows = [
        ("T1", 10.0, "COMPLETED", "2026-01-01T00:00:00"),
        ("T2", -5.0, "COMPLETED", "2026-01-02T00:00:00"),  # range violation (fare < 0)
        ("T3", 20.0, "CANCELLED", "BAD_DATE"),  # date violation
        ("T4", 10.0, "COMPLETED", "2026-01-04T00:00:00"),
    ]
    conn.executemany("INSERT INTO trips VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def temp_schema(tmp_path, temp_db):
    """A profiling_report.json-shaped schema file, produced by the real Profiler Tool."""
    from src.tools.dq.profiler_tool import ProfilerInput, run_profiler

    result = run_profiler(ProfilerInput(db_path=str(temp_db)))
    assert result.status == "success", result.error_message

    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        json.dumps([t.model_dump() for t in result.tables], ensure_ascii=False), encoding="utf-8"
    )
    return schema_path
