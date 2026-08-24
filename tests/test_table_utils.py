import pytest
from src.utils.table_utils import normalize_table_name
from src.api.quarantine_api import synthesize_remediation_sql


def test_normalize_table_name_legacy_and_composite():
    assert normalize_table_name("vinfast_bms") == "ev_telemetry"
    assert normalize_table_name("ev_telemetry__rule_anom_raw.ev_telemetry_22") == "ev_telemetry"
    assert normalize_table_name("vgreen_telemetry") == "charging_sessions"
    assert normalize_table_name("xanhsm_trips") == "trips"
    assert normalize_table_name("xanhsm_feedback") == "nlp_feedback"
    assert normalize_table_name("ev_telemetry") == "ev_telemetry"


def test_synthesize_remediation_sql_canonical_table():
    sql, strat, sev = synthesize_remediation_sql(
        rule_id="ev_telemetry__rule_anom_raw.ev_telemetry_22",
        reason="Vi phạm luật battery_soc range_boundary_check (ev_telemetry__rule_anom_raw.ev_telemetry_22): battery_soc >= 0 AND battery_soc <= 100",
        source_table="vinfast_bms"
    )
    assert "UPDATE ev_telemetry SET battery_soc = 0.0 WHERE battery_soc < 0.0;" in sql
    assert "vinfast_bms" not in sql
    assert sev == "CRITICAL"
