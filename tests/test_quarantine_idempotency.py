import os
import tempfile
import pytest
from src.db.connection import DuckDBManager
from src.tools.rule_executor import RuleExecutorTool
from src.services.dataset_engine import execute_rules_transactional


@pytest.fixture
def tmp_db(monkeypatch):
    """Create a temporary DuckDB database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = f.name
    if os.path.exists(db_path):
        os.unlink(db_path)
    db = DuckDBManager(db_path=db_path)
    db.init_schema()
    monkeypatch.setattr("src.tools.rule_executor.get_db", lambda: db)
    monkeypatch.setattr("src.services.audit.get_db", lambda: db)
    monkeypatch.setattr("src.db.connection.get_db", lambda: db)
    yield db
    db.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_quarantine_idempotency_rule_executor(tmp_db):
    """Executing the same rule against the same snapshot twice does NOT duplicate quarantine records."""
    # Seed quality rule
    tmp_db.execute(
        "INSERT INTO quality_rules (id, snapshot_id, rule_name, rule_type, rule_expression, status) VALUES (?, ?, ?, ?, ?, ?)",
        ["rule_temp_01", "snap_001", "temp_overheat", "range", "temperature_celsius < 80.0", "approved"]
    )
    # Seed telemetry rows (3 normal, 2 violating)
    for i in range(1, 6):
        temp = 90.0 if i in (2, 4) else 70.0
        tmp_db.execute(
            "INSERT INTO vgreen_telemetry (id, station_id, temperature_celsius, status) VALUES (?, ?, ?, ?)",
            [i, f"STATION-{i}", temp, "OK"]
        )

    executor = RuleExecutorTool()
    input_data = {
        "rule_id": "rule_temp_01",
        "dry_run": False,
        "snapshot_id": "snap_001",
        "rule_version_id": "v1.0"
    }

    # First execution
    res1 = executor.execute(input_data)
    assert res1["violations_found"] == 2
    assert res1["quarantined_count"] == 2

    count1 = tmp_db.execute("SELECT COUNT(*) FROM quarantine")[0][0]
    assert count1 == 2

    # Second execution (identical snapshot & rule_version)
    res2 = executor.execute(input_data)
    assert res2["violations_found"] == 2
    assert res2["quarantined_count"] == 2

    count2 = tmp_db.execute("SELECT COUNT(*) FROM quarantine")[0][0]
    assert count2 == 2, f"Idempotency failure: expected 2 quarantine records, got {count2}"

    # Check lineage columns
    rows = tmp_db.execute("SELECT snapshot_id, rule_version_id, source_row_id FROM quarantine ORDER BY source_row_id")
    assert len(rows) == 2
    assert rows[0][0] == "snap_001"
    assert rows[0][1] == "v1.0"
    assert rows[0][2] == 2
    assert rows[1][2] == 4


def test_quarantine_idempotency_dataset_engine(tmp_db):
    """execute_rules_transactional guarantees idempotency across repeated runs."""
    rows = [
        {"trip_id": "T1", "fare_amount": 15.0, "passenger_count": 2},
        {"trip_id": "T2", "fare_amount": -5.0, "passenger_count": 1},  # Anomaly
        {"trip_id": "T3", "fare_amount": 25.0, "passenger_count": 0},  # Anomaly
    ]
    rules = [
        {"rule_id": "R_FARE", "name": "Fare Positive", "expression": "fare_amount > 0", "decision": "approved"},
        {"rule_id": "R_PASS", "name": "Passengers Positive", "expression": "passenger_count > 0", "decision": "approved"},
    ]

    # Run 1
    execute_rules_transactional(
        rows=rows,
        rules=rules,
        snapshot_id="snap_ds_1",
        rule_version_id="v1.0",
        source_table="raw_taxi_trips",
        db=tmp_db
    )

    q_count_run1 = tmp_db.execute("SELECT COUNT(*) FROM quarantine WHERE snapshot_id = 'snap_ds_1'")[0][0]
    assert q_count_run1 == 2

    # Run 2 (duplicate execution)
    execute_rules_transactional(
        rows=rows,
        rules=rules,
        snapshot_id="snap_ds_1",
        rule_version_id="v1.0",
        source_table="raw_taxi_trips",
        db=tmp_db
    )

    q_count_run2 = tmp_db.execute("SELECT COUNT(*) FROM quarantine WHERE snapshot_id = 'snap_ds_1'")[0][0]
    assert q_count_run2 == 2, "Repeated dataset rule execution must be idempotent"


def test_quarantine_atomic_transaction(tmp_db):
    """Rule execution, quarantine insertion, and audit log write atomically inside a single transaction."""
    tmp_db.execute(
        "INSERT INTO quality_rules (id, snapshot_id, rule_name, rule_type, rule_expression, status) VALUES (?, ?, ?, ?, ?, ?)",
        ["rule_atomic", "snap_atomic", "voltage_check", "range", "voltage > 200.0", "approved"]
    )
    tmp_db.execute(
        "INSERT INTO vgreen_telemetry (id, station_id, voltage, status) VALUES (?, ?, ?, ?)",
        [101, "STATION-101", 150.0, "FAULT"]
    )

    audit_count_before = tmp_db.execute("SELECT COUNT(*) FROM audit_log")[0][0]
    q_count_before = tmp_db.execute("SELECT COUNT(*) FROM quarantine")[0][0]

    executor = RuleExecutorTool()
    res = executor.execute({
        "rule_id": "rule_atomic",
        "dry_run": False,
        "snapshot_id": "snap_atomic",
        "rule_version_id": "v1.0"
    })

    audit_count_after = tmp_db.execute("SELECT COUNT(*) FROM audit_log")[0][0]
    q_count_after = tmp_db.execute("SELECT COUNT(*) FROM quarantine")[0][0]

    assert res["quarantined_count"] == 1
    assert q_count_after == q_count_before + 1
    assert audit_count_after == audit_count_before + 1


def test_quarantine_chunked_batch_insertion(tmp_db):
    """Batch insertions are processed in 500-row chunks correctly."""
    rows = [{"trip_id": f"TRIP-{i}", "fare_amount": -10.0} for i in range(1, 1201)]
    rules = [{"rule_id": "R_CHUNK", "name": "Fare Check", "expression": "fare_amount > 0", "decision": "approved"}]

    res = execute_rules_transactional(
        rows=rows,
        rules=rules,
        snapshot_id="snap_chunk_1",
        rule_version_id="v1.0",
        source_table="raw_taxi_trips",
        db=tmp_db
    )

    assert res["quarantine_count"] == 1200
    q_db_count = tmp_db.execute("SELECT COUNT(*) FROM quarantine WHERE snapshot_id = 'snap_chunk_1'")[0][0]
    assert q_db_count == 1200

    # Test idempotency on large chunked batch
    execute_rules_transactional(
        rows=rows,
        rules=rules,
        snapshot_id="snap_chunk_1",
        rule_version_id="v1.0",
        source_table="raw_taxi_trips",
        db=tmp_db
    )
    q_db_count_2 = tmp_db.execute("SELECT COUNT(*) FROM quarantine WHERE snapshot_id = 'snap_chunk_1'")[0][0]
    assert q_db_count_2 == 1200
