import json
import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from src.services.llm import GemmaLLMAdapter, LLMResponse
from src.orchestrator.react_engine import ReActEngine, ReActStep, ReActResult
from src.tools.base import ToolRegistry, BaseTool, ToolCall
from src.tools.nlp_extractor import NLPExtractorTool
from src.tools.profiler import DataProfilerTool
from src.tools.anomaly_detector import AnomalyDetectorTool
from src.tools.telemetry_query import TelemetryQueryTool
from src.tools.rule_proposer import RuleProposerTool
from src.tools.rule_executor import RuleExecutorTool
from src.agents.profiler_agent import ProfilerAgent
from src.agents.anomaly_agent import AnomalyAgent
from src.agents.diagnosis_agent import DiagnosisAgent
from src.agents.rule_proposer_agent import RuleProposerAgent
from src.agents.executor_agent import ExecutorAgent
from src.agents.baselines import BaselineC0, BaselineC1, BaselineResult
from src.db.connection import DuckDBManager


@pytest.fixture
def mock_llm():
    llm = MagicMock(spec=GemmaLLMAdapter)
    return llm


@pytest.fixture
def tools():
    reg = ToolRegistry()
    reg.register(NLPExtractorTool())
    reg.register(DataProfilerTool())
    return reg


@pytest.fixture
def tmp_db():
    with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as f:
        db_path = f.name
    if os.path.exists(db_path):
        os.unlink(db_path)
    db = DuckDBManager(db_path=db_path)
    db.init_schema()
    db.execute("INSERT INTO ev_telemetry (record_id, vehicle_vin, battery_soc, battery_temp_c) VALUES ('R-1', 'VF8-001', 85.0, 35.0)")
    db.execute("INSERT INTO nlp_feedback (feedback_id, sentence, sentiment, topic) VALUES ('F-1', 'Tot lam', 2, 1)")
    yield db
    db.close()
    os.unlink(db_path)


# === LLMResponse Tests (3) ===

def test_llm_response_creation():
    r = LLMResponse(content="hello", tool_calls=[], finish_reason="stop", tokens_used=10)
    assert r.content == "hello"
    assert r.tokens_used == 10

def test_llm_response_defaults():
    r = LLMResponse()
    assert r.content == ""
    assert r.tool_calls == []
    assert r.tokens_used == 0

def test_llm_adapter_init():
    llm = GemmaLLMAdapter(api_key="test-key", model="gemma-4-27b-it")
    assert llm.model == "gemma-4-27b-it"
    assert llm.api_key == "test-key"


# === ReActStep Tests (3) ===

def test_react_step_creation():
    step = ReActStep(step_index=0, thought="thinking", action="FINISH")
    assert step.step_index == 0
    assert step.action == "FINISH"

def test_react_step_with_tool():
    step = ReActStep(step_index=1, thought="check data", action="data_profiler",
                     action_input={"table_name": "test"}, observation='{"row_count": 5}')
    assert step.action_input["table_name"] == "test"

def test_react_result_creation():
    result = ReActResult(task="test task")
    assert result.task == "test task"
    assert result.steps == []
    assert result.session_id  # auto-generated


# === ReActEngine Tests (8) ===

def test_engine_creation(mock_llm, tools):
    engine = ReActEngine(mock_llm, tools, max_steps=5)
    assert engine.max_steps == 5

def test_engine_finish_action(mock_llm, tools):
    mock_llm.chat.return_value = LLMResponse(
        content="Thought: Analysis complete.\nAction: FINISH\nAction Input: {}",
        finish_reason="stop"
    )
    engine = ReActEngine(mock_llm, tools, max_steps=5)
    result = engine.run("test task")
    assert result.status == "completed"
    assert len(result.steps) == 1

def test_engine_abstain_action(mock_llm, tools):
    mock_llm.chat.return_value = LLMResponse(
        content="Thought: I cannot do this.\nAction: ABSTAIN\nAction Input: {}",
        finish_reason="stop"
    )
    engine = ReActEngine(mock_llm, tools, max_steps=5)
    result = engine.run("impossible task")
    assert result.status == "abstained"

