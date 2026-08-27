import os
import tempfile
import pytest
from src.tools.base import BaseTool, ToolRegistry, ToolCall
from src.tools.nlp_extractor import NLPExtractorTool
from src.tools.telemetry_query import TelemetryQueryTool
from src.tools.anomaly_detector import AnomalyDetectorTool
from src.tools.rule_proposer import RuleProposerTool
from src.tools.profiler import DataProfilerTool
from src.tools.rule_executor import RuleExecutorTool
from src.db.connection import DuckDBManager


@pytest.fixture
def tmp_db():
    with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as f:
        db_path = f.name
    if os.path.exists(db_path):
        os.unlink(db_path)
    db = DuckDBManager(db_path=db_path)
    db.init_schema()
    # Seed some test data
    db.execute("INSERT INTO charging_sessions (vehicle_vin, session_id, station_id, station_temp_c, power_kw, duration_mins, kwh_consumed, status) VALUES ('VF8-001', 'S-1', 'VG-001', 45.0, 220.0, 75.0, 20.0, 'OK')")
    db.execute("INSERT INTO charging_sessions (vehicle_vin, session_id, station_id, station_temp_c, power_kw, duration_mins, kwh_consumed, status) VALUES ('VF8-002', 'S-2', 'VG-001', 90.0, 220.0, 95.0, 30.0, 'FAULT')")
    db.execute("INSERT INTO charging_sessions (vehicle_vin, session_id, station_id, station_temp_c, power_kw, duration_mins, kwh_consumed, status) VALUES ('VF8-003', 'S-3', 'VG-002', 35.0, 380.0, 50.0, 25.0, 'OK')")
    db.execute("INSERT INTO ev_telemetry (record_id, vehicle_vin, battery_soc, battery_temp_c, battery_current) VALUES ('R-1', 'VF8-001', 85.0, 35.0, 30.0)")
    db.execute("INSERT INTO ev_telemetry (record_id, vehicle_vin, battery_soc, battery_temp_c, battery_current) VALUES ('R-2', 'VF8-002', 150.0, 55.0, 20.0)")
    db.execute("INSERT INTO nlp_feedback (feedback_id, sentence, sentiment, topic) VALUES ('F-1', 'Tram sac tot lam', 2, 1)")
    db.execute("INSERT INTO nlp_feedback (feedback_id, sentence, sentiment, topic) VALUES ('F-2', 'ko sac dc, te vl', 0, 1)")
    db.execute("INSERT INTO trips (trip_id, trip_distance_km, fare_amount, total_fare) VALUES ('T-001', 15.5, 85000, 90000)")
    db.execute("INSERT INTO trips (trip_id, trip_distance_km, fare_amount, total_fare) VALUES ('T-002', 600.0, 500000, 520000)")    yield db
    db.close()
    os.unlink(db_path)


# === ToolRegistry Tests (5) ===

def test_registry_register_and_get():
    reg = ToolRegistry()
    tool = NLPExtractorTool()
    reg.register(tool)
    assert reg.get('vietnamese_nlp_extractor') is tool

def test_registry_list_tools():
    reg = ToolRegistry()
    reg.register(NLPExtractorTool())
    reg.register(RuleProposerTool())
    specs = reg.list_tools()
    assert len(specs) == 2
    assert all('function' in s for s in specs)

def test_registry_unknown_tool():
    reg = ToolRegistry()
    with pytest.raises(KeyError):
        reg.get('nonexistent')

def test_registry_execute():
    reg = ToolRegistry()
    reg.register(NLPExtractorTool())
    result = reg.execute('vietnamese_nlp_extractor', {'sentence': 'test'})
    assert isinstance(result, ToolCall)
    assert result.success

def test_registry_tool_names():
    reg = ToolRegistry()
    reg.register(NLPExtractorTool())
    reg.register(DataProfilerTool())
    assert 'vietnamese_nlp_extractor' in reg.tool_names
    assert 'data_profiler' in reg.tool_names


# === BaseTool Tests (3) ===

def test_tool_function_spec():
    tool = NLPExtractorTool()
    spec = tool.to_function_spec()
    assert spec['type'] == 'function'
    assert spec['function']['name'] == 'vietnamese_nlp_extractor'

def test_safe_execute_success():
    tool = NLPExtractorTool()
    result = tool.safe_execute({'sentence': 'ok'})
    assert result.success
    assert result.duration_ms >= 0

def test_safe_execute_captures_error():
    tool = AnomalyDetectorTool()
    # Missing required field
    result = tool.safe_execute({})
    assert not result.success or 'error' in result.output_data


