import pytest

from src.api.quarantine_api import synthesize_remediation_sql
from src.utils.table_utils import normalize_table_name


def test_normalize_table_name_canonical_and_composite():
    assert normalize_table_name("ev_telemetry__rule_anom_raw.ev_telemetry_22") == "ev_telemetry"
    assert normalize_table_name("main.charging_sessions") == "charging_sessions"
    assert normalize_table_name("clean.trips") == "trips"
    assert normalize_table_name("quarantine.nlp_feedback") == "nlp_feedback"
    assert normalize_table_name("ev_telemetry") == "ev_telemetry"


@pytest.mark.parametrize(
    "legacy_name",
    ["vinfast_bms", "vgreen_telemetry", "xanhsm_trips", "xanhsm_feedback"],
)
def test_normalize_table_name_rejects_legacy(legacy_name):
    with pytest.raises(ValueError):
        normalize_table_name(legacy_name)


def test_synthesize_remediation_sql_canonical_table():
    sql, strat, sev = synthesize_remediation_sql(
        rule_id="ev_telemetry__rule_anom_raw.ev_telemetry_22",
        reason="battery_soc range_boundary_check: battery_soc >= 0 AND battery_soc <= 100",
        source_table="ev_telemetry",
    )
    assert "UPDATE ev_telemetry SET battery_soc = 0.0 WHERE battery_soc < 0.0;" in sql
    assert sev == "CRITICAL"
