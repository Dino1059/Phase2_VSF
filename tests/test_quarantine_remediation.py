import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.db.connection import DuckDBManager, get_db
from src.api.quarantine_api import RejectRequest, RemediateRequest, reject_quarantine_group, remediate_quarantine_group, get_quarantine_groups, list_quarantine


@pytest.fixture
def tmp_db(monkeypatch):
    """Create a temporary DuckDB database for testing quarantine remediation."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = f.name
    if os.path.exists(db_path):
        os.unlink(db_path)
    db = DuckDBManager(db_path=db_path)
    db.init_schema()
    monkeypatch.setattr("src.api.quarantine_api.get_db", lambda: db)
    monkeypatch.setattr("src.db.connection.get_db", lambda: db)
    yield db
    db.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_quarantine_remediation_and_rejection_flow(tmp_db):
    """Verifies schema extension, status updates, rejection, and remediation flows."""
    # Seed quarantine records
    tmp_db.execute(
        """
        INSERT INTO quarantine (id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id, reason, original_data, lineage_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ["q_1", "snap_10", "vinfast_bms", 101, "R1_SOC", "v1.0", "battery_soc < 0.0 violation", '{"battery_soc": -5.2}', "hash_101"]
    )
    tmp_db.execute(
        """
        INSERT INTO quarantine (id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id, reason, original_data, lineage_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ["q_2", "snap_10", "vinfast_bms", 102, "R1_SOC", "v1.0", "battery_soc < 0.0 violation", '{"battery_soc": -12.0}', "hash_102"]
    )

    # 1. Check initial group status (defaults to QUARANTINED)
    groups_res = await get_quarantine_groups(source_table="vinfast_bms")
    assert groups_res["groups_count"] == 1
    grp = groups_res["groups"][0]
    assert grp["status"] == "QUARANTINED"
    assert grp["total_rows"] == 2

    # 2. Reject the remediation recommendation
    reject_res = await reject_quarantine_group(RejectRequest(
        rule_id="R1_SOC",
        source_table="vinfast_bms",
        reason="Operator rejected automated SQL patch; retaining for manual audit",
        action_by="Operator_Test"
    ))
    assert reject_res["status"] == "success"
    assert reject_res["group_status"] == "REJECTED_HELD"
    assert reject_res["rejected_count"] == 2

    # Verify status changed in DB
    rows = tmp_db.execute("SELECT status, user_action, action_by FROM quarantine WHERE rule_id = 'R1_SOC'")
    assert len(rows) == 2
    assert rows[0][0] == "REJECTED_HELD"
    assert rows[0][1] == "REJECTED"
    assert rows[0][2] == "Operator_Test"

    # Verify filtering groups by status
    pending_groups = await get_quarantine_groups(source_table="vinfast_bms", status="QUARANTINED")
    assert pending_groups["groups_count"] == 0

    rejected_groups = await get_quarantine_groups(source_table="vinfast_bms", status="REJECTED_HELD")
    assert rejected_groups["groups_count"] == 1
    assert rejected_groups["groups"][0]["status"] == "REJECTED_HELD"

    # 3. User changes mind and Accepts remediation on the REJECTED_HELD group
    rem_res = await remediate_quarantine_group(RemediateRequest(
        rule_id="R1_SOC",
        source_table="vinfast_bms",
        sql_query="UPDATE vinfast_bms SET battery_soc = 0.0 WHERE battery_soc < 0.0;",
        action_by="Operator_Test"
    ))
    assert rem_res["status"] == "success"
    assert rem_res["remediated_count"] == 2

    # Verify records cleared from quarantine table
    final_q = tmp_db.execute("SELECT COUNT(*) FROM quarantine WHERE rule_id = 'R1_SOC'")[0][0]
    assert final_q == 0

    # Verify audit log recorded
    audit_rows = tmp_db.execute("SELECT action, actor, target_table FROM audit_log WHERE target_id = 'R1_SOC' ORDER BY timestamp ASC")
    assert len(audit_rows) == 2
    assert audit_rows[0][0] == "QUARANTINE_REJECT"
    assert audit_rows[1][0] == "QUARANTINE_REMEDIATE"