# === NLPExtractorTool Tests (6) ===

def test_nlp_basic():
    tool = NLPExtractorTool()
    result = tool.execute({'sentence': 'Trạm sạc tốt lắm'})
    assert 'normalized_text' in result
    assert result['sentiment'] > 0

def test_nlp_teencode():
    tool = NLPExtractorTool()
    result = tool.execute({'sentence': 'ko sac dc vl'})
    assert len(result['teencode_found']) > 0

def test_nlp_empty():
    tool = NLPExtractorTool()
    result = tool.execute({'sentence': ''})
    assert result['normalized_text'] == ''

def test_nlp_aspects():
    tool = NLPExtractorTool()
    result = tool.execute({'sentence': 'trạm sạc Vincom nóng quá'})
    assert any(a['component'] == 'charger' for a in result['aspects'])

def test_nlp_sentiment_negative():
    tool = NLPExtractorTool()
    result = tool.execute({'sentence': 'dịch vụ tệ lắm, chậm lag'})
    assert result['sentiment'] < 0

def test_nlp_language_detection():
    tool = NLPExtractorTool()
    result = tool.execute({'sentence': 'The charging station is great'})
    assert result['language'] == 'en'


# === TelemetryQueryTool Tests (5) ===

def test_telemetry_basic(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.telemetry_query.get_db', lambda: tmp_db)
    tool = TelemetryQueryTool()
    result = tool.execute({})
    assert result['charging_records'] > 0

def test_telemetry_by_station(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.telemetry_query.get_db', lambda: tmp_db)
    tool = TelemetryQueryTool()
    result = tool.execute({'station_id': 'VG-001'})
    assert result['charging_records'] == 2

def test_telemetry_fault_only(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.telemetry_query.get_db', lambda: tmp_db)
    tool = TelemetryQueryTool()
    result = tool.execute({'fault_only': True})
    assert result['total_faults_found'] >= 1

def test_telemetry_empty_result(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.telemetry_query.get_db', lambda: tmp_db)
    tool = TelemetryQueryTool()
    result = tool.execute({'station_id': 'NONEXISTENT'})
    assert result['charging_records'] == 0

def test_telemetry_has_sample(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.telemetry_query.get_db', lambda: tmp_db)
    tool = TelemetryQueryTool()
    result = tool.execute({})
    assert 'charging_sample' in result


# === AnomalyDetectorTool Tests (6) ===

def test_anomaly_z_score(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.anomaly_detector.get_db', lambda: tmp_db)
    tool = AnomalyDetectorTool()
    result = tool.execute({'table_name': 'charging_sessions', 'column_name': 'station_temp_c'})
    assert 'anomalies_found' in result
    assert 'statistics' in result

def test_anomaly_iqr(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.anomaly_detector.get_db', lambda: tmp_db)
    tool = AnomalyDetectorTool()
    result = tool.execute({'table_name': 'charging_sessions', 'column_name': 'station_temp_c', 'method': 'iqr'})
    assert 'anomalies_found' in result

def test_anomaly_disallowed_table(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.anomaly_detector.get_db', lambda: tmp_db)
    tool = AnomalyDetectorTool()
    result = tool.execute({'table_name': 'raw_snapshots', 'column_name': 'row_count'})
    assert 'error' in result

def test_anomaly_invalid_column(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.anomaly_detector.get_db', lambda: tmp_db)
    tool = AnomalyDetectorTool()
    result = tool.execute({'table_name': 'charging_sessions', 'column_name': 'nonexistent'})
    assert result['anomalies_found'] == 0

def test_anomaly_statistics(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.anomaly_detector.get_db', lambda: tmp_db)
    tool = AnomalyDetectorTool()
    result = tool.execute({'table_name': 'charging_sessions', 'column_name': 'power_kw'})
    assert 'mean' in result['statistics']
    assert 'std' in result['statistics']

def test_anomaly_bms_soc(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.anomaly_detector.get_db', lambda: tmp_db)
    tool = AnomalyDetectorTool()
    result = tool.execute({'table_name': 'ev_telemetry', 'column_name': 'battery_soc'})
    assert result['statistics']['count'] == 2


# === RuleProposerTool Tests (5) ===

def test_propose_vgreen_rules():
    tool = RuleProposerTool()
    result = tool.execute({'target_table': 'charging_sessions'})
    assert result['rule_count'] >= 3
    assert all('rule_name' in r for r in result['proposed_rules'])

def test_propose_bms_rules():
    tool = RuleProposerTool()
    result = tool.execute({'target_table': 'ev_telemetry'})
    assert result['rule_count'] >= 2

def test_propose_feedback_rules():
    tool = RuleProposerTool()
    result = tool.execute({'target_table': 'nlp_feedback'})
    assert result['rule_count'] >= 2

def test_propose_with_anomaly_findings():
    tool = RuleProposerTool()
    result = tool.execute({
        'target_table': 'charging_sessions',
        'anomaly_findings': {'anomalies_found': 5, 'statistics': {'mean': 50.0, 'std': 10.0}, 'column_name': 'station_temp_c'}
    })
    assert any('3sigma' in r['rule_name'] for r in result['proposed_rules'])

def test_propose_unknown_table():
    tool = RuleProposerTool()
    result = tool.execute({'target_table': 'unknown_table'})
    assert result['rule_count'] == 0


# === DataProfilerTool Tests (5) ===

def test_profiler_basic(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.profiler.get_db', lambda: tmp_db)
    tool = DataProfilerTool()
    result = tool.execute({'table_name': 'charging_sessions'})
    assert result['row_count'] == 3
    assert len(result['columns']) > 0

def test_profiler_column_stats(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.profiler.get_db', lambda: tmp_db)
    tool = DataProfilerTool()
    result = tool.execute({'table_name': 'charging_sessions'})
    temp_col = next((c for c in result['columns'] if c['name'] == 'station_temp_c'), None)
    assert temp_col is not None
    assert 'mean_val' in temp_col

def test_profiler_null_stats(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.profiler.get_db', lambda: tmp_db)
    tool = DataProfilerTool()
    result = tool.execute({'table_name': 'charging_sessions'})
    fault_col = next((c for c in result['columns'] if c['name'] == 'status'), None)
    assert fault_col is not None
    assert fault_col['null_count'] >= 0

def test_profiler_disallowed_table(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.profiler.get_db', lambda: tmp_db)
    tool = DataProfilerTool()
    result = tool.execute({'table_name': 'nonexistent'})
    assert 'error' in result

def test_profiler_empty_table(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.profiler.get_db', lambda: tmp_db)
    tool = DataProfilerTool()
    result = tool.execute({'table_name': 'audit_log'})
    assert result['row_count'] == 0


# === RuleExecutorTool Tests (5) ===

def test_executor_dry_run(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.rule_executor.get_db', lambda: tmp_db)
    # Insert a test rule
    tmp_db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status) VALUES ('r1', 'temp_check', 'range', 'station_temp_c BETWEEN -10 AND 85', 0.95, 'approved')")
    tool = RuleExecutorTool()
    result = tool.execute({'rule_id': 'r1', 'dry_run': True})
    assert result['records_checked'] == 3
    assert result['violations_found'] == 1  # 90.0 is > 85
    assert result['quarantined_count'] == 0  # dry run

def test_executor_live_run(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.rule_executor.get_db', lambda: tmp_db)
    tmp_db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status) VALUES ('r2', 'soc_check', 'range', 'battery_soc BETWEEN 0 AND 100', 0.99, 'approved')")
    tool = RuleExecutorTool()
    result = tool.execute({'rule_id': 'r2', 'dry_run': False})
    assert result['violations_found'] == 1  # 150.0 > 100
    assert result['quarantined_count'] == 1

def test_executor_rule_not_found(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.rule_executor.get_db', lambda: tmp_db)
    tool = RuleExecutorTool()
    result = tool.execute({'rule_id': 'nonexistent'})
    assert 'error' in result

def test_executor_unapproved_rule(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.rule_executor.get_db', lambda: tmp_db)
    tmp_db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status) VALUES ('r3', 'test', 'range', 'sentiment > 0', 0.9, 'proposed')")
    tool = RuleExecutorTool()
    result = tool.execute({'rule_id': 'r3', 'dry_run': False})
    assert 'error' in result  # Can't execute unapproved rule

def test_executor_creates_audit_log(tmp_db, monkeypatch):
    monkeypatch.setattr('src.tools.rule_executor.get_db', lambda: tmp_db)
    tmp_db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status) VALUES ('r4', 'dist_check', 'range', 'trip_distance_km < 500', 0.95, 'approved')")
    tool = RuleExecutorTool()
    tool.execute({'rule_id': 'r4', 'dry_run': False})
    logs = tmp_db.execute("SELECT action FROM audit_log")
    assert any('EXECUTE_RULE' in str(l) for l in logs)



