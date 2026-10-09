from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.database.models import ReliabilityDetector, ReliabilityRuleModel
from fastapi.testclient import TestClient
from backend.api.main import app


def _payload():
    return {
        "rule_id": "L1-RANGE-TEMP", "dataset_id": "telemetry", "layer": "L1",
        "detector_id": "RANGE", "target_fields": ["battery_temp_c"],
        "params_json": {"min": -40, "max": 120},
    }


def test_reliability_rule_defaults_are_safe():
    rule = ReliabilityRuleModel(**_payload())
    assert rule.detector_id is ReliabilityDetector.RANGE
    assert rule.status.value == "DRAFT"
    assert rule.runtime_mode.value == "SHADOW"


def test_active_rule_requires_technical_approval():
    with pytest.raises(ValidationError, match="technical approval"):
        ReliabilityRuleModel(**_payload(), status="ACTIVE")
    rule = ReliabilityRuleModel(
        **_payload(), status="ACTIVE", approved_by="platform-owner",
        approved_at=datetime.now(timezone.utc), approval_role="DATA_PLATFORM_OWNER",
    )
    assert rule.status.value == "ACTIVE"


def test_detector_allowlist_parameters_and_window_are_validated():
    with pytest.raises(ValidationError):
        ReliabilityRuleModel(**(_payload() | {"detector_id": "PYTHON_EVAL"}))
    with pytest.raises(ValidationError, match="min and/or max"):
        ReliabilityRuleModel(**(_payload() | {"params_json": {}}))
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError, match="effective_to must be later"):
        ReliabilityRuleModel(**_payload(), effective_from=now, effective_to=now - timedelta(seconds=1))


def test_sql_defines_versioning_overlap_seed_and_lane_boundary():
    root = Path(__file__).parents[1]
    schema = (root / "database/schema.sql").read_text(encoding="utf-8")
    migration = (root / "database/migration_data_driven_lane_rules.sql").read_text(encoding="utf-8")
    policy = (root / "database/schema_audit_and_policy_rules.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS engine.reliability_rules" in schema
    assert "PRIMARY KEY (rule_id, version)" in schema
    assert "reliability_rules_no_overlapping_active_versions" in migration
    assert "ON CONFLICT (rule_id, version) DO NOTHING" in migration
    assert "'L1-ARITHMETIC-TOTAL-FARE'" in migration
    assert "'L1-CONDITION-ZERO-SPEED-RPM'" in migration
    assert "LEGACY compatibility table" in migration
    assert "rule_domain VARCHAR(20) NOT NULL DEFAULT 'LANE_B'" in policy


def test_reliability_rules_endpoint_is_available():
    response = TestClient(app).get("/api/rules/reliability")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