def test_engine_max_steps(mock_llm, tools):
    mock_llm.chat.return_value = LLMResponse(
        content="Thought: calling tool\nAction: vietnamese_nlp_extractor\nAction Input: {\"review_text\": \"test\"}",
        finish_reason="stop"
    )
    engine = ReActEngine(mock_llm, tools, max_steps=2)
    result = engine.run("test")
    assert result.status == "max_steps"
    assert len(result.steps) == 2

def test_engine_tool_call(mock_llm, tools):
    # First call: tool action, Second call: FINISH
    mock_llm.chat.side_effect = [
        LLMResponse(
            content="Thought: analyze text\nAction: vietnamese_nlp_extractor\nAction Input: {\"review_text\": \"t\u1ed1t l\u1eafm\"}",
            finish_reason="stop"
        ),
        LLMResponse(
            content="Thought: Done.\nAction: FINISH\nAction Input: {}",
            finish_reason="stop"
        )
    ]
    engine = ReActEngine(mock_llm, tools, max_steps=5)
    result = engine.run("analyze review")
    assert result.status == "completed"
    assert len(result.steps) == 2
    assert result.steps[0].action == "vietnamese_nlp_extractor"

def test_engine_function_calling(mock_llm, tools):
    """Test with Gemini-style function calling."""
    mock_llm.chat.side_effect = [
        LLMResponse(
            content="",
            tool_calls=[{"name": "vietnamese_nlp_extractor", "arguments": {"review_text": "test"}}],
            finish_reason="tool_call"
        ),
        LLMResponse(
            content="Thought: Done.\nAction: FINISH\nAction Input: {}",
            finish_reason="stop"
        )
    ]
    engine = ReActEngine(mock_llm, tools, max_steps=5)
    result = engine.run("test")
    assert len(result.steps) >= 1

def test_engine_parse_response(mock_llm, tools):
    engine = ReActEngine(mock_llm, tools)
    resp = LLMResponse(content="Thought: I should profile.\nAction: data_profiler\nAction Input: {\"table_name\": \"test\"}")
    step = engine._parse_response(0, resp)
    assert step.thought == "I should profile."
    assert step.action == "data_profiler"
    assert step.action_input["table_name"] == "test"

def test_engine_with_context(mock_llm, tools):
    mock_llm.chat.return_value = LLMResponse(
        content="Thought: Done.\nAction: FINISH\nAction Input: {}",
        finish_reason="stop"
    )
    engine = ReActEngine(mock_llm, tools, max_steps=3)
    result = engine.run("test", context={"extra": "data"})
    assert result.status == "completed"
    # Verify context was passed to LLM
    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]  # first positional arg
    assert any("extra" in str(m) for m in messages)


# === Agent Construction Tests (5) ===

def test_profiler_agent_init(mock_llm):
    agent = ProfilerAgent(mock_llm)
    assert agent.name == "profiler"
    assert "data_profiler" in agent.tools.tool_names

def test_anomaly_agent_init(mock_llm):
    agent = AnomalyAgent(mock_llm)
    assert agent.name == "anomaly_detector"
    assert "anomaly_detector" in agent.tools.tool_names
    assert "telemetry_query" in agent.tools.tool_names

def test_diagnosis_agent_init(mock_llm):
    agent = DiagnosisAgent(mock_llm)
    assert agent.name == "diagnosis"
    assert "vietnamese_nlp_extractor" in agent.tools.tool_names

def test_rule_proposer_agent_init(mock_llm):
    agent = RuleProposerAgent(mock_llm)
    assert agent.name == "rule_proposer"
    assert agent.tool.name == "quality_rule_proposer"

def test_executor_agent_init(mock_llm):
    agent = ExecutorAgent(mock_llm)
    assert agent.name == "executor"
    assert "rule_executor" in agent.tools.tool_names


# === Baseline Tests (6) ===

def test_baseline_c0_vgreen(tmp_db, monkeypatch):
    monkeypatch.setattr('src.agents.baselines.get_db', lambda: tmp_db)
    c0 = BaselineC0()
    result = c0.analyze("ev_telemetry")
    assert result.tier == "C0"
    assert len(result.rules_proposed) >= 2
    assert result.diagnosis.startswith("C0")

