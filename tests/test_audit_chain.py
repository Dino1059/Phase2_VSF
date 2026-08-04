import os
import tempfile
import pytest

from src.db.connection import DuckDBManager, get_db
import src.db.connection as conn_module
from src.services.audit import AuditService


@pytest.fixture
def audit_db():
    """Create a fresh temporary database for audit chain testing."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = f.name
    conn_module._db_manager = None
    db = get_db(db_path=db_path)
    db.init_schema()
    yield db
    db.close()
    conn_module._db_manager = None
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_sequential_logging_produces_valid_hash_chain(audit_db):
    """Test sequential event logging produces valid cryptographic hash chain."""
    id1 = AuditService.log("ACTION_1", "user_1", "table_a", "id_1", {"key": "val1"})
    id2 = AuditService.log("ACTION_2", "user_2", "table_b", "id_2", {"key": "val2"})
    id3 = AuditService.log("ACTION_3", "user_3", "table_c", "id_3", {"key": "val3"})

    history = AuditService.get_history(limit=10)
    # get_history returns newest first (DESC)
    rows_by_id = {r["id"]: r for r in history}

    r1 = rows_by_id[id1]
    r2 = rows_by_id[id2]
    r3 = rows_by_id[id3]

    assert r1["previous_event_hash"] == "0" * 64
    assert r2["previous_event_hash"] == r1["event_hash"]
    assert r3["previous_event_hash"] == r2["event_hash"]

    assert len(r1["event_hash"]) == 64
    assert len(r2["event_hash"]) == 64
    assert len(r3["event_hash"]) == 64


def test_verify_chain_integrity_returns_true_for_untouched_logs(audit_db):
    """Test verify_chain_integrity() returns True for untouched logs."""
    AuditService.log("CREATE", "system", "users", "u1", {"role": "admin"})
    AuditService.log("UPDATE", "admin", "users", "u1", {"role": "superadmin"})
    AuditService.log("DELETE", "admin", "users", "u2", None)

    is_valid, details = AuditService.verify_chain_integrity()
    assert is_valid is True
    assert details == []


def test_verify_chain_integrity_empty_table(audit_db):
    """Test verify_chain_integrity() returns True for empty audit log."""
    is_valid, details = AuditService.verify_chain_integrity()
    assert is_valid is True
    assert details == []


def test_modifying_audit_row_causes_integrity_failure(audit_db):
    """Test modifying/tampering with an audit row causes verify_chain_integrity() to return False."""
    id1 = AuditService.log("LOGIN", "alice", "sessions", "s1", {"ip": "127.0.0.1"})
    id2 = AuditService.log("TRANSFER", "alice", "accounts", "a1", {"amount": 100})
    id3 = AuditService.log("LOGOUT", "alice", "sessions", "s1", {})

    # Verify chain is initially intact
    is_valid, details = AuditService.verify_chain_integrity()
    assert is_valid is True

    # Tamper with row 2 details
    audit_db.execute(
        "UPDATE audit_log SET details = ? WHERE id = ?",
        ['{"amount": 1000000}', id2]
    )

    is_valid_tampered, tamper_details = AuditService.verify_chain_integrity()
    assert is_valid_tampered is False
    assert len(tamper_details) > 0
    assert any(id2 in item for item in tamper_details)


def test_modifying_previous_hash_causes_integrity_failure(audit_db):
    """Test modifying previous_event_hash directly causes verify_chain_integrity() to return False."""
    id1 = AuditService.log("ACTION_A", "actor_a")
    id2 = AuditService.log("ACTION_B", "actor_b")

    audit_db.execute(
        "UPDATE audit_log SET previous_event_hash = ? WHERE id = ?",
        ["f" * 64, id2]
    )

    is_valid, tamper_details = AuditService.verify_chain_integrity()
    assert is_valid is False
    assert len(tamper_details) > 0
