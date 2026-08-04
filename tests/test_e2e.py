"""End-to-end integration test: Seed → NLP → Orchestrate → HITL → Execute → Verify."""
import os
import tempfile
import pytest
from unittest.mock import MagicMock

from src.db.connection import DuckDBManager
from src.services.vietnamese_nlp import VietnameseNLPService
from src.services.llm import GemmaLLMAdapter, LLMResponse
from src.tools.base import ToolRegistry
from src.tools.nlp_extractor import NLPExtractorTool
from src.tools.profiler import DataProfilerTool
from src.tools.anomaly_detector import AnomalyDetectorTool
from src.orchestrator.react_engine import ReActEngine
from src.services.audit import AuditService


@pytest.fixture
def e2e_db():
    with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as f:
        db_path = f.name
    db = DuckDBManager(db_path=db_path)
    db.init_schema()
    # Seed data
    db.execute("INSERT INTO vgreen_telemetry (id, station_id, temperature_celsius, voltage, duty_cycle, status) VALUES (1, 'VG-001', 45.0, 220.0, 75.0, 'OK')")
    db.execute("INSERT INTO vgreen_telemetry (id, station_id, temperature_celsius, voltage, duty_cycle, status) VALUES (2, 'VG-001', 999.0, 220.0, 75.0, 'FAULT')")
    db.execute("INSERT INTO xanhsm_feedback (id, review_text, rating, source) VALUES (1, 'Dịch vụ tốt lắm', 5.0, 'csv')")
    db.execute("INSERT INTO xanhsm_feedback (id, review_text, rating, source) VALUES (2, 'App lag quá, xe bẩn', 1.0, 'csv')")
    yield db
    db.close()
    os.unlink(db_path)


def test_e2e_pipeline(e2e_db, monkeypatch):
    """Full E2E: Seed → NLP → Tool execution → ReAct → HITL queue → Verify."""
    # Step 1: NLP Analysis
    nlp = VietnameseNLPService()
    result = nlp.analyze("App lag quá, xe bẩn")
    assert result["sentiment"] in ["negative", "very_negative"]
    assert len(result["aspects"]) > 0

    # Step 2: Tool Registration
    tools = ToolRegistry()
    tools.register(NLPExtractorTool())
    tools.register(DataProfilerTool())
    tools.register(AnomalyDetectorTool())
    assert len(tools.tool_names) >= 3

    # Step 3: ReAct Engine with mocked LLM
    mock_llm = MagicMock(spec=GemmaLLMAdapter)
    mock_llm.chat.return_value = LLMResponse(
        content="Thought: Analysis complete. Found anomaly in temperature.\nAction: FINISH\nAction Input: {}",
        finish_reason="stop"
    )
    engine = ReActEngine(mock_llm, tools, max_steps=3)
    react_result = engine.run("Analyze vgreen_telemetry for anomalies")
    assert react_result.status == "completed"
    assert len(react_result.steps) >= 1

    # Step 4: HITL Queue (insert proposed rule)
    e2e_db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status, proposed_by) VALUES ('e2e-r1', 'temp_range', 'range', 'temperature_celsius BETWEEN -10 AND 85', 0.95, 'proposed', 'agent')")
    rules = e2e_db.execute("SELECT id, status FROM quality_rules WHERE id = 'e2e-r1'")
    assert rules[0][1] == "proposed"

    # Step 5: Approve rule
    e2e_db.execute("UPDATE quality_rules SET status = 'approved', approved_by = 'tester' WHERE id = 'e2e-r1'")
    approved = e2e_db.execute("SELECT status FROM quality_rules WHERE id = 'e2e-r1'")
    assert approved[0][0] == "approved"

    # Step 6: Execute and verify quarantine
    violations = e2e_db.execute("SELECT id FROM vgreen_telemetry WHERE NOT (temperature_celsius BETWEEN -10 AND 85)")
    assert len(violations) >= 1  # id=2 has temp=999

    # Step 7: Verify audit logging
    monkeypatch.setattr('src.services.audit.get_db', lambda: e2e_db)
    audit_id = AuditService.log("E2E_TEST", "tester", "vgreen_telemetry", "e2e-r1", {"violations": len(violations)})
    assert audit_id
    audit = e2e_db.execute("SELECT action FROM audit_log WHERE id = ?", [audit_id])
    assert audit[0][0] == "E2E_TEST"