def test_baseline_c0_feedback(tmp_db, monkeypatch):
    monkeypatch.setattr('src.agents.baselines.get_db', lambda: tmp_db)
    c0 = BaselineC0()
    result = c0.analyze("nlp_feedback")
    assert result.tier == "C0"
    assert len(result.rules_proposed) >= 1

def test_baseline_c0_unknown_table(tmp_db, monkeypatch):
    monkeypatch.setattr('src.agents.baselines.get_db', lambda: tmp_db)
    c0 = BaselineC0()
    result = c0.analyze("unknown")
    assert result.tier == "C0"
    assert isinstance(result.rules_proposed, list)

def test_baseline_c1_init(mock_llm):
    c1 = BaselineC1(mock_llm)
    assert c1.llm is mock_llm

def test_baseline_c1_analyze(mock_llm):
    mock_llm.chat.return_value = LLMResponse(
        content=json.dumps({"rules": [{"rule_name": "test"}], "diagnosis": "test diag"})
    )
    c1 = BaselineC1(mock_llm)
    result = c1.analyze("ev_telemetry")
    assert result.tier == "C1"
    assert len(result.rules_proposed) == 1

def test_baseline_c1_bad_json(mock_llm):
    mock_llm.chat.return_value = LLMResponse(content="not json")
    c1 = BaselineC1(mock_llm)
    result = c1.analyze("test")
    assert "C1" in result.diagnosis


# === Orchestrator Tests (4) ===

def test_orchestrator_import():
    from src.orchestrator.orchestrator import DataTrustOrchestrator, OrchestratorResult
    assert DataTrustOrchestrator is not None

def test_orchestrator_result():
    from src.orchestrator.orchestrator import OrchestratorResult
    r = OrchestratorResult()
    assert r.status == "pending"
    assert r.stages == []

def test_orchestrator_init(mock_llm):
    from src.orchestrator.orchestrator import DataTrustOrchestrator
    orch = DataTrustOrchestrator(mock_llm)
    assert orch.profiler is not None
    assert orch.anomaly is not None
    assert orch.diagnosis is not None
    assert orch.rule_proposer is not None
    assert orch.executor is not None

def test_orchestrator_has_execute_approved(mock_llm):
    from src.orchestrator.orchestrator import DataTrustOrchestrator
    orch = DataTrustOrchestrator(mock_llm)
    assert hasattr(orch, 'execute_approved_rules')

def test_baseline_result_defaults():
    r = BaselineResult(tier="C0", table_name="test")
    assert r.tier == "C0"
    assert r.table_name == "test"
    assert r.anomalies_found == 0

def test_react_engine_parse_response_default_thought(mock_llm, tools):
    engine = ReActEngine(mock_llm, tools)
    resp = LLMResponse(content="Action: FINISH\nAction Input: {}")
    step = engine._parse_response(0, resp)
    assert step.action == "FINISH"


# === Hardened LLM Adapter Tests ===

def test_llm_adapter_model_env_var(monkeypatch):
    from src.services.llm import GemmaLLMAdapter
    monkeypatch.setenv("GOOGLE_AI_MODEL", "gemini-2.0-flash")
    adapter = GemmaLLMAdapter(api_key="test-key")
    assert adapter.model == "gemini-2.0-flash"


def test_llm_adapter_chat_raises_llm_unavailable_exception():
    import pytest
    from src.services.llm import GemmaLLMAdapter, LLMUnavailableException
    adapter = GemmaLLMAdapter(api_key="invalid-key")
    with pytest.raises(LLMUnavailableException):
        adapter.chat([{"role": "user", "content": "hi"}])


def test_llm_adapter_structured_output_invalid_exception(monkeypatch):
    import pytest
    from unittest.mock import MagicMock
    from src.services.llm import GemmaLLMAdapter, LLMResponse, StructuredOutputInvalidException
    adapter = GemmaLLMAdapter(api_key="test-key")
    monkeypatch.setattr(adapter, "chat", MagicMock(return_value=LLMResponse(content="invalid json response", finish_reason="stop")))
    with pytest.raises(StructuredOutputInvalidException):
        adapter.structured_output("test prompt", {"type": "object"})


