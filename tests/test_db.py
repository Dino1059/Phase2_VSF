import os
import tempfile
import pytest
from src.db.connection import DuckDBManager


@pytest.fixture
def tmp_db():
    """Create a temporary DuckDB database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = f.name
    if os.path.exists(db_path):
        os.unlink(db_path)
    db = DuckDBManager(db_path=db_path)
    db.init_schema()
    yield db
    db.close()
    os.unlink(db_path)


def test_duckdb_manager_creates_database(tmp_db):
    """DuckDBManager creates a valid database file."""
    assert os.path.exists(tmp_db.db_path)


def test_init_schema_creates_all_tables(tmp_db):
    """init_schema creates all 10 required tables."""
    tables = tmp_db.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY table_name"
    )
    table_names = [t[0] for t in tables]
    expected = [
        "agent_traces", "audit_log", "profile_results", "quality_rules",
        "quarantine", "raw_snapshots", "charging_sessions", "ev_telemetry",
        "nlp_feedback", "trips"
    ]
    for name in expected:
        assert name in table_names, f"Missing table: {name}"


def test_init_schema_idempotent(tmp_db):
    """Calling init_schema twice should not error."""
    tmp_db.init_schema()  # second call
    tables = tmp_db.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
    )
    assert len(tables) >= 10



def test_insert_and_query_raw_snapshots(tmp_db):
    """Can insert and query raw_snapshots."""
    tmp_db.execute(
        "INSERT INTO raw_snapshots (id, source_name, file_path, sha256_hash, row_count, column_count) VALUES (?, ?, ?, ?, ?, ?)",
        ["snap-1", "test_topic", "/tmp/test.csv", "abc123" * 10 + "abcd", 100, 5]
    )
    rows = tmp_db.execute("SELECT * FROM raw_snapshots WHERE id = 'snap-1'")
    assert len(rows) == 1
    assert rows[0][1] == "test_topic"


def test_insert_and_query_nlp_feedback(tmp_db):
    """Can insert and query nlp_feedback."""
    tmp_db.execute(
        "INSERT INTO nlp_feedback (feedback_id, sentence, sentiment, topic) VALUES (?, ?, ?, ?)",
        ["1", "Trạm sạc rất tốt", 4, 1]
    )
    rows = tmp_db.execute("SELECT sentence FROM nlp_feedback WHERE feedback_id = '1'")
    assert len(rows) == 1
    assert rows[0][0] == "Trạm sạc rất tốt"


def test_insert_and_query_charging_sessions(tmp_db):
    """Can insert and query charging_sessions."""
    tmp_db.execute(
        "INSERT INTO charging_sessions (session_id, station_id, station_temp_c, status) VALUES (?, ?, ?, ?)",
        ["S-1", "VG-001", 85.5, "THERMAL_FAULT"]
    )
    rows = tmp_db.execute("SELECT station_temp_c FROM charging_sessions WHERE station_id = 'VG-001'")
    assert rows[0][0] == 85.5


def test_insert_and_query_ev_telemetry(tmp_db):
    """Can insert and query ev_telemetry."""
    tmp_db.execute(
        "INSERT INTO ev_telemetry (record_id, vehicle_vin, battery_soc) VALUES (?, ?, ?)",
        ["0x4B", "VF8-001", 72.5]
    )
    rows = tmp_db.execute("SELECT record_id FROM ev_telemetry WHERE vehicle_vin = 'VF8-001'")
    assert rows[0][0] == "0x4B"


def test_insert_and_query_quality_rules(tmp_db):
    """Can insert quality rules with default status."""
    tmp_db.execute(
        "INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence) VALUES (?, ?, ?, ?, ?)",
        ["rule-1", "temp_check", "range", "station_temp_c < 80.0", 0.95]
    )
    rows = tmp_db.execute("SELECT status FROM quality_rules WHERE id = 'rule-1'")
    assert rows[0][0] == "proposed"


def test_insert_and_query_quarantine(tmp_db):
    """Can insert quarantine records."""
    tmp_db.execute(
        "INSERT INTO quarantine (id, source_table, source_row_id, reason, lineage_hash) VALUES (?, ?, ?, ?, ?)",
        ["q-1", "charging_sessions", 1, "Temperature exceeds threshold", "sha256hash"]
    )
    rows = tmp_db.execute("SELECT reason FROM quarantine WHERE id = 'q-1'")
    assert "Temperature" in rows[0][0]


def test_insert_and_query_agent_traces(tmp_db):
    """Can insert agent execution traces."""
    tmp_db.execute(
        "INSERT INTO agent_traces (id, session_id, agent_type, step_index, thought, action) VALUES (?, ?, ?, ?, ?, ?)",
        ["trace-1", "sess-1", "orchestrator", 0, "Analyzing data", "profile_data"]
    )
    rows = tmp_db.execute("SELECT agent_type FROM agent_traces WHERE session_id = 'sess-1'")
    assert rows[0][0] == "orchestrator"


def test_insert_and_query_trips(tmp_db):
    """Can insert and query trips."""
    tmp_db.execute(
        "INSERT INTO trips (trip_id, driver_id, trip_distance_km, fare_amount) VALUES (?, ?, ?, ?)",
        ["TRIP-001", "DRV-001", 12.5, 85000.0]
    )
    rows = tmp_db.execute("SELECT fare_amount FROM trips WHERE trip_id = 'TRIP-001'")
    assert rows[0][0] == 85000.0


def test_insert_and_query_profile_results(tmp_db):
    """Can insert and query profile_results."""
    tmp_db.execute(
        "INSERT INTO profile_results (id, snapshot_id, column_name, dtype, null_count, null_pct) VALUES (?, ?, ?, ?, ?, ?)",
        ["prof-1", "snap-1", "temperature", "FLOAT", 5, 0.5]
    )
    rows = tmp_db.execute("SELECT column_name FROM profile_results WHERE id = 'prof-1'")
    assert rows[0][0] == "temperature"


def test_insert_and_query_audit_log(tmp_db):
    """Can insert and query audit_log."""
    tmp_db.execute(
        "INSERT INTO audit_log (id, action, actor, target_table) VALUES (?, ?, ?, ?)",
        ["aud-1", "APPROVE_RULE", "human", "quality_rules"]
    )
    rows = tmp_db.execute("SELECT action FROM audit_log WHERE id = 'aud-1'")
    assert rows[0][0] == "APPROVE_RULE"


def test_execute_returns_empty_for_empty_table(tmp_db):
    """Query on empty table returns empty list."""
    rows = tmp_db.execute("SELECT * FROM audit_log")
    assert rows == []


def test_seed_database(tmp_db):
    """seed_database populates tables and raw_snapshots."""
    from src.db.seed import seed_database
    seed_database(db_path=tmp_db.db_path)
    
    snaps = tmp_db.execute("SELECT COUNT(*) FROM raw_snapshots")
    assert snaps[0][0] == 5

    feedback = tmp_db.execute("SELECT COUNT(*) FROM nlp_feedback")
    assert feedback[0][0] > 0

    vgreen = tmp_db.execute("SELECT COUNT(*) FROM charging_sessions")
    assert vgreen[0][0] > 0

    bms = tmp_db.execute("SELECT COUNT(*) FROM ev_telemetry")
    assert bms[0][0] > 0

    land = tmp_db.execute("SELECT COUNT(*) FROM landing.ev_telemetry")
    assert land[0][0] > 0

    trips = tmp_db.execute("SELECT COUNT(*) FROM trips")
    assert trips[0][0] > 0


def test_seed_database_provenance_verification(tmp_db):
    """seed_database assigns explicit DataProvenance metadata and tag across all ingested snapshots."""
    from src.db.seed import seed_database
    from src.reliability.models.provenance import DataProvenance

    seed_database(db_path=tmp_db.db_path)
    
    rows = tmp_db.execute("SELECT source_name, provenance, tag FROM raw_snapshots")
    assert len(rows) == 5
    for r in rows:
        assert r[1] == DataProvenance.SEMI_SYNTHETIC.value
        assert r[2] == "Semi-Synthetic Causal Digital Twin"


def test_integrated_benchmark_dataset_provenance_tag(tmp_db):
    """Integrated benchmark dataset is tagged explicitly as Semi-Synthetic Causal Digital Twin in DuckDB datasets table."""
    from src.db.seed import seed_database
    from src.reliability.models.provenance import DataProvenance

    seed_database(db_path=tmp_db.db_path)

    rows = tmp_db.execute("SELECT dataset_key, provenance, tag FROM datasets WHERE dataset_key = 'integrated_benchmark'")
    assert len(rows) == 1
    key, prov, tag = rows[0]
    assert key == "integrated_benchmark"
    assert prov == DataProvenance.SEMI_SYNTHETIC.value
    assert tag == "Semi-Synthetic Causal Digital Twin"


def test_config_dataset_provenance_enum_assignment():
    """Config contains explicit DataProvenance Enum assignments and metadata for all datasets."""
    from src.config import get_settings
    from src.reliability.models.provenance import DataProvenance

    settings = get_settings()
    
    # Check integrated benchmark metadata
    bm_prov = settings.get_dataset_provenance("integrated_benchmark")
    assert bm_prov == DataProvenance.SEMI_SYNTHETIC
    
    meta = settings.get_dataset_metadata("integrated_benchmark")
    assert meta["tag"] == "Semi-Synthetic Causal Digital Twin"
    assert meta["horizon_days"] == 60
    assert meta["vin_count"] == 30
    assert meta["station_count"] == 4
    assert meta["provenance"] == DataProvenance.SEMI_SYNTHETIC.value

    # Check all registered datasets have valid DataProvenance enum
    for ds_key in settings.dataset_registry.keys():
        prov = settings.get_dataset_provenance(ds_key)
        assert isinstance(prov, DataProvenance)
        assert prov in [
            DataProvenance.SEMI_SYNTHETIC,
            DataProvenance.REAL_OPERATIONAL,
            DataProvenance.PUBLIC_PROXY,
            DataProvenance.SYNTHETIC,
        ]


def test_data_provenance_enum_values():
    """DataProvenance Enum defines all four required provenance metadata categories."""
    from src.reliability.models.provenance import DataProvenance

    assert DataProvenance.SEMI_SYNTHETIC.value == "SEMI_SYNTHETIC"
    assert DataProvenance.REAL_OPERATIONAL.value == "REAL_OPERATIONAL"
    assert DataProvenance.PUBLIC_PROXY.value == "PUBLIC_PROXY"
    assert DataProvenance.SYNTHETIC.value == "SYNTHETIC"



